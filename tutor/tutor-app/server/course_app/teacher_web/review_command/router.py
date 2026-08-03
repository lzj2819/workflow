"""CT-008 FastAPI APIRouter（不挂载；挂载归 backfill/平台）。

PUT /api/v1/teacher/submissions/{submission_id}/review：
- ACCESS-GATE 端口注入：会话认证 + 课程范围授权（拒绝 → 401/403，
  AccessDeniedLogged 由 GATE 实现记录，本叶子只调用）；
- 请求/应答字段与 contracts/ct-008.json 一致（additionalProperties=false）；
- request_id 幂等：重复请求返回同一复核记录；
- annotation 与 final_grade 至少其一；final_grade ∈ A–E；
- NO_ORIGINAL_GRADE：scoring_failed 且无原始等级时拒绝设置最终等级；
- adjustment_reason 可选、不强制（TD-09/DD-007）；
- M05-IC-05 模块内事件在业务提交后发布（LCD-004）。
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import ReviewCommandError, ValidationFailedError
from .ports import AccessGatePort, ReviewEventPublisher
from .service import ReviewCommandService


class ReviewRequest(BaseModel):
    """CT-008 请求体（contracts/ct-008.json request，additionalProperties=false）。

    submission_id 为路径参数；annotation 与 final_grade 至少其一由服务层校验。
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    annotation: str | None = None
    final_grade: str | None = Field(default=None, pattern="^[A-E]$")
    adjustment_reason: str | None = None


def _error_response(exc: ReviewCommandError) -> JSONResponse:
    """冻结错误码 → HTTP 映射；不新增公共错误码、不暴露内部细节。"""
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": str(exc)},
    )


def _teacher_session(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def _parse_body(request: Request) -> ReviewRequest:
    try:
        raw = await request.json()
    except json.JSONDecodeError as exc:
        raise ValidationFailedError("request body must be valid JSON") from exc
    try:
        return ReviewRequest.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailedError(f"request validation failed: {exc.title}") from exc


def create_router(
    *,
    service: ReviewCommandService,
    access_gate: AccessGatePort,
    event_publisher: ReviewEventPublisher | None = None,
) -> APIRouter:
    """装配 CT-008 路由（/api/v1 前缀）；不挂载。

    依赖注入：
    - service：ReviewCommandService（GUARD+POLICY+WRITER）；
    - access_gate：ACCESS-GATE 端口（实现归 backfill，测试注入 stub）；
    - event_publisher：M05-IC-05 端口（提交后发布；投影失败按 adjustment_id
      重放，不改变 CT-008 成功响应）。
    """
    router = APIRouter(prefix="/api/v1", tags=["review-command"])

    @router.put("/teacher/submissions/{submission_id}/review")
    async def _put_review(submission_id: str, request: Request):
        try:
            grant = access_gate.authorize(
                teacher_session=_teacher_session(request),
                submission_id=submission_id,
            )
            payload = await _parse_body(request)
            outcome = service.apply_review(
                operator=grant.operator,
                submission_id=submission_id,
                request_id=payload.request_id,
                annotation=payload.annotation,
                final_grade=payload.final_grade,
                adjustment_reason=payload.adjustment_reason,
            )
        except ReviewCommandError as exc:
            return _error_response(exc)
        # M05-IC-05 只在业务写入提交后可见（LCD-004）；失败不回滚已提交记录。
        if event_publisher is not None and outcome.events:
            event_publisher.publish(outcome.events)
        return {"review_record": outcome.payload}

    return router
