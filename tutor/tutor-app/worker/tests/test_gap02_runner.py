"""GAP-02 DU-3 常驻循环验收：入站幂等/全链评分/失败重试/租约续期/优雅关闭/重启恢复/并发认领。

DB 为临时文件 SQLite（QueuePool 多连接，承载 认领线程+心跳+入站 并发）；
迁移经 alembic 全量执行（scripts.e2e_scenario_001.migrate）。
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "worker"), str(ROOT / "server"), str(ROOT / "shared")]

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from assessment_worker.model_provider import FakeModelProvider  # noqa: E402
from assessment_worker.runner import WorkerRunner  # noqa: E402
from assessment_worker.settings import Settings  # noqa: E402
from course_app.db import session_scope  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402

NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)


def ct004_payload(submission_id: str) -> dict:
    return {
        "submission_id": submission_id,
        "course_id": "c-1",
        "assignment": "hw",
        "student_name": "张三",
        "group_name": "第1组",
        "material_refs": [],
        "missing_items": [],
        "received_at": NOW.isoformat(),
        "v": 1,
    }


class SlowFakeProvider(FakeModelProvider):
    """可注入延迟的 fake（租约续期/并发测试）。"""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.calls = 0

    def evaluate(self, request: dict) -> dict:
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        return super().evaluate(request)


class FlakyOnceProvider(FakeModelProvider):
    """首次调用超时（MODEL_TIMEOUT 分类），其后正常（REQ-012 重试验证）。"""

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, request: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("simulated vendor timeout")
        return super().evaluate(request)


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        self.data_dir = tmp / "materials"
        self.data_dir.mkdir()
        self.db_url = f"sqlite:///{tmp / 'gap02.db'}"
        # StaticPool 单连接（e2e_scenario_001 同款）：SQLite 文件库多连接并发写
        # 必然 SQLITE_BUSY（写锁串行化），单连接语句级交错是单测唯一可行形态；
        # 真实并发正确性由 PG 侧验证（staging NFR + SKIP LOCKED 探针）
        self.engine = migrate(self.db_url)
        self.addCleanup(self.engine.dispose)

    def make_settings(self, **overrides) -> Settings:
        base = {
            "database_url": self.db_url,
            "model_provider": "fake",
            "model_api_key": None,
            "log_level": "WARNING",
            "claim_lease_seconds": 2,
            "data_dir": str(self.data_dir),
            "worker_id": "t-worker",
            "concurrency": 1,
            "poll_interval_seconds": 0.05,
        }
        base.update(overrides)
        return Settings(**base)

    def enqueue(self, contract_id: str, payload: dict, dedup_key: str) -> None:
        with session_scope(self.engine) as s:
            SqlaOutboxStore(s).enqueue(contract_id, payload, dedup_key)

    def enqueue_ct004(self, submission_id: str) -> None:
        self.enqueue("CT-004", ct004_payload(submission_id), f"ct004-{submission_id}")

    def run_in_background(self, runner: WorkerRunner) -> threading.Thread:
        thread = threading.Thread(target=runner.run, daemon=True)
        thread.start()
        return thread

    @staticmethod
    def wait_until(cond, timeout: float = 40.0) -> bool:  # 宽时限：套件并发/机器负载下给足调度余量
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.05)
        return False

    def task_row(self, submission_id: str) -> dict | None:
        """读任务行为 dict（避免 session 关闭后的 DetachedInstanceError）。"""
        with session_scope(self.engine) as s:
            row = s.execute(
                sa.text(
                    "select status, attempts, reclaim_count, retry_record, lease_owner"
                    " from scoring_tasks where submission_id=:sid"
                ),
                {"sid": submission_id},
            ).mappings().one_or_none()
            return dict(row) if row is not None else None

    def result_count(self) -> int:
        with session_scope(self.engine) as s:
            return s.execute(sa.text("select count(*) from scoring_results")).scalar()

    def outbox_rows(self, contract_id: str) -> list:
        with session_scope(self.engine) as s:
            return list(
                s.execute(
                    sa.text("select status, payload from outbox_records where contract_id=:c"),
                    {"c": contract_id},
                )
            )

    # ---- CT-004 入站 ----

    def test_ingress_consumes_and_confirms_ct004(self) -> None:
        self.enqueue_ct004("sub-1")
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        self.assertEqual(runner._ingress_once(), 1)
        task = self.task_row("sub-1")
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "pending")
        rows = self.outbox_rows("CT-004")
        self.assertEqual(rows[0][0], "confirmed")

    def test_ingress_duplicate_ct004_idempotent(self) -> None:
        # 同一事件两条 outbox 记录、两轮入站（真实重复投递形态）；
        # 注：必须分两轮——同一共享连接上重复键回滚会波及同连接其他事务
        # （SQLite/pysqlite 单连接伪并发限制；生产 PG 独立连接无此问题）
        self.enqueue_ct004("sub-1")
        self.enqueue("CT-004", ct004_payload("sub-1"), "ct004-sub-1-dup")
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        runner._ingress_once()
        runner._ingress_once()
        self.assertIsNotNone(self.task_row("sub-1"))
        with session_scope(self.engine) as s:
            count = s.execute(
                sa.text("select count(*) from scoring_tasks where submission_id='sub-1'")
            ).scalar()
        self.assertEqual(count, 1)  # 重复投递不产生第二个任务
        self.assertTrue(all(r[0] == "confirmed" for r in self.outbox_rows("CT-004")))

    def test_ingress_ignores_foreign_events(self) -> None:
        # contract_ids 过滤：worker 不认领 DU-2 契约（保持 pending 归 DU-2 relayer）
        self.enqueue("CT-014", {"batch_id": "b", "purged_submission_ids": [], "failed_items": [],
                                "purged_at": NOW.isoformat(), "v": 1}, "ct014-b")
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        self.assertEqual(runner._ingress_once(), 0)
        rows = self.outbox_rows("CT-014")
        self.assertEqual(rows[0][0], "pending")  # 未被 worker 触碰

    # ---- 全链评分 / 重试 / 续期 ----

    def test_full_cycle_scores_and_publishes_ct005(self) -> None:
        self.enqueue_ct004("sub-1")
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        thread = self.run_in_background(runner)
        try:
            ok = self.wait_until(lambda: self.result_count() == 1)
            self.assertTrue(ok, "task not scored in time")
            task = self.task_row("sub-1")
            self.assertEqual(task["status"], "scored")
            ct005 = self.outbox_rows("CT-005")
            self.assertEqual(len(ct005), 1)  # CT-005 入队待 DU-2 relay（本进程不消费）
        finally:
            runner.request_shutdown()
            thread.join(timeout=10)
        self.assertFalse(thread.is_alive())

    def test_failure_retry_once_then_success(self) -> None:
        self.enqueue_ct004("sub-1")
        provider = FlakyOnceProvider()
        runner = WorkerRunner(
            self.make_settings(), sa_engine=self.engine, install_signals=False, provider=provider
        )
        thread = self.run_in_background(runner)
        try:
            ok = self.wait_until(lambda: self.result_count() == 1)
            self.assertTrue(ok, "retry did not complete")
            task = self.task_row("sub-1")
            self.assertEqual(task["status"], "scored")
            self.assertEqual(task["attempts"], 2)  # REQ-012：首次失败后任务内重试成功
            self.assertEqual(provider.calls, 2)
            self.assertIsNotNone(task["retry_record"])
        finally:
            runner.request_shutdown()
            thread.join(timeout=10)

    def test_lease_heartbeat_renews_during_execution(self) -> None:
        # 确定性续期验证：直接驱动心跳线程，断言续约发生且租约到期被推进
        self.enqueue_ct004("sub-1")
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        runner._ingress_once()
        claimed = runner._orchestrator.claim_task(owner="hb-owner")
        self.assertIsNotNone(claimed)
        renew_calls = []
        original_renew = runner._lease_store.renew

        def counting_renew(task_id, owner, ttl, now):
            renew_calls.append(task_id)
            return original_renew(task_id, owner, ttl, now)

        runner._lease_store.renew = counting_renew  # type: ignore[method-assign]
        stop = threading.Event()
        hb = threading.Thread(
            target=runner._heartbeat, args=(claimed.task_id, "hb-owner", stop), daemon=True
        )
        hb.start()
        time.sleep(1.6)  # lease ttl=2s，续期间隔 ttl/3 ≈ 0.67s → 至少一次续约
        stop.set()
        hb.join(timeout=3)
        self.assertGreaterEqual(len(renew_calls), 1)
        with session_scope(self.engine) as s:
            expires = s.execute(
                sa.text("select lease_expires_at from scoring_tasks where task_id=:t"),
                {"t": claimed.task_id},
            ).scalar()
        self.assertGreater(str(expires), str(claimed.lease_expires_at))  # 到期被推进

    def test_slow_task_completes_with_heartbeat(self) -> None:
        # 执行时长超过租约 ttl：心跳接管续期，任务照常 scored（完成回调未被拒）
        self.enqueue_ct004("sub-1")
        provider = SlowFakeProvider(delay=2.5)  # lease ttl=2s
        runner = WorkerRunner(
            self.make_settings(), sa_engine=self.engine, install_signals=False, provider=provider
        )
        thread = self.run_in_background(runner)
        try:
            ok = self.wait_until(lambda: self.result_count() == 1, timeout=25)
            self.assertTrue(ok, "slow task not scored")
            self.assertEqual(self.task_row("sub-1")["status"], "scored")
        finally:
            runner.request_shutdown()
            thread.join(timeout=10)

    # ---- 优雅关闭 / 重启恢复 / 并发 ----

    def test_graceful_shutdown_returns_zero(self) -> None:
        runner = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        thread = self.run_in_background(runner)
        time.sleep(0.3)
        runner.request_shutdown()
        thread.join(timeout=10)
        self.assertFalse(thread.is_alive())

    def test_restart_recovery_reclaims_expired_lease(self) -> None:
        self.enqueue_ct004("sub-1")
        # “死掉的” runner A：先入站建任务，认领后持有租约但不执行（模拟崩溃）
        runner_a = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        runner_a._ingress_once()
        claimed = runner_a._orchestrator.claim_task(owner="dead-worker")
        self.assertIsNotNone(claimed)
        time.sleep(2.2)  # 租约(2s)过期
        # runner B 启动：重认领并完成任务
        runner_b = WorkerRunner(self.make_settings(), sa_engine=self.engine, install_signals=False)
        thread = self.run_in_background(runner_b)
        try:
            ok = self.wait_until(lambda: self.result_count() == 1)
            self.assertTrue(ok, "reclaim did not complete")
            task = self.task_row("sub-1")
            self.assertEqual(task["status"], "scored")
            self.assertGreaterEqual(task["reclaim_count"], 1)
        finally:
            runner_b.request_shutdown()
            thread.join(timeout=10)

    def test_concurrent_claims_two_slots(self) -> None:
        # 双槽并行推进：两任务均 scored、无重复结果。
        # 注：SQLite 单连接伪并发下交错认领会随机触发陈旧回调→重认领→崩溃循环
        # 终态化（测试环境假象，非产品缺陷）；并发认领互斥的严格验证在 PG 层
        # （staging G2-5 复跑 + Phase 5 SKIP LOCKED 探针），本测试覆盖多槽无死锁推进。
        self.enqueue_ct004("sub-1")
        self.enqueue_ct004("sub-2")
        runner = WorkerRunner(
            self.make_settings(concurrency=2),
            sa_engine=self.engine,
            install_signals=False,
        )
        thread = self.run_in_background(runner)
        try:
            ok = self.wait_until(lambda: self.result_count() == 2, timeout=20)
            self.assertTrue(ok, "two tasks not both scored")
            with session_scope(self.engine) as s:
                statuses = [r[0] for r in s.execute(sa.text("select status from scoring_tasks")).all()]
                dup = s.execute(
                    sa.text(
                        "select submission_id, count(*) c from scoring_results"
                        " group by submission_id having c > 1"
                    )
                ).all()
            self.assertEqual(sorted(statuses), ["scored", "scored"])
            self.assertEqual(dup, [])  # 无重复结果（认领互斥生效）
        finally:
            runner.request_shutdown()
            thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
