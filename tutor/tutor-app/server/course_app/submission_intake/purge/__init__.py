"""SI-PURGE：CT-012 清除执行与 CT-014 回传（T-B01c 回填；IC-SI-06 / ST-07）。

公共入口：`PurgeExecutor`（CT-012 消费 → 逐项清除 → CT-014 同事务入队）、
`validate_ct012`（冻结契约校验）、登记模型 `PurgeExecutionRow` /
`PurgeExecutionItemRow`（ST-07）、`PurgeValidationError`。
"""
from __future__ import annotations

from .errors import PurgeValidationError
from .executor import (
    CT_014,
    Ct012Command,
    OutboxProvider,
    PurgeExecutor,
    PurgeItemResult,
    PurgeReport,
    validate_ct012,
)
from .models import (
    EXECUTION_COMPLETED,
    EXECUTION_PARTIAL,
    RESULT_FAILED,
    RESULT_PURGED,
    Base,
    PurgeExecutionItemRow,
    PurgeExecutionRow,
)

__all__ = [
    "Base",
    "CT_014",
    "Ct012Command",
    "EXECUTION_COMPLETED",
    "EXECUTION_PARTIAL",
    "OutboxProvider",
    "PurgeExecutionItemRow",
    "PurgeExecutionRow",
    "PurgeExecutor",
    "PurgeItemResult",
    "PurgeReport",
    "PurgeValidationError",
    "RESULT_FAILED",
    "RESULT_PURGED",
    "validate_ct012",
]
