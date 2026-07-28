"""L17 教师网页 API 客户端层（只消费已冻结契约，经注入）。

消费面（contracts/ct-007.json、ct-008.json、ct-009.json、ct-011.json）：

- CT-007 教师课程数据查询（GET /api/v1/teacher/courses/... 视图族，只读）；
- CT-008 教师批注与最终等级调整（PUT /api/v1/teacher/submissions/{id}/review，
  客户端生成幂等键 request_id）；
- CT-009 展示视图生成（POST /api/v1/teacher/presentations）；
- CT-011 删除确认（POST /api/v1/teacher/deletion-batches/{batch_id}/confirm，
  仅调用、不实现——端点归 backfill）；
- 教师会话创建：登录页只对接会话 API；会话校验由平台/backfill 承担。

本层不实现任何后端端点或业务结论。L14/L15/L16 同波次未集成，按冻结契约
注入 stub（测试）或 HttpTeacherApiClient（真实 HTTP 调用，无新增依赖语义）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

# 冻结错误码（contracts/ct-007..ct-011.json error_codes 并集；不新增公共错误码）。
AUTH_INVALID = "AUTH_INVALID"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
VALIDATION_FAILED = "VALIDATION_FAILED"
NO_ORIGINAL_GRADE = "NO_ORIGINAL_GRADE"
NO_AVAILABLE_SUBMISSION = "NO_AVAILABLE_SUBMISSION"
BATCH_NOT_EXPIRED = "BATCH_NOT_EXPIRED"

#: CT-007 status 冻结枚举（contracts/ct-007.json response.status）。
STATUS_UPLOAD_FAILED = "upload_failed"
STATUS_REJECTED = "rejected"
STATUS_RECEIVED = "received"
STATUS_PROCESSING = "processing"
STATUS_SCORED = "scored"
STATUS_SCORING_FAILED = "scoring_failed"

#: CT-008/CT-007 等级冻结枚举（A..E）。
GRADES = ("A", "B", "C", "D", "E")

_STATUS_TO_ERROR = {401: AUTH_INVALID, 403: FORBIDDEN, 404: NOT_FOUND}


class TeacherApiError(Exception):
    """父契约冻结错误码承载；UI 只呈现，不改写为业务成功。"""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(frozen=True)
class TeacherSession:
    """登录返回的教师会话引用（不透明；UI 不解析，页面不回显明文）。"""

    token: str


class TeacherApiClient(Protocol):
    """UI → CMP-ACCESS-GATE 的注入端口（TUI-IC 适配边界）。

    所有方法的应答均为对应契约 response 的 dict 镜像；字段语义以
    contracts/*.json 为准，UI 不补充默认值、不伪造等级。
    """

    def create_session(self, *, teacher_account: str, password: str) -> TeacherSession:
        """教师登录：仅对接会话 API；凭证校验归平台/backfill。"""
        ...

    def query_view(
        self,
        *,
        teacher_session: str,
        course_id: str | None = None,
        group_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> dict[str, Any]:
        """CT-007 视图族查询（课程/小组/学生/提交详情/删除批次）。"""
        ...

    def save_review(
        self,
        *,
        teacher_session: str,
        submission_id: str,
        request_id: str,
        annotation: str | None = None,
        final_grade: str | None = None,
        adjustment_reason: str | None = None,
    ) -> dict[str, Any]:
        """CT-008 保存批注/最终等级；request_id 为客户端幂等键。"""
        ...

    def generate_presentation(
        self, *, teacher_session: str, group_ids: Sequence[str]
    ) -> dict[str, Any]:
        """CT-009 生成展示视图快照（presentation_id + blocks[]）。"""
        ...

    def confirm_deletion_batch(
        self,
        *,
        teacher_session: str,
        batch_id: str,
        confirm: bool = True,
        exclusions: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """CT-011 删除批次确认（仅调用；端点实现归 backfill）。"""
        ...


class HttpTeacherApiClient:
    """基于 httpx 的 CT-007/008/009/011 客户端（仅发起调用，不实现端点）。

    端点路径取各自冻结契约的 endpoint.path；鉴权按 CT-007 teacher_session
    （Bearer 会话凭证）。错误应答 {"code", "message"} 映射为 TeacherApiError；
    无 code 的非 2xx 按 HTTP 状态映射到冻结码（401/403/404）。
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: Any = None,
    ) -> None:
        import httpx  # noqa: PLC0415  （集中、惰性导入第三方依赖）

        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    # -- 内部工具 ---------------------------------------------------------

    @staticmethod
    def _headers(teacher_session: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {teacher_session}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            code = None
            message = ""
            try:
                body = response.json()
            except ValueError:
                body = {}
            if isinstance(body, dict):
                code = body.get("code")
                message = str(body.get("message") or body.get("detail") or "")
            code = code or _STATUS_TO_ERROR.get(response.status_code, VALIDATION_FAILED)
            raise TeacherApiError(code, message)
        return response.json()

    @staticmethod
    def _view_path(
        *,
        course_id: str | None,
        group_id: str | None,
        student_id: str | None,
        submission_id: str | None,
    ) -> str:
        """CT-007 视图族定位参数 → 路径（/api/v1/teacher/courses/...）。"""
        path = "/api/v1/teacher/courses"
        if course_id is not None:
            path += f"/{course_id}"
        if group_id is not None:
            path += f"/groups/{group_id}"
        if student_id is not None:
            path += f"/students/{student_id}"
        if submission_id is not None:
            path += f"/submissions/{submission_id}"
        return path

    # -- 端口实现 ---------------------------------------------------------

    def create_session(self, *, teacher_account: str, password: str) -> TeacherSession:
        body = self._request(
            "POST",
            "/api/v1/teacher/session",
            json={"teacher_account": teacher_account, "password": password},
        )
        return TeacherSession(token=str(body["teacher_session"]))

    def query_view(
        self,
        *,
        teacher_session: str,
        course_id: str | None = None,
        group_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            self._view_path(
                course_id=course_id,
                group_id=group_id,
                student_id=student_id,
                submission_id=submission_id,
            ),
            headers=self._headers(teacher_session),
        )

    def save_review(
        self,
        *,
        teacher_session: str,
        submission_id: str,
        request_id: str,
        annotation: str | None = None,
        final_grade: str | None = None,
        adjustment_reason: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"request_id": request_id}
        if annotation is not None:
            payload["annotation"] = annotation
        if final_grade is not None:
            payload["final_grade"] = final_grade
        if adjustment_reason is not None:
            payload["adjustment_reason"] = adjustment_reason
        return self._request(
            "PUT",
            f"/api/v1/teacher/submissions/{submission_id}/review",
            json=payload,
            headers=self._headers(teacher_session),
        )

    def generate_presentation(
        self, *, teacher_session: str, group_ids: Sequence[str]
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/teacher/presentations",
            json={"group_ids": list(group_ids)},
            headers=self._headers(teacher_session),
        )

    def confirm_deletion_batch(
        self,
        *,
        teacher_session: str,
        batch_id: str,
        confirm: bool = True,
        exclusions: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"confirm": confirm}
        if exclusions is not None:
            payload["exclusions"] = list(exclusions)
        return self._request(
            "POST",
            f"/api/v1/teacher/deletion-batches/{batch_id}/confirm",
            json=payload,
            headers=self._headers(teacher_session),
        )
