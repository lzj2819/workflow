"""T-B02a RESULT-PUBLISHER 单元测试（SQLite）。

覆盖任务卡语义断言：
- CT-005 scored/scoring_failed 载荷形状与 L03 orchestrator 既有入队载荷完全一致
  （同一事件经两条路径产生，逐字段相等；dedup_key 规则一致）；
- 同事务语义（KD-002）：publish 于调用方 session 内，commit 前对其他连接不可见，
  rollback 全消；ResultPublisher 内部不 commit/rollback；
- 投递确认语义（同 T-B01b）：pending → claim_due 认领 delivering（确认前不推进
  confirmed，认领期间不被重复认领）→ confirm 后 confirmed 且不再投递；
  retry 进 retry_wait，到期前不可见、到期后重投；
- scored_at 序列化与 L03 _iso 一致（naive 按 UTC）。

仅 SQLite 本地库；无网络、无外部服务。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from tutor_shared.outbox import (  # noqa: E402
    OUTBOX_METADATA,
    OUTBOX_RECORDS_TABLE,
    InMemoryOutboxStore,
    OutboxStore,
)

from assessment_worker.result_publisher import ResultPublisher  # noqa: E402
from assessment_worker.scoring_orchestrator import (  # noqa: E402
    CT005_CONTRACT_ID,
    DIMENSIONS,
    InvalidAssessmentResult,
    OrchestratorBase,
    ScoringOrchestrator,
    SqlaTaskLeaseStore,
)

T0 = datetime(2026, 7, 20, 1, 0, 0)  # naive UTC（与 L03 时间戳约定一致）
SCORED_AT = datetime(2026, 7, 20, 1, 5, 0)
# enqueue 以真实时钟写 next_attempt_at；取运行时 +1h 保证 due 语义稳定
NOW = datetime.now(timezone.utc) + timedelta(hours=1)


class CapturingOutboxStore(OutboxStore):
    """记录 enqueue 参数并转发内存实现（比对 L03 入队载荷用）。"""

    def __init__(self) -> None:
        self._inner = InMemoryOutboxStore()
        self.enqueued: list[tuple[str, dict, str]] = []

    def enqueue(self, contract_id, payload, dedup_key):
        self.enqueued.append((contract_id, payload, dedup_key))
        return self._inner.enqueue(contract_id, payload, dedup_key)

    def fetch_due(self, now, limit=50):
        return self._inner.fetch_due(now, limit)

    def mark_confirmed(self, record_id):
        self._inner.mark_confirmed(record_id)

    def mark_retry(self, record_id, next_attempt_at=None):
        self._inner.mark_retry(record_id, next_attempt_at)


def ct004_event(submission_id: str = "sub-1") -> dict:
    return {
        "submission_id": submission_id,
        "course_id": "course-1",
        "assignment": "实现命令行待办管理器",
        "student_name": "张三",
        "group_name": "G1",
        "material_refs": [
            {"category": "代码", "ref": "materials/sub-1/main.py", "filename": "main.py"},
            {"category": "对话", "ref": "materials/sub-1/dialogue.md"},
        ],
        "missing_items": [],
        "received_at": "2026-07-20T00:59:00+00:00",
        "v": 1,
    }


def valid_result() -> dict:
    return {
        "original_grade": "B",
        "dimension_rationales": [
            {"dimension": d, "rationale": f"{d}的文字依据"} for d in DIMENSIONS
        ],
        "teacher_suggestions": ["建议补充需求澄清轮次"],
        "missing_materials_impact": None,
        "prompt_version": "p1",
        "rubric_version": "r1",
        "model_meta": {"request_id": "req-1", "duration_ms": 1234},
    }


class PublisherTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = sa.create_engine(f"sqlite:///{Path(self._tmp.name) / 't.db'}")
        OUTBOX_METADATA.create_all(self.engine)
        OrchestratorBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmp.cleanup()

    def _count_outbox(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count()).select_from(OUTBOX_RECORDS_TABLE)
            ).scalar_one()

    def _publish_scored(self, submission_id: str = "sub-1"):
        """以独立事务发布一条 scored（模拟 L03 终态事务提交后）。"""
        with self.Session() as session:
            publisher = ResultPublisher(session)
            record = publisher.publish_scored(
                submission_id=submission_id,
                original_grade="B",
                dimension_rationales=[
                    {"dimension": d, "rationale": f"{d}的文字依据"} for d in DIMENSIONS
                ],
                teacher_suggestions=["建议补充需求澄清轮次"],
                scored_at=SCORED_AT,
            )
            session.commit()
        return record


# ------------------------------------------------------------ 同事务语义（KD-002）


class TransactionSemanticsTests(PublisherTestBase):
    def test_enqueue_invisible_until_caller_commits(self):
        session = self.Session()
        try:
            publisher = ResultPublisher(session)
            record = publisher.publish_scored(
                submission_id="sub-1",
                original_grade="B",
                dimension_rationales=[
                    {"dimension": d, "rationale": "r"} for d in DIMENSIONS
                ],
                teacher_suggestions=["s"],
                scored_at=SCORED_AT,
            )
            # commit 前：其他连接不可见（事务边界归调用方）
            self.assertEqual(self._count_outbox(), 0)
            self.assertEqual(publisher.delivery_status(record.record_id), "pending")
            session.commit()
            self.assertEqual(self._count_outbox(), 1)
        finally:
            session.close()

    def test_rollback_discards_enqueue(self):
        session = self.Session()
        try:
            publisher = ResultPublisher(session)
            publisher.publish_scored(
                submission_id="sub-1",
                original_grade="B",
                dimension_rationales=[
                    {"dimension": d, "rationale": "r"} for d in DIMENSIONS
                ],
                teacher_suggestions=["s"],
                scored_at=SCORED_AT,
            )
            session.rollback()
            self.assertEqual(self._count_outbox(), 0)
        finally:
            session.close()


# -------------------------------------------------- CT-005 载荷形状与 L03 一致


class PayloadShapeTests(PublisherTestBase):
    def _orchestrator(self, outbox: OutboxStore) -> ScoringOrchestrator:
        return ScoringOrchestrator(
            self.Session, SqlaTaskLeaseStore(self.Session), outbox
        )

    def test_scored_payload_matches_l03(self):
        capture = CapturingOutboxStore()
        orchestrator = self._orchestrator(capture)
        orchestrator.handle_submission_received(ct004_event("sub-1"))
        claimed = orchestrator.claim_task("worker-1", now=T0)
        orchestrator.complete_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=claimed.attempt_no,
            scored_at=SCORED_AT,
            now=claimed.lease_expires_at - timedelta(seconds=1),
            **valid_result(),
        )
        self.assertEqual(len(capture.enqueued), 1)
        contract_id, l03_payload, l03_dedup = capture.enqueued[0]

        with self.Session() as session:
            publisher = ResultPublisher(session)
            record = publisher.publish_scored(
                submission_id="sub-1",
                original_grade="B",
                dimension_rationales=[
                    {"dimension": d, "rationale": f"{d}的文字依据"} for d in DIMENSIONS
                ],
                teacher_suggestions=["建议补充需求澄清轮次"],
                scored_at=SCORED_AT,
            )
            session.commit()

        self.assertEqual(contract_id, CT005_CONTRACT_ID)
        self.assertEqual(record.contract_id, contract_id)
        self.assertEqual(record.payload, l03_payload)
        self.assertEqual(record.dedup_key, l03_dedup)
        self.assertEqual(record.dedup_key, "sub-1:scored")
        self.assertEqual(record.payload["scored_at"], "2026-07-20T01:05:00+00:00")

    def test_scoring_failed_payload_matches_l03(self):
        capture = CapturingOutboxStore()
        orchestrator = self._orchestrator(capture)
        orchestrator.handle_submission_received(ct004_event("sub-1"))
        claimed = orchestrator.claim_task("worker-1", now=T0)
        orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=1,
            error_kind="MODEL_TIMEOUT",
            now=claimed.lease_expires_at - timedelta(seconds=2),
        )
        orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=2,
            error_kind="MODEL_ERROR",
            now=claimed.lease_expires_at - timedelta(seconds=1),
        )
        self.assertEqual(len(capture.enqueued), 1)
        contract_id, l03_payload, l03_dedup = capture.enqueued[0]

        with self.Session() as session:
            publisher = ResultPublisher(session)
            record = publisher.publish_scoring_failed(
                submission_id="sub-1",
                failure_reason=l03_payload["failure_reason"],
                retry_record=l03_payload["retry_record"],
            )
            session.commit()

        self.assertEqual(record.contract_id, contract_id)
        self.assertEqual(record.payload, l03_payload)
        self.assertEqual(record.dedup_key, l03_dedup)
        self.assertEqual(record.dedup_key, "sub-1:scoring_failed")
        # scoring_failed 载荷不写任何等级（INV-1）
        self.assertNotIn("original_grade", record.payload)
        self.assertEqual(record.payload["outcome"], "scoring_failed")
        self.assertEqual(record.payload["v"], 1)

    def test_scored_payload_domain_validation_reused(self):
        with self.Session() as session:
            publisher = ResultPublisher(session)
            with self.assertRaises(InvalidAssessmentResult) as ctx:
                publisher.publish_scored(
                    submission_id="sub-1",
                    original_grade="Z",  # 非法等级：INV-4 领域校验拒绝
                    dimension_rationales=[
                        {"dimension": d, "rationale": "r"} for d in DIMENSIONS
                    ],
                    teacher_suggestions=["s"],
                    scored_at=SCORED_AT,
                )
            session.rollback()
        self.assertIn("INVALID_RESPONSE_SCHEMA", str(ctx.exception))
        self.assertEqual(self._count_outbox(), 0)


# ---------------------------------------------------------- 投递确认语义（T-B01b）


class DeliverySemanticsTests(PublisherTestBase):
    def test_pending_claim_confirm_flow(self):
        record = self._publish_scored()
        with self.Session() as session:
            publisher = ResultPublisher(session)
            self.assertEqual(publisher.delivery_status(record.record_id), "pending")

            claimed = publisher.claim_due(NOW)
            self.assertEqual([r.record_id for r in claimed], [record.record_id])
            self.assertEqual(claimed[0].status, "delivering")
            self.assertEqual(claimed[0].attempts, 1)
            self.assertEqual(claimed[0].contract_id, CT005_CONTRACT_ID)
            self.assertEqual(claimed[0].dedup_key, "sub-1:scored")
            # 消费方确认前不推进 confirmed（仍为 delivering）
            self.assertEqual(publisher.delivery_status(record.record_id), "delivering")
            # 认领期间不被重复认领
            self.assertEqual(publisher.claim_due(NOW), [])

            publisher.confirm(record.record_id)
            session.commit()
            self.assertEqual(publisher.delivery_status(record.record_id), "confirmed")
            # 确认后不再投递
            self.assertEqual(publisher.claim_due(NOW), [])

    def test_retry_wait_redelivers_after_backoff(self):
        record = self._publish_scored()
        retry_at = NOW + timedelta(seconds=30)
        with self.Session() as session:
            publisher = ResultPublisher(session)
            claimed = publisher.claim_due(NOW)
            publisher.retry(claimed[0].record_id, next_attempt_at=retry_at)
            session.commit()
            self.assertEqual(
                publisher.delivery_status(record.record_id), "retry_wait"
            )
            # 到期前不可见
            self.assertEqual(publisher.claim_due(NOW + timedelta(seconds=29)), [])
            # 到期后重投（attempts 递增）
            redelivered = publisher.claim_due(NOW + timedelta(seconds=31))
            self.assertEqual([r.record_id for r in redelivered], [record.record_id])
            self.assertEqual(redelivered[0].attempts, 2)

    def test_payload_roundtrip_through_sql_outbox(self):
        self._publish_scored()
        with self.Session() as session:
            publisher = ResultPublisher(session)
            claimed = publisher.claim_due(NOW)
            payload = claimed[0].payload
            self.assertEqual(payload["submission_id"], "sub-1")
            self.assertEqual(payload["outcome"], "scored")
            self.assertEqual(payload["original_grade"], "B")
            self.assertEqual(len(payload["dimension_rationales"]), 5)
            self.assertEqual(
                payload["teacher_suggestions"], ["建议补充需求澄清轮次"]
            )
            self.assertEqual(payload["scored_at"], "2026-07-20T01:05:00+00:00")
            self.assertEqual(payload["v"], 1)

    def test_delivery_status_unknown_record(self):
        with self.Session() as session:
            publisher = ResultPublisher(session)
            self.assertIsNone(publisher.delivery_status(999999))


if __name__ == "__main__":
    unittest.main()
