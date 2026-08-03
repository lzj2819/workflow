"""CMP-PRES-BLOCK-ASSEMBLER：合格小组读模型片段 → CT-009 GroupSection 区块。

PRES-IC-02：输入 group_view / eligibility / missing_marks，输出
group_section_input。只做字段组合与缺失表达；不做资格裁决、不写快照、
不修改源读模型（P-READ-MODEL-ONLY）。区块字段与 contracts/ct-009.json
blocks[] 一致：group_id、project_result、process_summary、grades、
annotations、missing_marks。
"""
from __future__ import annotations

from .missing_marks import GroupEvaluation


def _project_result(evaluation: GroupEvaluation) -> dict | None:
    """项目结果引用：最新可用提交的「结果」材料引用；缺失 → None（并标记）。"""
    latest = evaluation.available_submissions[0]
    for material in latest.material_refs:
        if material.category == "结果":
            return {
                "submission_id": latest.submission_id,
                "result_ref": material.ref,
            }
    return None


def _process_summary(evaluation: GroupEvaluation) -> str:
    """过程摘要：引用评估产出事实的确定性文本（A-003），不伪造评分。"""
    submissions = evaluation.available_submissions
    graded = sum(
        1 for s in submissions if s.original_grade is not None or s.final_grade is not None
    )
    annotated = sum(1 for s in submissions if s.annotations)
    latest_status = submissions[0].status
    return (
        f"小组 {evaluation.group_id}：可用提交 {len(submissions)} 份；"
        f"最新提交状态 {latest_status}；"
        f"已出评分 {graded} 份；含教师批注 {annotated} 份。"
    )


def _grades(evaluation: GroupEvaluation) -> list[dict]:
    """评分（原始/最终复制值）：仅列出已有任一评分的可用提交。"""
    return [
        {
            "submission_id": s.submission_id,
            "original_grade": s.original_grade,
            "final_grade": s.final_grade,
        }
        for s in evaluation.available_submissions
        if s.original_grade is not None or s.final_grade is not None
    ]


def _annotations(evaluation: GroupEvaluation) -> list[dict]:
    """教师批注（按可用提交展开，保留来源 submission_id）。"""
    return [
        {
            "submission_id": s.submission_id,
            "operator": a.operator,
            "excerpt": a.excerpt,
            "updated_at": a.updated_at,
        }
        for s in evaluation.available_submissions
        for a in s.annotations
    ]


def assemble_block(evaluation: GroupEvaluation) -> dict:
    """装配单组 CT-009 区块；缺失类别在 missing_marks 显式列出（不隐藏）。"""
    if not evaluation.eligible:
        raise ValueError(
            f"ineligible group {evaluation.group_id}: {evaluation.reason}"
        )
    return {
        "group_id": evaluation.group_id,
        "project_result": _project_result(evaluation),
        "process_summary": _process_summary(evaluation),
        "grades": _grades(evaluation),
        "annotations": _annotations(evaluation),
        "missing_marks": list(evaluation.missing_marks),
    }
