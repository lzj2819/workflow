"""L14 CMP-REVIEW-COMMAND：复核写侧（CT-008）、ReviewRecord 聚合。

公开面：ReviewCommandService（GUARD+POLICY+WRITER、M05-IC-01 端口实现）、
create_router（CT-008 APIRouter，不挂载）、端口抽象与冻结错误类型。
"""
from __future__ import annotations

from . import models  # noqa: F401  （确保 ST-REVIEW-RECORD 元数据随包导入）
from .errors import (
    AuthInvalidError,
    ForbiddenError,
    NoOriginalGradeError,
    NotFoundError,
    ReviewCommandError,
    ValidationFailedError,
)
from .models import Base, GradeAdjustmentRecord, ReviewIdempotencyRecord, ReviewRecord
from .ports import (
    AccessGatePort,
    AccessGrant,
    InMemoryReviewEventPublisher,
    ReviewEvent,
    ReviewEventPublisher,
    SubmissionStatus,
    SubmissionStatusPort,
)
from .router import create_router
from .service import ReviewCommandOutcome, ReviewCommandService, review_record_payload

__all__ = [
    "AccessGatePort",
    "AccessGrant",
    "AuthInvalidError",
    "Base",
    "ForbiddenError",
    "GradeAdjustmentRecord",
    "InMemoryReviewEventPublisher",
    "NoOriginalGradeError",
    "NotFoundError",
    "ReviewCommandError",
    "ReviewCommandOutcome",
    "ReviewCommandService",
    "ReviewEvent",
    "ReviewEventPublisher",
    "ReviewIdempotencyRecord",
    "ReviewRecord",
    "SubmissionStatus",
    "SubmissionStatusPort",
    "ValidationFailedError",
    "create_router",
    "review_record_payload",
]
