"""ResultPublisher：CT-005 scored / scoring_failed 的 SQL Outbox 发布端口。

载荷形状与 L03 orchestrator 的终态入队载荷一致（contracts/ct-005.json）：
- scored：{submission_id, outcome:"scored", original_grade,
  dimension_rationales, teacher_suggestions, scored_at(ISO), v:1}；
- scoring_failed：{submission_id, outcome:"scoring_failed", failure_reason,
  retry_record, v:1}（不写任何等级，INV-1）；
- dedup_key = f"{submission_id}:{outcome}"（IDM-2，与 L03 同一规则）。

事务边界归调用方：本类内部不 commit/rollback；enqueue 须发生在 L03 终态
事务（session.begin()）内。投递/确认方法（claim_due/confirm/retry）只是
SqlaOutboxStore 的转发，供投递器装配与断言使用。
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa

from tutor_shared.outbox import OUTBOX_RECORDS_TABLE, OutboxRecord, SqlaOutboxStore

from assessment_worker.scoring_orchestrator.orchestrator import (
    CT005_CONTRACT_ID,
    STATUS_SCORED,
    STATUS_SCORING_FAILED,
    validate_assessment_result,
)


def _iso(dt: datetime) -> str:
    """与 L03 orchestrator._iso 一致的序列化（naive 按 UTC 解释）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class ResultPublisher:
    """CT-005 发布端口；构造接收 L03 终态事务内的既有 Session。"""

    def __init__(self, session) -> None:
        self._session = session
        self._store = SqlaOutboxStore(session)

    # ---------------------------------------------------------------- publish

    def publish_scored(
        self,
        *,
        submission_id: str,
        original_grade: str,
        dimension_rationales: list,
        teacher_suggestions: list,
        scored_at: datetime,
    ) -> OutboxRecord:
        """enqueue CT-005 scored 载荷（形状同 L03 complete_assessment 入队载荷）。

        领域校验复用 L03 validate_assessment_result（INV-4）；校验失败抛
        InvalidAssessmentResult，不产生任何 Outbox 写入。
        """
        validate_assessment_result(
            original_grade, dimension_rationales, teacher_suggestions
        )
        payload = {
            "submission_id": submission_id,
            "outcome": STATUS_SCORED,
            "original_grade": original_grade,
            "dimension_rationales": list(dimension_rationales),
            "teacher_suggestions": list(teacher_suggestions),
            "scored_at": _iso(scored_at),
            "v": 1,
        }
        return self._store.enqueue(
            CT005_CONTRACT_ID, payload, dedup_key=self._dedup_key(submission_id, STATUS_SCORED)
        )

    def publish_scoring_failed(
        self,
        *,
        submission_id: str,
        failure_reason: str,
        retry_record: dict,
    ) -> OutboxRecord:
        """enqueue CT-005 scoring_failed 载荷（形状同 L03 失败终态入队载荷）。"""
        if not isinstance(failure_reason, str) or not failure_reason:
            raise ValueError("failure_reason must be a non-empty string")
        if (
            not isinstance(retry_record, dict)
            or not isinstance(retry_record.get("attempts"), int)
            or not isinstance(retry_record.get("last_error"), str)
            or not retry_record.get("last_error")
        ):
            raise ValueError(
                "retry_record must be a dict with int attempts and non-empty last_error"
            )
        payload = {
            "submission_id": submission_id,
            "outcome": STATUS_SCORING_FAILED,
            "failure_reason": failure_reason,
            "retry_record": dict(retry_record),
            "v": 1,
        }
        return self._store.enqueue(
            CT005_CONTRACT_ID,
            payload,
            dedup_key=self._dedup_key(submission_id, STATUS_SCORING_FAILED),
        )

    # --------------------------------------------------------------- delivery

    def claim_due(self, now: datetime, limit: int = 50) -> list[OutboxRecord]:
        """认领到期记录（delivering）；消费方确认前不推进为 confirmed。"""
        return self._store.fetch_due(now, limit=limit)

    def confirm(self, record_id: int) -> None:
        """消费方确认：delivering → confirmed（之后不再投递）。"""
        self._store.mark_confirmed(record_id)

    def retry(self, record_id: int, next_attempt_at: datetime | None = None) -> None:
        """投递失败：delivering → retry_wait（退避后重投）。"""
        self._store.mark_retry(record_id, next_attempt_at)

    def delivery_status(self, record_id: int) -> str | None:
        """投递状态查询（pending/delivering/retry_wait/confirmed）供断言。"""
        return self._session.execute(
            sa.select(OUTBOX_RECORDS_TABLE.c.status).where(
                OUTBOX_RECORDS_TABLE.c.id == record_id
            )
        ).scalar_one_or_none()

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _dedup_key(submission_id: str, outcome: str) -> str:
        """IDM-2：与 L03 orchestrator._dedup_key 同一规则。"""
        if not isinstance(submission_id, str) or not submission_id:
            raise ValueError("submission_id must be a non-empty string")
        return f"{submission_id}:{outcome}"
