"""L09 SI-API：CT-001/CT-002/auth-token 端点、认证、幂等接入、30 秒编排。Phase 3 (W2)。

公共入口：`create_router`（APIRouter，不挂载；挂载归 backfill/平台）。
"""
from __future__ import annotations

from .errors import (
    AUTH_INVALID,
    ERROR_HTTP_STATUS,
    NOT_FOUND,
    PAYLOAD_TOO_LARGE,
    REJECTED_MEMBERSHIP,
    UNSUPPORTED_MEDIA_TYPE,
    VALIDATION_FAILED,
    AuthInvalidError,
    SiApiError,
)
from .models import RESULT_GRANTED, RESULT_REJECTED, AuthTokenGrant, Base
from .orchestrator import SYNC_BUDGET_SECONDS, IntakeOrchestrator
from .ports import (
    MaterialChunk,
    MembershipResult,
    MembershipVerifierPort,
    TransferResult,
    TransferSessionPort,
)
from .router import create_router
from .tokens import TOKEN_TTL_SECONDS, AuthContext, IssuedToken, TokenService

__all__ = [
    "AUTH_INVALID",
    "AuthContext",
    "AuthInvalidError",
    "AuthTokenGrant",
    "Base",
    "ERROR_HTTP_STATUS",
    "IntakeOrchestrator",
    "IssuedToken",
    "MaterialChunk",
    "MembershipResult",
    "MembershipVerifierPort",
    "NOT_FOUND",
    "PAYLOAD_TOO_LARGE",
    "REJECTED_MEMBERSHIP",
    "RESULT_GRANTED",
    "RESULT_REJECTED",
    "SYNC_BUDGET_SECONDS",
    "TOKEN_TTL_SECONDS",
    "SiApiError",
    "TokenService",
    "TransferResult",
    "TransferSessionPort",
    "UNSUPPORTED_MEDIA_TYPE",
    "VALIDATION_FAILED",
    "create_router",
]
