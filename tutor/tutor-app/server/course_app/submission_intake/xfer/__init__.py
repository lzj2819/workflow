"""L08 SI-XFER：分片上传会话、断点续传、合并、500MB/白名单校验。Phase 3 (W2) 实现。

公共入口（IC-SI-01）：`UploadTransferService`（建会话/追分片/合并/中止/查询）。
SI-STORE 以 `MaterialStorePort` 抽象注入（实现归 backfill）。
"""
from __future__ import annotations

from .errors import (
    ChunkDigestConflictError,
    ChunkOutOfOrderError,
    SessionNotFoundError,
    SessionStateError,
    SizeLimitExceededError,
    TypeNotAllowedError,
    XferError,
)
from .models import Base, ChunkReceipt, FinalizeAttempt, UploadSession
from .service import (
    ACCEPTED,
    DUPLICATE,
    FAILED_TERMINAL,
    FILE_TYPE_WHITELIST,
    INTERRUPTED_RETRYABLE,
    MATERIAL_CATEGORIES,
    MAX_SUBMISSION_BYTES,
    MERGED,
    PENDING_VERIFICATION,
    RECEIVING,
    AppendResult,
    FinalizeResult,
    SessionView,
    UploadTransferService,
)
from .store import MaterialStorePort, StorageIoError

__all__ = [
    "ACCEPTED",
    "AppendResult",
    "Base",
    "ChunkDigestConflictError",
    "ChunkOutOfOrderError",
    "ChunkReceipt",
    "DUPLICATE",
    "FAILED_TERMINAL",
    "FILE_TYPE_WHITELIST",
    "FinalizeAttempt",
    "FinalizeResult",
    "INTERRUPTED_RETRYABLE",
    "MATERIAL_CATEGORIES",
    "MAX_SUBMISSION_BYTES",
    "MERGED",
    "MaterialStorePort",
    "PENDING_VERIFICATION",
    "RECEIVING",
    "SessionNotFoundError",
    "SessionStateError",
    "SessionView",
    "SizeLimitExceededError",
    "StorageIoError",
    "TypeNotAllowedError",
    "UploadSession",
    "UploadTransferService",
    "XferError",
]
