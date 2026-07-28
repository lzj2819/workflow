"""L03 CMP-SCORING-ORCHESTRATOR 测试。

覆盖 verification-checklist 语义断言：CT-004 消费幂等与持久化后确认、状态机守卫、
REQ-012 重试一次、认领互斥与崩溃重认领上限、ICT-005/ICT-006 终态事务与 CT-005 载荷、
迁移文件可导入且 revision 链正确。单测数据库 SQLite（sqlite:///:memory:）。
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import InMemoryOutboxStore, OutboxStore  # noqa: E402

from assessment_worker.scoring_orchestrator import (  # noqa: E402
    CRASH_LOOP_FAILURE_REASON,
    DIMENSIONS,
    DUPLICATE_TERMINAL_CALLBACK,
    STALE_TERMINAL_CALLBACK,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_SCORED,
    STATUS_SCORING_FAILED,
    InvalidAssessmentFailure,
    InvalidAssessmentResult,
    OrchestratorBase,
    RetryEntered,
    ScoringOrchestrator,
    ScoringResult,
    ScoringTask,
    SqlaTaskLeaseStore,
    TerminalCallbackRejected,
)

T0 = datetime(2026, 7, 20, 1, 0, 0, tzinfo=timezone.utc)


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
        "missing_items": ["截图"],
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
        "missing_materials_impact": "缺少截图，最终功能维度仅依据代码与结果描述",
        "prompt_version": "p1",
        "rubric_version": "r1",
        "model_meta": {"request_id": "req-1", "duration_ms": 1234, "attempts_used": 1},
    }


class FailingOutboxStore(OutboxStore):
    """enqueue 即失败，用于证明终态事务原子性（INV-3）。"""

    def enqueue(self, contract_id, payload, dedup_key):
        raise RuntimeError("outbox unavailable")

    def fetch_due(self, now, limit=50):
        return []

    def mark_confirmed(self, record_id):
        pass

    def mark_retry(self, record_id, next_attempt_at=None):
        pass


class OrchestratorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        OrchestratorBase.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.lease_store = SqlaTaskLeaseStore(self.session_factory)
        self.outbox = InMemoryOutboxStore()
        self.orchestrator = ScoringOrchestrator(
            self.session_factory, self.lease_store, self.outbox
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    # ---------------------------------------------------------------- helpers

    def ingest(self, submission_id: str = "sub-1"):
        return self.orchestrator.handle_submission_received(ct004_event(submission_id))

    def get_task(self, submission_id: str = "sub-1") -> ScoringTask:
        with self.session_factory() as session:
            return session.scalar(
                sa.select(ScoringTask).where(ScoringTask.submission_id == submission_id)
            )

    def get_result(self, task_id: str) -> ScoringResult | None:
        with self.session_factory() as session:
            return session.get(ScoringResult, task_id)

    def outbox_records(self) -> list:
        return self.outbox.fetch_due(datetime.max.replace(tzinfo=timezone.utc))

    def claim(self, owner: str = "worker-1", at: datetime = T0):
        return self.orchestrator.claim_task(owner, now=at)

    def complete(self, claimed, **overrides):
        kwargs = dict(valid_result(), **overrides)
        return self.orchestrator.complete_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=claimed.attempt_no,
            now=claimed.lease_expires_at - timedelta(seconds=1),
            **kwargs,
        )

    # ------------------------------------------------------------- CT-004 幂等

    def test_ct004_persists_task_before_ack(self):
        result = self.ingest()
        self.assertTrue(result.created)
        task = self.get_task()
        self.assertEqual(task.status, STATUS_PENDING)
        self.assertEqual(task.attempts, 0)
        self.assertEqual(task.reclaim_count, 0)
        self.assertIsNone(task.started_at)
        self.assertIsNone(task.finished_at)
        # LCD-004：deadline_at = created_at + 10min（仅跟踪，不强杀）
        self.assertEqual(
            task.deadline_at, task.created_at + timedelta(seconds=600)
        )
        self.assertEqual(task.course_id, "course-1")
        self.assertEqual(len(task.material_refs), 2)
        self.assertEqual(task.missing_items, ["截图"])

    def test_ct004_duplicate_event_is_idempotent(self):
        first = self.ingest()
        second = self.ingest()
        self.assertTrue(first.created)
        self.assertFalse(second.created)  # 幂等 no-op，事件照常确认
        self.assertEqual(first.task_id, second.task_id)
        with self.session_factory() as session:
            count = session.scalar(sa.select(sa.func.count(ScoringTask.task_id)))
        self.assertEqual(count, 1)  # 重复事件不产生重复任务（INV-5）

    def test_ct004_missing_field_rejected_before_ack(self):
        event = ct004_event()
        del event["submission_id"]
        with self.assertRaises(ValueError):
            self.orchestrator.handle_submission_received(event)

    # ------------------------------------------------------------- ICT-001 认领

    def test_claim_transitions_pending_to_in_progress(self):
        self.ingest()
        claimed = self.claim()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.attempt_no, 1)
        self.assertEqual(claimed.submission_id, "sub-1")
        self.assertEqual(claimed.assignment, "实现命令行待办管理器")
        task = self.get_task()
        self.assertEqual(task.status, STATUS_IN_PROGRESS)
        self.assertEqual(task.attempts, 1)
        self.assertEqual(task.lease_owner, "worker-1")
        self.assertEqual(task.lease_expires_at, T0.replace(tzinfo=None) + timedelta(seconds=120))
        self.assertIsNotNone(task.started_at)

    def test_claim_returns_none_when_no_task(self):
        self.assertIsNone(self.claim())

    def test_claim_mutual_exclusion_while_lease_active(self):
        self.ingest()
        first = self.claim(owner="worker-1", at=T0)
        self.assertIsNotNone(first)
        # 租约未过期：另一 worker 不可认领（CON-1）
        self.assertIsNone(
            self.claim(owner="worker-2", at=T0 + timedelta(seconds=60))
        )
        task = self.get_task()
        self.assertEqual(task.lease_owner, "worker-1")
        self.assertEqual(task.reclaim_count, 0)

    def test_reclaim_after_lease_expiry_preserves_attempt(self):
        self.ingest()
        first = self.claim(owner="worker-1", at=T0)
        expired_at = first.lease_expires_at + timedelta(seconds=1)
        # 崩溃后租约到期：同一 attempt 重跑，attempts 不增，reclaim_count+1（LCD-002）
        second = self.claim(owner="worker-2", at=expired_at)
        self.assertIsNotNone(second)
        self.assertEqual(second.attempt_no, 1)
        self.assertEqual(second.lease_owner, "worker-2")
        task = self.get_task()
        self.assertEqual(task.attempts, 1)
        self.assertEqual(task.reclaim_count, 1)

    def test_reclaim_cap_terminalizes_crash_loop(self):
        self.ingest()
        at = T0
        for owner in ("w1", "w2", "w3", "w4"):
            claimed = self.claim(owner=owner, at=at)
            self.assertIsNotNone(claimed)
            at = claimed.lease_expires_at + timedelta(seconds=1)
        # 第 4 次认领后 reclaim_count=3；再认领触发崩溃循环终态化（LCD-002）
        self.assertIsNone(self.claim(owner="w5", at=at))
        task = self.get_task()
        self.assertEqual(task.status, STATUS_SCORING_FAILED)
        self.assertEqual(task.failure_reason, CRASH_LOOP_FAILURE_REASON)
        self.assertIsNotNone(task.finished_at)
        self.assertIsNone(self.get_result(task.task_id))  # 不写任何等级
        records = self.outbox_records()
        self.assertEqual(len(records), 1)
        payload = records[0].payload
        self.assertEqual(records[0].contract_id, "CT-005")
        self.assertEqual(records[0].dedup_key, "sub-1:scoring_failed")
        self.assertEqual(payload["outcome"], "scoring_failed")
        self.assertEqual(payload["failure_reason"], CRASH_LOOP_FAILURE_REASON)
        self.assertEqual(payload["retry_record"]["attempts"], 1)
        self.assertEqual(payload["v"], 1)
        # 终态任务永不被重认领（CON-2）
        self.assertIsNone(self.claim(owner="w6", at=at + timedelta(days=1)))

    # ------------------------------------------------------------- ICT-005 完成

    def test_complete_assessment_commits_scored_transaction(self):
        self.ingest()
        claimed = self.claim()
        committed = self.complete(claimed)
        self.assertEqual(committed.outcome, STATUS_SCORED)
        self.assertEqual(committed.attempts, 1)
        task = self.get_task()
        self.assertEqual(task.status, STATUS_SCORED)
        self.assertIsNotNone(task.finished_at)
        result = self.get_result(claimed.task_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.original_grade, "B")
        self.assertEqual(len(result.dimension_rationales), 5)
        self.assertEqual(result.prompt_version, "p1")
        self.assertEqual(result.rubric_version, "r1")
        records = self.outbox_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.contract_id, "CT-005")
        self.assertEqual(record.dedup_key, "sub-1:scored")  # IDM-2
        payload = record.payload
        self.assertEqual(
            set(payload),
            {
                "submission_id",
                "outcome",
                "original_grade",
                "dimension_rationales",
                "teacher_suggestions",
                "scored_at",
                "v",
            },
        )
        self.assertEqual(payload["submission_id"], "sub-1")
        self.assertEqual(payload["outcome"], "scored")
        self.assertEqual(payload["original_grade"], "B")
        self.assertEqual(len(payload["dimension_rationales"]), 5)
        self.assertEqual(payload["teacher_suggestions"], ["建议补充需求澄清轮次"])
        self.assertTrue(payload["scored_at"])
        self.assertEqual(payload["v"], 1)

    def test_complete_after_single_retry_returns_to_main_flow(self):
        self.ingest()
        claimed = self.claim()
        self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=1,
            error_kind="MODEL_TIMEOUT",
            now=T0 + timedelta(seconds=10),
        )
        committed = self.orchestrator.complete_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=2,
            now=T0 + timedelta(seconds=20),
            **valid_result(),
        )
        self.assertEqual(committed.outcome, STATUS_SCORED)
        self.assertEqual(committed.attempts, 2)
        self.assertEqual(self.get_task().status, STATUS_SCORED)

    def test_complete_rejects_invalid_grade(self):
        self.ingest()
        claimed = self.claim()
        with self.assertRaises(InvalidAssessmentResult):
            self.complete(claimed, original_grade="F")
        self.assertEqual(self.get_task().status, STATUS_IN_PROGRESS)
        self.assertEqual(self.outbox_records(), [])

    def test_complete_rejects_incomplete_dimensions(self):
        self.ingest()
        claimed = self.claim()
        bad = valid_result()
        bad["dimension_rationales"] = bad["dimension_rationales"][:4]
        with self.assertRaises(InvalidAssessmentResult):
            self.complete(claimed, **bad)
        duplicated = valid_result()
        duplicated["dimension_rationales"][4] = {
            "dimension": DIMENSIONS[0],
            "rationale": "重复维度",
        }
        with self.assertRaises(InvalidAssessmentResult):
            self.complete(claimed, **duplicated)

    def test_stale_and_duplicate_terminal_callbacks_rejected(self):
        self.ingest()
        claimed = self.claim()
        self.complete(claimed)
        # 重复终态回调：拒绝且不改变终态（终态不可逆）
        with self.assertRaises(TerminalCallbackRejected) as ctx:
            self.complete(claimed)
        self.assertEqual(ctx.exception.reason, DUPLICATE_TERMINAL_CALLBACK)
        # 错误 attempt / 错误 owner / 未知任务：过期回调拒绝
        self.ingest("sub-2")
        claimed2 = self.claim(owner="worker-9", at=T0)
        with self.assertRaises(TerminalCallbackRejected) as ctx2:
            self.orchestrator.complete_assessment(
                claimed2.task_id,
                owner=claimed2.lease_owner,
                attempt_no=2,
                now=T0,
                **valid_result(),
            )
        self.assertEqual(ctx2.exception.reason, STALE_TERMINAL_CALLBACK)
        with self.assertRaises(TerminalCallbackRejected):
            self.orchestrator.complete_assessment(
                claimed2.task_id,
                owner="someone-else",
                attempt_no=1,
                now=T0,
                **valid_result(),
            )
        with self.assertRaises(TerminalCallbackRejected):
            self.orchestrator.complete_assessment(
                "no-such-task",
                owner="worker-9",
                attempt_no=1,
                now=T0,
                **valid_result(),
            )
        self.assertEqual(len(self.outbox_records()), 1)  # 只有第一次终态事件

    def test_terminal_commit_requires_active_lease(self):
        self.ingest()
        claimed = self.claim(owner="worker-1", at=T0)
        expired = claimed.lease_expires_at + timedelta(seconds=1)
        with self.assertRaises(TerminalCallbackRejected):
            self.orchestrator.complete_assessment(
                claimed.task_id,
                owner="worker-1",
                attempt_no=1,
                now=expired,
                **valid_result(),
            )
        self.assertEqual(self.get_task().status, STATUS_IN_PROGRESS)
        self.assertEqual(self.outbox_records(), [])

    def test_terminal_transaction_rolls_back_when_outbox_fails(self):
        orchestrator = ScoringOrchestrator(
            self.session_factory, self.lease_store, FailingOutboxStore()
        )
        orchestrator.handle_submission_received(ct004_event())
        claimed = orchestrator.claim_task("worker-1", now=T0)
        with self.assertRaises(RuntimeError):
            orchestrator.complete_assessment(
                claimed.task_id,
                owner="worker-1",
                attempt_no=1,
                now=T0 + timedelta(seconds=1),
                **valid_result(),
            )
        # INV-3：业务写入与 Outbox 入队同一事务，整体回滚
        self.assertEqual(self.get_task().status, STATUS_IN_PROGRESS)
        self.assertIsNone(self.get_result(claimed.task_id))

    # ------------------------------------------------------------- ICT-006 失败

    def test_first_failure_enters_single_retry_without_terminal(self):
        self.ingest()
        claimed = self.claim()
        entered = self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=1,
            error_kind="MODEL_TIMEOUT",
            now=T0 + timedelta(seconds=5),
        )
        self.assertIsInstance(entered, RetryEntered)
        self.assertEqual(entered.next_attempt_no, 2)
        task = self.get_task()
        self.assertEqual(task.status, STATUS_IN_PROGRESS)  # 不终态
        self.assertEqual(task.attempts, 2)
        self.assertEqual(
            task.retry_record["first_failure"]["error_kind"], "MODEL_TIMEOUT"
        )
        self.assertEqual(self.outbox_records(), [])  # 重试不产生终态事件

    def test_second_failure_commits_scoring_failed_transaction(self):
        self.ingest()
        claimed = self.claim()
        self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=1,
            error_kind="MODEL_TIMEOUT",
            now=T0 + timedelta(seconds=5),
        )
        committed = self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=2,
            error_kind="MODEL_ERROR",
            now=T0 + timedelta(seconds=30),
        )
        self.assertEqual(committed.outcome, STATUS_SCORING_FAILED)
        self.assertEqual(committed.attempts, 2)
        task = self.get_task()
        self.assertEqual(task.status, STATUS_SCORING_FAILED)
        self.assertEqual(task.failure_reason, "MODEL_ERROR")
        self.assertEqual(task.attempts, 2)  # REQ-012：attempts 上限 2
        self.assertEqual(
            task.retry_record["second_failure"]["error_kind"], "MODEL_ERROR"
        )
        self.assertIsNone(self.get_result(task.task_id))  # 不伪造等级（INV-1）
        records = self.outbox_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.dedup_key, "sub-1:scoring_failed")
        payload = record.payload
        self.assertEqual(
            set(payload),
            {"submission_id", "outcome", "failure_reason", "retry_record", "v"},
        )
        self.assertEqual(payload["failure_reason"], "MODEL_ERROR")
        self.assertEqual(payload["retry_record"]["attempts"], 2)
        self.assertEqual(payload["retry_record"]["last_error"], "MODEL_ERROR")
        self.assertTrue(payload["retry_record"]["retried_at"])
        self.assertEqual(payload["v"], 1)

    def test_retry_budget_cannot_be_exceeded(self):
        self.ingest()
        claimed = self.claim()
        for attempt_no, kind in ((1, "MODEL_TIMEOUT"), (2, "MODEL_ERROR")):
            self.orchestrator.fail_assessment(
                claimed.task_id,
                owner=claimed.lease_owner,
                attempt_no=attempt_no,
                error_kind=kind,
                now=T0 + timedelta(seconds=attempt_no),
            )
        # 第三次失败回调被拒绝（REQ-012 仅一次重试；终态不可逆）
        with self.assertRaises(TerminalCallbackRejected):
            self.orchestrator.fail_assessment(
                claimed.task_id,
                owner=claimed.lease_owner,
                attempt_no=2,
                error_kind="MODEL_ERROR",
                now=T0 + timedelta(seconds=60),
            )
        task = self.get_task()
        self.assertEqual(task.attempts, 2)
        self.assertEqual(task.status, STATUS_SCORING_FAILED)
        self.assertEqual(len(self.outbox_records()), 1)

    def test_duplicate_attempt_failure_callback_deduplicated(self):
        self.ingest()
        claimed = self.claim()
        self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=1,
            error_kind="MODEL_TIMEOUT",
            now=T0 + timedelta(seconds=5),
        )
        # 同一 attempt 的重复失败回调：按 attempt_no 去重，不再消耗重试
        with self.assertRaises(TerminalCallbackRejected) as ctx:
            self.orchestrator.fail_assessment(
                claimed.task_id,
                owner=claimed.lease_owner,
                attempt_no=1,
                error_kind="MODEL_TIMEOUT",
                now=T0 + timedelta(seconds=6),
            )
        self.assertEqual(ctx.exception.reason, STALE_TERMINAL_CALLBACK)
        self.assertEqual(self.get_task().attempts, 2)

    def test_unknown_error_kind_rejected(self):
        self.ingest()
        claimed = self.claim()
        with self.assertRaises(InvalidAssessmentFailure):
            self.orchestrator.fail_assessment(
                claimed.task_id,
                owner=claimed.lease_owner,
                attempt_no=1,
                error_kind="SOME_UNKNOWN_ERROR",
                now=T0,
            )
        self.assertEqual(self.get_task().attempts, 1)

    def test_crash_reclaim_does_not_spend_retry_budget(self):
        self.ingest()
        first = self.claim(owner="worker-1", at=T0)
        reclaimed = self.claim(
            owner="worker-2", at=first.lease_expires_at + timedelta(seconds=1)
        )
        # 崩溃重认领后 classified 失败仍按 attempt_no=1 进入唯一一次重试
        entered = self.orchestrator.fail_assessment(
            reclaimed.task_id,
            owner="worker-2",
            attempt_no=1,
            error_kind="MATERIAL_UNREADABLE",
            now=reclaimed.lease_expires_at - timedelta(seconds=1),
        )
        self.assertEqual(entered.next_attempt_no, 2)
        task = self.get_task()
        self.assertEqual(task.reclaim_count, 1)
        self.assertEqual(task.attempts, 2)


class TestMigration(unittest.TestCase):
    def _load_module(self):
        path = ROOT / "server" / "migrations" / "versions" / "0004_scoring_tasks.py"
        spec = importlib.util.spec_from_file_location("migration_0004_scoring_tasks", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_chain(self):
        module = self._load_module()
        self.assertEqual(module.revision, "0004_scoring_tasks")
        self.assertEqual(module.down_revision, "0001_baseline")

    def test_upgrade_and_downgrade_on_sqlite(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module = self._load_module()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            module.op = Operations(MigrationContext.configure(conn))
            module.upgrade()
            self.assertEqual(
                set(sa.inspect(conn).get_table_names()),
                {"scoring_tasks", "scoring_results"},
            )
            module.downgrade()
            self.assertEqual(sa.inspect(conn).get_table_names(), [])
        engine.dispose()

    def test_migration_schema_matches_orm_models(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module = self._load_module()
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            module.op = Operations(MigrationContext.configure(conn))
            module.upgrade()
            for table in ("scoring_tasks", "scoring_results"):
                migrated = {
                    c["name"] for c in sa.inspect(conn).get_columns(table)
                }
                modeled = set(OrchestratorBase.metadata.tables[table].columns.keys())
                self.assertEqual(migrated, modeled)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
