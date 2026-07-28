"""SI-API-INTAKE-ORCHESTRATOR：30 秒同步接收编排（NFR-003、LCD-SIAPI-002/004）。

编排顺序（RF-01）：幂等预查 → IC-SI-01 会话/材料接收 → IC-SI-03 归属校验
（有限快速重试，LCD-001）→ IC-SI-04 ConfirmReceived / MarkRejected。

- 幂等（LCD-SIAPI-004）：以 submission_uuid 预查 SI-CORE 既有结果；命中时不重复
  创建会话/合并材料（不重新调用 IC-SI-01），只重新实时校验名单后经 IC-SI-04
  幂等命令复用首次结果；不缓存名单通过结论（REQ-006）。
- 完整性基线：expected_categories 取材料类别全集（CT-004 冻结枚举），
  missing_items 由 SI-CORE 完整性报告计算（缺失显式标记，不阻断 received）。
- 预算：同步路径只做校验+持久化+应答；评分触发经 Outbox 事件异步，不阻塞应答。
"""
from __future__ import annotations

import time
from typing import Callable, Sequence

from course_app.course_roster.errors import RosterUnavailableError
from course_app.submission_intake.core import (
    CATEGORIES,
    CommandResult,
    NotFoundError,
    SubmissionCoreService,
    SubmissionView,
)

from .errors import (
    IntakeBudgetExhaustedError,
    MembershipUnavailableError,
    NotFoundApiError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from .ports import (
    XFER_ERROR_SIZE_LIMIT,
    XFER_ERROR_TYPE_NOT_ALLOWED,
    XFER_STATE_MERGED,
    MaterialChunk,
    MembershipResult,
    MembershipVerifierPort,
    TransferSessionPort,
)

#: NFR-003：30 秒同步接收确认预算（秒）。
SYNC_BUDGET_SECONDS = 30.0

#: LCD-001：ROSTER_UNAVAILABLE 有限快速重试次数（含首次）。
ROSTER_ATTEMPTS = 2


class IntakeOrchestrator:
    """LC-SIAPI-002..005：CT-001/CT-002 编排（不持久化业务状态）。"""

    def __init__(
        self,
        *,
        core_service: SubmissionCoreService,
        transfer_port: TransferSessionPort,
        membership_verifier: MembershipVerifierPort,
        budget_seconds: float = SYNC_BUDGET_SECONDS,
        roster_attempts: int = ROSTER_ATTEMPTS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._core = core_service
        self._transfer = transfer_port
        self._verifier = membership_verifier
        self._budget = budget_seconds
        self._roster_attempts = max(1, roster_attempts)
        self._clock = clock

    # ---- CT-001 接收编排 ----

    def submit(
        self,
        *,
        submission_uuid: str,
        invite_code: str,
        student_name: str,
        group_name: str,
        assignment: str,
        chunks: Sequence[MaterialChunk],
    ) -> CommandResult:
        """CT-001 同步接收：返回 SI-CORE 命令结果（received / rejected / upload_failed）。"""
        deadline = self._clock() + self._budget
        existing = self._try_query(submission_uuid)

        material_refs: Sequence[str] = ()
        if existing is None:
            # 首次：经 IC-SI-01 建立会话并接收材料（L08 端口注入）。
            declared = tuple(dict.fromkeys(c.category for c in chunks))
            transfer = self._transfer.ingest(
                submission_uuid=submission_uuid,
                declared_categories=declared,
                chunks=chunks,
            )
            self._check_budget(deadline)
            if transfer.error_code == XFER_ERROR_SIZE_LIMIT:
                raise PayloadTooLargeError("submission exceeds 500MB limit")
            if transfer.error_code == XFER_ERROR_TYPE_NOT_ALLOWED:
                raise UnsupportedMediaTypeError("material type not in whitelist")
            if transfer.state != XFER_STATE_MERGED:
                # 重试窗口耗尽的终态失败：标记 upload_failed（CT-002 可见），
                # 不应答 received（不得伪造；由路由层映射暂态失败）。
                return self._core.mark_upload_failed(
                    submission_uuid=submission_uuid,
                    failure_reason=transfer.failure_reason or "upload failed",
                    upload_session_state=transfer.state,
                    material_refs=list(transfer.material_refs),
                    expected_categories=list(declared),
                    assignment=assignment,
                    student_name=student_name,
                    group_name=group_name,
                )
            material_refs = transfer.material_refs

        # 归属校验（IC-SI-03）：每次实时执行，不缓存通过结论；幂等重发也重新校验。
        membership = self._verify_with_retry(
            invite_code=invite_code, student_name=student_name, group_name=group_name
        )
        self._check_budget(deadline)

        if membership.verified:
            return self._core.confirm_received(
                submission_uuid=submission_uuid,
                course_id=membership.course_id or "",
                assignment=assignment,
                student_name=student_name,
                group_name=group_name,
                material_refs=list(material_refs),
                expected_categories=list(CATEGORIES),
                verification={"verified": True, "course_id": membership.course_id},
            )
        # REJECTED_MEMBERSHIP：业务终态（status=rejected，非 HTTP 错误）。
        reason = membership.reason or "membership verification failed"
        return self._core.mark_rejected(
            submission_uuid=submission_uuid,
            failure_reason=f"REJECTED_MEMBERSHIP: {reason}",
            verification={
                "verified": False,
                "course_id": membership.course_id,
                "reason": reason,
            },
            course_id=membership.course_id,
            assignment=assignment,
            student_name=student_name,
            group_name=group_name,
        )

    # ---- CT-002 只读查询 ----

    def query(self, submission_uuid: str) -> SubmissionView:
        """CT-002：只读状态查询；未知 uuid → NOT_FOUND。"""
        try:
            return self._core.query_by_uuid(submission_uuid)
        except NotFoundError as exc:
            raise NotFoundApiError("unknown submission_uuid") from exc

    # ---- auth-token 名单核对（LC-SIAPI-007） ----

    def verify_membership(
        self, *, invite_code: str, student_name: str, group_name: str
    ) -> MembershipResult:
        """auth-token 签发前的实时名单核对（不缓存结论）。"""
        return self._verify_with_retry(
            invite_code=invite_code, student_name=student_name, group_name=group_name
        )

    # ---- 内部 ----

    def _try_query(self, submission_uuid: str) -> SubmissionView | None:
        try:
            return self._core.query_by_uuid(submission_uuid)
        except NotFoundError:
            return None

    def _verify_with_retry(
        self, *, invite_code: str, student_name: str, group_name: str
    ) -> MembershipResult:
        """LCD-001：ROSTER_UNAVAILABLE 有限快速重试；耗尽 → 暂态失败（不创建提交）。"""
        for attempt in range(self._roster_attempts):
            try:
                return self._verifier(
                    invite_code=invite_code,
                    student_name=student_name,
                    group_name=group_name,
                )
            except RosterUnavailableError:
                if attempt + 1 >= self._roster_attempts:
                    raise MembershipUnavailableError(
                        "course roster unavailable after limited retries"
                    ) from None
        raise MembershipUnavailableError("course roster unavailable")  # pragma: no cover

    def _check_budget(self, deadline: float) -> None:
        if self._clock() > deadline:
            raise IntakeBudgetExhaustedError("30s sync budget exhausted")
