"""RUBRIC-PROMPT-COMPOSER（ICT-002，T-B02b）：RubricPolicy 版本化存证 + 提示组装。

边界：
- compose() 纯组装、无副作用，同版本同输入同输出；五维枚举与
  contracts/ct-010.json 一致；缺失材料声明对齐 L12 影响口径；
- 三桶预算编排（budgets.py）与 L12 _minimize_materials 折叠口径一致，
  增加确定性截断与缺失类别标签化；KD-001 数据最小化；
- 从 PG/SQLite 只读 ST-004 active 策略；不接真实供应商、不发网络。
"""
from assessment_worker.rubric.budgets import (
    BUCKET_BUDGETS,
    BUCKET_BY_CATEGORY,
    CT010_MATERIAL_BUCKETS,
    TRUNCATION_MARKER,
    missing_label,
    orchestrate_material_buckets,
    truncate_to_budget,
)
from assessment_worker.rubric.composer import (
    RubricPromptComposer,
    build_material_manifest,
    build_missing_declaration,
)
from assessment_worker.rubric.models import (
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    RubricBase,
    RubricPolicy,
)

__all__ = [
    "BUCKET_BUDGETS",
    "BUCKET_BY_CATEGORY",
    "CT010_MATERIAL_BUCKETS",
    "STATUS_ACTIVE",
    "STATUS_SUPERSEDED",
    "TRUNCATION_MARKER",
    "RubricBase",
    "RubricPolicy",
    "RubricPromptComposer",
    "build_material_manifest",
    "build_missing_declaration",
    "missing_label",
    "orchestrate_material_buckets",
    "truncate_to_budget",
]
