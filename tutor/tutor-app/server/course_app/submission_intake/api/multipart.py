"""CT-001 真实 multipart/form-data 二进制接入与分片会话协议（T-B01d，KD-004/005）。

协议事实来源：plugin/src/upload_client/session-driver.js（L10）。冻结 CT-001
为单端点 `POST /api/v1/submissions`（contracts/ct-001.json endpoint），分片协议
以 `phase` 字段区分子协议步骤（create_session / chunk / merge），属冻结
versioning 注记「分片协议字段向后兼容追加」范围，未新增线上端点、未改契约。

本模块提供组合根可挂载的 router（正式挂载归 T-B03d）：

- multipart/form-data：元数据 JSON part（`metadata`）+ 二进制分片 parts；
  流式读取请求体，单次请求 500MB 上限守卫（KD-004）；
- 分片会话协议（JSON 或 multipart 元数据承载）：
  - phase=create_session：建/复用上传会话（submission_uuid 幂等），登记会话身份；
  - phase=chunk：追加二进制分片（严格顺序由 L08 承载；重放同摘要去重）；
  - phase=merge：全部分片确认后驱动既有 L09 编排（IC-SI-01 适配器短路 +
    IC-SI-03 实时归属校验 + IC-SI-04 聚合确认），应答与 CT-001 冻结 schema 一致；
- JSON 兼容通道：无 phase 的 JSON 请求按既有 L09 行为处理（content_ref 占位
  通道不回归，供测试与本地工具）。

错误映射与 L09 错误码表一致（errors.py）：413 PAYLOAD_TOO_LARGE、
415 UNSUPPORTED_MEDIA_TYPE、401 AUTH_INVALID、400 VALIDATION_FAILED；
存储暂态失败映射 503 暂态（不带公共错误码，不暴露内部细节）。

已知边界：分片会话身份（invite_code/姓名/小组/作业与分片元数据）按 upload_session_id
进程内登记；进程重启后 merge 阶段无法恢复身份，将应答 400，客户端清除本地
checkpoint 后重发 create_session 即可幂等恢复（L08 会话与已确认分片在库，重放
按 duplicate 去重）。持久化身份表需新增迁移，超出本任务允许路径，见完成记录风险。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from email.message import Message as _HeaderMessage
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from course_app.submission_intake.core import status as st
from course_app.submission_intake.xfer.errors import (
    SessionNotFoundError,
    SizeLimitExceededError,
    TypeNotAllowedError,
    XferError,
)
from course_app.submission_intake.xfer.service import (
    MAX_SUBMISSION_BYTES,
    MERGED as XFER_MERGED,
    PENDING_VERIFICATION as XFER_PENDING_VERIFICATION,
    UploadTransferService,
)
from course_app.submission_intake.xfer.store import StorageIoError

from .errors import (
    PayloadTooLargeError,
    SiApiError,
    UnsupportedMediaTypeError,
    ValidationFailedError,
)
from .orchestrator import IntakeOrchestrator
from .ports import MaterialChunk
from .router import (
    SubmissionRequest,
    _bearer_token,
    _error_response,
    _received_payload,
    _rejected_payload,
)
from .tokens import TOKEN_TTL_SECONDS, TokenService

SessionScopeFactory = Callable[[], AbstractContextManager[Session]]

#: 单次请求体 500MB 上限守卫（KD-004；累计内容上限另由 L08 在会话维度强制）。
MAX_REQUEST_BYTES = MAX_SUBMISSION_BYTES

#: 单请求 multipart part 数上限（防滥用；正常提交分片数远小于此）。
_MAX_PARTS = 1024

_PHASE_CREATE_SESSION = "create_session"
_PHASE_CHUNK = "chunk"
_PHASE_MERGE = "merge"


class _StorageTransientError(SiApiError):
    """SI-STORE I/O 暂态失败 → 503（不带公共错误码，客户端按幂等键重试）。"""

    code = "STORAGE_IO_TRANSIENT"  # 内部标识，不出现在应答体
    http_status = 503


@dataclass(frozen=True)
class _Part:
    """单个 multipart part（表单字段或文件）。"""

    name: str
    filename: str | None
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class _SessionIdentity:
    """create_session 登记的分片会话身份与分片元数据（merge 阶段编排输入）。"""

    submission_uuid: str
    invite_code: str
    student_name: str
    group_name: str
    assignment: str
    chunks: tuple[MaterialChunk, ...]


def _header_params(header: str, value: str) -> _HeaderMessage:
    msg = _HeaderMessage()
    msg[header] = value
    return msg


async def _read_body_with_guard(request: Request, limit: int) -> bytes:
    """流式读取请求体；Content-Length 预检 + 累计超 limit 即 413。"""
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                raise PayloadTooLargeError("request body exceeds 500MB limit")
        except ValueError as exc:
            raise ValidationFailedError("invalid Content-Length header") from exc
    buf = bytearray()
    async for piece in request.stream():
        buf.extend(piece)
        if len(buf) > limit:
            raise PayloadTooLargeError("request body exceeds 500MB limit")
    return bytes(buf)


def _parse_multipart(body: bytes, content_type: str) -> list[_Part]:
    """解析 multipart/form-data 缓冲体（stdlib only，不引入新依赖）。"""
    msg = _header_params("content-type", content_type)
    if msg.get_content_type() != "multipart/form-data":
        raise ValidationFailedError("content-type must be multipart/form-data")
    boundary = msg.get_param("boundary", header="content-type")
    if not boundary:
        raise ValidationFailedError("multipart boundary missing")
    try:
        delimiter = b"--" + str(boundary).encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValidationFailedError("multipart boundary must be ASCII") from exc
    segments = body.split(delimiter)
    if len(segments) < 2:
        raise ValidationFailedError("malformed multipart body")
    parts: list[_Part] = []
    for segment in segments[1:]:
        if segment.startswith(b"--"):
            break  # 结束标记（其后为 epilogue）
        if segment.startswith(b"\r\n"):
            segment = segment[2:]
        # 分隔符前的 CRLF 属分隔符（RFC 2046），不属于 part 内容。
        if segment.endswith(b"\r\n"):
            segment = segment[:-2]
        header_block, sep, data = segment.partition(b"\r\n\r\n")
        if not sep:
            raise ValidationFailedError("malformed multipart part headers")
        headers: dict[str, str] = {}
        for line in header_block.split(b"\r\n"):
            hname, hsep, hvalue = line.partition(b":")
            if not hsep:
                raise ValidationFailedError("malformed multipart part header line")
            headers[hname.strip().lower().decode("latin-1")] = hvalue.strip().decode(
                "latin-1"
            )
        disp = _header_params(
            "content-disposition", headers.get("content-disposition", "")
        )
        if disp.get_content_disposition() != "form-data":
            raise ValidationFailedError("multipart part must be form-data")
        name = disp.get_param("name", header="content-disposition")
        if not name:
            raise ValidationFailedError("multipart part missing name")
        filename = disp.get_param("filename", header="content-disposition")
        parts.append(
            _Part(
                name=str(name),
                filename=str(filename) if filename is not None else None,
                content_type=headers.get("content-type"),
                data=data,
            )
        )
        if len(parts) > _MAX_PARTS:
            raise ValidationFailedError("too many multipart parts")
    return parts


def _metadata_json(part: _Part) -> dict:
    try:
        raw = json.loads(part.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationFailedError("metadata part must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValidationFailedError("metadata part must be a JSON object")
    return raw


def _required_str(raw: dict, field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValidationFailedError(f"{field_name} is required")
    return value


def _chunk_index(raw: dict) -> int:
    value = raw.get("chunk_index")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationFailedError("chunk_index must be a non-negative integer")
    return value


def _chunk_meta(raw: Any) -> MaterialChunk:
    """校验分片元数据（类别冻结枚举由 MaterialChunk 消费方 L08 再次校验）。"""
    if not isinstance(raw, dict):
        raise ValidationFailedError("chunk metadata must be an object")
    category = raw.get("category")
    if not isinstance(category, str) or not category:
        raise ValidationFailedError("chunk.category is required")
    filename = raw.get("filename")
    media_type = raw.get("media_type")
    size_bytes = raw.get("size_bytes")
    if filename is not None and not isinstance(filename, str):
        raise ValidationFailedError("chunk.filename must be a string")
    if media_type is not None and not isinstance(media_type, str):
        raise ValidationFailedError("chunk.media_type must be a string")
    if size_bytes is not None and (
        isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0
    ):
        raise ValidationFailedError("chunk.size_bytes must be a non-negative integer")
    return MaterialChunk(
        category=category,
        filename=filename,
        media_type=media_type,
        size_bytes=size_bytes,
        content_ref=raw.get("content_ref") if isinstance(raw.get("content_ref"), str) else None,
    )


def create_multipart_router(
    *,
    session_factory: SessionScopeFactory,
    xfer: UploadTransferService,
    orchestrator: IntakeOrchestrator,
    token_ttl_seconds: int = TOKEN_TTL_SECONDS,
    max_request_bytes: int = MAX_REQUEST_BYTES,
) -> APIRouter:
    """装配 CT-001 multipart/分片协议路由（/api/v1 前缀）；不挂载。

    依赖注入：
    - session_factory：ST-06 事务会话（Bearer 认证复用 L09 TokenService）；
    - xfer：L08 UploadTransferService 真实实例（IC-SI-01 端口实现）；
    - orchestrator：L09 IntakeOrchestrator（其 transfer_port 适配器必须指向同一
      xfer 实例，merge/单次上传经幂等短路复用已确认分片）；
    - max_request_bytes：单次请求体守卫上限（默认 CT-001 冻结 500MB；测试可缩小）。
    """
    tokens = TokenService(session_factory, ttl_seconds=token_ttl_seconds)
    # 分片会话身份登记（upload_session_id → 身份与分片元数据；进程内，见模块 docstring）。
    session_identities: dict[str, _SessionIdentity] = {}

    router = APIRouter(prefix="/api/v1", tags=["submission-intake-multipart"])

    def _authenticate(request: Request) -> None:
        tokens.authenticate(_bearer_token(request))

    def _final_response(result) -> Any:
        if result.status == st.RECEIVED:
            return _received_payload(result)
        if result.status == st.REJECTED:
            return _rejected_payload(result)
        # upload_failed 等：不伪造 received；真实状态经 CT-002 可查。
        return JSONResponse(
            status_code=500,
            content={"detail": "intake incomplete; query status via CT-002"},
        )

    def _map_append_error(exc: Exception) -> SiApiError:
        """L08 分片/会话错误 → L09 冻结错误分类（413/415/400；暂态 503）。"""
        if isinstance(exc, SizeLimitExceededError):
            return PayloadTooLargeError("submission exceeds 500MB limit")
        if isinstance(exc, TypeNotAllowedError):
            return UnsupportedMediaTypeError("material type not in whitelist")
        if isinstance(exc, StorageIoError):
            return _StorageTransientError("transient storage failure; retry")
        if isinstance(exc, XferError):
            # CHUNK_OUT_OF_ORDER / CHUNK_DIGEST_CONFLICT / SESSION_NOT_FOUND /
            # ILLEGAL_STATE：客户端协议错误，不新增公共错误码。
            return ValidationFailedError(str(exc))
        return ValidationFailedError("chunk rejected")

    def _append_chunk(
        *, session_id: str, seq: int, meta: MaterialChunk, content: bytes
    ) -> dict:
        try:
            result = xfer.append_chunk(
                session_id=session_id,
                seq=seq,
                category=meta.category,
                content=content,
                media_type=meta.media_type,
            )
        except (XferError, StorageIoError) as exc:
            raise _map_append_error(exc) from exc
        return {
            "acked": True,
            "chunk_index": result.seq,
            "duplicate": result.duplicate,
            "received_bytes": result.received_bytes,
            "next_expected_seq": result.next_expected_seq,
        }

    # ---- 分片会话协议（形状以 session-driver.js 为准） ----

    def _phase_create_session(raw: dict) -> dict:
        submission_uuid = _required_str(raw, "submission_uuid")
        chunks_raw = raw.get("material_chunks")
        if not isinstance(chunks_raw, list) or not chunks_raw:
            raise ValidationFailedError("material_chunks must be a non-empty array")
        metas = tuple(_chunk_meta(c) for c in chunks_raw)
        declared = tuple(dict.fromkeys(m.category for m in metas))
        try:
            view = xfer.create_session(
                submission_uuid=submission_uuid, declared_categories=declared
            )
        except (XferError, StorageIoError) as exc:
            raise _map_append_error(exc) from exc
        session_identities[view.session_id] = _SessionIdentity(
            submission_uuid=submission_uuid,
            invite_code=_required_str(raw, "invite_code"),
            student_name=_required_str(raw, "student_name"),
            group_name=_required_str(raw, "group_name"),
            assignment=_required_str(raw, "assignment"),
            chunks=metas,
        )
        return {
            "upload_session_id": view.session_id,
            "submission_uuid": submission_uuid,
            "next_expected_seq": view.next_expected_seq,
        }

    def _phase_chunk(raw: dict, content: bytes | None) -> dict:
        session_id = _required_str(raw, "upload_session_id")
        seq = _chunk_index(raw)
        chunk_raw = raw.get("chunk")
        meta = _chunk_meta(chunk_raw)
        if content is None:
            content = _inline_content(chunk_raw)
        return _append_chunk(session_id=session_id, seq=seq, meta=meta, content=content)

    def _phase_merge(raw: dict) -> Any:
        session_id = _required_str(raw, "upload_session_id")
        submission_uuid = _required_str(raw, "submission_uuid")
        identity = session_identities.get(session_id)
        if identity is None or identity.submission_uuid != submission_uuid:
            raise ValidationFailedError(
                "unknown upload session identity; resend create_session"
            )
        try:
            view = xfer.get_session(submission_uuid=submission_uuid)
        except SessionNotFoundError as exc:
            raise ValidationFailedError(str(exc)) from exc
        if view.next_expected_seq != len(identity.chunks):
            raise ValidationFailedError(
                f"chunks incomplete: {view.next_expected_seq}/{len(identity.chunks)} confirmed"
            )
        result = orchestrator.submit(
            submission_uuid=identity.submission_uuid,
            invite_code=identity.invite_code,
            student_name=identity.student_name,
            group_name=identity.group_name,
            assignment=identity.assignment,
            chunks=identity.chunks,
        )
        return _final_response(result)

    def _inline_content(chunk_raw: Any) -> bytes:
        """JSON 通道分片字节来源：content（utf-8 字符串）或 content_ref 字面占位。"""
        if isinstance(chunk_raw, dict):
            content = chunk_raw.get("content")
            if isinstance(content, str):
                return content.encode("utf-8")
            content_ref = chunk_raw.get("content_ref")
            if isinstance(content_ref, str):
                return content_ref.encode("utf-8")
        raise ValidationFailedError("chunk requires binary part, content, or content_ref")

    # ---- JSON 兼容通道（无 phase：既有 L09 CT-001 行为，content_ref 占位） ----

    def _legacy_submit(raw: dict) -> Any:
        try:
            payload = SubmissionRequest.model_validate(raw)
        except ValidationError as exc:
            raise ValidationFailedError(
                f"request validation failed: {exc.title}"
            ) from exc
        chunks = [
            MaterialChunk(
                category=c.category,
                filename=c.filename,
                media_type=c.media_type,
                size_bytes=c.size_bytes,
                content_ref=c.content_ref,
            )
            for c in payload.material_chunks
        ]
        result = orchestrator.submit(
            submission_uuid=payload.submission_uuid,
            invite_code=payload.invite_code,
            student_name=payload.student_name,
            group_name=payload.group_name,
            assignment=payload.assignment,
            chunks=chunks,
        )
        return _final_response(result)

    # ---- 请求分发 ----

    async def _handle_json(request: Request) -> Any:
        try:
            raw = await request.json()
        except json.JSONDecodeError as exc:
            raise ValidationFailedError("request body must be valid JSON") from exc
        if not isinstance(raw, dict):
            raise ValidationFailedError("request body must be a JSON object")
        phase = raw.get("phase")
        if phase is None:
            return _legacy_submit(raw)
        if phase == _PHASE_CREATE_SESSION:
            return _phase_create_session(raw)
        if phase == _PHASE_CHUNK:
            return _phase_chunk(raw, content=None)
        if phase == _PHASE_MERGE:
            return _phase_merge(raw)
        raise ValidationFailedError(f"unknown phase: {phase}")

    async def _handle_multipart(request: Request) -> Any:
        body = await _read_body_with_guard(request, max_request_bytes)
        parts = _parse_multipart(body, request.headers.get("content-type", ""))
        metadata_parts = [p for p in parts if p.name == "metadata" and p.filename is None]
        if len(metadata_parts) != 1:
            raise ValidationFailedError("exactly one metadata part is required")
        raw = _metadata_json(metadata_parts[0])
        binaries = [p for p in parts if not (p.name == "metadata" and p.filename is None)]
        phase = raw.get("phase")
        if phase in (_PHASE_CREATE_SESSION, _PHASE_MERGE):
            if binaries:
                raise ValidationFailedError(f"{phase} phase must not carry binary parts")
            if phase == _PHASE_CREATE_SESSION:
                return _phase_create_session(raw)
            return _phase_merge(raw)
        if phase == _PHASE_CHUNK:
            if len(binaries) != 1:
                raise ValidationFailedError(
                    "chunk phase requires exactly one binary part"
                )
            return _phase_chunk(raw, content=binaries[0].data)
        if phase is not None:
            raise ValidationFailedError(f"unknown phase: {phase}")
        return _multipart_single_shot(raw, binaries)

    def _multipart_single_shot(raw: dict, binaries: list[_Part]) -> Any:
        """单次 multipart 上传：元数据 + 每分片一个二进制 part（顺序对应）。"""
        if not binaries:
            # 无二进制 part：等价 JSON 兼容通道（content_ref 占位）。
            return _legacy_submit(raw)
        try:
            payload = SubmissionRequest.model_validate(raw)
        except ValidationError as exc:
            raise ValidationFailedError(
                f"request validation failed: {exc.title}"
            ) from exc
        if len(binaries) != len(payload.material_chunks):
            raise ValidationFailedError(
                "binary parts count must match material_chunks count"
            )
        declared = tuple(dict.fromkeys(c.category for c in payload.material_chunks))
        try:
            view = xfer.create_session(
                submission_uuid=payload.submission_uuid, declared_categories=declared
            )
            # 幂等重放：已 merged 会话不可写，跳过追加分片（L08 finalize 幂等）。
            if view.state not in (XFER_MERGED, XFER_PENDING_VERIFICATION):
                for seq, (meta, part) in enumerate(
                    zip(payload.material_chunks, binaries)
                ):
                    xfer.append_chunk(
                        session_id=view.session_id,
                        seq=seq,
                        category=meta.category,
                        content=part.data,
                        media_type=meta.media_type,
                    )
        except (XferError, StorageIoError) as exc:
            raise _map_append_error(exc) from exc
        chunks = [
            MaterialChunk(
                category=c.category,
                filename=c.filename,
                media_type=c.media_type,
                size_bytes=c.size_bytes,
                content_ref=c.content_ref,
            )
            for c in payload.material_chunks
        ]
        result = orchestrator.submit(
            submission_uuid=payload.submission_uuid,
            invite_code=payload.invite_code,
            student_name=payload.student_name,
            group_name=payload.group_name,
            assignment=payload.assignment,
            chunks=chunks,
        )
        return _final_response(result)

    @router.post("/submissions")
    async def _submissions(request: Request):
        try:
            _authenticate(request)
            content_type = request.headers.get("content-type", "").split(";")[0].strip()
            if content_type.lower() == "multipart/form-data":
                return await _handle_multipart(request)
            return await _handle_json(request)
        except SiApiError as exc:
            return _error_response(exc)

    return router
