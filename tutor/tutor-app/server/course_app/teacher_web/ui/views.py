"""L17 教师网页 SSR 视图（Jinja2 模板 + 少量原生 JS，DD-003 / LCD-TUI-001）。

- 页面壳由服务端渲染；写操作（复核保存、展示生成、删除确认）经注入的
  TeacherApiClient 只消费 CT-007/008/009/011 冻结契约，不新增后端端点语义。
- 会话：登录页只对接会话 API；成功后在 HttpOnly Cookie 中持有不透明会话
  引用，页面 HTML 不回显令牌明文。会话校验由平台/backfill 承担。
- 写操作幂等键（CT-008 request_id）在交互边界生成（LCD-TUI-003）；模板
  原生 JS 在提交期间禁用重复触发，权威幂等仍归服务端。
- 失败优先可见（LCD-TUI-004 / A-005）：scoring_failed 展示真实
  failure_reason 与 retry_record，不显示伪造等级；missing_marks 可见不隐藏。

路由均为 HTML 页面（/teacher/...），不是 API；不挂载（挂载归平台装配）。
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .client import (
    AUTH_INVALID,
    BATCH_NOT_EXPIRED,
    FORBIDDEN,
    GRADES,
    NO_AVAILABLE_SUBMISSION,
    NO_ORIGINAL_GRADE,
    TeacherApiClient,
    TeacherApiError,
)
from .view_models import (
    deletion_batches_vm,
    presentation_vm,
    submission_detail_vm,
)

SESSION_COOKIE = "teacher_session"

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _default_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/teacher/login", status_code=303)


def create_router(
    *,
    api_client: TeacherApiClient,
    templates: Jinja2Templates | None = None,
) -> APIRouter:
    """装配教师网页 SSR 路由；不挂载。api_client 经注入（stub 或真实实现）。"""
    templates = templates or _default_templates()
    router = APIRouter(prefix="/teacher", tags=["teacher-ui"])

    def render(
        request: Request,
        name: str,
        context: dict[str, Any] | None = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request, name, context or {}, status_code=status_code
        )

    def session_token(request: Request) -> str | None:
        token = request.cookies.get(SESSION_COOKIE)
        return token if token else None

    def query_or_page(
        request: Request, **scope: Any
    ) -> tuple[dict[str, Any] | None, HTMLResponse | None]:
        """CT-007 查询 + 统一失败页（AUTH_INVALID→登录；FORBIDDEN→访问拒绝）。"""
        token = session_token(request)
        try:
            return api_client.query_view(teacher_session=token or "", **scope), None
        except TeacherApiError as exc:
            if exc.code == AUTH_INVALID:
                return None, _login_redirect()
            if exc.code == FORBIDDEN:
                # 无权限访问：拒绝读取的呈现；AccessDeniedLogged 由 GATE 承担。
                return None, render(
                    request,
                    "error.html",
                    {"code": FORBIDDEN, "message": "无权限访问该课程资源"},
                    status_code=403,
                )
            return None, render(
                request,
                "error.html",
                {"code": exc.code, "message": str(exc)},
                status_code=502,
            )

    def require_session(request: Request) -> str | None:
        return session_token(request)

    # -- 登录（只对接会话 API） -------------------------------------------

    @router.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        return render(request, "login.html", {})

    @router.post("/login")
    async def login_submit(request: Request):
        form = await request.form()
        account = str(form.get("teacher_account") or "")
        password = str(form.get("password") or "")
        try:
            session = api_client.create_session(
                teacher_account=account, password=password
            )
        except TeacherApiError as exc:
            return render(
                request,
                "login.html",
                {"error": str(exc) or exc.code, "teacher_account": account},
                status_code=401 if exc.code == AUTH_INVALID else 502,
            )
        response = RedirectResponse(url="/teacher/courses", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            session.token,
            httponly=True,
            samesite="lax",
        )
        return response

    # -- CT-007 课程/小组/学生/提交浏览 ------------------------------------

    @router.get("/courses", response_class=HTMLResponse)
    def courses_page(request: Request):
        if require_session(request) is None:
            return _login_redirect()
        payload, page = query_or_page(request)
        if page is not None:
            return page
        return render(
            request,
            "courses.html",
            {
                "courses": list(payload.get("courses") or []),
                "deletion_batches": deletion_batches_vm(payload),
            },
        )

    @router.get("/courses/{course_id}", response_class=HTMLResponse)
    def groups_page(course_id: str, request: Request):
        if require_session(request) is None:
            return _login_redirect()
        payload, page = query_or_page(request, course_id=course_id)
        if page is not None:
            return page
        return render(
            request,
            "groups.html",
            {
                "course_id": course_id,
                "groups": list(payload.get("groups") or []),
                "deletion_batches": deletion_batches_vm(payload),
            },
        )

    @router.get("/courses/{course_id}/groups/{group_id}", response_class=HTMLResponse)
    def students_page(course_id: str, group_id: str, request: Request):
        if require_session(request) is None:
            return _login_redirect()
        payload, page = query_or_page(request, course_id=course_id, group_id=group_id)
        if page is not None:
            return page
        return render(
            request,
            "students.html",
            {
                "course_id": course_id,
                "group_id": group_id,
                "students": list(payload.get("students") or []),
                "submissions": list(payload.get("submissions") or []),
            },
        )

    def _submission_detail_page(
        request: Request,
        submission_id: str,
        *,
        notice: str | None = None,
        error: str | None = None,
        draft: dict[str, Any] | None = None,
    ):
        payload, page = query_or_page(request, submission_id=submission_id)
        if page is not None:
            return page
        vm = submission_detail_vm(payload)
        return render(
            request,
            "submission_detail.html",
            {
                "vm": vm,
                "grades": GRADES,
                "notice": notice,
                "error": error,
                # 失败保留草稿（LCD-TUI-003/004：显式重试，不自动重试父写契约）。
                "draft": draft or {},
            },
        )

    @router.get("/submissions/{submission_id}", response_class=HTMLResponse)
    def submission_detail_page(submission_id: str, request: Request):
        if require_session(request) is None:
            return _login_redirect()
        return _submission_detail_page(request, submission_id)

    # -- CT-008 复核工作台（批注 / 最终等级） -------------------------------

    @router.post("/submissions/{submission_id}/review")
    async def review_submit(submission_id: str, request: Request):
        token = require_session(request)
        if token is None:
            return _login_redirect()
        form = await request.form()
        annotation = str(form.get("annotation") or "").strip() or None
        final_grade = str(form.get("final_grade") or "").strip() or None
        adjustment_reason = str(form.get("adjustment_reason") or "").strip() or None
        if annotation is None and final_grade is None:
            return _submission_detail_page(
                request,
                submission_id,
                error="批注与最终等级至少填写其一（CT-008）",
                draft={"annotation": annotation or "", "adjustment_reason": adjustment_reason or ""},
            )
        # LCD-TUI-003：幂等键在本次明确提交的交互边界生成。
        request_id = uuid.uuid4().hex
        try:
            result = api_client.save_review(
                teacher_session=token,
                submission_id=submission_id,
                request_id=request_id,
                annotation=annotation,
                final_grade=final_grade,
                adjustment_reason=adjustment_reason,
            )
        except TeacherApiError as exc:
            if exc.code == AUTH_INVALID:
                return _login_redirect()
            draft = {
                "annotation": annotation or "",
                "adjustment_reason": adjustment_reason or "",
            }
            if exc.code == NO_ORIGINAL_GRADE:
                return _submission_detail_page(
                    request,
                    submission_id,
                    error="无原始等级，不能设置最终等级（NO_ORIGINAL_GRADE）；不得伪造等级",
                    draft=draft,
                )
            return _submission_detail_page(
                request, submission_id, error=f"{exc.code}: {exc}", draft=draft
            )
        record = (result or {}).get("review_record") or {}
        operator = record.get("operator")
        updated_at = record.get("updated_at")
        notice = "复核已保存"
        if operator and updated_at:
            notice = f"复核已保存（操作者 {operator}，时间 {updated_at}）"
        return _submission_detail_page(request, submission_id, notice=notice)

    # -- CT-009 展示工作区 --------------------------------------------------

    @router.get("/courses/{course_id}/presentation", response_class=HTMLResponse)
    def presentation_select_page(course_id: str, request: Request):
        if require_session(request) is None:
            return _login_redirect()
        payload, page = query_or_page(request, course_id=course_id)
        if page is not None:
            return page
        return render(
            request,
            "presentation_select.html",
            {"course_id": course_id, "groups": list(payload.get("groups") or [])},
        )

    @router.post("/presentations", response_class=HTMLResponse)
    async def presentation_generate(request: Request):
        token = require_session(request)
        if token is None:
            return _login_redirect()
        form = await request.form()
        group_ids = [str(g) for g in form.getlist("group_ids") if str(g).strip()]
        course_id = str(form.get("course_id") or "")
        if not group_ids:
            return render(
                request,
                "presentation_select.html",
                {"course_id": course_id, "groups": [], "error": "请至少选择一个小组"},
                status_code=400,
            )
        try:
            payload = api_client.generate_presentation(
                teacher_session=token, group_ids=group_ids
            )
        except TeacherApiError as exc:
            if exc.code == AUTH_INVALID:
                return _login_redirect()
            if exc.code == NO_AVAILABLE_SUBMISSION:
                # 阻止生成并说明原因（D-AC-REQ-010-01 exceptions）。
                return render(
                    request,
                    "presentation_select.html",
                    {
                        "course_id": course_id,
                        "groups": [],
                        "error": f"无法生成展示视图：{exc}（NO_AVAILABLE_SUBMISSION）",
                    },
                    status_code=422,
                )
            return render(
                request,
                "error.html",
                {"code": exc.code, "message": str(exc)},
                status_code=502,
            )
        return render(request, "presentation.html", {"vm": presentation_vm(payload)})

    # -- CT-011 删除批次确认（仅调用，端点实现归 backfill） ------------------

    @router.get("/deletion-batches/{batch_id}", response_class=HTMLResponse)
    def deletion_batch_page(batch_id: str, request: Request):
        if require_session(request) is None:
            return _login_redirect()
        payload, page = query_or_page(request)
        if page is not None:
            return page
        batches = deletion_batches_vm(payload)
        batch = next((b for b in batches if b["batch_id"] == batch_id), None)
        if batch is None:
            return render(
                request,
                "error.html",
                {"code": "NOT_FOUND", "message": f"未找到删除批次 {batch_id}"},
                status_code=404,
            )
        return render(request, "deletion_batch.html", {"batch": batch})

    @router.post("/deletion-batches/{batch_id}/confirm", response_class=HTMLResponse)
    async def deletion_batch_confirm(batch_id: str, request: Request):
        token = require_session(request)
        if token is None:
            return _login_redirect()
        form = await request.form()
        raw_exclusions = str(form.get("exclusions") or "")
        exclusions = [e.strip() for e in raw_exclusions.split(",") if e.strip()]
        try:
            result = api_client.confirm_deletion_batch(
                teacher_session=token,
                batch_id=batch_id,
                confirm=True,
                exclusions=exclusions or None,
            )
        except TeacherApiError as exc:
            if exc.code == AUTH_INVALID:
                return _login_redirect()
            status = 409 if exc.code == BATCH_NOT_EXPIRED else 502
            return render(
                request,
                "error.html",
                {"code": exc.code, "message": str(exc), "batch_id": batch_id},
                status_code=status,
            )
        scope = result.get("pending_deletion_scope")
        if isinstance(scope, list):
            scope_text = "、".join(str(s) for s in scope)
        else:
            scope_text = str(scope)
        return render(
            request,
            "deletion_batch_result.html",
            {
                "batch_id": result.get("batch_id", batch_id),
                "batch_status": result.get("batch_status"),
                "pending_deletion_scope": scope_text,
            },
        )

    return router
