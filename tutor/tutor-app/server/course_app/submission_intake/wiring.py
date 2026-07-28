"""MOD-02 集成接线（Integration Owner 所有）：IC-SI-01 真实接线 L09 → L08。

XferTransferAdapter 把 L09 的 TransferSessionPort（ingest 粒度）映射到
L08 UploadTransferService（create_session / append_chunk / finalize）。

纪律：
- 仅做端口形状适配与错误码透传（SIZE_LIMIT_EXCEEDED / TYPE_NOT_ALLOWED 由
  L09 映射 413/415；其余错误以 failure_reason 表达，不伪造成功）；
- 分片字节来源：Phase 1 契约落地以 content_ref 为传输占位，真实 multipart
  二进制接入归 backfill；本适配器经 content_loader 注入字节来源（默认按
  content_ref 字面编码，仅集成测试使用）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from course_app.submission_intake.api.ports import (
    XFER_ERROR_SIZE_LIMIT,
    XFER_ERROR_TYPE_NOT_ALLOWED,
    XFER_STATE_FAILED_TERMINAL,
    XFER_STATE_MERGED,
    MaterialChunk,
    TransferResult,
)
from course_app.submission_intake.xfer.errors import (
    SizeLimitExceededError,
    TypeNotAllowedError,
    XferError,
)
from course_app.submission_intake.xfer.service import UploadTransferService
from course_app.submission_intake.xfer.store import StorageIoError

ContentLoader = Callable[[MaterialChunk], bytes]


def _default_content_loader(chunk: MaterialChunk) -> bytes:
    """默认字节来源：content_ref 字面编码（仅集成测试传输约定）。"""
    return (chunk.content_ref or "").encode("utf-8")


class XferTransferAdapter:
    """IC-SI-01 端口实现：L08 真实会话承载 L09 ingest 语义（幂等、可续传）。"""

    def __init__(
        self,
        xfer: UploadTransferService,
        content_loader: ContentLoader = _default_content_loader,
    ) -> None:
        self._xfer = xfer
        self._load = content_loader

    def ingest(
        self,
        *,
        submission_uuid: str,
        declared_categories: Sequence[str],
        chunks: Sequence[MaterialChunk],
    ) -> TransferResult:
        try:
            view = self._xfer.create_session(
                submission_uuid=submission_uuid, declared_categories=declared_categories
            )
            # 断点续传：已确认分片跳过（checkpoint 只记已确认分片，INV-5）
            for seq in range(view.next_expected_seq, len(chunks)):
                chunk = chunks[seq]
                self._xfer.append_chunk(
                    session_id=view.session_id,
                    seq=seq,
                    category=chunk.category,
                    content=self._load(chunk),
                    media_type=chunk.media_type,
                )
            final = self._xfer.finalize(session_id=view.session_id)
        except (SizeLimitExceededError, TypeNotAllowedError) as exc:
            return TransferResult(
                state=XFER_STATE_FAILED_TERMINAL,
                failure_reason=str(exc),
                error_code=(
                    XFER_ERROR_SIZE_LIMIT
                    if isinstance(exc, SizeLimitExceededError)
                    else XFER_ERROR_TYPE_NOT_ALLOWED
                ),
            )
        except StorageIoError as exc:
            # 存储暂态失败：会话保留 interrupted_retryable，客户端可整体重试（幂等）
            return TransferResult(
                state=XFER_STATE_FAILED_TERMINAL,
                failure_reason=f"retryable storage failure: {exc}",
            )
        except XferError as exc:
            return TransferResult(
                state=XFER_STATE_FAILED_TERMINAL, failure_reason=str(exc)
            )
        return TransferResult(state=XFER_STATE_MERGED, material_refs=tuple(final.material_refs))
