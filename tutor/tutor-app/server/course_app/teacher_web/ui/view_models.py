"""L17 PageViewModel 装配（L2 架构：缺失字段保持显式 missing，不填默认等级）。

输入为 CT-007/CT-009 冻结契约响应的 dict 镜像；输出为模板上下文。
所有转换只读、不补充业务结论：

- scoring_failed：保留 failure_reason / retry_record，不产生等级；
- original_grade / final_grade 缺失保持 None（模板渲染显式缺失标记）；
- missing_marks 原样透传（缺失可见，不隐藏缺口）。
"""
from __future__ import annotations

from typing import Any

from .client import STATUS_SCORING_FAILED

#: 模板可见的显式缺失标记文案（PageViewModel：缺失字段不填默认值）。
MISSING_MARK = "缺失"


def submission_detail_vm(payload: dict[str, Any]) -> dict[str, Any]:
    """CT-007 提交详情响应 → 详情页 PageViewModel。"""
    status = payload.get("status")
    original_grade = payload.get("original_grade")
    final_grade = payload.get("final_grade")
    return {
        "submission_id": payload.get("submission_id"),
        "material_refs": list(payload.get("material_refs") or []),
        "status": status,
        "scoring_failed": status == STATUS_SCORING_FAILED,
        "original_grade": original_grade,
        # 五维依据 / 教师建议 / 批注：仅教师侧可见（学生无此界面）。
        "dimension_rationales": list(payload.get("dimension_rationales") or []),
        "teacher_suggestions": list(payload.get("teacher_suggestions") or []),
        "annotations": list(payload.get("annotations") or []),
        "final_grade": final_grade,
        # 失败优先可见（LCD-TUI-004）：原因与重试结果显式呈现。
        "failure_reason": payload.get("failure_reason"),
        "retry_record": payload.get("retry_record"),
        # 无原始等级时不提供可编辑最终等级入口（CT-008 NO_ORIGINAL_GRADE；
        # 不得伪造等级）。批注仍可编辑。
        "final_grade_editable": original_grade is not None,
    }


def presentation_vm(payload: dict[str, Any]) -> dict[str, Any]:
    """CT-009 展示视图响应 → 展示页 PageViewModel（missing_marks 原样可见）。"""
    blocks = []
    for block in payload.get("blocks") or []:
        blocks.append(
            {
                "group_id": block.get("group_id"),
                "project_result": block.get("project_result"),
                "process_summary": block.get("process_summary"),
                "grades": list(block.get("grades") or []),
                "annotations": list(block.get("annotations") or []),
                "missing_marks": list(block.get("missing_marks") or []),
            }
        )
    return {
        "presentation_id": payload.get("presentation_id"),
        "blocks": blocks,
    }


def deletion_batches_vm(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """CT-007 deletion_batches[] → 删除批次列表 PageViewModel。"""
    batches = []
    for batch in payload.get("deletion_batches") or []:
        batches.append(
            {
                "batch_id": batch.get("batch_id"),
                "retention_due_at": batch.get("retention_due_at"),
                "scope": batch.get("scope"),
                "batch_status": batch.get("batch_status"),
                "exclusions": list(batch.get("exclusions") or []),
            }
        )
    return batches
