"""T-B03c RETENTION-GOVERNANCE 核心服务（MOD-05 / NFR-004 / DF-3 / FLOW-011）。

职责（除 SCENARIO-016 端到端声明外的保留治理）：
- 到期批处理 `mark_due_batches`：retention_due_at = 课程结束时间 + 1 年；课程结束
  时间经注入的 CP-COURSE-ENDTIME 只读端口解析（FLOW-011 同进程，非网络调用）；
  到期生成/更新待确认批次（幂等，时钟可注入）；
- CT-011 确认 `confirm_batch`：未到期 → BatchNotExpiredError（BATCH_NOT_EXPIRED）；
  同批次重复确认幂等（executing/partially_failed/completed 返回现状、不重发
  CT-012）；**审计记录（DeletionConfirmed）先于任何清除动作写入**——同事务内先
  flush 审计行，再经 OutboxStore 抽象发布 CT-012（KD-002 同事务提交）；
- CT-014 消费 `handle_ct014`：按 batch_id + purged_at 幂等回写批次状态
  （completed / partially_failed + failed_items 保留供重跑）；完成时追加
  RecordsDeleted 审计；审计记录永久留存不在删除范围；
- M05-IC-06 读端口 `list_batches`：L15 deletion_batches[] 视图只读供给。

边界：不实现/不声称 AssessmentResult（MOD-04）删除接线（CCR-001 pending）；
不声称 SCENARIO-016 完成。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, ContextManager, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from tutor_shared.outbox import OutboxStore

from course_app.course_roster.admin import get_course_end_time
from course_app.course_roster.models import Course
from course_app.submission_intake.core.models import Submission
from course_app.teacher_web.review_query.ports import RetentionBatchView

from .errors import (
    BatchNotExpiredError,
    BatchNotFoundError,
    Ct014ValidationError,
)
from .models import (
    ACTION_DELETION_CONFIRMED,
    ACTION_RECORDS_DELETED,
    STATUS_AWAITING_CONFIRM,
    STATUS_COMPLETED,
    STATUS_EXECUTING,
    STATUS_PARTIALLY_FAILED,
    STATUS_PENDING_MARK,
    DeletionAuditRecord,
    DeletionBatch,
)

CT_012 = "CT-012"

#: 删除范围（v1：课程全量提交）
SCOPE_COURSE = "course"

SessionScopeFactory = Callable[[], ContextManager[Session]]

#: CP-COURSE-ENDTIME 端口形状（FLOW-011 同进程只读调用；课程不存在/无结束时间
#: 返回 None）。默认实现为 L01 admin.get_course_end_time。
CourseEndTimePort = Callable[[Session, str], datetime | None]

#: 课程目录端口形状（到期批处理的课程枚举；默认直读同库 courses 目录）。
CourseCatalogPort = Callable[[Session], Iterable[str]]

#: OutboxStore 实例（测试/内存）或按 Session 构造的工厂（SQL 同事务入队，KD-002；
#: 组合根直接传 SqlaOutboxStore 类即可）。
OutboxProvider = OutboxStore | Callable[[Session], OutboxStore]

_CT014_REQUIRED = frozenset(
    {"batch_id", "purged_submission_ids", "failed_items", "purged_at", "v"}
)


def _naive_utc(dt: datetime) -> datetime:
    """归一化为 naive UTC（与时间列口径一致）。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _iso(dt: datetime) -> datetime:
    """naive UTC 读回值按 UTC 解释（ISO 输出用）。"""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def plus_one_year(dt: datetime) -> datetime:
    """课程结束时间 + 1 年（NFR-004 保留期；2/29 归并 2/28）。"""
    try:
        return dt.replace(year=dt.year + 1)
    except ValueError:  # 2 月 29 日 → 次年 2 月 28 日
        return dt.replace(year=dt.year + 1, day=28)


def derive_batch_id(course_id: str, scope: str) -> str:
    """确定性批次标识（课程 + 范围唯一 → 到期标记幂等）。"""
    return f"{course_id}:{scope}"


def default_course_end_time_port(session: Session, course_id: str) -> datetime | None:
    """CP-COURSE-ENDTIME 默认绑定：L01 只读端口（FLOW-011 同进程）。"""
    end = get_course_end_time(session, course_id)
    return _naive_utc(end) if end is not None else None


def default_course_catalog(session: Session) -> list[str]:
    """课程目录默认实现：同库 courses 目录枚举（只读）。"""
    return list(session.scalars(select(Course.course_id).order_by(Course.course_id)))


@dataclass(frozen=True)
class MarkDueItem:
    """单课程到期标记结果。"""

    batch_id: str
    course_id: str
    retention_due_at: datetime
    status: str  # 标记后状态
    created: bool


@dataclass(frozen=True)
class MarkDueReport:
    """一次到期批处理汇总。"""

    marked: tuple[MarkDueItem, ...]
    skipped_course_ids: tuple[str, ...]  # 无课程或无结束时间


@dataclass(frozen=True)
class ConfirmResult:
    """CT-011 确认结果（首次执行与幂等重放共用形状）。"""

    batch_id: str
    batch_status: str
    pending_deletion_scope: tuple[str, ...]
    audit_record_id: str | None  # 幂等重放时为本次 None（未重复执行）
    already_confirmed: bool


@dataclass(frozen=True)
class Ct014Event:
    """校验后的 CT-014 事件（冻结契约字段，additionalProperties=false）。"""

    batch_id: str
    purged_submission_ids: tuple[str, ...]
    failed_items: tuple[dict, ...]
    purged_at: str


@dataclass(frozen=True)
class Ct014Result:
    """CT-014 回写结果。"""

    batch_id: str
    batch_status: str
    applied: bool  # False = 同 batch_id + purged_at 重复事件幂等空操作


def validate_ct014(payload: dict) -> Ct014Event:
    """按 contracts/ct-014.json 校验事件本体；不满足冻结契约抛 Ct014ValidationError。"""
    if not isinstance(payload, dict):
        raise Ct014ValidationError("CT-014 payload must be an object")
    missing = _CT014_REQUIRED - payload.keys()
    if missing:
        raise Ct014ValidationError(f"CT-014 missing fields: {sorted(missing)}")
    extra = payload.keys() - _CT014_REQUIRED
    if extra:
        raise Ct014ValidationError(f"CT-014 unexpected fields: {sorted(extra)}")
    if payload["v"] != 1:
        raise Ct014ValidationError(f"CT-014 unsupported v: {payload['v']!r}")
    batch_id = payload["batch_id"]
    if not isinstance(batch_id, str) or not batch_id:
        raise Ct014ValidationError("CT-014 batch_id must be a non-empty string")
    purged_at = payload["purged_at"]
    if not isinstance(purged_at, str) or not purged_at:
        raise Ct014ValidationError("CT-014 purged_at must be a non-empty string")
    purged_ids = payload["purged_submission_ids"]
    if not isinstance(purged_ids, (list, tuple)) or any(
        not isinstance(sid, str) or not sid for sid in purged_ids
    ):
        raise Ct014ValidationError(
            "CT-014 purged_submission_ids must be non-empty strings"
        )
    failed_items = payload["failed_items"]
    if not isinstance(failed_items, (list, tuple)):
        raise Ct014ValidationError("CT-014 failed_items must be an array")
    normalized_failed: list[dict] = []
    for item in failed_items:
        if (
            not isinstance(item, dict)
            or set(item.keys()) != {"submission_id", "reason"}
            or not isinstance(item["submission_id"], str)
            or not item["submission_id"]
            or not isinstance(item["reason"], str)
            or not item["reason"]
        ):
            raise Ct014ValidationError(
                "CT-014 failed_items[] must be {submission_id, reason} non-empty strings"
            )
        normalized_failed.append(
            {"submission_id": item["submission_id"], "reason": item["reason"]}
        )
    return Ct014Event(
        batch_id=batch_id,
        purged_submission_ids=tuple(dict.fromkeys(purged_ids)),
        failed_items=tuple(normalized_failed),
        purged_at=purged_at,
    )


class RetentionService:
    """保留治理唯一服务入口（到期标记 / CT-011 确认 / CT-014 回写 / 批次视图）。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文；
    - `outbox_store`：OutboxStore 实例或 `Callable[[Session], OutboxStore]`
      （SQL 接线传工厂使 CT-012 行与批次更新同事务提交，KD-002）；
    - `course_end_time_port`：CP-COURSE-ENDTIME 只读端口（默认 L01 实现；
      FLOW-011 同进程，禁止网络化）；
    - `course_catalog`：课程枚举端口（mark_due_batches 未显式传 course_ids 时）；
    - `clock`：可注入时钟（测试固定时间）。
    """

    def __init__(
        self,
        session_factory: SessionScopeFactory,
        outbox_store: OutboxProvider,
        *,
        course_end_time_port: CourseEndTimePort | None = None,
        course_catalog: CourseCatalogPort | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._outbox_provider = outbox_store
        self._end_time_port = course_end_time_port or default_course_end_time_port
        self._course_catalog = course_catalog or default_course_catalog
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ---- 时间 ----

    def _now(self) -> datetime:
        return _naive_utc(self._clock())

    # ---- 到期批处理（FLOW-011） ----

    def mark_due_batches(
        self,
        now: datetime | None = None,
        *,
        course_ids: Iterable[str] | None = None,
        scope: str = SCOPE_COURSE,
    ) -> MarkDueReport:
        """到期标记：课程结束 + 1 年到期 → 生成/更新待确认批次（幂等）。

        - 每课程至多一个 (course_id, scope) 批次；重复执行收敛同一批次；
        - 未到期批次为 pending_mark，到期（retention_due_at <= now）为
          awaiting_confirm；课程结束时间变化时更新 retention_due_at 并按当前
          时钟重算到期状态（仅 pending_mark/awaiting_confirm 阶段可改）；
        - executing/partially_failed/completed 批次不回退、不改写；
        - 课程不存在或无结束时间 → 跳过（CP-COURSE-ENDTIME 返回 None）。
        """
        current = _naive_utc(now) if now is not None else self._now()
        marked: list[MarkDueItem] = []
        skipped: list[str] = []
        with self._session_factory() as session:
            ids = list(course_ids) if course_ids is not None else list(
                self._course_catalog(session)
            )
            for course_id in dict.fromkeys(ids):
                end = self._end_time_port(session, course_id)
                if end is None:
                    skipped.append(course_id)
                    continue
                due = _naive_utc(plus_one_year(end))
                target_status = (
                    STATUS_AWAITING_CONFIRM if due <= current else STATUS_PENDING_MARK
                )
                batch_id = derive_batch_id(course_id, scope)
                batch = session.get(DeletionBatch, batch_id)
                created = False
                if batch is None:
                    batch = DeletionBatch(
                        batch_id=batch_id,
                        course_id=course_id,
                        scope=scope,
                        retention_due_at=due,
                        status=target_status,
                        exclusions=[],
                        failed_items=[],
                        cleared_submission_ids=[],
                        applied_purge_marks=[],
                        created_at=current,
                        confirmed_at=None,
                        confirmed_by=None,
                        updated_at=current,
                    )
                    session.add(batch)
                    created = True
                elif batch.status in (STATUS_PENDING_MARK, STATUS_AWAITING_CONFIRM):
                    batch.retention_due_at = due
                    batch.status = target_status
                    batch.updated_at = current
                marked.append(
                    MarkDueItem(
                        batch_id=batch.batch_id,
                        course_id=course_id,
                        retention_due_at=due,
                        status=batch.status,
                        created=created,
                    )
                )
        return MarkDueReport(marked=tuple(marked), skipped_course_ids=tuple(skipped))

    # ---- 待删除范围解析 ----

    @staticmethod
    def _pending_scope(session: Session, batch: DeletionBatch) -> list[str]:
        """课程范围未清除提交 − 教师排除项 − 已删除（只读 SI-CORE 登记）。"""
        excluded = set(batch.exclusions or ())
        cleared = set(batch.cleared_submission_ids or ())
        rows = session.scalars(
            select(Submission.submission_id)
            .where(
                Submission.course_id == batch.course_id,
                Submission.deleted_at.is_(None),
            )
            .order_by(Submission.submission_id)
        ).all()
        return [
            sid for sid in rows if sid not in excluded and sid not in cleared
        ]

    # ---- CT-011 确认 ----

    def batch_course_id(self, batch_id: str) -> str | None:
        """批次课程归属（端点授权前置查询；不存在返回 None → NOT_FOUND）。"""
        with self._session_factory() as session:
            batch = session.get(DeletionBatch, batch_id)
            return None if batch is None else batch.course_id

    def confirm_batch(
        self,
        *,
        batch_id: str,
        operator: str,
        exclusions: Sequence[str] = (),
    ) -> ConfirmResult:
        """CT-011 删除确认：审计先行 → 批次 executing → 同事务发布 CT-012。

        - 未到期（retention_due_at > now）→ BatchNotExpiredError；
        - 重复确认幂等：executing/partially_failed/completed 直接返回现状，
          不重复写审计、不重发 CT-012（CT-011 idempotency 条款）；
        - 顺序断言：DeletionConfirmed 审计行先 flush，随后才 enqueue CT-012
          （审计记录先于任何清除动作写入；同本地事务提交，KD-002）。
        """
        now = self._now()
        keep = sorted({e for e in exclusions if isinstance(e, str) and e})
        with self._session_factory() as session:
            batch = session.get(DeletionBatch, batch_id)
            if batch is None:
                raise BatchNotFoundError(f"deletion batch {batch_id!r} not found")
            if batch.status in (
                STATUS_EXECUTING,
                STATUS_PARTIALLY_FAILED,
                STATUS_COMPLETED,
            ):
                # 幂等重放：同一批次重复确认返回同一状态，不重复执行
                return ConfirmResult(
                    batch_id=batch.batch_id,
                    batch_status=batch.status,
                    pending_deletion_scope=tuple(
                        self._pending_scope(session, batch)
                    ),
                    audit_record_id=None,
                    already_confirmed=True,
                )
            if batch.retention_due_at > now:
                raise BatchNotExpiredError(
                    f"deletion batch {batch_id!r} not expired "
                    f"(due at {batch.retention_due_at.isoformat()})"
                )
            batch.exclusions = keep
            submission_ids = self._pending_scope(session, batch)
            # 1) 审计先行：DeletionConfirmed 先于任何清除动作写入并 flush
            audit_record_id = f"audit-{uuid.uuid4().hex}"
            session.add(
                DeletionAuditRecord(
                    audit_record_id=audit_record_id,
                    batch_id=batch.batch_id,
                    course_id=batch.course_id,
                    action=ACTION_DELETION_CONFIRMED,
                    scope=batch.scope,
                    operator=operator,
                    submission_ids=list(submission_ids),
                    created_at=now,
                )
            )
            session.flush()
            # 2) 批次状态迁移（同事务）
            batch.status = STATUS_EXECUTING
            batch.confirmed_at = now
            batch.confirmed_by = operator
            batch.updated_at = now
            # 3) CT-012 载荷与 contracts/ct-012.json 一致（additionalProperties=false）
            ct012_payload = {
                "batch_id": batch.batch_id,
                "submission_ids": list(submission_ids),
                "scope": batch.scope,
                "operator": operator,
                "executed_at": _iso(now).isoformat(),
                "audit_record_id": audit_record_id,
                "v": 1,
            }
            # 消费方（SI-PURGE）按 batch_id 幂等去重
            self._outbox_for(session).enqueue(
                CT_012, ct012_payload, batch.batch_id
            )
            session.flush()
            return ConfirmResult(
                batch_id=batch.batch_id,
                batch_status=batch.status,
                pending_deletion_scope=tuple(submission_ids),
                audit_record_id=audit_record_id,
                already_confirmed=False,
            )

    # ---- CT-014 / CT-015 消费回写（CCR-001 双回流） ----

    def handle_ct014(self, payload: dict) -> Ct014Result:
        """CT-014 PurgeCompleted（MOD-02 材料清除结果）消费入口。"""
        return self._apply_purge_flow(payload, flow="CT-014")

    def handle_ct015(self, payload: dict) -> Ct014Result:
        """CT-015 AssessmentPurgeCompleted（MOD-04 评分清除结果，CCR-001）消费入口。"""
        return self._apply_purge_flow(payload, flow="CT-015")

    def _apply_purge_flow(self, payload: dict, *, flow: str) -> Ct014Result:
        """单路回流回写 + 双路聚合判定（CCR-001 §2.1.3 / §2.4）。

        - 按 (flow, batch_id + purged_at) 幂等：重复事件为空操作（CT-014/CT-015
          各自的 idempotency）；
        - 批次完成条件 = CT-014 与 CT-015 **双到达**；任一路有失败项 →
          partially_failed（failed_items 逐路保留并标注 flow，供重跑）；双路均无
          失败 → completed 并追加 RecordsDeleted 审计（只增不删）；
        - cleared_submission_ids 为两路 purged 并集（重跑部分成功不丢既有进度）；
        - 审计记录不受影响（只追加，永久留存）。
        """
        event = validate_ct014(payload)  # CT-015 与 CT-014 事件形状一致（镜像）
        now = self._now()
        marks_field = "applied_purge_marks" if flow == "CT-014" else "ct015_purge_marks"
        with self._session_factory() as session:
            batch = session.get(DeletionBatch, event.batch_id)
            if batch is None:
                raise BatchNotFoundError(
                    f"deletion batch {event.batch_id!r} not found"
                )
            marks = list(getattr(batch, marks_field) or [])
            if event.purged_at in marks:
                return Ct014Result(
                    batch_id=batch.batch_id,
                    batch_status=batch.status,
                    applied=False,
                )
            marks.append(event.purged_at)
            setattr(batch, marks_field, marks)
            # 单路状态登记（到达 + 最新失败项 + purged 并集累积）
            states = {f: dict(s) for f, s in (batch.flow_states or {}).items()}
            state = states.get(flow, {})
            state["arrived"] = True
            state["failed_items"] = [dict(item) for item in event.failed_items]
            state["purged_submission_ids"] = sorted(
                set(state.get("purged_submission_ids", ())) | set(event.purged_submission_ids)
            )
            states[flow] = state
            batch.flow_states = states
            # 双路聚合
            cleared: set[str] = set()
            merged_failed: list[dict] = []
            for f in ("CT-014", "CT-015"):
                fstate = states.get(f, {})
                cleared |= set(fstate.get("purged_submission_ids", ()))
                for item in fstate.get("failed_items", ()):
                    merged_failed.append(
                        {
                            "submission_id": item["submission_id"],
                            "reason": item["reason"],
                            "flow": f,
                        }
                    )
            batch.cleared_submission_ids = sorted(cleared)
            batch.failed_items = merged_failed
            both_arrived = all(
                states.get(f, {}).get("arrived") for f in ("CT-014", "CT-015")
            )
            was_completed = batch.status == STATUS_COMPLETED
            if not both_arrived:
                batch.status = STATUS_EXECUTING  # 双回流未齐，保持执行中
            elif merged_failed:
                batch.status = STATUS_PARTIALLY_FAILED
            else:
                batch.status = STATUS_COMPLETED
                if not was_completed:
                    # DeletionConfirmed → RecordsDeleted 审计链闭合（只追加；
                    # 已完成批次的重跑不重复追加）
                    session.add(
                        DeletionAuditRecord(
                            audit_record_id=f"audit-{uuid.uuid4().hex}",
                            batch_id=batch.batch_id,
                            course_id=batch.course_id,
                            action=ACTION_RECORDS_DELETED,
                            scope=batch.scope,
                            operator=batch.confirmed_by or "",
                            submission_ids=sorted(cleared),
                            created_at=now,
                        )
                    )
            batch.updated_at = now
            session.flush()
            return Ct014Result(
                batch_id=batch.batch_id,
                batch_status=batch.status,
                applied=True,
            )

    # ---- M05-IC-06 只读批次视图 ----

    def list_batches(
        self,
        *,
        course_id: str | None = None,
        batch_id: str | None = None,
        submission_id: str | None = None,
    ) -> tuple[RetentionBatchView, ...]:
        """M05-IC-06：只读批次视图（查询不改变批次状态，天然幂等）。"""
        with self._session_factory() as session:
            stmt = select(DeletionBatch).order_by(
                DeletionBatch.course_id, DeletionBatch.batch_id
            )
            if course_id is not None:
                stmt = stmt.where(DeletionBatch.course_id == course_id)
            if batch_id is not None:
                stmt = stmt.where(DeletionBatch.batch_id == batch_id)
            views: list[RetentionBatchView] = []
            for batch in session.scalars(stmt).all():
                if submission_id is not None:
                    involved = (
                        set(batch.cleared_submission_ids or ())
                        | {item["submission_id"] for item in (batch.failed_items or ())}
                        | set(self._pending_scope(session, batch))
                    )
                    if submission_id not in involved:
                        continue
                views.append(
                    RetentionBatchView(
                        batch_id=batch.batch_id,
                        retention_due_at=_iso(batch.retention_due_at).isoformat(),
                        scope=batch.scope,
                        batch_status=batch.status,
                        exclusions=tuple(batch.exclusions or ()),
                        cleared_submission_ids=tuple(
                            batch.cleared_submission_ids or ()
                        ),
                    )
                )
            return tuple(views)

    # ---- 内部 ----

    def _outbox_for(self, session: Session) -> OutboxStore:
        provider = self._outbox_provider
        if isinstance(provider, OutboxStore):
            return provider
        return provider(session)


__all__ = [
    "CT_012",
    "ConfirmResult",
    "CourseCatalogPort",
    "CourseEndTimePort",
    "Ct014Event",
    "Ct014Result",
    "MarkDueItem",
    "MarkDueReport",
    "OutboxProvider",
    "RetentionService",
    "SCOPE_COURSE",
    "derive_batch_id",
    "plus_one_year",
    "validate_ct014",
]
