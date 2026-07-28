"""CT-001 / CT-002 / auth-token FastAPI APIRouter（不挂载；挂载归 backfill/平台）。

- POST /api/v1/auth/token：邀请码+姓名+小组 → 名单核对（IC-SI-03 注入）→
  不透明令牌签发（服务端存哈希，ST-06 审计，TTL 30 天，DD-004）。
- POST /api/v1/submissions：Bearer 认证 → 幂等（submission_uuid）→ 归属校验 →
  分片会话与材料接收（IC-SI-01 端口注入）→ 聚合确认（IC-SI-04）→ 30 秒内应答。
- GET /api/v1/submissions/{submission_uuid}：只读状态查询（CT-002）。

应答字段与 contracts/ct-001.json、ct-002.json、auth-token.json 一致；
错误码只映射父冻结值（见 errors.py）。REJECTED_MEMBERSHIP 为业务终态应答
（status=rejected，HTTP 200），不是 HTTP 错误。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Literal, TypeVar

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from course_app.submission_intake.core import CommandResult, SubmissionCoreService
from course_app.submission_intake.core import status as st

from .errors import AuthInvalidError, SiApiError, ValidationFailedError
from .models import Base as _AuthBase  # noqa: F401  （确保 ST-06 元数据随包导入）
from .orchestrator import SYNC_BUDGET_SECONDS, IntakeOrchestrator
from .ports import (
    MaterialChunk,
    MembershipVerifierPort,
    TransferSessionPort,
)
from .tokens import TOKEN_TTL_SECONDS, AuthContext, TokenService

SessionScopeFactory = Callable[[], AbstractContextManager[Session]]

#: CT-001 材料类别冻结枚举（contracts/ct-001.json material_chunks[].category）。
Category = Literal["对话", "代码", "截图", "结果"]


class AuthTokenRequest(BaseModel):
    """auth-token 请求（contracts/auth-token.json request，additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    invite_code: str = Field(min_length=1)
    student_name: str = Field(min_length=1)
    group_name: str = Field(min_length=1)


class MaterialChunkPayload(BaseModel):
    """CT-001 material_chunks[] 元素（chunk 级 additionalProperties=true）。"""

    model_config = ConfigDict(extra="allow")

    category: Category
    filename: str | None = None
    media_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    content_ref: str | None = None


class SubmissionRequest(BaseModel):
    """CT-001 请求（contracts/ct-001.json request，additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    submission_uuid: str = Field(min_length=1)
    invite_code: str = Field(min_length=1)
    student_name: str = Field(min_length=1)
    group_name: str = Field(min_length=1)
    assignment: str = Field(min_length=1)
    material_chunks: list[MaterialChunkPayload]


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _error_response(exc: SiApiError) -> JSONResponse:
    """冻结错误码 → HTTP 映射；内部暂态失败不携带新公共码、不暴露内部细节。"""
    if exc.http_status >= 500:
        # 暂态/内部失败：不带 code 字段（不新增公共错误码），提示经 CT-002 查证。
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": "transient failure; retry or query status via CT-002"},
        )
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": str(exc)},
    )


PayloadT = TypeVar("PayloadT", bound=BaseModel)


async def _parse_body(request: Request, model: type[PayloadT]) -> PayloadT:
    try:
        raw = await request.json()
    except json.JSONDecodeError as exc:
        raise ValidationFailedError("request body must be valid JSON") from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailedError(f"request validation failed: {exc.title}") from exc


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthInvalidError("missing or malformed Authorization header")
    return token.strip()


def _received_payload(result: CommandResult) -> dict:
    """CT-001 response_received（contracts/ct-001.json，additionalProperties=false）。"""
    return {
        "submission_id": result.submission_id,
        "received_at": _as_utc(result.received_at).isoformat(),
        "status": "received",
        "missing_items": list(result.missing_items),
    }


def _rejected_payload(result: CommandResult) -> dict:
    """CT-001 response_rejected（REJECTED_MEMBERSHIP 业务终态，HTTP 200）。"""
    return {
        "status": "rejected",
        "rejection_reason": result.failure_reason or "REJECTED_MEMBERSHIP",
    }


def create_router(
    *,
    session_factory: SessionScopeFactory,
    membership_verifier: MembershipVerifierPort,
    transfer_port: TransferSessionPort,
    core_service: SubmissionCoreService,
    token_ttl_seconds: int = TOKEN_TTL_SECONDS,
    sync_budget_seconds: float = SYNC_BUDGET_SECONDS,
) -> APIRouter:
    """装配 CT-001/CT-002/auth-token 路由（/api/v1 前缀）；不挂载。

    依赖注入：
    - session_factory：ST-06 事务会话（如 functools.partial(db.session_scope, engine)）；
    - membership_verifier：IC-SI-03 端口（测试可注入 L01 verify_membership 包装）；
    - transfer_port：IC-SI-01 冻结端口（L08 同波次未集成，注入 stub）；
    - core_service：IC-SI-04 实现（L02 SubmissionCoreService）或 stub。
    """
    tokens = TokenService(session_factory, ttl_seconds=token_ttl_seconds)
    orchestrator = IntakeOrchestrator(
        core_service=core_service,
        transfer_port=transfer_port,
        membership_verifier=membership_verifier,
        budget_seconds=sync_budget_seconds,
    )

    router = APIRouter(prefix="/api/v1", tags=["submission-intake"])

    def _authenticate(request: Request) -> AuthContext:
        return tokens.authenticate(_bearer_token(request))

    @router.post("/auth/token")
    async def _issue_token(request: Request):
        try:
            payload = await _parse_body(request, AuthTokenRequest)
            membership = orchestrator.verify_membership(
                invite_code=payload.invite_code,
                student_name=payload.student_name,
                group_name=payload.group_name,
            )
            issued = tokens.issue(
                membership=membership,
                invite_code=payload.invite_code,
                student_name=payload.student_name,
                group_name=payload.group_name,
                request_id=request.headers.get("x-request-id"),
            )
        except SiApiError as exc:
            return _error_response(exc)
        return {
            "access_token": issued.access_token,
            "token_type": issued.token_type,
            "expires_in": issued.expires_in,
        }

    @router.post("/submissions")
    async def _create_submission(request: Request):
        try:
            _authenticate(request)
            payload = await _parse_body(request, SubmissionRequest)
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
        except SiApiError as exc:
            return _error_response(exc)
        if result.status == st.RECEIVED:
            return _received_payload(result)
        if result.status == st.REJECTED:
            return _rejected_payload(result)
        # upload_failed 等：不伪造 received；真实状态经 CT-002 可查。
        return JSONResponse(
            status_code=500,
            content={"detail": "intake incomplete; query status via CT-002"},
        )

    @router.get("/submissions/{submission_uuid}")
    def _get_submission(submission_uuid: str, request: Request):
        try:
            _authenticate(request)
            view = orchestrator.query(submission_uuid)
        except SiApiError as exc:
            return _error_response(exc)
        payload = {
            "submission_id": view.submission_id,
            "status": view.status,
            "missing_items": list(view.missing_items),
        }
        # failure_reason 仅在 upload_failed / rejected / scoring_failed 时返回（CT-002）。
        if view.failure_reason is not None:
            payload["failure_reason"] = view.failure_reason
        return payload

    return router
