"""CT-003 / CT-013 FastAPI APIRouter（不挂载；由集成方注册到 DU-2 应用）。

- POST /api/v1/courses/verify-membership（CT-003，VERIFIER）
- POST /api/v1/courses/{course_id}/roster（CT-013，ADMIN）

应答字段与 contracts/ct-003.json、ct-013.json 一致。
教师会话鉴权（AUTH_INVALID/FORBIDDEN + AccessDeniedLogged，KD-005）属 DU-2
平台面，由集成方在挂载时以依赖注入接入；本叶子不实现（delegated，见完成报告）。
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from course_app.course_roster import admin, verifier
from course_app.course_roster.errors import (
    ERROR_ROSTER_UNAVAILABLE,
    CourseNotFoundError,
    RosterUnavailableError,
)

SessionScopeFactory = Callable[[], AbstractContextManager[Session]]


class VerifyMembershipRequest(BaseModel):
    """CT-003 请求（contracts/ct-003.json request，additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    invite_code: str = Field(min_length=1)
    student_name: str = Field(min_length=1)
    group_name: str = Field(min_length=1)


class VerifyMembershipResponse(BaseModel):
    """CT-003 应答（required: verified, course_id；reason 仅 verified=false 时返回）。"""

    model_config = ConfigDict(extra="forbid")

    verified: bool
    course_id: str
    reason: str | None = None


class RosterEntryPayload(BaseModel):
    """CT-013 roster_entries[] 元素；空串等格式错误由服务层逐项报告（conflicts[]）。"""

    model_config = ConfigDict(extra="forbid")

    student_name: str
    group_name: str


class RosterImportRequest(BaseModel):
    """CT-013 请求体（course_id 为路径参数；additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    roster_entries: list[RosterEntryPayload] = Field(min_length=1)


class ImportResultPayload(BaseModel):
    """CT-013 import_result（契约内 additionalProperties=true，此处不扩展字段）。"""

    imported_count: int = Field(ge=0)
    skipped_duplicates: list[dict]
    conflicts: list[dict]


class RosterImportResponse(BaseModel):
    """CT-013 应答（required: import_result；additionalProperties=false）。"""

    model_config = ConfigDict(extra="forbid")

    import_result: ImportResultPayload


def _roster_unavailable_response() -> JSONResponse:
    # CT-003 错误语义：不向调用方暴露内部错误细节
    return JSONResponse(
        status_code=503,
        content={
            "code": ERROR_ROSTER_UNAVAILABLE,
            "message": "course roster temporarily unavailable; safe to retry",
        },
    )


def create_router(session_scope_factory: SessionScopeFactory) -> APIRouter:
    """装配 CT-003/CT-013 路由（/api/v1 前缀，KD-005）；不挂载，挂载点由集成方决定。

    session_scope_factory：返回单事务会话上下文管理器
    （如 functools.partial(course_app.db.session_scope, engine)）。
    CT-003 结论与校验记录在同一事务提交后才应答（P4：未成功记录则不应答结论）。
    """
    router = APIRouter(prefix="/api/v1/courses", tags=["course-roster"])

    @router.post(
        "/verify-membership",
        response_model=VerifyMembershipResponse,
        response_model_exclude_none=True,
    )
    def _verify_membership(payload: VerifyMembershipRequest):
        try:
            with session_scope_factory() as session:
                outcome = verifier.verify_membership(
                    session,
                    invite_code=payload.invite_code,
                    student_name=payload.student_name,
                    group_name=payload.group_name,
                )
        except (RosterUnavailableError, SQLAlchemyError):
            return _roster_unavailable_response()
        return VerifyMembershipResponse(
            verified=outcome.verified, course_id=outcome.course_id, reason=outcome.reason
        )

    @router.post("/{course_id}/roster", response_model=RosterImportResponse)
    def _import_roster(course_id: str, payload: RosterImportRequest):
        try:
            with session_scope_factory() as session:
                result = admin.import_roster(
                    session,
                    course_id=course_id,
                    entries=[e.model_dump() for e in payload.roster_entries],
                )
        except CourseNotFoundError:
            return JSONResponse(
                status_code=404, content={"code": "NOT_FOUND", "message": "course not found"}
            )
        return RosterImportResponse(
            import_result=ImportResultPayload(
                imported_count=result.imported_count,
                skipped_duplicates=result.skipped_duplicates,
                conflicts=result.conflicts,
            )
        )

    return router
