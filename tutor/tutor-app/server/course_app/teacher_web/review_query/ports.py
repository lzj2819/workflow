"""L15 CMP-REVIEW-QUERY 消费端口抽象（M05-IC-02 / M05-IC-06 / ACCESS-GATE）。

- M05-IC-02 读模型查询端口（owner：CMP-READMODEL-PROJECTOR，backfill 实现）。
  本叶子只定义消费方冻结面并注入消费；**不自建读模型表、不做投影逻辑**。
  读模型秒级滞后按最终一致接受；读取失败抛 ReadModelUnavailableError，
  调用方整体转可重试失败，不降级缺字段。
- M05-IC-06 删除治理读端口（owner：CMP-RETENTION-GOVERNANCE，backfill 实现）。
  只读批次视图；读取失败抛 RetentionViewUnavailableError，不得省略
  deletion_batches[] 掩盖端口错误（LCD-RQ-003）。
- ACCESS-GATE 课程范围授权端口（owner：CMP-ACCESS-GATE，backfill 实现）。
  认证/授权在 GATE 终止：拒绝时抛 AccessDeniedError 并由其实现记录
  AccessDeniedLogged；会话非法抛 AuthInvalidError。本层不复制授权规则
  （LCD-RQ-005），只消费已授权上下文。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

#: CT-007 status 冻结值域（contracts/ct-007.json response.status enum）。
SUBMISSION_STATUSES = (
    "upload_failed",
    "rejected",
    "received",
    "processing",
    "scored",
    "scoring_failed",
)

#: CT-007 等级冻结值域（original_grade / final_grade enum）。
GRADES = ("A", "B", "C", "D", "E")


# ---- ACCESS-GATE 授权端口（owner：CMP-ACCESS-GATE） ----


@dataclass(frozen=True)
class AuthorizedQueryContext:
    """GATE 建立的已授权 CT-007 查询上下文（请求内瞬时，不持久化）。"""

    teacher_id: str
    course_id: str | None = None


class AccessGatePort(Protocol):
    """课程范围授权检查：无权抛 AccessDeniedError（403 + AccessDeniedLogged
    由其实现记录）；会话非法抛 AuthInvalidError。每次实时调用，不缓存。"""

    def authorize(
        self, *, teacher_session: str, course_id: str | None
    ) -> AuthorizedQueryContext: ...


# ---- M05-IC-02 读模型查询端口（owner：CMP-READMODEL-PROJECTOR） ----


@dataclass(frozen=True)
class ReadModelView:
    """M05-IC-02 输出：按选择范围过滤后的读模型视图（ST-READ-MODEL 派生事实）。

    字段对应 M05-IC-02 输出集：courses/groups/students/submissions/
    material_refs/status/original_grade/dimension_rationales/
    teacher_suggestions/annotations/final_grade/missing_marks；
    failure_reason/retry_record 为 ST-READ-MODEL 中的失败投影事实
    （CT-005 scoring_failed 投影），scoring_failed 时随视图返回。
    """

    courses: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    groups: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    students: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    submissions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    material_refs: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    status: str | None = None
    original_grade: str | None = None
    dimension_rationales: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    teacher_suggestions: tuple[str, ...] = field(default_factory=tuple)
    annotations: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    final_grade: str | None = None
    missing_marks: tuple[str, ...] = field(default_factory=tuple)
    failure_reason: str | None = None
    retry_record: dict[str, Any] | None = None


class ReadModelQueryPort(Protocol):
    """M05-IC-02：只读天然幂等；短暂滞后按最终一致接受；无重试放大。

    实现归 PROJECTOR/backfill；本叶子注入 stub 或表实现均可，但读模型表
    结构 owner 为 PROJECTOR。读取失败抛 ReadModelUnavailableError。
    """

    def query(
        self,
        *,
        course_id: str | None = None,
        group_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> ReadModelView: ...


# ---- M05-IC-06 删除治理读端口（owner：CMP-RETENTION-GOVERNANCE） ----


@dataclass(frozen=True)
class RetentionBatchView:
    """M05-IC-06 输出：删除批次只读视图（查询不改变批次状态）。"""

    batch_id: str
    retention_due_at: str
    scope: str
    batch_status: str
    exclusions: tuple[str, ...] = field(default_factory=tuple)
    cleared_submission_ids: tuple[str, ...] = field(default_factory=tuple)


class RetentionViewPort(Protocol):
    """M05-IC-06：只读天然幂等；读取失败抛 RetentionViewUnavailableError，
    调用方整体失败（不得降级为缺字段应答）。"""

    def list_batches(
        self,
        *,
        course_id: str | None = None,
        batch_id: str | None = None,
        submission_id: str | None = None,
    ) -> tuple[RetentionBatchView, ...]: ...
