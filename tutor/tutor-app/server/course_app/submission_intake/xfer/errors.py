"""SI-XFER 错误类型（IC-SI-01 错误语义）。

冻结错误码沿用父契约值域：SESSION_NOT_FOUND、CHUNK_OUT_OF_ORDER、
SIZE_LIMIT_EXCEEDED、TYPE_NOT_ALLOWED（L09 SI-API 分别映射
404/409/413 PAYLOAD_TOO_LARGE/415 UNSUPPORTED_MEDIA_TYPE，HTTP 映射不在本层）。
CHUNK_DIGEST_CONFLICT 与 ILLEGAL_STATE 为包内追加的内部错误码（字段只追加规则），
不改变父契约冻结集合。STORAGE_IO_FAILED 由 SI-STORE 端口抛出并原样透传。
"""
from __future__ import annotations


class XferError(Exception):
    """SI-XFER 命令错误基类；`code` 为对外稳定错误码。"""

    code = "XFER_ERROR"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class SessionNotFoundError(XferError):
    """未知 session_id / submission_uuid。"""

    code = "SESSION_NOT_FOUND"


class ChunkOutOfOrderError(XferError):
    """分片序号不等于 next_expected_seq（L2D-002 严格顺序）；可续传重试。"""

    code = "CHUNK_OUT_OF_ORDER"


class ChunkDigestConflictError(XferError):
    """session_id+seq 已存在但摘要不同；冲突不覆盖原分片。"""

    code = "CHUNK_DIGEST_CONFLICT"


class SizeLimitExceededError(XferError):
    """累计或单片大小超过 500MB（KD-004）；映射 PAYLOAD_TOO_LARGE 语义。"""

    code = "SIZE_LIMIT_EXCEEDED"


class TypeNotAllowedError(XferError):
    """材料类别或文件类型不在 CT-001 白名单（KD-004）；映射 UNSUPPORTED_MEDIA_TYPE 语义。"""

    code = "TYPE_NOT_ALLOWED"


class SessionStateError(XferError):
    """会话处于不可写状态（merged/pending_verification/failed_terminal/已过期）。

    包内内部错误码；对外由 L09 映射为既有父错误分类。
    """

    code = "ILLEGAL_STATE"
