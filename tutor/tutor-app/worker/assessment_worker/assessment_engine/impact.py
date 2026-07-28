"""缺失材料影响说明（D-AC-REQ-008-01 boundaries / LCD-AE-002）。

missing_items[] 非空时不判失败，仍生成结果，并在结果中列出缺失类别对评估的影响。
"""
from __future__ import annotations


def build_missing_materials_impact(missing_items: list) -> str | None:
    """由 missing_items[] 生成 missing_materials_impact 文本；无缺失返回 None。"""
    if not missing_items:
        return None
    lines = ["本次评估缺少以下材料类别，相关维度的评估置信度降低："]
    for item in missing_items:
        lines.append(f"- {item}：该类别材料缺失，对应维度仅能依据其余已提供材料推断")
    return "\n".join(lines)
