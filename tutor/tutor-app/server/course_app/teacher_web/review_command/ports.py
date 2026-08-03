"""CMP-REVIEW-COMMAND 消费/提供端口抽象（进程内注入，DD-004 口径）。

- AccessGatePort：CMP-ACCESS-GATE 冻结面。实现归 backfill；本叶子只调用。
  实现应在拒绝时抛出 errors.AuthInvalidError / ForbiddenError，并由 GATE
  记录 AccessDeniedLogged（本叶子不实现该留痕）。
- SubmissionStatusPort：L02 状态查询只读端口（IC-SI-04 查询面注入），用于
  区分 NOT_FOUND（目标不存在）与 NO_ORIGINAL_GRADE（scoring_failed 且无
  原始等级）。
- ReviewEventPublisher：M05-IC-05 模块内事件端口（AnnotationSaved /
  GradeAdjusted）。只在业务写入提交后调用（LCD-004）；投影失败由 RMP 按
  adjustment_id 重放，不回滚已提交的 ReviewRecord。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

# ---- ACCESS-GATE 端口（owner：CMP-ACCESS-GATE，实现归 backfill） ----


@dataclass(frozen=True)
class AccessGrant:
    """ACCESS-GATE 授权通过输出：operator 为教师操作者标识。"""

    operator: str


class AccessGatePort(Protocol):
    """CT-008 前置会话认证 + 课程范围授权；每次请求实时调用，不缓存。

    拒绝时抛 `errors.AuthInvalidError`（401）或 `errors.ForbiddenError`（403）；
    AccessDeniedLogged 由 GATE 实现侧记录。
    """

    def authorize(self, *, teacher_session: str | None, submission_id: str) -> AccessGrant: ...


# ---- L02 状态查询端口（IC-SI-04 查询面，注入） ----


@dataclass(frozen=True)
class SubmissionStatus:
    """L02 提交状态只读视图（status 取值沿用 SI-CORE 状态机）。"""

    submission_id: str
    status: str


class SubmissionStatusPort(Protocol):
    """按 submission_id 查询提交状态；目标不存在返回 None（→ NOT_FOUND）。"""

    def get_submission_status(self, submission_id: str) -> SubmissionStatus | None: ...


# ---- M05-IC-05 模块内事件端口（consumer：CMP-READMODEL-PROJECTOR） ----

EVENT_ANNOTATION_SAVED = "AnnotationSaved"
EVENT_GRADE_ADJUSTED = "GradeAdjusted"


@dataclass(frozen=True)
class ReviewEvent:
    """M05-IC-05 固定字段：submission_id/operator/updated_at/adjustment_id + 摘要。"""

    event_type: str  # AnnotationSaved / GradeAdjusted
    submission_id: str
    adjustment_id: str
    operator: str
    updated_at: str  # ISO date-time
    annotation_excerpt: str | None = None
    final_grade: str | None = None


class ReviewEventPublisher(Protocol):
    """M05-IC-05：业务事务提交后调用；不跨模块投递。"""

    def publish(self, events: Sequence[ReviewEvent]) -> None: ...


@dataclass
class InMemoryReviewEventPublisher:
    """进程内事件收集器（M05-IC-05 最小载体；可追溯重放依据 adjustment_id）。"""

    events: list[ReviewEvent] = field(default_factory=list)

    def publish(self, events: Sequence[ReviewEvent]) -> None:
        self.events.extend(events)
