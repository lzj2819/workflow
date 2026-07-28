"""CMP-PRES-MISSING-MARKS：资格判定与显式缺失标记（PRES-IC-01，纯函数）。

守护两条相反规则（LCD-PRES-002）：
- P-PRESENTATION-ELIGIBILITY：任一选定小组无可用提交 → 整体
  NO_AVAILABLE_SUBMISSION，资格失败在持久化前终止，不写部分快照；
- P-MISSING-MARKS-VISIBLE：材料缺失仍生成视图，缺失类别在 missing_marks
  中显式列出，不隐藏缺口、不把缺失改写为成功。

缺失标记只表达读模型事实：可用提交材料引用未覆盖的类别 + 读模型自身
报告的 missing_marks（取冻结枚举交集），按冻结枚举顺序稳定输出。
"""
from __future__ import annotations

from dataclasses import dataclass

from .ports import MATERIAL_CATEGORIES, GroupReadView, SubmissionView


@dataclass(frozen=True)
class GroupEvaluation:
    """单组资格评估结果（PRES-IC-01 输出；请求内派生状态，不持久化）。"""

    group_id: str
    view: GroupReadView | None
    eligible: bool
    reason: str | None
    available_submissions: tuple[SubmissionView, ...]
    missing_marks: tuple[str, ...]


def _missing_marks(submissions: tuple[SubmissionView, ...]) -> tuple[str, ...]:
    """冻结枚举顺序的缺失类别：未覆盖类别 ∪ 读模型报告缺失（不隐藏缺口）。"""
    present: set[str] = set()
    reported: set[str] = set()
    for submission in submissions:
        present.update(m.category for m in submission.material_refs)
        reported.update(submission.missing_marks)
    return tuple(
        category
        for category in MATERIAL_CATEGORIES
        if category not in present or category in reported
    )


def evaluate_group(*, group_id: str, view: GroupReadView | None) -> GroupEvaluation:
    """评估单组资格与缺失标记；资格失败携带可观察原因说明。"""
    if view is None:
        return GroupEvaluation(
            group_id=group_id,
            view=None,
            eligible=False,
            reason=f"小组 {group_id} 在读模型中无记录，无可用提交",
            available_submissions=(),
            missing_marks=(),
        )
    available = tuple(s for s in view.submissions if s.available)
    if not available:
        statuses = sorted({s.status for s in view.submissions}) or ["<none>"]
        return GroupEvaluation(
            group_id=group_id,
            view=view,
            eligible=False,
            reason=(
                f"小组 {group_id} 无可用提交（现有提交状态均不可用："
                f"{', '.join(statuses)}）"
            ),
            available_submissions=(),
            missing_marks=(),
        )
    return GroupEvaluation(
        group_id=group_id,
        view=view,
        eligible=True,
        reason=None,
        available_submissions=available,
        missing_marks=_missing_marks(available),
    )
