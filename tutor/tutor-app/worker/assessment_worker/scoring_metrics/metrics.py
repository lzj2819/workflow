"""ScoringMetrics：SM-002 / SM-003 度量与积压表盘（ICT-008 查询端口）。

口径（MOD-04 03-state-and-data 派生状态）：
- SM-002 = 任务创建 → scored 时长 ≤10min 的任务数 / 有时长口径的 scored 任务数
  （duration 仅在 record_task_created 已见该 submission_id 时可计）；
- SM-003 = 进入终态（scored + scoring_failed）的任务数 / 已创建任务总数；
- 积压 = 已创建 − 已终态。

接口：record_task_created(submission_id, at) / record_terminal(submission_id,
outcome, at)；两者均幂等（同 submission_id 重复记录不重复计数）。
计数/表盘落入 tutor_shared.metrics.registry（可注入独立 registry 供单测隔离），
供 /metrics 文本暴露；snapshot() 为 ICT-008 只读查询端口，返回当前指标快照。

本组件仅统计，不读写 ST-001/ST-002，不含学生标识与材料内容；进程内状态，
重启后由事件流重建（KD-003 基础监控口径）。
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from tutor_shared.metrics import MetricsRegistry
from tutor_shared.metrics import registry as default_registry

from assessment_worker.settings import TASK_BUDGET_SECONDS

OUTCOME_SCORED = "scored"
OUTCOME_SCORING_FAILED = "scoring_failed"
TERMINAL_OUTCOMES = (OUTCOME_SCORED, OUTCOME_SCORING_FAILED)

# registry 指标名（Prometheus 风格文本暴露）
METRIC_TASKS_CREATED = "scoring_tasks_created_total"
METRIC_TASKS_SCORED = "scoring_tasks_scored_total"
METRIC_TASKS_SCORING_FAILED = "scoring_tasks_scoring_failed_total"
METRIC_SM002_WITHIN_TARGET = "scoring_sm002_within_target_total"
GAUGE_BACKLOG = "scoring_backlog"
GAUGE_SM002_ATTAINMENT = "scoring_sm002_attainment_rate"
GAUGE_SM003_COVERAGE = "scoring_sm003_coverage_rate"


def _utc_naive(at: datetime) -> datetime:
    """时间戳归一化为 naive UTC（与 L03 时间戳约定一致）。"""
    if not isinstance(at, datetime):
        raise ValueError("at must be a datetime")
    if at.tzinfo is not None:
        return at.astimezone(timezone.utc).replace(tzinfo=None)
    return at


class ScoringMetrics:
    """SM-002/SM-003/积压度量器；线程安全；snapshot() 为 ICT-008 查询端口。"""

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        *,
        target_seconds: float = TASK_BUDGET_SECONDS,
    ) -> None:
        if target_seconds <= 0:
            raise ValueError("target_seconds must be positive")
        self._registry = registry if registry is not None else default_registry
        self._target = float(target_seconds)
        self._lock = threading.Lock()
        self._created: dict[str, datetime] = {}
        self._terminal: dict[str, str] = {}
        self._scored_durations: list[float] = []
        self._sm002_within = 0

    # ------------------------------------------------------------------ API

    def record_task_created(self, submission_id: str, at: datetime) -> None:
        """记录任务创建（SM-002 口径起点）；重复 submission_id 幂等忽略。"""
        self._validate_submission_id(submission_id)
        at = _utc_naive(at)
        with self._lock:
            if submission_id in self._created:
                return
            self._created[submission_id] = at
            self._registry.inc(METRIC_TASKS_CREATED)
            self._sync_gauges_locked()

    def record_terminal(self, submission_id: str, outcome: str, at: datetime) -> None:
        """记录终态（scored / scoring_failed）；同 submission_id 幂等忽略。

        outcome=scored 且创建时间已知时计入 SM-002 时长口径；
        创建时间未知的终态仍计入 SM-003 覆盖率，但不进 SM-002 分母。
        """
        self._validate_submission_id(submission_id)
        if outcome not in TERMINAL_OUTCOMES:
            raise ValueError(f"outcome must be one of {TERMINAL_OUTCOMES}")
        at = _utc_naive(at)
        with self._lock:
            if submission_id in self._terminal:
                return
            self._terminal[submission_id] = outcome
            if outcome == OUTCOME_SCORED:
                self._registry.inc(METRIC_TASKS_SCORED)
                created_at = self._created.get(submission_id)
                if created_at is not None:
                    duration = (at - created_at).total_seconds()
                    self._scored_durations.append(duration)
                    if duration <= self._target:
                        self._sm002_within += 1
                        self._registry.inc(METRIC_SM002_WITHIN_TARGET)
            else:
                self._registry.inc(METRIC_TASKS_SCORING_FAILED)
            self._sync_gauges_locked()

    def snapshot(self) -> dict:
        """ICT-008 查询端口：当前指标快照（只读、无副作用）。"""
        with self._lock:
            return {
                "tasks_created": len(self._created),
                "tasks_terminal": len(self._terminal),
                "scored": sum(1 for o in self._terminal.values() if o == OUTCOME_SCORED),
                "scoring_failed": sum(
                    1 for o in self._terminal.values() if o == OUTCOME_SCORING_FAILED
                ),
                "backlog": len(self._created) - len(self._terminal),
                "target_seconds": self._target,
                "sm002_measured": len(self._scored_durations),
                "sm002_within_target": self._sm002_within,
                "sm002_attainment_rate": self._sm002_rate_locked(),
                "sm003_coverage_rate": self._sm003_rate_locked(),
            }

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _validate_submission_id(submission_id: str) -> None:
        if not isinstance(submission_id, str) or not submission_id:
            raise ValueError("submission_id must be a non-empty string")

    def _sm002_rate_locked(self) -> float | None:
        if not self._scored_durations:
            return None
        return self._sm002_within / len(self._scored_durations)

    def _sm003_rate_locked(self) -> float | None:
        if not self._created:
            return None
        return len(self._terminal) / len(self._created)

    def _sync_gauges_locked(self) -> None:
        self._registry.gauge(GAUGE_BACKLOG, float(len(self._created) - len(self._terminal)))
        sm002 = self._sm002_rate_locked()
        if sm002 is not None:
            self._registry.gauge(GAUGE_SM002_ATTAINMENT, sm002)
        sm003 = self._sm003_rate_locked()
        if sm003 is not None:
            self._registry.gauge(GAUGE_SM003_COVERAGE, sm003)
