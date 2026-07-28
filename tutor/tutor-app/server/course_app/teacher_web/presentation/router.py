"""CT-009 展示视图生成 FastAPI APIRouter（不挂载；挂载归 backfill/平台）。

- POST /api/v1/teacher/presentations：ACCESS-GATE 端口注入鉴权 → 规范化
  group_ids → 幂等命中返回最新快照 / 读模型装配 + 资格判定 + 快照写入 →
  应答 presentation_id + blocks[]（contracts/ct-009.json）。
- 错误码只映射父冻结值（errors.py）；内部暂态失败不携带新公共码、
  不暴露内部细节。
- 数据源为 M05-IC-02 读模型查询端口（注入）；不做跨模块同步读（LCD-004）。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import TypeVar

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from .coordinator import PresentationCoordinator
from .errors import PresentationError, ValidationFailedError
from .models import Base as _PresentationBase  # noqa: F401  （确保元数据随包导入）
from .output import to_response
from .ports import AccessGatePort, ReadModelQueryPort
from .store import SnapshotStore, default_time_window

SessionScopeFactory = Callable[[], AbstractContextManager[Session]]


class PresentationRequest(BaseModel):
    """CT-009 请求（contracts/ct-009.json request，additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    group_ids: list[str] = Field(min_length=1)


def _error_response(exc: PresentationError) -> JSONResponse:
    """冻结错误码 → HTTP 映射；内部暂态失败不携带新公共码。"""
    if exc.http_status >= 500:
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": "transient failure; retry with the same parameters"},
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


def _validate_group_ids(group_ids: list[str]) -> list[str]:
    """items minLength=1（contracts/ct-009.json request schema）。"""
    if any(not gid.strip() for gid in group_ids):
        raise ValidationFailedError("group_ids items must be non-empty strings")
    return group_ids


def create_router(
    *,
    session_factory: SessionScopeFactory,
    access_gate: AccessGatePort,
    read_model: ReadModelQueryPort,
    time_window_fn: Callable[[], str] = default_time_window,
) -> APIRouter:
    """装配 CT-009 路由（/api/v1 前缀）；不挂载。

    依赖注入：
    - session_factory：ST-PRESENTATION-VIEW 事务会话；
    - access_gate：CMP-ACCESS-GATE 冻结端口（认证 + 课程授权范围）；
    - read_model：M05-IC-02 读模型查询端口（与 L15 同一冻结端口）；
    - time_window_fn：父幂等键时间窗（默认 UTC 自然日；测试可注入）。
    """
    store = SnapshotStore(session_factory)
    coordinator = PresentationCoordinator(
        read_model=read_model, store=store, time_window_fn=time_window_fn
    )

    router = APIRouter(prefix="/api/v1", tags=["teacher-presentation"])

    @router.post("/teacher/presentations")
    async def _create_presentation(request: Request):
        try:
            auth = access_gate.authorize(
                authorization=request.headers.get("authorization")
            )
            payload = await _parse_body(request, PresentationRequest)
            snapshot = coordinator.generate(
                auth=auth, group_ids=_validate_group_ids(payload.group_ids)
            )
        except PresentationError as exc:
            return _error_response(exc)
        return to_response(snapshot)

    return router
