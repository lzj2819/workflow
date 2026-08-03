"""SCORING-METRICS（ICT-008，T-B02b）：SM-002/SM-003 度量与积压表盘。

边界：仅进程内统计（record_task_created / record_terminal，幂等）；
计数/表盘接入 tutor_shared.metrics.registry 供 /metrics 暴露；
snapshot() 为 ICT-008 只读查询端口。不读写业务表、不含学生标识与材料内容。
"""
from assessment_worker.scoring_metrics.metrics import (
    GAUGE_BACKLOG,
    GAUGE_SM002_ATTAINMENT,
    GAUGE_SM003_COVERAGE,
    METRIC_SM002_WITHIN_TARGET,
    METRIC_TASKS_CREATED,
    METRIC_TASKS_SCORED,
    METRIC_TASKS_SCORING_FAILED,
    OUTCOME_SCORED,
    OUTCOME_SCORING_FAILED,
    TERMINAL_OUTCOMES,
    ScoringMetrics,
)

__all__ = [
    "GAUGE_BACKLOG",
    "GAUGE_SM002_ATTAINMENT",
    "GAUGE_SM003_COVERAGE",
    "METRIC_SM002_WITHIN_TARGET",
    "METRIC_TASKS_CREATED",
    "METRIC_TASKS_SCORED",
    "METRIC_TASKS_SCORING_FAILED",
    "OUTCOME_SCORED",
    "OUTCOME_SCORING_FAILED",
    "TERMINAL_OUTCOMES",
    "ScoringMetrics",
]
