"""CT-011 删除确认 FastAPI APIRouter（不挂载；挂载归 T-B03d 组合根/平台）。

- POST /api/v1/teacher/deletion-batches/{batch_id}/confirm：Bearer 会话认证
  （ACCESS-GATE）→ 课程范围授权（拒绝 403 + AccessDeniedLogged 由 GATE 记录）→
  RetentionService.confirm_batch（审计先行 + CT-012 发布）。
- 请求体与 contracts/ct-011.json request 一致（confirm 恒 true、exclusions[]
  可选、additionalProperties=false）；响应含 batch_id/batch_status/
  pending_deletion_scope（required），附 retention_due_at/exclusions
  （additionalProperties=true）。
- 错误码只映射 CT-011 父冻结值：AUTH_INVALID(401)/FORBIDDEN(403)/
  NOT_FOUND(404)/BATCH_NOT_EXPIRED(409)。
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..access_gate.errors import AccessDeniedError, AuthInvalidError
from ..access_gate.service import AccessGateService
from .errors import BatchNotExpiredError, BatchNotFoundError, RetentionError
from .service import RetentionService

#: AccessDeniedLogged 审计 source 标识（追加式日志来源列）。
SOURCE_CT011 = "CT-011-retention"


class ConfirmRequest(BaseModel):
    """CT-011 请求体（contracts/ct-011.json request，additionalProperties=false）。

    batch_id 为路径参数（契约 required 中的 batch_id 由路径供给）。
    """

    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    exclusions: list[str] = Field(default_factory=list)


def _error_response(code: str, message: str, http_status: int) -> JSONResponse:
    """冻结错误码 → HTTP 映射（不新增公共错误码）。"""
    return JSONResponse(
        status_code=http_status,
        content={"code": code, "message": message},
    )


def create_router(
    *,
    service: RetentionService,
    access_gate: AccessGateService,
) -> APIRouter:
    """装配 CT-011 删除确认路由（/api/v1 前缀）；不挂载。"""
    router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-retention"])

    @router.post("/deletion-batches/{batch_id}/confirm")
    def _confirm(batch_id: str, request: Request, body: ConfirmRequest):
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return _error_response(
                "AUTH_INVALID", "missing or malformed Authorization header", 401
            )
        try:
            identity = access_gate.verify_session(token.strip())
        except AuthInvalidError as exc:
            return _error_response("AUTH_INVALID", str(exc), 401)
        course_id = service.batch_course_id(batch_id)
        if course_id is None:
            return _error_response(
                "NOT_FOUND", f"deletion batch {batch_id!r} not found", 404
            )
        try:
            access_gate.require_grant(
                identity,
                course_id=course_id,
                action="confirm.deletion",
                source=SOURCE_CT011,
            )
        except AccessDeniedError as exc:
            return _error_response("FORBIDDEN", str(exc), 403)
        try:
            result = service.confirm_batch(
                batch_id=batch_id,
                operator=identity.teacher_id,
                exclusions=body.exclusions,
            )
        except BatchNotFoundError as exc:
            return _error_response("NOT_FOUND", str(exc), 404)
        except BatchNotExpiredError as exc:
            return _error_response("BATCH_NOT_EXPIRED", str(exc), 409)
        except RetentionError as exc:
            return _error_response(exc.code, str(exc), exc.http_status)
        return {
            "batch_id": result.batch_id,
            "batch_status": result.batch_status,
            "pending_deletion_scope": list(result.pending_deletion_scope),
        }

    return router


__all__ = ["ConfirmRequest", "SOURCE_CT011", "create_router"]
