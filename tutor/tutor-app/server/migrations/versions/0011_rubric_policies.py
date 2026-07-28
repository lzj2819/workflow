"""T-B02b RUBRIC-PROMPT-COMPOSER：ST-004 RubricPolicy 版本化存证表。

Revision ID: 0011_rubric_policies
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：CMP-RUBRIC-PROMPT-COMPOSER，MOD-04）：
- rubric_policies：五维度评分准则与提示模板存证（ST-004）。rubric_version +
  prompt_version 为版本标识；status ∈ {active, superseded}；评分主路径只读，
  一次评估固定使用单一 active 版本；旧版本随结果存证保留可追溯（LCD-003），
  版本变更不要求历史结果重算。
- 同库 active 唯一：部分唯一索引 uq_rubric_policies_active
  （status='active'，PG/SQLite 均支持部分索引）。
- 种子 v1：五维模板（与 contracts/ct-010.json 五维枚举一致）+ 缺失材料影响
  提示 + A–E 默认区间（FR-008）。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型（dimensions/grade_bands 用 sa.JSON）。
并行多头之一，集成时 alembic merge heads。
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0011_rubric_policies"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None

SEED_RUBRIC_VERSION = "rubric-v1"
SEED_PROMPT_VERSION = "prompt-v1"

# 与 contracts/ct-010.json response.dimension_rationales.dimension 枚举一致（顺序固定）
SEED_DIMENSIONS = ["需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性"]
# FR-008 默认区间（ST-004：A=90–100 … E=0–59）
SEED_GRADE_BANDS = {
    "A": "90–100",
    "B": "80–89",
    "C": "70–79",
    "D": "60–69",
    "E": "0–59",
}

# 种子 v1 模板：含五维度、默认区间、缺失材料影响提示与输出格式要求。
# {{assignment}} / {{material_manifest}} / {{missing_declaration}} 为组装占位符，
# 由 RubricPromptComposer 纯替换（同版本同输入同输出）。
SEED_TEMPLATE_BODY = """你是课程作业评估助手。请依据以下五维度评分准则，对学生提交进行评估。

【作业要求】
{{assignment}}

【评分维度】（须逐维度给出文字依据）
1. 需求理解
2. Codex 迭代过程
3. 代码质量
4. 最终功能
5. 文档/展示完整性

【等级默认区间】
A=90–100；B=80–89；C=70–79；D=60–69；E=0–59

【提交材料清单】
{{material_manifest}}

【缺失材料声明】
{{missing_declaration}}
缺失材料影响提示：对声明缺失的类别，对应维度仅能依据其余已提供材料推断，评估置信度相应降低；不得因材料缺失而伪造评估依据。

【输出格式要求】
仅输出 JSON，不输出任何 JSON 以外的内容：
{"grade": "A–E 之一", "dimension_rationales": [{"dimension": "维度名", "rationale": "文字依据"}]（恰为上述五维度，顺序一致）, "suggestions": ["教师专用建议"]}"""

SEED_CREATED_AT = datetime(2026, 7, 21, 0, 0, 0)  # 固定种子时间，保证可重放

_ACTIVE_ONLY = sa.text("status = 'active'")


def upgrade() -> None:
    op.create_table(
        "rubric_policies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rubric_version", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("template_body", sa.Text, nullable=False),
        sa.Column("dimensions", sa.JSON, nullable=False),
        sa.Column("grade_bands", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint(
            "rubric_version", "prompt_version", name="uq_rubric_policies_version"
        ),
    )
    op.create_index(
        "uq_rubric_policies_active",
        "rubric_policies",
        ["status"],
        unique=True,
        sqlite_where=_ACTIVE_ONLY,
        postgresql_where=_ACTIVE_ONLY,
    )
    seed = sa.table(
        "rubric_policies",
        sa.column("rubric_version", sa.String),
        sa.column("prompt_version", sa.String),
        sa.column("template_body", sa.Text),
        sa.column("dimensions", sa.JSON),
        sa.column("grade_bands", sa.JSON),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(
        seed,
        [
            {
                "rubric_version": SEED_RUBRIC_VERSION,
                "prompt_version": SEED_PROMPT_VERSION,
                "template_body": SEED_TEMPLATE_BODY,
                "dimensions": SEED_DIMENSIONS,
                "grade_bands": SEED_GRADE_BANDS,
                "status": "active",
                "created_at": SEED_CREATED_AT,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_rubric_policies_active", table_name="rubric_policies")
    op.drop_table("rubric_policies")
