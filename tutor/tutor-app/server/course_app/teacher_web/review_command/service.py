"""CMP-RC-REVIEW-IDEMPOTENCY-GUARD / INTEGRITY-POLICY / RECORD-WRITER 服务。

CT-008（教师批注/最终等级调整）与 M05-IC-01（PROJECTOR 幂等创建复核记录）
共用同一聚合不变量（LCD-002 单写方）：

- GUARD：CT-008 按 request_id、M05-IC-01 按 submission_id 查重；命中回放
  首次结果，不重复写入（LCD-003 两种键分层、同事务、不互相替代）；
- POLICY：annotation/final_grade 至少其一；final_grade 写入要求原始等级
  存在（NO_ORIGINAL_GRADE，禁伪造）；adjustment_reason 可选不强制
  （TD-09/DD-007/LCD-001）；目标不存在 → NOT_FOUND；
- WRITER：ReviewRecord + GradeAdjustmentRecord + 幂等记录同一本地事务；
  原始等级复制值只在 M05-IC-01 首次创建时写入，之后不可变；并发后写为准，
  每次成功变更追加唯一 adjustment_id，历史不覆盖；
- M05-IC-05 事件只在事务提交后由调用方发布（LCD-004）。
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from .errors import (
    NoOriginalGradeError,
    NotFoundError,
    ValidationFailedError,
)
from .models import (
    KEY_KIND_CT008_REQUEST,
    KEY_KIND_MIC01_SUBMISSION,
    MUTATION_ADJUSTED,
    MUTATION_ANNOTATED,
    MUTATION_ANNOTATED_ADJUSTED,
    STATUS_ADJUSTED,
    STATUS_ANNOTATED,
    STATUS_CREATED_ON_SCORED,
    GradeAdjustmentRecord,
    ReviewIdempotencyRecord,
    ReviewRecord,
)
from .ports import (
    EVENT_ANNOTATION_SAVED,
    EVENT_GRADE_ADJUSTED,
    ReviewEvent,
    SubmissionStatusPort,
)

SessionScopeFactory = Callable[[], AbstractContextManager[Session]]

#: final_grade / original_grade 值域（contracts/ct-008.json enum）。
GRADE_VALUES = frozenset({"A", "B", "C", "D", "E"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def review_record_payload(record: ReviewRecord) -> dict:
    """CT-008 review_record 应答（contracts/ct-008.json response）。"""
    return {
        "review_record_id": record.review_record_id,
        "submission_id": record.submission_id,
        "original_grade": record.original_grade,
        "final_grade": record.final_grade,
        "annotation": record.annotation,
        "operator": record.operator,
        "updated_at": _as_utc(record.updated_at).isoformat(),
    }


@dataclass(frozen=True)
class ReviewCommandOutcome:
    """CT-008 服务输出：应答载荷 + 提交后待发布事件 + 幂等命中标记。"""

    payload: dict
    events: tuple[ReviewEvent, ...] = field(default_factory=tuple)
    duplicate: bool = False


class ReviewCommandService:
    """复核写侧应用服务（GUARD+POLICY+WRITER；ST-REVIEW-RECORD 唯一写方）。"""

    def __init__(
        self,
        session_factory: SessionScopeFactory,
        *,
        submission_status: SubmissionStatusPort | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._submission_status = submission_status

    # ---- M05-IC-01：复核记录创建端口（供 READMODEL-PROJECTOR 幂等调用） ----

    def create_review_record(
        self,
        *,
        submission_id: str,
        original_grade: str,
        dimension_rationales: Sequence | None = None,
        scored_at: datetime | None = None,
    ) -> dict:
        """M05-IC-01：按 submission_id 幂等创建 ReviewRecord。

        重复 scored 事件返回既有记录，不覆盖原始等级、不追加调整记录；
        original_grade 缺失/非法 → VALIDATION_FAILED（不产生部分写入）。
        """
        if not submission_id:
            raise ValidationFailedError("submission_id is required")
        if original_grade not in GRADE_VALUES:
            raise ValidationFailedError("original_grade must be one of A-E")
        with self._session_factory() as session:
            existing = self._find_by_submission(session, submission_id)
            if existing is not None:
                return review_record_payload(existing)
            now = _utcnow()
            record = ReviewRecord(
                review_record_id=_new_id("rr"),
                submission_id=submission_id,
                original_grade=original_grade,
                dimension_rationales=list(dimension_rationales or []),
                scored_at=scored_at,
                final_grade=None,
                annotation=None,
                operator=None,
                status=STATUS_CREATED_ON_SCORED,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.flush()
            session.add(
                ReviewIdempotencyRecord(
                    request_key=submission_id,
                    key_kind=KEY_KIND_MIC01_SUBMISSION,
                    submission_id=submission_id,
                    review_record_id=record.review_record_id,
                    response_snapshot=review_record_payload(record),
                    created_at=now,
                )
            )
            return review_record_payload(record)

    # ---- CT-008：教师批注与最终等级调整 ----

    def apply_review(
        self,
        *,
        operator: str,
        submission_id: str,
        request_id: str,
        annotation: str | None = None,
        final_grade: str | None = None,
        adjustment_reason: str | None = None,
    ) -> ReviewCommandOutcome:
        """CT-008 命令：幂等守卫 → 完整性校验 → 同事务写入 + 留痕。"""
        if annotation is None and final_grade is None:
            raise ValidationFailedError(
                "annotation and final_grade: at least one is required"
            )
        if final_grade is not None and final_grade not in GRADE_VALUES:
            raise ValidationFailedError("final_grade must be one of A-E")
        if not operator:
            raise ValidationFailedError("operator is required")

        with self._session_factory() as session:
            hit = session.get(ReviewIdempotencyRecord, request_id)
            if hit is not None:
                if hit.key_kind != KEY_KIND_CT008_REQUEST or (
                    hit.submission_id != submission_id
                ):
                    # 同键不同目标不复用结果（父级校验语义）。
                    raise ValidationFailedError(
                        "request_id already used for a different mutation"
                    )
                return ReviewCommandOutcome(
                    payload=dict(hit.response_snapshot), duplicate=True
                )

            if self._submission_status is not None and (
                self._submission_status.get_submission_status(submission_id) is None
            ):
                raise NotFoundError(f"submission not found: {submission_id}")

            record = self._find_by_submission(session, submission_id)
            if final_grade is not None and (
                record is None or record.original_grade is None
            ):
                # scoring_failed / 无原始等级：拒绝设置最终等级（禁伪造）；
                # 批注路径不受影响，可继续保存。
                raise NoOriginalGradeError(
                    "cannot set final_grade without an original grade"
                )

            now = _utcnow()
            if record is None:
                record = ReviewRecord(
                    review_record_id=_new_id("rr"),
                    submission_id=submission_id,
                    original_grade=None,
                    dimension_rationales=None,
                    scored_at=None,
                    final_grade=None,
                    annotation=None,
                    operator=None,
                    status=STATUS_ANNOTATED,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                session.flush()

            final_before = record.final_grade
            if annotation is not None:
                record.annotation = annotation
            if final_grade is not None:
                record.final_grade = final_grade
            record.operator = operator
            record.updated_at = now
            if final_grade is not None:
                record.status = STATUS_ADJUSTED
            elif record.status != STATUS_ADJUSTED:
                record.status = STATUS_ANNOTATED

            if annotation is not None and final_grade is not None:
                mutation_kind = MUTATION_ANNOTATED_ADJUSTED
            elif final_grade is not None:
                mutation_kind = MUTATION_ADJUSTED
            else:
                mutation_kind = MUTATION_ANNOTATED
            adjustment_id = _new_id("adj")
            session.add(
                GradeAdjustmentRecord(
                    adjustment_id=adjustment_id,
                    review_record_id=record.review_record_id,
                    mutation_kind=mutation_kind,
                    final_grade_before=final_before,
                    final_grade_after=record.final_grade,
                    annotation_after=record.annotation,
                    adjustment_reason=adjustment_reason,  # 可选，不强制（DD-007）
                    operator=operator,
                    request_id=request_id,
                    created_at=now,
                )
            )

            payload = review_record_payload(record)
            session.add(
                ReviewIdempotencyRecord(
                    request_key=request_id,
                    key_kind=KEY_KIND_CT008_REQUEST,
                    submission_id=submission_id,
                    review_record_id=record.review_record_id,
                    response_snapshot=payload,
                    created_at=now,
                )
            )

            updated_iso = _as_utc(record.updated_at).isoformat()
            events: list[ReviewEvent] = []
            if annotation is not None:
                events.append(
                    ReviewEvent(
                        event_type=EVENT_ANNOTATION_SAVED,
                        submission_id=submission_id,
                        adjustment_id=adjustment_id,
                        operator=operator,
                        updated_at=updated_iso,
                        annotation_excerpt=annotation[:80],
                    )
                )
            if final_grade is not None:
                events.append(
                    ReviewEvent(
                        event_type=EVENT_GRADE_ADJUSTED,
                        submission_id=submission_id,
                        adjustment_id=adjustment_id,
                        operator=operator,
                        updated_at=updated_iso,
                        final_grade=final_grade,
                    )
                )
            return ReviewCommandOutcome(payload=payload, events=tuple(events))

    # ---- 内部 ----

    @staticmethod
    def _find_by_submission(
        session: Session, submission_id: str
    ) -> ReviewRecord | None:
        return (
            session.query(ReviewRecord)
            .filter(ReviewRecord.submission_id == submission_id)
            .one_or_none()
        )
