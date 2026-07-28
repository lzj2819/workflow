"""L16 CMP-PRESENTATION 注入端口（M05-IC-02 读模型查询、ACCESS-GATE）。

- M05-IC-02（owner：CMP-READMODEL-PROJECTOR；consumer：CMP-REVIEW-QUERY /
  CMP-PRESENTATION）：read-only；输入 course_id/group_id/student_id/
  submission_id；输出 courses/groups/students/submissions/material_refs/
  status/original_grade/dimension_rationales/teacher_suggestions/
  annotations/final_grade/missing_marks。本包只定义消费侧 Protocol 与
  冻结 DTO，与 L15 共用同一冻结端口形状；实现由 PROJECTOR/backfill 注入。
- ACCESS-GATE：认证与课程范围授权（A-001/FR-009），返回教师身份与课程
  授权范围；失败抛 AuthInvalidError / ForbiddenError（父冻结码）。

P-READ-MODEL-ONLY：展示区块只能从 M05-IC-02 返回的数据装配，不做跨模块
同步读（LCD-004）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

#: CT-009 missing_marks 冻结枚举（contracts/ct-009.json blocks[].missing_marks）。
MATERIAL_CATEGORIES: tuple[str, ...] = ("对话", "代码", "截图", "结果")

#: 不可用提交状态（终态，无展示价值）：其余状态视为可用提交。
UNAVAILABLE_SUBMISSION_STATUSES: frozenset[str] = frozenset(
    {"rejected", "upload_failed", "purged"}
)


@dataclass(frozen=True)
class MaterialRef:
    """材料引用（MOD-02 所有权；读模型只存引用不存本体）。"""

    category: str
    ref: str


@dataclass(frozen=True)
class AnnotationView:
    """教师批注读模型视图。"""

    operator: str
    excerpt: str
    updated_at: str | None = None


@dataclass(frozen=True)
class SubmissionView:
    """M05-IC-02 单提交视图：状态、材料引用、评分与批注、读模型缺失事实。"""

    submission_id: str
    status: str
    student_id: str | None = None
    material_refs: tuple[MaterialRef, ...] = ()
    original_grade: str | None = None
    final_grade: str | None = None
    dimension_rationales: tuple[dict, ...] = ()
    teacher_suggestions: tuple[str, ...] = ()
    annotations: tuple[AnnotationView, ...] = ()
    missing_marks: tuple[str, ...] = ()
    submitted_at: str | None = None

    @property
    def available(self) -> bool:
        """可用提交：非终态不可用（rejected/upload_failed/purged）。"""
        return self.status not in UNAVAILABLE_SUBMISSION_STATUSES


@dataclass(frozen=True)
class GroupReadView:
    """M05-IC-02 小组视图：课程归属、学生与提交列表、读模型版本。"""

    course_id: str
    group_id: str
    read_model_version: str = ""
    students: tuple[dict, ...] = ()
    submissions: tuple[SubmissionView, ...] = ()
    extra: dict = field(default_factory=dict)


class ReadModelQueryPort(Protocol):
    """M05-IC-02 读模型查询端口（read-only；只读天然幂等）。

    读模型短暂落后按最终一致处理；字段不足/超时由实现方抛
    ReadModelUnavailableError，本层不降级为缺字段成功应答。
    """

    def group_view(
        self,
        *,
        group_id: str,
        course_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> GroupReadView | None:
        """返回小组读模型视图；小组无记录返回 None。"""
        ...


@dataclass(frozen=True)
class AuthContext:
    """ACCESS-GATE 授权结果：教师身份与课程授权范围（A-001）。"""

    teacher_id: str
    course_ids: tuple[str, ...]


class AccessGatePort(Protocol):
    """CMP-ACCESS-GATE 端口：认证 + 课程范围授权（M05-FLOW-001 入口）。

    会话缺失/无效 → AuthInvalidError；实现方只做认证与授权范围供给，
    小组-课程归属比对由本层在读到视图后执行（FORBIDDEN）。
    """

    def authorize(self, *, authorization: str | None) -> AuthContext:
        """校验 Bearer 会话，返回教师授权上下文。"""
        ...
