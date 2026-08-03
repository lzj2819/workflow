"""RETENTION-GOVERNANCE：保留治理与 CT-011（T-B03c 回填；NFR-004 / DF-3 / FLOW-011）。

公共入口：
- `RetentionService`：到期批处理 mark_due_batches、CT-011 确认 confirm_batch
  （审计先行 + CT-012 同事务发布）、CT-014/CT-015 消费 handle_ct014/handle_ct015
  （CCR-001 双回流聚合：双到达且无失败项才 completed）、M05-IC-06 批次视图
  list_batches；
- `create_router`：CT-011 FastAPI APIRouter（不挂载）；
- `RetentionViewPortAdapter`：L15 deletion_batches[] 读端口实现（M05-IC-06）；
- 持久化模型 `DeletionBatch` / `DeletionAuditRecord`（迁移 0014_retention +
  0016 CCR-001 双回流列）；
- `validate_ct014`：CT-014/CT-015 冻结契约校验（两事件形状一致）。

边界：AssessmentResult（MOD-04）删除接线经 CCR-001 方案 A 落地（CT-012 消费 +
墓碑 + CT-015 回流，实现归 MOD-04 scoring_orchestrator/purge.py）。
"""
from __future__ import annotations

from .api import ConfirmRequest, create_router
from .errors import (
    BatchNotExpiredError,
    BatchNotFoundError,
    Ct014ValidationError,
    RetentionError,
)
from .models import (
    ACTION_DELETION_CONFIRMED,
    ACTION_RECORDS_DELETED,
    BATCH_STATUSES,
    STATUS_AWAITING_CONFIRM,
    STATUS_COMPLETED,
    STATUS_EXECUTING,
    STATUS_PARTIALLY_FAILED,
    STATUS_PENDING_MARK,
    Base,
    DeletionAuditRecord,
    DeletionBatch,
)
from .read_port import RetentionViewPortAdapter
from .service import (
    CT_012,
    SCOPE_COURSE,
    ConfirmResult,
    CourseCatalogPort,
    CourseEndTimePort,
    Ct014Event,
    Ct014Result,
    MarkDueItem,
    MarkDueReport,
    OutboxProvider,
    RetentionService,
    derive_batch_id,
    plus_one_year,
    validate_ct014,
)

__all__ = [
    "ACTION_DELETION_CONFIRMED",
    "ACTION_RECORDS_DELETED",
    "BATCH_STATUSES",
    "Base",
    "BatchNotExpiredError",
    "BatchNotFoundError",
    "CT_012",
    "ConfirmRequest",
    "ConfirmResult",
    "CourseCatalogPort",
    "CourseEndTimePort",
    "Ct014Event",
    "Ct014Result",
    "Ct014ValidationError",
    "DeletionAuditRecord",
    "DeletionBatch",
    "MarkDueItem",
    "MarkDueReport",
    "OutboxProvider",
    "RetentionError",
    "RetentionService",
    "RetentionViewPortAdapter",
    "SCOPE_COURSE",
    "STATUS_AWAITING_CONFIRM",
    "STATUS_COMPLETED",
    "STATUS_EXECUTING",
    "STATUS_PARTIALLY_FAILED",
    "STATUS_PENDING_MARK",
    "create_router",
    "derive_batch_id",
    "plus_one_year",
    "validate_ct014",
]
