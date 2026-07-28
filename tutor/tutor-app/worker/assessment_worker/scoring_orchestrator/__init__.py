"""L03 CMP-SCORING-ORCHESTRATOR：评分任务持久化、状态机、认领/租约、终态事务（Phase 2 W1）。

边界：不实现 CT-010 模型调用（ACL backfill）、五维评估装配（L12）、提示编排
（RUBRIC-PROMPT-COMPOSER backfill）、CT-005 投递器（RESULT-PUBLISHER backfill）、
度量组件、CT-012 消费/删除（CCR-001 pending）。
"""
from assessment_worker.scoring_orchestrator.errors import (
    DUPLICATE_TERMINAL_CALLBACK,
    STALE_TERMINAL_CALLBACK,
    InvalidAssessmentFailure,
    InvalidAssessmentResult,
    OrchestratorError,
    TerminalCallbackRejected,
)
from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore
from assessment_worker.scoring_orchestrator.models import (
    OrchestratorBase,
    ScoringResult,
    ScoringTask,
)
from assessment_worker.scoring_orchestrator.orchestrator import (
    CT005_CONTRACT_ID,
    CRASH_LOOP_FAILURE_REASON,
    DIMENSIONS,
    ERROR_TAXONOMY,
    GRADES,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_SCORED,
    STATUS_SCORING_FAILED,
    ClaimedTask,
    IngressResult,
    OutcomeCommitted,
    RetryEntered,
    ScoringOrchestrator,
    validate_assessment_result,
)

__all__ = [
    "CT005_CONTRACT_ID",
    "CRASH_LOOP_FAILURE_REASON",
    "DIMENSIONS",
    "DUPLICATE_TERMINAL_CALLBACK",
    "ERROR_TAXONOMY",
    "GRADES",
    "STALE_TERMINAL_CALLBACK",
    "STATUS_IN_PROGRESS",
    "STATUS_PENDING",
    "STATUS_SCORED",
    "STATUS_SCORING_FAILED",
    "ClaimedTask",
    "IngressResult",
    "InvalidAssessmentFailure",
    "InvalidAssessmentResult",
    "OrchestratorBase",
    "OrchestratorError",
    "OutcomeCommitted",
    "RetryEntered",
    "ScoringOrchestrator",
    "ScoringResult",
    "ScoringTask",
    "SqlaTaskLeaseStore",
    "TerminalCallbackRejected",
    "validate_assessment_result",
]
