"""SI-CORE-AGG：Submission 聚合根、状态机守卫与终态幂等（SIC-ST-01 语义 owner）。

聚合只计算迁移结果并改模型行，不做外部 IO；物理提交由 SI-CORE-TX 协调。
幂等语义（SIC-INV-01/06）：
- `submission_uuid` 唯一，重复创建命令解析为同一 Submission（idempotent_hit）；
- CT-005 终态回写按 submission_id+outcome 幂等，重复事件为空操作（duplicate_ignored）；
- CT-004 ack 重复确认、已删除记录重复清除均为空操作。
"""
from __future__ import annotations

import uuid as uuidlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from . import status as st
from .errors import IllegalTransitionError, ValidationError
from .models import Submission

#: CT-004 消费方确认语义（LCD-003）：仅 task_persisted 可推进 processing。
CONSUMER_ACK_TASK_PERSISTED = "task_persisted"

APPLIED = "applied"
IDEMPOTENT_HIT = "idempotent_hit"
DUPLICATE_IGNORED = "duplicate_ignored"


@dataclass(frozen=True)
class TransitionResult:
    """SIC-ST-04：一次命令的迁移结果（短生命周期返回值，不持久化）。"""

    submission_id: str
    from_state: str
    to_state: str
    outcome: str  # applied / idempotent_hit / duplicate_ignored
    detail: str = ""


def new_submission_id() -> str:
    return f"sub-{uuidlib.uuid4().hex}"


class SubmissionAggregate:
    """Submission 生命周期命令与守卫；绑定一次事务的 Session。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ---- 查询（只读，无写副作用） ----

    def find_by_uuid(self, submission_uuid: str) -> Submission | None:
        return (
            self._session.query(Submission)
            .filter(Submission.submission_uuid == submission_uuid)
            .one_or_none()
        )

    def find_by_id(self, submission_id: str) -> Submission | None:
        return self._session.get(Submission, submission_id)

    # ---- 创建（∅ → received / rejected / upload_failed） ----

    def create(
        self,
        *,
        submission_uuid: str,
        course_id: str | None,
        assignment: str | None,
        student_name: str | None,
        group_name: str | None,
        status: str,
        failure_reason: str | None,
        now: datetime,
    ) -> Submission:
        if status not in st.CREATION_STATUSES:
            raise IllegalTransitionError(f"illegal creation status: {status}")
        if self.find_by_uuid(submission_uuid) is not None:
            raise IllegalTransitionError(f"submission_uuid already exists: {submission_uuid}")
        submission = Submission(
            submission_id=new_submission_id(),
            submission_uuid=submission_uuid,
            course_id=course_id,
            assignment=assignment,
            student_name=student_name,
            group_name=group_name,
            status=status,
            failure_reason=failure_reason,
            version=0,
            received_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(submission)
        self._session.flush()
        return submission

    # ---- received → processing ----

    def advance_to_processing(
        self,
        submission: Submission,
        *,
        consumer_ack: str,
        expected_state: str | None,
        now: datetime,
    ) -> TransitionResult:
        if submission.status == st.PROCESSING:
            # 重复 task_persisted 确认为空操作（幂等），不受 expected_state 影响。
            return TransitionResult(
                submission.submission_id, st.PROCESSING, st.PROCESSING, DUPLICATE_IGNORED,
                "duplicate consumer_ack",
            )
        if consumer_ack != CONSUMER_ACK_TASK_PERSISTED:
            raise IllegalTransitionError(f"unexpected consumer_ack: {consumer_ack!r}")
        self._ensure_expected_state(submission, expected_state)
        st.ensure_transition(submission.status, st.PROCESSING)
        from_state = submission.status
        self._mutate(submission, status=st.PROCESSING, processing_at=now, now=now)
        return TransitionResult(submission.submission_id, from_state, st.PROCESSING, APPLIED)

    # ---- processing → scored / scoring_failed（CT-005） ----

    def apply_scoring_outcome(
        self,
        submission: Submission,
        *,
        outcome: str,
        expected_state: str | None,
        failure_reason: str | None,
        now: datetime,
    ) -> TransitionResult:
        if outcome not in st.SCORING_OUTCOMES:
            raise ValidationError(f"unknown outcome: {outcome!r}")
        if submission.status == outcome:
            # 按 submission_id+outcome 幂等：重复终态事件不改终态。
            return TransitionResult(
                submission.submission_id, outcome, outcome, DUPLICATE_IGNORED,
                "duplicate terminal outcome",
            )
        self._ensure_expected_state(submission, expected_state)
        st.ensure_transition(submission.status, outcome)
        if outcome == st.SCORING_FAILED:
            if not failure_reason:
                raise ValidationError("failure_reason is required for scoring_failed")
            self._mutate(
                submission, status=outcome, failure_reason=failure_reason,
                scoring_terminal_at=now, now=now,
            )
        else:
            self._mutate(
                submission, status=outcome, failure_reason=None,
                scoring_terminal_at=now, now=now,
            )
        return TransitionResult(submission.submission_id, st.PROCESSING, outcome, APPLIED)

    # ---- 任一存续状态 → deleted（CT-012 单项清除回写） ----

    def purge(self, submission: Submission, *, now: datetime) -> TransitionResult:
        if submission.status == st.DELETED:
            return TransitionResult(
                submission.submission_id, st.DELETED, st.DELETED, DUPLICATE_IGNORED,
                "already deleted",
            )
        st.ensure_transition(submission.status, st.DELETED)
        from_state = submission.status
        self._mutate(submission, status=st.DELETED, deleted_at=now, now=now)
        return TransitionResult(submission.submission_id, from_state, st.DELETED, APPLIED)

    # ---- 内部 ----

    @staticmethod
    def _ensure_expected_state(submission: Submission, expected_state: str | None) -> None:
        if expected_state is not None and submission.status != expected_state:
            raise IllegalTransitionError(
                f"expected_state={expected_state}, actual={submission.status}"
            )

    def _mutate(self, submission: Submission, *, now: datetime, **changes) -> None:
        for key, value in changes.items():
            setattr(submission, key, value)
        submission.version += 1
        submission.updated_at = now
        self._session.flush()
