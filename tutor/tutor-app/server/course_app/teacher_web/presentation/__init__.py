"""L16 CMP-PRESENTATION：展示视图生成与快照（CT-009）。Phase 4 (W3)。

公共入口：`create_router`（APIRouter，不挂载；挂载归 backfill/平台）。
快照导出：静态 HTML（DD-003/LCD-008，v1 不做 PDF）。
"""
from __future__ import annotations

from .assembler import assemble_block
from .coordinator import PresentationCoordinator
from .errors import (
    AUTH_INVALID,
    ERROR_HTTP_STATUS,
    FORBIDDEN,
    NO_AVAILABLE_SUBMISSION,
    VALIDATION_FAILED,
    AuthInvalidError,
    ForbiddenError,
    NoAvailableSubmissionError,
    PresentationError,
    ReadModelUnavailableError,
    ValidationFailedError,
)
from .missing_marks import GroupEvaluation, evaluate_group
from .models import (
    STATUS_ACTIVE,
    STATUS_PURGED,
    STATUS_SUPERSEDED,
    Base,
    PresentationIdempotencyRecord,
    PresentationViewRecord,
)
from .output import EXPORT_FORMAT_HTML, render_html, to_response
from .ports import (
    MATERIAL_CATEGORIES,
    UNAVAILABLE_SUBMISSION_STATUSES,
    AccessGatePort,
    AnnotationView,
    AuthContext,
    GroupReadView,
    MaterialRef,
    ReadModelQueryPort,
    SubmissionView,
)
from .router import create_router
from .store import (
    Snapshot,
    SnapshotStore,
    default_time_window,
    generation_key,
    group_set_key,
    normalize_group_ids,
)

__all__ = [
    "AUTH_INVALID",
    "ERROR_HTTP_STATUS",
    "EXPORT_FORMAT_HTML",
    "FORBIDDEN",
    "MATERIAL_CATEGORIES",
    "NO_AVAILABLE_SUBMISSION",
    "STATUS_ACTIVE",
    "STATUS_PURGED",
    "STATUS_SUPERSEDED",
    "UNAVAILABLE_SUBMISSION_STATUSES",
    "VALIDATION_FAILED",
    "AccessGatePort",
    "AnnotationView",
    "AuthContext",
    "AuthInvalidError",
    "Base",
    "ForbiddenError",
    "GroupEvaluation",
    "GroupReadView",
    "MaterialRef",
    "NoAvailableSubmissionError",
    "PresentationCoordinator",
    "PresentationError",
    "PresentationIdempotencyRecord",
    "PresentationViewRecord",
    "ReadModelQueryPort",
    "ReadModelUnavailableError",
    "Snapshot",
    "SnapshotStore",
    "SubmissionView",
    "ValidationFailedError",
    "assemble_block",
    "create_router",
    "default_time_window",
    "evaluate_group",
    "generation_key",
    "group_set_key",
    "normalize_group_ids",
    "render_html",
    "to_response",
]
