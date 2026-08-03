"""L15 CMP-REVIEW-QUERY：教师查询读装配（CT-007）。Phase 4 (W3) 实现。"""
from __future__ import annotations

from .assemblers import (
    OutcomeAdapter,
    RetentionViewAdapter,
    ScopeAssembler,
    SubmissionDetailAssembler,
)
from .errors import (
    AccessDeniedError,
    AuthInvalidError,
    NotFoundError,
    ReadModelUnavailableError,
    RetentionViewUnavailableError,
    RetryableQueryError,
    RqError,
    ValidationFailedError,
)
from .facade import QueryFacade, ReviewQueryService, create_facade
from .ports import (
    GRADES,
    SUBMISSION_STATUSES,
    AccessGatePort,
    AuthorizedQueryContext,
    ReadModelQueryPort,
    ReadModelView,
    RetentionBatchView,
    RetentionViewPort,
)
from .router import create_router

__all__ = [
    "GRADES",
    "SUBMISSION_STATUSES",
    "AccessDeniedError",
    "AccessGatePort",
    "AuthInvalidError",
    "AuthorizedQueryContext",
    "NotFoundError",
    "OutcomeAdapter",
    "QueryFacade",
    "ReadModelQueryPort",
    "ReadModelUnavailableError",
    "ReadModelView",
    "RetentionBatchView",
    "RetentionViewAdapter",
    "RetentionViewPort",
    "RetentionViewUnavailableError",
    "RetryableQueryError",
    "ReviewQueryService",
    "RqError",
    "ScopeAssembler",
    "SubmissionDetailAssembler",
    "ValidationFailedError",
    "create_facade",
    "create_router",
]
