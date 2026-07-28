"""平台层测试：config / logging / metrics / health / outbox / lease（零第三方依赖）。"""
from __future__ import annotations

import json
import logging
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from tutor_shared import health as shared_health  # noqa: E402
from tutor_shared.config import ConfigError, get_bool, get_int, require_str  # noqa: E402
from tutor_shared.lease import InMemoryLeaseStore  # noqa: E402
from tutor_shared.logging import JsonFormatter  # noqa: E402
from tutor_shared.metrics import MetricsRegistry  # noqa: E402
from tutor_shared.outbox import InMemoryOutboxStore, default_backoff  # noqa: E402

T0 = datetime(2026, 7, 20, tzinfo=timezone.utc)


class TestConfig(unittest.TestCase):
    def test_get_int_and_bool(self):
        env = {"A": "42", "B": "yes", "C": "off"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(get_int("A", 0), 42)
            self.assertTrue(get_bool("B", False))
            self.assertFalse(get_bool("C", True))
            self.assertEqual(get_int("MISSING", 7), 7)
            with self.assertRaises(ConfigError):
                get_bool("A", False)

    def test_require_str(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ConfigError):
                require_str("NOPE")


class TestLogging(unittest.TestCase):
    def test_json_formatter(self):
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        record.run_id = "tutor-r01"
        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["msg"], "hello world")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["run_id"], "tutor-r01")
        self.assertIn("ts", payload)


class TestMetrics(unittest.TestCase):
    def test_render(self):
        registry = MetricsRegistry()
        registry.inc("submissions_received_total")
        registry.inc("submissions_received_total", 2)
        registry.gauge("scoring_backlog", 5)
        text = registry.render_text()
        self.assertIn("submissions_received_total 3", text)
        self.assertIn("scoring_backlog 5", text)


class TestHealth(unittest.TestCase):
    def test_readiness_aggregation(self):
        report = shared_health.readiness({
            "ok_check": lambda: (True, "fine"),
            "bad_check": lambda: (False, "down"),
        })
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["checks"]["ok_check"]["status"], "ok")
        self.assertEqual(report["checks"]["bad_check"]["status"], "fail")

    def test_check_exception_is_fail(self):
        def boom():
            raise ValueError("x")

        report = shared_health.readiness({"boom": boom})
        self.assertEqual(report["status"], "not_ready")
        self.assertIn("boom", report["checks"])

    def test_liveness(self):
        self.assertEqual(shared_health.liveness(), {"status": "ok"})


class TestOutbox(unittest.TestCase):
    def test_full_cycle_with_retry(self):
        store = InMemoryOutboxStore()
        record = store.enqueue("CT-004", {"submission_id": "s1"}, dedup_key="s1")
        self.assertEqual(record.status, "pending")

        # 用运行时真实时钟（OutboxRecord.next_attempt_at 取真实 now），避免日期脆弱
        t0 = datetime.now(timezone.utc) + timedelta(seconds=1)
        due = store.fetch_due(t0)
        self.assertEqual([r.record_id for r in due], [record.record_id])
        self.assertEqual(due[0].status, "delivering")
        self.assertEqual(due[0].attempts, 1)
        self.assertEqual(store.fetch_due(t0), [])  # delivering 中不可重复认领

        store.mark_retry(record.record_id, t0 + timedelta(seconds=5))
        self.assertEqual(store.fetch_due(t0), [])  # retry_wait 未到时间
        due = store.fetch_due(t0 + timedelta(seconds=6))
        self.assertEqual(len(due), 1)
        store.mark_confirmed(record.record_id)
        self.assertEqual(store._records[record.record_id].status, "confirmed")

    def test_backoff_caps_at_60s(self):
        self.assertEqual(default_backoff(1).total_seconds(), 1)
        self.assertEqual(default_backoff(10).total_seconds(), 60)


class TestLease(unittest.TestCase):
    def test_claim_renew_expire_reclaim(self):
        store = InMemoryLeaseStore(max_reclaims=3)
        ttl = timedelta(seconds=120)
        lease = store.claim("t1", "w1", ttl, T0)
        self.assertIsNotNone(lease)
        self.assertIsNone(store.claim("t1", "w2", ttl, T0))  # 未过期不可抢

        self.assertTrue(store.renew("t1", "w1", ttl, T0))
        self.assertFalse(store.renew("t1", "w2", ttl, T0))

        expired = T0 + ttl + timedelta(seconds=1)
        lease2 = store.claim("t1", "w2", ttl, expired)
        self.assertIsNotNone(lease2)
        self.assertEqual(lease2.reclaim_count, 1)

        store.release("t1", "w2")
        self.assertIsNone(store.get("t1"))

    def test_max_reclaims_then_terminal(self):
        store = InMemoryLeaseStore(max_reclaims=3)
        ttl = timedelta(seconds=10)
        now = T0
        self.assertIsNotNone(store.claim("t2", "w", ttl, now))  # rc=0
        for expected_rc in (1, 2, 3):
            now += ttl + timedelta(seconds=1)
            lease = store.claim("t2", "w", ttl, now)
            self.assertEqual(lease.reclaim_count, expected_rc)
        now += ttl + timedelta(seconds=1)
        self.assertIsNone(store.claim("t2", "w", ttl, now))  # rc>=3 → 终态化


if __name__ == "__main__":
    unittest.main()
