"""L15 CMP-REVIEW-QUERY 查询门面（CMP-RQ-QUERY-FACADE，LCD-RQ-001）。

CT-007 唯一装配边界：接收 GATE 路由后的已授权上下文，协调 Scope/Detail/
Outcome/Retention 四个装配 child，输出完整 CT-007 响应。

- 不认证授权（GATE 职责）、不直接读底层表、不持有查询缓存、不新增公开端点。
- 完整性：deletion_batches[] 即使为空也返回空数组（LCD-RQ-003）。
- 失败收敛：M05-IC-02 / M05-IC-06 任一必需端口失败 → RetryableQueryError，
  禁止 partial success / 缺字段成功（LCD-RQ-004）。
- 只读无副作用：不写业务状态、不发事件、不改变投影位点。
"""
from __future__ import annotations

from typing import Any

from .assemblers import (
    OutcomeAdapter,
    RetentionViewAdapter,
    ScopeAssembler,
    SubmissionDetailAssembler,
)
from .errors import (
    ReadModelUnavailableError,
    RetentionViewUnavailableError,
    RetryableQueryError,
)
from .ports import (
    AccessGatePort,
    AuthorizedQueryContext,
    ReadModelQueryPort,
    RetentionViewPort,
)


class QueryFacade:
    """CMP-RQ-QUERY-FACADE：CT-007 视图族编排与响应完整性校验。"""

    def __init__(
        self,
        *,
        read_model: ReadModelQueryPort,
        retention_view: RetentionViewPort,
    ) -> None:
        outcome_adapter = OutcomeAdapter()
        self._scope = ScopeAssembler(read_model)
        self._detail = SubmissionDetailAssembler(read_model, outcome_adapter)
        self._retention = RetentionViewAdapter(retention_view)

    def course_list(self, context: AuthorizedQueryContext) -> dict[str, Any]:
        """课程列表视图（CT-007 层级入口）。"""
        try:
            return self._scope.course_list(context)
        except (ReadModelUnavailableError, RetentionViewUnavailableError) as exc:
            raise RetryableQueryError(str(exc)) from exc

    def group_list(
        self,
        context: AuthorizedQueryContext,
        *,
        course_id: str,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        """小组列表视图（可选 group_id 过滤并附 students[]）。"""
        try:
            return self._scope.group_list(context, course_id, group_id)
        except (ReadModelUnavailableError, RetentionViewUnavailableError) as exc:
            raise RetryableQueryError(str(exc)) from exc

    def student_detail(
        self, context: AuthorizedQueryContext, *, course_id: str, student_id: str
    ) -> dict[str, Any]:
        """学生详情视图：students[] + submissions[]。"""
        try:
            return self._scope.student_detail(context, course_id, student_id)
        except (ReadModelUnavailableError, RetentionViewUnavailableError) as exc:
            raise RetryableQueryError(str(exc)) from exc

    def submission_detail(
        self, context: AuthorizedQueryContext, *, course_id: str, submission_id: str
    ) -> dict[str, Any]:
        """提交详情完整响应：详情字段 + 结果分支 + deletion_batches[]（必需）。

        任一必需部分失败禁止 partial success（RQ-IC-005）。
        """
        try:
            detail = self._detail.assemble(context, course_id, submission_id)
            detail["deletion_batches"] = self._retention.assemble(
                course_id, submission_id=submission_id
            )
        except (ReadModelUnavailableError, RetentionViewUnavailableError) as exc:
            raise RetryableQueryError(str(exc)) from exc
        return detail


def create_facade(
    *,
    access_gate: AccessGatePort,
    read_model: ReadModelQueryPort,
    retention_view: RetentionViewPort,
) -> "ReviewQueryService":
    """装配 GATE → Facade 调用链（RQ-BIND-CT-007-GATE-FACADE）。"""
    return ReviewQueryService(
        access_gate=access_gate,
        facade=QueryFacade(read_model=read_model, retention_view=retention_view),
    )


class ReviewQueryService:
    """GATE 授权 + Facade 装配的编排入口（CT-007 已认证授权后唯一入口）。"""

    def __init__(
        self, *, access_gate: AccessGatePort, facade: QueryFacade
    ) -> None:
        self._access_gate = access_gate
        self._facade = facade

    def _authorize(
        self, teacher_session: str, course_id: str | None
    ) -> AuthorizedQueryContext:
        """ACCESS-GATE 端口调用：403 + AccessDeniedLogged 由其实现。"""
        return self._access_gate.authorize(
            teacher_session=teacher_session, course_id=course_id
        )

    def course_list(self, *, teacher_session: str) -> dict[str, Any]:
        context = self._authorize(teacher_session, None)
        return self._facade.course_list(context)

    def group_list(
        self,
        *,
        teacher_session: str,
        course_id: str,
        group_id: str | None = None,
    ) -> dict[str, Any]:
        context = self._authorize(teacher_session, course_id)
        return self._facade.group_list(context, course_id=course_id, group_id=group_id)

    def student_detail(
        self, *, teacher_session: str, course_id: str, student_id: str
    ) -> dict[str, Any]:
        context = self._authorize(teacher_session, course_id)
        return self._facade.student_detail(
            context, course_id=course_id, student_id=student_id
        )

    def submission_detail(
        self, *, teacher_session: str, course_id: str, submission_id: str
    ) -> dict[str, Any]:
        context = self._authorize(teacher_session, course_id)
        return self._facade.submission_detail(
            context, course_id=course_id, submission_id=submission_id
        )
