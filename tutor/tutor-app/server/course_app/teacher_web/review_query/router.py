"""CT-007 教师课程数据查询 FastAPI APIRouter（不挂载；挂载归 backfill/平台）。

视图族端点（/api/v1 前缀，teacher_session 经 Authorization: Bearer 携带）：

- GET /api/v1/teacher/courses：课程列表。
- GET /api/v1/teacher/courses/{course_id}/groups：小组列表
  （可选 ?group_id= 过滤并附 students[]）。
- GET /api/v1/teacher/courses/{course_id}/students/{student_id}：学生详情
  （students[] + submissions[]）。
- GET /api/v1/teacher/courses/{course_id}/submissions/{submission_id}：提交详情
  （material_refs/status/original_grade/dimension_rationales/
  teacher_suggestions/annotations/final_grade/deletion_batches[]，
  scoring_failed 时 failure_reason + retry_record，不伪造等级）。

应答字段与 contracts/ct-007.json 一致；错误码只映射父冻结值
（AUTH_INVALID/FORBIDDEN/NOT_FOUND/VALIDATION_FAILED）。端口失败 → 503
暂态失败，不携带新公共 code，不返回部分成功（LCD-RQ-004）。

依赖注入（进程内，DD-004 同口径）：
- access_gate：ACCESS-GATE 端口（owner backfill；403 + AccessDeniedLogged
  由其实现）；
- read_model：M05-IC-02 端口（owner PROJECTOR/backfill；本叶子注入 stub 或
  表实现均可，但不建读模型表）；
- retention_view：M05-IC-06 端口（owner RETENTION-GOVERNANCE/backfill）。
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .errors import AuthInvalidError, RetryableQueryError, RqError
from .facade import ReviewQueryService, create_facade
from .ports import AccessGatePort, ReadModelQueryPort, RetentionViewPort


def _teacher_session(request: Request) -> str:
    """CT-007 required_fields: [teacher_session]（Bearer/会话凭证）。"""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthInvalidError("missing or malformed Authorization header")
    return token.strip()


def _error_response(exc: RqError) -> JSONResponse:
    """冻结错误码 → HTTP 映射；暂态失败不带 code（不新增公共错误码）。"""
    if exc.http_status >= 500:
        return JSONResponse(
            status_code=exc.http_status,
            content={"detail": "transient failure; retry the query"},
        )
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": str(exc)},
    )


def create_router(
    *,
    access_gate: AccessGatePort,
    read_model: ReadModelQueryPort,
    retention_view: RetentionViewPort,
) -> APIRouter:
    """装配 CT-007 视图族路由（/api/v1 前缀）；不挂载。"""
    service: ReviewQueryService = create_facade(
        access_gate=access_gate,
        read_model=read_model,
        retention_view=retention_view,
    )

    router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-review-query"])

    @router.get("/courses")
    def _list_courses(request: Request):
        try:
            return service.course_list(
                teacher_session=_teacher_session(request)
            )
        except RqError as exc:
            return _error_response(exc)

    @router.get("/courses/{course_id}/groups")
    def _list_groups(course_id: str, request: Request, group_id: str | None = None):
        try:
            return service.group_list(
                teacher_session=_teacher_session(request),
                course_id=course_id,
                group_id=group_id,
            )
        except RqError as exc:
            return _error_response(exc)

    @router.get("/courses/{course_id}/students/{student_id}")
    def _get_student(course_id: str, student_id: str, request: Request):
        try:
            return service.student_detail(
                teacher_session=_teacher_session(request),
                course_id=course_id,
                student_id=student_id,
            )
        except RqError as exc:
            return _error_response(exc)

    @router.get("/courses/{course_id}/submissions/{submission_id}")
    def _get_submission(course_id: str, submission_id: str, request: Request):
        try:
            return service.submission_detail(
                teacher_session=_teacher_session(request),
                course_id=course_id,
                submission_id=submission_id,
            )
        except RqError as exc:
            return _error_response(exc)

    return router


__all__ = ["RetryableQueryError", "create_router"]
