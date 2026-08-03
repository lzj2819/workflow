"""L02 SI-CORE：Submission 聚合、状态机、完整性报告、单事务持久化。Phase 2 (W1) 实现。

公共入口（IC-SI-04）：`SubmissionCoreService`（命令编排/单事务/Outbox 同事务入队）。
"""
from __future__ import annotations

from . import status
from .aggregate import (
    APPLIED,
    DUPLICATE_IGNORED,
    IDEMPOTENT_HIT,
    SubmissionAggregate,
    TransitionResult,
)
from .errors import (
    CoreError,
    IllegalTransitionError,
    MaterialMetadataUnavailableError,
    NotFoundError,
    ValidationError,
)
from .integrity import (
    CATEGORIES,
    IntegrityReportData,
    MaterialMetadata,
    MaterialMetadataReader,
    build_manifest_and_report,
)
from .models import Base, IntegrityReportRow, Submission, SubmissionMaterial
from .service import CommandResult, SubmissionCoreService, SubmissionView

__all__ = [
    "APPLIED",
    "Base",
    "CATEGORIES",
    "CommandResult",
    "CoreError",
    "DUPLICATE_IGNORED",
    "IDEMPOTENT_HIT",
    "IllegalTransitionError",
    "IntegrityReportData",
    "IntegrityReportRow",
    "MaterialMetadata",
    "MaterialMetadataReader",
    "MaterialMetadataUnavailableError",
    "NotFoundError",
    "Submission",
    "SubmissionAggregate",
    "SubmissionCoreService",
    "SubmissionMaterial",
    "SubmissionView",
    "TransitionResult",
    "ValidationError",
    "build_manifest_and_report",
    "status",
]
