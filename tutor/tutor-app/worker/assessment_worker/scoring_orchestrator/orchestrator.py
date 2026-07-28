"""CMP-SCORING-ORCHESTRATOR：CT-004 幂等消费、任务状态机、重试一次、终态事务。

状态机（ST-001 / INV-1~5 / CON-1~2 / IDM-2）：

- pending → in_progress（ICT-001 条件认领，租约见 lease_store）；
- in_progress → scored（ICT-005 终态事务：ST-001 + ST-002 + CT-005 Outbox 入队）；
- in_progress → scoring_failed（ICT-006 第二次失败或崩溃循环上限；
  终态事务：ST-001 + CT-005 Outbox 入队，不写任何等级）；
- REQ-012 / INV-2：自动重试仅一次，attempts ≤ 2；崩溃重认领不耗重试预算；
- LCD-004：deadline_at 仅跟踪统计，不强杀、不伪标记 scoring_failed。

终态事务经 shared/tutor_shared/outbox.py 的 OutboxStore 抽象入队
（dedup_key = submission_id + 终态；支持实例或按 Session 构造的工厂，
KD-002 同事务语义与 SI-PURGE OutboxProvider 同形）；发布由 backfill 的
RESULT-PUBLISHER 负责。
CT-012 评分清除消费归本包 purge.py（ICT-009，CCR-001 已实施）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import or_, select

from tutor_shared.lease import LeaseStore
from tutor_shared.outbox import OutboxStore

from ..settings import CLAIM_LEASE_SECONDS, MAX_RECLAIM_COUNT, TASK_BUDGET_SECONDS
from .errors import (
    DUPLICATE_TERMINAL_CALLBACK,
    STALE_TERMINAL_CALLBACK,
    InvalidAssessmentFailure,
    InvalidAssessmentResult,
    TerminalCallbackRejected,
)
from .lease_store import as_naive_utc
from .models import ScoringResult, ScoringTask
from .purge import is_tombstoned

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_SCORED = "scored"
STATUS_SCORING_FAILED = "scoring_failed"
TERMINAL_STATUSES = (STATUS_SCORED, STATUS_SCORING_FAILED)

# CT-005 / INV-4（contracts/ct-005.json；与 assessment_worker.model_provider 对齐）
GRADES = ("A", "B", "C", "D", "E")
DIMENSIONS = ("需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性")
# 继承的 classified 错误分类法（L1 ICT-006；L2 04 §5）
ERROR_TAXONOMY = (
    "MODEL_TIMEOUT",
    "MODEL_ERROR",
    "INVALID_RESPONSE_SCHEMA",
    "MATERIAL_UNREADABLE",
    "PROMPT_ASSEMBLY_FAILED",
)
# LCD-002：reclaim_count 超上限的基础设施失败终态化原因
CRASH_LOOP_FAILURE_REASON = "REPEATED_WORKER_CRASH"

CT005_CONTRACT_ID = "CT-005"

CT004_REQUIRED_FIELDS = (
    "submission_id",
    "course_id",
    "assignment",
    "student_name",
    "group_name",
    "material_refs",
    "missing_items",
    "received_at",
    "v",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return as_naive_utc(value)
    if isinstance(value, str):
        return as_naive_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    raise ValueError(f"invalid datetime value: {value!r}")


@dataclass(frozen=True)
class IngressResult:
    """CT-004 消费结果；返回即表示任务已持久化（或幂等命中），事件方可确认。"""

    task_id: str
    submission_id: str
    created: bool  # False = 重复事件幂等 no-op（INV-5），事件照常确认
    tombstoned: bool = False  # True = CCR-001 重放守卫：提交已评分清除，拒绝重建任务


@dataclass(frozen=True)
class ClaimedTask:
    """ICT-001 输出载荷：任务上下文 + 当前尝试号 + 租约。"""

    task_id: str
    submission_id: str
    course_id: str
    assignment: str
    material_refs: list
    missing_items: list
    attempt_no: int
    deadline_at: datetime
    lease_owner: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class RetryEntered:
    """ICT-006 第一次失败：已记录 first_failure 并进入唯一一次重试。"""

    task_id: str
    attempt_no: int
    next_attempt_no: int
    error_kind: str


@dataclass(frozen=True)
class OutcomeCommitted:
    """终态事务已提交（scored / scoring_failed）。"""

    task_id: str
    submission_id: str
    outcome: str
    attempts: int


def validate_assessment_result(
    original_grade: Any,
    dimension_rationales: Any,
    teacher_suggestions: Any,
) -> None:
    """ICT-005 领域校验（INV-4）；失败映射 INVALID_RESPONSE_SCHEMA。"""
    problems: list[str] = []
    if original_grade not in GRADES:
        problems.append(f"original_grade must be one of {GRADES}")
    if not isinstance(dimension_rationales, (list, tuple)) or len(dimension_rationales) != 5:
        problems.append("dimension_rationales must contain exactly five entries")
    else:
        seen = []
        for entry in dimension_rationales:
            if (
                not isinstance(entry, dict)
                or entry.get("dimension") not in DIMENSIONS
                or not entry.get("rationale")
            ):
                problems.append("each rationale requires a valid dimension and non-empty rationale")
                break
            seen.append(entry["dimension"])
        else:
            if sorted(seen) != sorted(DIMENSIONS):
                problems.append("dimension_rationales must cover each of the five dimensions once")
    if not isinstance(teacher_suggestions, (list, tuple)) or any(
        not isinstance(s, str) or not s for s in teacher_suggestions
    ):
        problems.append("teacher_suggestions must be a list of non-empty strings")
    if problems:
        raise InvalidAssessmentResult("INVALID_RESPONSE_SCHEMA: " + "; ".join(problems))


class ScoringOrchestrator:
    """评分任务编排（DU-3 一致性核心）。

    依赖注入：session_factory（与 DU-2 同一数据库；单测 SQLite）、
    LeaseStore（ICT-001 认领抽象）、OutboxStore（终态事件入队抽象）。
    终态方法在 ``session.begin()`` 块内完成业务写入 + Outbox 入队：
    任一步失败整体回滚（INV-3）。
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        lease_store: LeaseStore,
        outbox_store: OutboxStore,
        *,
        task_budget_seconds: int = TASK_BUDGET_SECONDS,
        lease_ttl_seconds: int = CLAIM_LEASE_SECONDS,
        max_reclaims: int = MAX_RECLAIM_COUNT,
    ) -> None:
        self._session_factory = session_factory
        self._lease_store = lease_store
        # OutboxStore 实例（测试/内存）或按 Session 构造的工厂（KD-002 同事务入队；
        # 与 SI-PURGE OutboxProvider 同形）
        self._outbox_provider = outbox_store
        self._task_budget = timedelta(seconds=task_budget_seconds)
        self._lease_ttl = timedelta(seconds=lease_ttl_seconds)
        self._max_reclaims = max_reclaims

    # ------------------------------------------------------------------ CT-004

    def handle_submission_received(self, event: dict) -> IngressResult:
        """消费 CT-004：按 submission_id 幂等创建任务；任务持久化后才返回（确认事件）。

        重复事件命中唯一键时为幂等 no-op（created=False），不产生重复任务，事件照常确认。
        """
        missing = [k for k in CT004_REQUIRED_FIELDS if k not in event]
        if missing:
            raise ValueError(f"CT-004 event missing required fields: {missing}")
        submission_id = event["submission_id"]
        if not isinstance(submission_id, str) or not submission_id:
            raise ValueError("CT-004 submission_id must be a non-empty string")
        if not isinstance(event["material_refs"], list) or not isinstance(
            event["missing_items"], list
        ):
            raise ValueError("CT-004 material_refs/missing_items must be arrays")

        # CCR-001 重放守卫：已评分清除（墓碑存在）的提交不重建评分任务；
        # 事件照常确认（墓碑即清除完成的证据），防止旧 CT-004 重放复活已删数据。
        with self._session_factory() as session:
            if is_tombstoned(session, submission_id):
                return IngressResult(
                    task_id="", submission_id=submission_id, created=False, tombstoned=True
                )

        task_id = uuid.uuid4().hex
        created_at = _utcnow()
        task = ScoringTask(
            task_id=task_id,
            submission_id=submission_id,
            course_id=event["course_id"],
            assignment=event["assignment"],
            student_name=event["student_name"],
            group_name=event["group_name"],
            material_refs=event["material_refs"],
            missing_items=event["missing_items"],
            received_at=_parse_dt(event["received_at"]),
            status=STATUS_PENDING,
            attempts=0,
            failure_reason=None,
            retry_record=None,
            lease_owner=None,
            lease_expires_at=None,
            reclaim_count=0,
            created_at=created_at,
            started_at=None,
            deadline_at=created_at + self._task_budget,
            finished_at=None,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(task)
        except IntegrityError:
            with self._session_factory() as session:
                existing = session.scalar(
                    select(ScoringTask).where(ScoringTask.submission_id == submission_id)
                )
            if existing is None:  # 唯一键之外的完整性错误：不确认事件
                raise
            return IngressResult(
                task_id=existing.task_id, submission_id=submission_id, created=False
            )
        return IngressResult(task_id=task_id, submission_id=submission_id, created=True)

    # ----------------------------------------------------------------- ICT-001

    def claim_task(self, owner: str, now: datetime | None = None) -> ClaimedTask | None:
        """认领下一个可执行任务（pending 或租约到期的 in_progress）。

        无可认领任务或竞争失败返回 None；发现 reclaim_count 超上限的崩溃循环任务时
        先终态化（scoring_failed + CT-005 Outbox，LCD-002）再返回 None。
        """
        now = as_naive_utc(now) if now is not None else _utcnow()
        with self._session_factory() as session:
            candidate = session.scalar(
                select(ScoringTask.task_id)
                .where(
                    or_(
                        ScoringTask.status == STATUS_PENDING,
                        (ScoringTask.status == STATUS_IN_PROGRESS)
                        & ScoringTask.lease_expires_at.is_not(None)
                        & (ScoringTask.lease_expires_at <= now),
                    )
                )
                .order_by(ScoringTask.created_at, ScoringTask.task_id)
                .limit(1)
            )
        if candidate is None:
            return None
        lease = self._lease_store.claim(candidate, owner, self._lease_ttl, now)
        if lease is None:
            self._handle_claim_denied(candidate, now)
            return None
        with self._session_factory() as session:
            task = session.get(ScoringTask, candidate)
        return ClaimedTask(
            task_id=task.task_id,
            submission_id=task.submission_id,
            course_id=task.course_id,
            assignment=task.assignment,
            material_refs=task.material_refs,
            missing_items=task.missing_items,
            attempt_no=task.attempts,
            deadline_at=task.deadline_at,
            lease_owner=lease.owner,
            lease_expires_at=lease.expires_at,
        )

    def _handle_claim_denied(self, task_id: str, now: datetime) -> None:
        """区分「被他人持有」与「崩溃循环上限」；后者终态化（不写等级）。"""
        with self._session_factory() as session:
            task = session.get(ScoringTask, task_id)
            crash_loop = (
                task is not None
                and task.status == STATUS_IN_PROGRESS
                and task.lease_expires_at is not None
                and task.lease_expires_at <= now
                and task.reclaim_count >= self._max_reclaims
            )
        if not crash_loop:
            return  # CLAIM_CONFLICT：其他 worker 持有，等待下轮轮询
        with self._session_factory.begin() as session:
            task = session.get(ScoringTask, task_id)
            task.status = STATUS_SCORING_FAILED
            task.failure_reason = CRASH_LOOP_FAILURE_REASON
            task.finished_at = now
            self._outbox_for(session).enqueue(
                CT005_CONTRACT_ID,
                self._scoring_failed_payload(task),
                dedup_key=self._dedup_key(task.submission_id, STATUS_SCORING_FAILED),
            )

    def _outbox_for(self, session: Session) -> OutboxStore:
        provider = self._outbox_provider
        if isinstance(provider, OutboxStore):
            return provider
        return provider(session)

    # ----------------------------------------------------------------- ICT-005

    def complete_assessment(
        self,
        task_id: str,
        *,
        owner: str,
        attempt_no: int,
        original_grade: str,
        dimension_rationales: list,
        teacher_suggestions: list,
        scored_at: datetime | str | None = None,
        missing_materials_impact: str | None = None,
        prompt_version: str | None = None,
        rubric_version: str | None = None,
        model_meta: dict | None = None,
        now: datetime | None = None,
    ) -> OutcomeCommitted:
        """ICT-005：scored 终态事务（ST-001 + ST-002 + CT-005 Outbox 入队，INV-3）。

        守卫：当前 in_progress + 同一 attempt + 持有未过期租约 + 无既有终态结果；
        过期/重复/不匹配回调拒绝且不产生任何业务状态变更。
        """
        validate_assessment_result(original_grade, dimension_rationales, teacher_suggestions)
        now = as_naive_utc(now) if now is not None else _utcnow()
        scored_at_dt = _parse_dt(scored_at) if scored_at is not None else now
        with self._session_factory.begin() as session:
            task = self._load_for_terminal(session, task_id, owner, attempt_no, now)
            if session.get(ScoringResult, task_id) is not None:
                raise TerminalCallbackRejected(
                    DUPLICATE_TERMINAL_CALLBACK, "terminal result already exists"
                )
            task.status = STATUS_SCORED
            task.finished_at = scored_at_dt
            session.add(
                ScoringResult(
                    task_id=task.task_id,
                    submission_id=task.submission_id,
                    original_grade=original_grade,
                    dimension_rationales=list(dimension_rationales),
                    teacher_suggestions=list(teacher_suggestions),
                    scored_at=scored_at_dt,
                    missing_materials_impact=missing_materials_impact,
                    prompt_version=prompt_version,
                    rubric_version=rubric_version,
                    model_meta=model_meta,
                )
            )
            self._outbox_for(session).enqueue(
                CT005_CONTRACT_ID,
                {
                    "submission_id": task.submission_id,
                    "outcome": STATUS_SCORED,
                    "original_grade": original_grade,
                    "dimension_rationales": list(dimension_rationales),
                    "teacher_suggestions": list(teacher_suggestions),
                    "scored_at": _iso(scored_at_dt),
                    "v": 1,
                },
                dedup_key=self._dedup_key(task.submission_id, STATUS_SCORED),
            )
            return OutcomeCommitted(
                task_id=task.task_id,
                submission_id=task.submission_id,
                outcome=STATUS_SCORED,
                attempts=task.attempts,
            )

    # ----------------------------------------------------------------- ICT-006

    def fail_assessment(
        self,
        task_id: str,
        *,
        owner: str,
        attempt_no: int,
        error_kind: str,
        now: datetime | None = None,
    ) -> RetryEntered | OutcomeCommitted:
        """ICT-006：classified 失败处理（REQ-012 重试一次）。

        attempt_no=1：记录 first_failure，attempts 推进为 2（唯一一次重试），不终态；
        attempt_no=2：补全 retry_record，scoring_failed 终态事务 + CT-005 Outbox
        （不写任何等级，INV-1/INV-2）。按 attempt_no 去重。
        """
        if error_kind not in ERROR_TAXONOMY:
            raise InvalidAssessmentFailure(f"unknown error_kind: {error_kind!r}")
        now = as_naive_utc(now) if now is not None else _utcnow()
        with self._session_factory.begin() as session:
            task = self._load_for_terminal(session, task_id, owner, attempt_no, now)
            record = dict(task.retry_record or {})
            failure = {"error_kind": error_kind, "at": _iso(now)}
            if attempt_no == 1:
                record["first_failure"] = failure
                task.retry_record = record
                task.attempts = 2
                return RetryEntered(
                    task_id=task.task_id,
                    attempt_no=1,
                    next_attempt_no=2,
                    error_kind=error_kind,
                )
            record["second_failure"] = failure
            task.retry_record = record
            task.status = STATUS_SCORING_FAILED
            task.failure_reason = error_kind
            task.finished_at = now
            self._outbox_for(session).enqueue(
                CT005_CONTRACT_ID,
                self._scoring_failed_payload(task),
                dedup_key=self._dedup_key(task.submission_id, STATUS_SCORING_FAILED),
            )
            return OutcomeCommitted(
                task_id=task.task_id,
                submission_id=task.submission_id,
                outcome=STATUS_SCORING_FAILED,
                attempts=task.attempts,
            )

    # ---------------------------------------------------------------- internals

    def _load_for_terminal(
        self,
        session: Session,
        task_id: str,
        owner: str,
        attempt_no: int,
        now: datetime,
    ) -> ScoringTask:
        """终态守卫矩阵（L2 03 §3.3）：任务/尝试/租约/状态四重匹配。"""
        task = session.scalar(
            select(ScoringTask).where(ScoringTask.task_id == task_id).with_for_update()
        )
        if task is None:
            raise TerminalCallbackRejected(STALE_TERMINAL_CALLBACK, "unknown task_id")
        if task.status in TERMINAL_STATUSES:
            raise TerminalCallbackRejected(
                DUPLICATE_TERMINAL_CALLBACK, "task already terminal"
            )
        if task.status != STATUS_IN_PROGRESS or task.attempts != attempt_no:
            raise TerminalCallbackRejected(
                STALE_TERMINAL_CALLBACK, "task state or attempt mismatch"
            )
        if (
            task.lease_owner != owner
            or task.lease_expires_at is None
            or task.lease_expires_at <= now
        ):
            raise TerminalCallbackRejected(
                STALE_TERMINAL_CALLBACK, "no active lease for this owner"
            )
        return task

    @staticmethod
    def _dedup_key(submission_id: str, outcome: str) -> str:
        """IDM-2：同一任务最多一条逻辑终态事件（submission_id + 终态）。"""
        return f"{submission_id}:{outcome}"

    @staticmethod
    def _scoring_failed_payload(task: ScoringTask) -> dict:
        """CT-005 scoring_failed 两件套（failure_reason + retry_record）+ v=1。"""
        record = task.retry_record or {}
        first = record.get("first_failure") or {}
        second = record.get("second_failure") or {}
        retry_record = {
            "attempts": max(task.attempts, 1),
            "last_error": second.get("error_kind")
            or first.get("error_kind")
            or task.failure_reason,
        }
        if first.get("at"):
            retry_record["retried_at"] = first["at"]
        return {
            "submission_id": task.submission_id,
            "outcome": STATUS_SCORING_FAILED,
            "failure_reason": task.failure_reason,
            "retry_record": retry_record,
            "v": 1,
        }
