"""ICT-009（CCR-001 方案 A）：MOD-04 评分清除执行器 + CT-004 重放守卫验收。

覆盖：清除评分内容+任务并写墓碑、CT-015 载荷/幂等键、重复 CT-012 幂等空操作、
重放旧 CT-004 不重建任务、契约校验失败可观测。
"""
from __future__ import annotations

import sys
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.models import (  # noqa: E402
    AssessmentPurgeTombstone,
    OrchestratorBase,
    ScoringResult,
    ScoringTask,
)
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from assessment_worker.scoring_orchestrator.purge import (  # noqa: E402
    AssessmentPurgeExecutor,
    Ct012ValidationError,
)

NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)


def ct004(submission_id: str) -> dict:
    return {
        "submission_id": submission_id,
        "course_id": "c-1",
        "assignment": "hw",
        "student_name": "张三",
        "group_name": "第1组",
        "material_refs": [],
        "missing_items": [],
        "received_at": "2026-07-23T11:00:00+00:00",
        "v": 1,
    }


def ct012(batch_id: str, ids: tuple[str, ...]) -> dict:
    return {
        "batch_id": batch_id,
        "submission_ids": list(ids),
        "scope": "course",
        "operator": "teacher-x",
        "executed_at": NOW.isoformat(),
        "audit_record_id": "audit-1",
        "v": 1,
    }


class AssessmentPurgeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        OrchestratorBase.metadata.create_all(self.engine)
        sm = sessionmaker(bind=self.engine, expire_on_commit=False)

        @contextmanager
        def scope():
            session = sm()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        self.scope = scope
        self.outbox = InMemoryOutboxStore()
        self.orchestrator = ScoringOrchestrator(sm, SqlaTaskLeaseStore(sm), self.outbox)
        self.executor = AssessmentPurgeExecutor(scope, self.outbox, clock=lambda: NOW)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _score(self, submission_id: str) -> None:
        ingress = self.orchestrator.handle_submission_received(ct004(submission_id))
        claimed = self.orchestrator.claim_task(owner="w1")
        self.orchestrator.complete_assessment(
            claimed.task_id,
            owner="w1",
            attempt_no=claimed.attempt_no,
            original_grade="B",
            dimension_rationales=[
                {"dimension": d, "rationale": f"{d} rationale"}
                for d in (
                    "需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性"
                )
            ],
            teacher_suggestions=["s"],
        )
        self.assertTrue(ingress.created)

    def _rows(self, model, submission_id: str) -> list:
        with self.scope() as s:
            return list(s.scalars(sa.select(model).where(model.submission_id == submission_id)))

    def test_purge_deletes_results_tasks_writes_tombstone_and_ct015(self) -> None:
        self._score("sub-1")
        self.assertEqual(len(self._rows(ScoringResult, "sub-1")), 1)
        report = self.executor.execute(ct012("batch-1", ("sub-1",)))
        self.assertEqual(report.purged_submission_ids, ("sub-1",))
        self.assertEqual(report.failed_items, ())
        self.assertEqual(self._rows(ScoringResult, "sub-1"), [])
        self.assertEqual(self._rows(ScoringTask, "sub-1"), [])
        tombs = self._rows(AssessmentPurgeTombstone, "sub-1")
        self.assertEqual(len(tombs), 1)
        self.assertEqual(tombs[0].batch_id, "batch-1")
        # CT-015 载荷与冻结契约一致（additionalProperties=false）
        payload = report.ct015_payload
        self.assertEqual(
            set(payload),
            {"batch_id", "purged_submission_ids", "failed_items", "purged_at", "v"},
        )
        self.assertEqual(payload["v"], 1)
        record = self.outbox._records[report.outbox_record_id]
        self.assertEqual(record.contract_id, "CT-015")
        self.assertEqual(record.dedup_key, f"batch-1:{NOW.isoformat()}")

    def test_repeat_ct012_idempotent(self) -> None:
        self._score("sub-1")
        self.executor.execute(ct012("batch-1", ("sub-1",)))
        again = self.executor.execute(ct012("batch-1", ("sub-1",)))
        self.assertEqual(again.purged_submission_ids, ("sub-1",))  # 空操作仍计 purged
        self.assertEqual(again.failed_items, ())
        self.assertEqual(len(self._rows(AssessmentPurgeTombstone, "sub-1")), 1)

    def test_replay_guard_blocks_ct004_rebuild(self) -> None:
        self._score("sub-1")
        self.executor.execute(ct012("batch-1", ("sub-1",)))
        ingress = self.orchestrator.handle_submission_received(ct004("sub-1"))
        self.assertFalse(ingress.created)
        self.assertTrue(ingress.tombstoned)
        self.assertEqual(self._rows(ScoringTask, "sub-1"), [])  # 不重建任务

    def test_unknown_submission_counts_as_purged(self) -> None:
        # 契约幂等语义：清除不存在的记录为空操作（已删除态）
        report = self.executor.execute(ct012("batch-1", ("sub-x",)))
        self.assertEqual(report.purged_submission_ids, ("sub-x",))
        self.assertEqual(report.failed_items, ())

    def test_invalid_payload_rejected(self) -> None:
        with self.assertRaises(Ct012ValidationError):
            self.executor.execute({"batch_id": "b", "v": 1})
        with self.assertRaises(Ct012ValidationError):
            self.executor.execute(ct012("b", ("sub-1",)) | {"extra": 1})
        with self.assertRaises(Ct012ValidationError):
            self.executor.execute(ct012("b", ("sub-1",)) | {"v": 2})


if __name__ == "__main__":
    unittest.main()
