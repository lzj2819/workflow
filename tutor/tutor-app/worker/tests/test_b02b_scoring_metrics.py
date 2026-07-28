"""T-B02b SCORING-METRICS 单元测试（纯进程内，无需数据库）。

覆盖任务卡语义断言：
- SM-002：创建→scored 时长 ≤10min（TASK_BUDGET_SECONDS）目标达成率，
  仅计入创建时间已知的 scored 任务；
- SM-003：（scored + scoring_failed）/ 已创建任务总数覆盖率；
- 积压表盘 = 已创建 − 已终态；
- record_task_created / record_terminal 幂等（重复记录不重复计数）；
- 计数/表盘落 tutor_shared.metrics.MetricsRegistry（文本暴露含指标名）；
- snapshot() 为 ICT-008 只读快照；分母为零时比率为 None（不伪造 0/0）。
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

from tutor_shared.metrics import MetricsRegistry  # noqa: E402

from assessment_worker.scoring_metrics import (  # noqa: E402
    GAUGE_BACKLOG,
    GAUGE_SM002_ATTAINMENT,
    GAUGE_SM003_COVERAGE,
    METRIC_SM002_WITHIN_TARGET,
    METRIC_TASKS_CREATED,
    METRIC_TASKS_SCORED,
    METRIC_TASKS_SCORING_FAILED,
    ScoringMetrics,
)
from assessment_worker.settings import TASK_BUDGET_SECONDS  # noqa: E402

T0 = datetime(2026, 7, 20, 1, 0, 0)  # naive UTC


class ScoringMetricsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MetricsRegistry()
        self.metrics = ScoringMetrics(self.registry)


class TestScoringMetrics(ScoringMetricsTestBase):
    def test_sm002_attainment_rate(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_task_created("sub-2", T0)
        self.metrics.record_task_created("sub-3", T0)
        # sub-1：5min 达标；sub-2：11min 超标；sub-3：终态失败不计入 SM-002
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(minutes=5))
        self.metrics.record_terminal("sub-2", "scored", T0 + timedelta(minutes=11))
        self.metrics.record_terminal("sub-3", "scoring_failed", T0 + timedelta(minutes=2))

        snap = self.metrics.snapshot()
        self.assertEqual(snap["target_seconds"], float(TASK_BUDGET_SECONDS))
        self.assertEqual(snap["sm002_measured"], 2)
        self.assertEqual(snap["sm002_within_target"], 1)
        self.assertAlmostEqual(snap["sm002_attainment_rate"], 0.5)

    def test_sm003_coverage_rate(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_task_created("sub-2", T0)
        self.metrics.record_task_created("sub-3", T0)
        self.metrics.record_task_created("sub-4", T0)
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(minutes=1))
        self.metrics.record_terminal("sub-2", "scoring_failed", T0 + timedelta(minutes=1))
        self.metrics.record_terminal("sub-3", "scored", T0 + timedelta(minutes=1))

        snap = self.metrics.snapshot()
        self.assertEqual(snap["tasks_created"], 4)
        self.assertEqual(snap["tasks_terminal"], 3)
        self.assertEqual(snap["scored"], 2)
        self.assertEqual(snap["scoring_failed"], 1)
        self.assertAlmostEqual(snap["sm003_coverage_rate"], 0.75)

    def test_backlog_gauge(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_task_created("sub-2", T0)
        snap = self.metrics.snapshot()
        self.assertEqual(snap["backlog"], 2)
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(minutes=1))
        snap = self.metrics.snapshot()
        self.assertEqual(snap["backlog"], 1)

    def test_idempotent_records(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_task_created("sub-1", T0 + timedelta(minutes=9))
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(minutes=5))
        self.metrics.record_terminal("sub-1", "scoring_failed", T0 + timedelta(minutes=6))

        snap = self.metrics.snapshot()
        self.assertEqual(snap["tasks_created"], 1)
        self.assertEqual(snap["tasks_terminal"], 1)
        self.assertEqual(snap["scored"], 1)
        self.assertEqual(snap["scoring_failed"], 0)
        # 首次创建时间保留：时长 5min 达标
        self.assertEqual(snap["sm002_within_target"], 1)

    def test_terminal_without_known_creation_counts_sm003_not_sm002(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_terminal("sub-ghost", "scored", T0 + timedelta(minutes=1))

        snap = self.metrics.snapshot()
        self.assertEqual(snap["tasks_terminal"], 1)
        self.assertAlmostEqual(snap["sm003_coverage_rate"], 1.0)
        self.assertEqual(snap["sm002_measured"], 0)
        self.assertIsNone(snap["sm002_attainment_rate"])

    def test_rates_none_when_denominator_zero(self):
        snap = self.metrics.snapshot()
        self.assertIsNone(snap["sm002_attainment_rate"])
        self.assertIsNone(snap["sm003_coverage_rate"])
        self.assertEqual(snap["backlog"], 0)

    def test_boundary_duration_counts_within_target(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(seconds=TASK_BUDGET_SECONDS))
        snap = self.metrics.snapshot()
        self.assertEqual(snap["sm002_within_target"], 1)
        self.assertAlmostEqual(snap["sm002_attainment_rate"], 1.0)

    def test_registry_counters_and_gauges(self):
        self.metrics.record_task_created("sub-1", T0)
        self.metrics.record_task_created("sub-2", T0)
        self.metrics.record_terminal("sub-1", "scored", T0 + timedelta(minutes=5))
        self.metrics.record_terminal("sub-2", "scoring_failed", T0 + timedelta(minutes=1))

        text = self.registry.render_text()
        self.assertIn(f"{METRIC_TASKS_CREATED} 2.0", text)
        self.assertIn(f"{METRIC_TASKS_SCORED} 1.0", text)
        self.assertIn(f"{METRIC_TASKS_SCORING_FAILED} 1.0", text)
        self.assertIn(f"{METRIC_SM002_WITHIN_TARGET} 1.0", text)
        self.assertIn(f"{GAUGE_BACKLOG} 0.0", text)
        self.assertIn(f"{GAUGE_SM002_ATTAINMENT} 1.0", text)
        self.assertIn(f"{GAUGE_SM003_COVERAGE} 1.0", text)

    def test_aware_datetime_normalized_to_naive_utc(self):
        aware = datetime(2026, 7, 20, 9, 0, 0, tzinfo=timezone(timedelta(hours=8)))
        self.metrics.record_task_created("sub-1", aware)
        # UTC 01:00 创建，UTC 01:05（+8h 09:05）scored，时长 5min 达标
        self.metrics.record_terminal(
            "sub-1", "scored", datetime(2026, 7, 20, 9, 5, 0, tzinfo=timezone(timedelta(hours=8)))
        )
        snap = self.metrics.snapshot()
        self.assertEqual(snap["sm002_within_target"], 1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.metrics.record_task_created("", T0)
        with self.assertRaises(ValueError):
            self.metrics.record_terminal("sub-1", "bogus", T0)
        with self.assertRaises(ValueError):
            self.metrics.record_terminal("sub-1", "scored", "not-a-datetime")
        with self.assertRaises(ValueError):
            ScoringMetrics(self.registry, target_seconds=0)


if __name__ == "__main__":
    unittest.main()
