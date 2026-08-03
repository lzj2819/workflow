"""SI-CORE-TX：命令编排、单事务边界与 Outbox 同事务入队（IC-SI-04 owner 端口）。

一致性（SIC-INV-05 / KD-002）：
- Submission 状态 + 材料清单 + 完整性报告 + CT-004/CT-006 Outbox 行在同一本地
  事务提交；任一步失败整体回滚，不产生部分 Submission 或孤立 Outbox；
- Outbox 投递与投递表归 SI-RELAY（backfill），本层只经
  `tutor_shared.outbox.OutboxStore` 抽象在事务内入队，dedup_key=submission_id；
- rejected 不发布任何事件；CT-006 在 received 与终态 upload_failed 发布（LCD-002）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, ContextManager, Sequence

from sqlalchemy.orm import Session

from tutor_shared.outbox import OutboxStore

from . import status as st
from .aggregate import APPLIED, IDEMPOTENT_HIT, SubmissionAggregate, TransitionResult
from .errors import IllegalTransitionError, NotFoundError
from .integrity import (
    IntegrityReportData,
    MaterialMetadataReader,
    build_manifest_and_report,
)
from .models import IntegrityReportRow, Submission, SubmissionMaterial

CT_004 = "CT-004"
CT_006 = "CT-006"

UPLOAD_SESSION_FAILED_TERMINAL = "failed_terminal"


@dataclass(frozen=True)
class CommandResult:
    """IC-SI-04 命令输出：submission_id/status/received_at?/missing_items/failure_reason?/transition_result。"""

    submission_id: str
    status: str
    received_at: datetime
    missing_items: tuple[str, ...]
    failure_reason: str | None
    transition_result: TransitionResult


@dataclass(frozen=True)
class SubmissionView:
    """IC-SI-03 / CT-002 只读视图。"""

    submission_id: str
    status: str
    failure_reason: str | None
    missing_items: tuple[str, ...]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ct004_payload(
    submission: Submission,
    materials: Sequence[SubmissionMaterial],
    missing_items: Sequence[str],
) -> dict:
    return {
        "submission_id": submission.submission_id,
        "course_id": submission.course_id or "",
        "assignment": submission.assignment or "",
        "student_name": submission.student_name or "",
        "group_name": submission.group_name or "",
        "material_refs": [
            {
                "category": m.category,
                "ref": m.material_ref,
                **({"filename": m.filename} if m.filename else {}),
                **({"size_bytes": m.size_bytes} if m.size_bytes is not None else {}),
            }
            for m in materials
        ],
        "missing_items": list(missing_items),
        "received_at": submission.received_at.isoformat(),
        "v": 1,
    }


def _ct006_payload(submission: Submission, missing_items: Sequence[str]) -> dict:
    return {
        "submission_id": submission.submission_id,
        "course_id": submission.course_id or "",
        "assignment": submission.assignment or "",
        "student_name": submission.student_name or "",
        "group_name": submission.group_name or "",
        "status": submission.status,
        "missing_items": list(missing_items),
        "received_at": submission.received_at.isoformat(),
        "v": 1,
    }


class SubmissionCoreService:
    """IC-SI-04 提交聚合命令与查询端口实现（供 SI-API / SI-RELAY / SI-PURGE 消费）。

    依赖注入：
    - `session_factory`：返回 Session 上下文管理器（默认 `course_app.db.session_scope` 风格），
      提供单事务边界；异常回滚。
    - `outbox_store`：`tutor_shared.outbox.OutboxStore` 抽象（投递归 SI-RELAY backfill）。
    - `metadata_reader`：SI-STORE 元数据端口抽象（实现归 SI-STORE backfill）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        outbox_store: OutboxStore,
        metadata_reader: MaterialMetadataReader,
    ) -> None:
        self._session_factory = session_factory
        self._outbox = outbox_store
        self._metadata_reader = metadata_reader

    # ---- 创建命令（∅ → 创建态；submission_uuid 幂等） ----

    def confirm_received(
        self,
        *,
        submission_uuid: str,
        course_id: str,
        assignment: str,
        student_name: str,
        group_name: str,
        material_refs: Sequence[str],
        expected_categories: Sequence[str],
        verification: dict,
    ) -> CommandResult:
        """∅ → received；同事务写清单/报告并 enqueue CT-004 + CT-006。"""
        if not verification.get("verified"):
            raise IllegalTransitionError("precondition failed: verification=verified")
        for name, value in (
            ("course_id", course_id),
            ("assignment", assignment),
            ("student_name", student_name),
            ("group_name", group_name),
        ):
            if not value:
                raise IllegalTransitionError(f"precondition failed: {name} required")
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            existing = aggregate.find_by_uuid(submission_uuid)
            if existing is not None:
                return self._idempotent_result(session, existing)
            built = build_manifest_and_report(
                material_refs, expected_categories, self._metadata_reader, now
            )
            submission = aggregate.create(
                submission_uuid=submission_uuid,
                course_id=course_id,
                assignment=assignment,
                student_name=student_name,
                group_name=group_name,
                status=st.RECEIVED,
                failure_reason=None,
                now=now,
            )
            materials = self._persist_manifest_and_report(session, submission, built.entries, built.report)
            missing = list(built.report.missing_items)
            # Outbox 行与业务写入同一事务（SIC-INV-05）：入队失败则整体回滚。
            self._outbox.enqueue(CT_004, _ct004_payload(submission, materials, missing), submission.submission_id)
            self._outbox.enqueue(CT_006, _ct006_payload(submission, missing), submission.submission_id)
            return CommandResult(
                submission_id=submission.submission_id,
                status=st.RECEIVED,
                received_at=now,
                missing_items=tuple(missing),
                failure_reason=None,
                transition_result=TransitionResult(
                    submission.submission_id, "∅", st.RECEIVED, APPLIED
                ),
            )

    def mark_rejected(
        self,
        *,
        submission_uuid: str,
        failure_reason: str,
        verification: dict,
        course_id: str | None = None,
        assignment: str | None = None,
        student_name: str | None = None,
        group_name: str | None = None,
    ) -> CommandResult:
        """∅ → rejected（终态）；不发布 CT-004/CT-006。"""
        if verification.get("verified"):
            raise IllegalTransitionError("precondition failed: verification=not_verified")
        if not failure_reason:
            raise IllegalTransitionError("failure_reason is required")
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            existing = aggregate.find_by_uuid(submission_uuid)
            if existing is not None:
                return self._idempotent_result(session, existing)
            submission = aggregate.create(
                submission_uuid=submission_uuid,
                course_id=course_id or verification.get("course_id"),
                assignment=assignment,
                student_name=student_name,
                group_name=group_name,
                status=st.REJECTED,
                failure_reason=failure_reason,
                now=now,
            )
            return CommandResult(
                submission_id=submission.submission_id,
                status=st.REJECTED,
                received_at=now,
                missing_items=(),
                failure_reason=failure_reason,
                transition_result=TransitionResult(
                    submission.submission_id, "∅", st.REJECTED, APPLIED
                ),
            )

    def mark_upload_failed(
        self,
        *,
        submission_uuid: str,
        failure_reason: str,
        upload_session_state: str,
        material_refs: Sequence[str] = (),
        expected_categories: Sequence[str] = (),
        course_id: str | None = None,
        assignment: str | None = None,
        student_name: str | None = None,
        group_name: str | None = None,
    ) -> CommandResult:
        """∅ → upload_failed（终态）；同事务写已知清单/报告并 enqueue CT-006（LCD-002）。"""
        if upload_session_state != UPLOAD_SESSION_FAILED_TERMINAL:
            raise IllegalTransitionError(
                "precondition failed: upload_session_state=failed_terminal"
            )
        if not failure_reason:
            raise IllegalTransitionError("failure_reason is required")
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            existing = aggregate.find_by_uuid(submission_uuid)
            if existing is not None:
                return self._idempotent_result(session, existing)
            built = build_manifest_and_report(
                material_refs, expected_categories, self._metadata_reader, now
            )
            submission = aggregate.create(
                submission_uuid=submission_uuid,
                course_id=course_id,
                assignment=assignment,
                student_name=student_name,
                group_name=group_name,
                status=st.UPLOAD_FAILED,
                failure_reason=failure_reason,
                now=now,
            )
            self._persist_manifest_and_report(session, submission, built.entries, built.report)
            missing = list(built.report.missing_items)
            self._outbox.enqueue(CT_006, _ct006_payload(submission, missing), submission.submission_id)
            return CommandResult(
                submission_id=submission.submission_id,
                status=st.UPLOAD_FAILED,
                received_at=now,
                missing_items=tuple(missing),
                failure_reason=failure_reason,
                transition_result=TransitionResult(
                    submission.submission_id, "∅", st.UPLOAD_FAILED, APPLIED
                ),
            )

    # ---- 生命周期命令 ----

    def advance_to_processing(
        self,
        *,
        submission_id: str,
        expected_state: str = st.RECEIVED,
        consumer_ack: str,
    ) -> CommandResult:
        """received → processing（CT-004 task_persisted 确认，LCD-003）；重复确认为空操作。"""
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            submission = self._must_find(aggregate, submission_id)
            result = aggregate.advance_to_processing(
                submission, consumer_ack=consumer_ack, expected_state=expected_state, now=now
            )
            return self._result_from_row(session, submission, result)

    def apply_scoring_outcome(
        self,
        *,
        submission_id: str,
        expected_state: str = st.PROCESSING,
        outcome: str,
        failure_reason: str | None = None,
    ) -> CommandResult:
        """processing → scored/scoring_failed（CT-005）；重复终态事件为空操作。"""
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            submission = self._must_find(aggregate, submission_id)
            result = aggregate.apply_scoring_outcome(
                submission,
                outcome=outcome,
                expected_state=expected_state,
                failure_reason=failure_reason,
                now=now,
            )
            return self._result_from_row(session, submission, result)

    def purge_submission(self, *, submission_id: str) -> CommandResult:
        """任一存续状态 → deleted（CT-012 单项回写）；已删除为空操作。"""
        now = _utcnow()
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            submission = self._must_find(aggregate, submission_id)
            result = aggregate.purge(submission, now=now)
            return self._result_from_row(session, submission, result)

    # ---- 查询（CT-002 只读视图，无写副作用） ----

    def query_by_uuid(self, submission_uuid: str) -> SubmissionView:
        with self._session_factory() as session:
            aggregate = SubmissionAggregate(session)
            submission = aggregate.find_by_uuid(submission_uuid)
            if submission is None:
                raise NotFoundError(f"unknown submission_uuid: {submission_uuid}")
            return SubmissionView(
                submission_id=submission.submission_id,
                status=submission.status,
                failure_reason=submission.failure_reason,
                missing_items=self._missing_items(session, submission.submission_id),
            )

    # ---- 内部 ----

    @staticmethod
    def _must_find(aggregate: SubmissionAggregate, submission_id: str) -> Submission:
        submission = aggregate.find_by_id(submission_id)
        if submission is None:
            raise NotFoundError(f"unknown submission_id: {submission_id}")
        return submission

    @staticmethod
    def _persist_manifest_and_report(
        session: Session,
        submission: Submission,
        entries,
        report: IntegrityReportData,
    ) -> list[SubmissionMaterial]:
        materials = [
            SubmissionMaterial(
                submission_id=submission.submission_id,
                material_ref=entry.material_ref,
                category=entry.category,
                size_bytes=entry.size_bytes,
                declared=entry.declared,
                filename=entry.filename,
            )
            for entry in entries
        ]
        session.add_all(materials)
        session.add(
            IntegrityReportRow(
                submission_id=submission.submission_id,
                expected_categories=list(report.expected_categories),
                received_categories=list(report.received_categories),
                missing_items=list(report.missing_items),
                report_version=report.report_version,
                generated_at=report.generated_at,
            )
        )
        session.flush()
        return materials

    def _missing_items(self, session: Session, submission_id: str) -> tuple[str, ...]:
        report = session.get(IntegrityReportRow, submission_id)
        if report is None:
            return ()
        return tuple(report.missing_items)

    def _result_from_row(
        self, session: Session, submission: Submission, result: TransitionResult
    ) -> CommandResult:
        return CommandResult(
            submission_id=submission.submission_id,
            status=submission.status,
            received_at=submission.received_at,
            missing_items=self._missing_items(session, submission.submission_id),
            failure_reason=submission.failure_reason,
            transition_result=result,
        )

    def _idempotent_result(self, session: Session, existing: Submission) -> CommandResult:
        """DUPLICATE_UUID：返回首次结果，不产生重复记录或重复事件。"""
        return CommandResult(
            submission_id=existing.submission_id,
            status=existing.status,
            received_at=existing.received_at,
            missing_items=self._missing_items(session, existing.submission_id),
            failure_reason=existing.failure_reason,
            transition_result=TransitionResult(
                existing.submission_id, "∅", existing.status, IDEMPOTENT_HIT,
                "duplicate submission_uuid",
            ),
        )
