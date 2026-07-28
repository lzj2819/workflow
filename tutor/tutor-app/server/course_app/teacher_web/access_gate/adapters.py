"""三种冻结端口形状的 ACCESS-GATE 适配器（T-B03a；不改 L14/L15/L16 代码）。

- ReviewCommandAccessGate（L14 operator 形）：authorize(teacher_session, submission_id)
  → review_command.ports.AccessGrant。submission → course 经 SI-CORE 提交登记解析；
  提交不存在时无法确定课程范围，本适配器只完成认证即放行，NOT_FOUND 由 L14 服务层
  判定（不改变叶子既有错误语义）；提交存在但课程无授权 → 403 + AccessDeniedLogged。
- ReviewQueryAccessGate（L15 AuthorizedQueryContext 形）：authorize(teacher_session,
  course_id) → AuthorizedQueryContext；course_id 为 None（课程列表）只认证不鉴权。
- PresentationAccessGate（L16 AuthContext 形）：authorize(authorization) → AuthContext。
  按端口契约只做认证与授权范围供给，小组-课程归属比对由 L16 自身执行（FORBIDDEN）。

每个适配器只调用 AccessGateService 并把内部错误翻译为对应叶子的冻结错误类型；
AccessDeniedLogged 审计由服务层在 403 前追加（不含口令/令牌明文）。
"""
from __future__ import annotations

from typing import Callable, ContextManager

from sqlalchemy import select
from sqlalchemy.orm import Session

from course_app.submission_intake.core.models import Submission
from course_app.teacher_web.presentation import errors as pr_errors
from course_app.teacher_web.presentation import ports as pr_ports
from course_app.teacher_web.review_command import errors as rc_errors
from course_app.teacher_web.review_command import ports as rc_ports
from course_app.teacher_web.review_query import errors as rq_errors
from course_app.teacher_web.review_query import ports as rq_ports

from .errors import AccessDeniedError, AuthInvalidError
from .service import AccessGateService, TeacherIdentity

# 审计 source 标识（追加式日志来源列）。
SOURCE_L14 = "L14-review-command"
SOURCE_L15 = "L15-review-query"


class ReviewCommandAccessGate:
    """L14 AccessGatePort 形：authorize(teacher_session, submission_id) -> AccessGrant。"""

    def __init__(
        self,
        *,
        service: AccessGateService,
        session_factory: Callable[[], ContextManager[Session]],
    ) -> None:
        self._service = service
        self._session_factory = session_factory

    def _submission_course(self, submission_id: str) -> str | None:
        with self._session_factory() as session:
            return session.scalar(
                select(Submission.course_id).where(
                    Submission.submission_id == submission_id
                )
            )

    def authorize(
        self, *, teacher_session: str | None, submission_id: str
    ) -> rc_ports.AccessGrant:
        try:
            identity = self._service.verify_session(teacher_session)
        except AuthInvalidError as exc:
            raise rc_errors.AuthInvalidError(str(exc)) from exc
        course_id = self._submission_course(submission_id)
        if course_id is None:
            # 提交不存在/无课程归属：课程范围无从判定，认证通过即放行；
            # NOT_FOUND 由 L14 服务层按 SubmissionStatusPort 判定。
            return rc_ports.AccessGrant(operator=identity.teacher_id)
        try:
            self._service.require_grant(
                identity,
                course_id=course_id,
                action="authorize.review",
                source=SOURCE_L14,
            )
        except AccessDeniedError as exc:
            raise rc_errors.ForbiddenError(str(exc)) from exc
        return rc_ports.AccessGrant(operator=identity.teacher_id)


class ReviewQueryAccessGate:
    """L15 AccessGatePort 形：authorize(teacher_session, course_id) -> AuthorizedQueryContext。"""

    def __init__(self, *, service: AccessGateService) -> None:
        self._service = service

    def authorize(
        self, *, teacher_session: str, course_id: str | None
    ) -> rq_ports.AuthorizedQueryContext:
        try:
            identity = self._service.verify_session(teacher_session)
        except AuthInvalidError as exc:
            raise rq_errors.AuthInvalidError(str(exc)) from exc
        if course_id is not None:
            try:
                self._service.require_grant(
                    identity,
                    course_id=course_id,
                    action="authorize.query",
                    source=SOURCE_L15,
                )
            except AccessDeniedError as exc:
                raise rq_errors.AccessDeniedError(str(exc)) from exc
        return rq_ports.AuthorizedQueryContext(
            teacher_id=identity.teacher_id, course_id=course_id
        )


class PresentationAccessGate:
    """L16 AccessGatePort 形：authorize(authorization) -> AuthContext。

    只做认证与授权范围供给（小组-课程归属比对由 L16 读到视图后执行）。
    """

    def __init__(self, *, service: AccessGateService) -> None:
        self._service = service

    @staticmethod
    def _bearer_token(authorization: str | None) -> str | None:
        if not authorization:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return token.strip()

    def authorize(self, *, authorization: str | None) -> pr_ports.AuthContext:
        token = self._bearer_token(authorization)
        if token is None:
            raise pr_errors.AuthInvalidError("teacher session required")
        try:
            identity: TeacherIdentity = self._service.verify_session(token)
        except AuthInvalidError as exc:
            raise pr_errors.AuthInvalidError(str(exc)) from exc
        return pr_ports.AuthContext(
            teacher_id=identity.teacher_id, course_ids=identity.course_ids
        )


__all__ = [
    "PresentationAccessGate",
    "ReviewCommandAccessGate",
    "ReviewQueryAccessGate",
]
