"""CMP-MEMBERSHIP-VERIFIER：CT-003 归属校验（策略 P1–P5）。

- P3：每次调用经 CP-ROSTER-QUERY 直读当前已提交名单；无任何结论缓存。
- P4：每次产生结论的调用写入一条独立 VerificationRecord，与结论同一本地事务
  （记录写入失败 → ROSTER_UNAVAILABLE，不应答结论）；不可用调用不产生记录（R2）。
- P5：拒绝原因区分 INVALID_INVITE_CODE / ROSTER_ENTRY_NOT_FOUND。
- 内部故障映射 ROSTER_UNAVAILABLE，不向调用方暴露内部细节。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from course_app.course_roster import admin
from course_app.course_roster.errors import (
    REASON_INVALID_INVITE_CODE,
    REASON_ROSTER_ENTRY_NOT_FOUND,
    RosterStoreError,
    RosterUnavailableError,
)
from course_app.course_roster.models import VerificationRecord


@dataclass(frozen=True)
class VerificationOutcome:
    """值对象 VerificationOutcome：verified + reason?（通过时附 course_id）。"""

    verified: bool
    course_id: str  # 邀请码无效时为空串（契约必填字段，无课程可解析；见完成报告注记）
    reason: str | None


def verify_membership(
    session,
    *,
    invite_code: str,
    student_name: str,
    group_name: str,
    verified_at: datetime | None = None,
) -> VerificationOutcome:
    """CT-003：直读当前名单判定归属，并同事务写入独立校验记录。

    判定仅基于当前已提交名单（P2）；每次调用完整执行，不复用任何旧结论（P3）。
    名单存储故障 → RosterUnavailableError（不产生通过/拒绝记录，R2）。
    """
    try:
        result = admin.query_roster(
            session,
            invite_code=invite_code,
            student_name=student_name,
            group_name=group_name,
        )
    except RosterStoreError as exc:
        raise RosterUnavailableError("course roster unavailable") from exc

    record_course_id: str | None
    if result.course_id is None:
        outcome = VerificationOutcome(False, "", REASON_INVALID_INVITE_CODE)
        record_course_id = None
    elif not result.entry_found:
        outcome = VerificationOutcome(False, result.course_id, REASON_ROSTER_ENTRY_NOT_FOUND)
        record_course_id = result.course_id
    else:
        outcome = VerificationOutcome(True, result.course_id, None)
        record_course_id = result.course_id

    record = VerificationRecord(
        invite_code=invite_code,
        student_name=student_name,
        group_name=group_name,
        verified=outcome.verified,
        reason=outcome.reason,
        course_id=record_course_id,
        verified_at=verified_at or datetime.now(timezone.utc),
    )
    session.add(record)
    try:
        session.flush()
    except SQLAlchemyError as exc:
        raise RosterUnavailableError("course roster unavailable") from exc
    return outcome
