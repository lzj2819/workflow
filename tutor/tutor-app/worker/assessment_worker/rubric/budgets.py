"""CT-010 三桶预算编排（KD-001 数据最小化；LCD-005 截断策略落地）。

类别 → 桶映射与 L12 assessment_engine.engine._minimize_materials 完全一致
（只读复用其口径，不修改 L12 代码）：未识别类别折叠进 result_description
并带 [类别] 标签。本模块在其上增加：

1. 每桶确定性截断预算（字符数；同输入同输出；截断追加固定标记）；
2. 缺失类别标签化处理：missing_items[] 中每个缺失类别在其映射桶内追加
   固定 [缺失材料] 标签（未识别缺失类别进 result_description），标签在
   截断之后追加，保证不被预算截断吞掉。

纯函数、无副作用；不发网络、不读材料文件（材料内容经 ICT-003 端口进入）。
"""
from __future__ import annotations

# 与 L12 engine._BUCKET_BY_CATEGORY 同一映射（对齐既有折叠口径）
BUCKET_BY_CATEGORY = {
    "对话": "dialogue_summary",
    "对话摘要": "dialogue_summary",
    "dialogue": "dialogue_summary",
    "dialogue_summary": "dialogue_summary",
    "代码": "code",
    "code": "code",
    "结果描述": "result_description",
    "result": "result_description",
    "result_description": "result_description",
}
CT010_MATERIAL_BUCKETS = ("dialogue_summary", "code", "result_description")

# 每桶字符预算（确定性截断；NFR-003 单次 ≤3min 的体量控制，LCD-005 实现细节）
BUCKET_BUDGETS = {
    "dialogue_summary": 4000,
    "code": 8000,
    "result_description": 2000,
}

TRUNCATION_MARKER = "\n[已截断：超出本桶预算]"
MISSING_LABEL_TEMPLATE = (
    "[缺失材料] {item}：该类别材料未提供，对应维度仅能依据其余已提供材料推断"
)


def truncate_to_budget(text: str, budget: int) -> str:
    """确定性截断：超长时保留前 budget 字符并追加固定标记。"""
    if budget <= 0:
        raise ValueError("budget must be positive")
    if len(text) <= budget:
        return text
    return text[:budget] + TRUNCATION_MARKER


def missing_label(item: str) -> str:
    """缺失类别固定标签（与缺失材料影响口径一致，不携带类别以外标识）。"""
    return MISSING_LABEL_TEMPLATE.format(item=item)


def orchestrate_material_buckets(
    materials: dict,
    missing_items: list | None = None,
    budgets: dict | None = None,
) -> dict:
    """把 {类别: 内容} 编排进 CT-010 三个最小化桶。

    折叠口径与 L12 _minimize_materials 一致；随后按桶预算确定性截断，
    最后为 missing_items[] 追加 [缺失材料] 标签。同输入同输出。
    """
    budgets = BUCKET_BUDGETS if budgets is None else budgets
    missing_items = [] if missing_items is None else list(missing_items)

    folded: dict[str, list[str]] = {name: [] for name in CT010_MATERIAL_BUCKETS}
    for category, content in materials.items():
        bucket = BUCKET_BY_CATEGORY.get(category)
        if bucket is None:
            folded["result_description"].append(f"[{category}]\n{content}")
        else:
            folded[bucket].append(content)

    buckets: dict[str, str] = {}
    for name in CT010_MATERIAL_BUCKETS:
        joined = "\n".join(folded[name])
        buckets[name] = truncate_to_budget(joined, budgets[name])

    for item in missing_items:
        bucket = BUCKET_BY_CATEGORY.get(item, "result_description")
        label = missing_label(item)
        buckets[bucket] = f"{buckets[bucket]}\n{label}" if buckets[bucket] else label

    return buckets
