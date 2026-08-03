"""L16 CMP-PRESENTATION：ST-PRESENTATION-VIEW 与 ST-IDEMPOTENCY-PRESENTATION 表。

Revision ID: 0008_presentation_views
Revises: b9c6e3d6276a
Create Date: 2026-07-20

表（owner：CMP-PRES-SNAPSHOT-STORE）：
- presentation_views：展示视图快照（生成参数、blocks JSON、来源读模型版本、
  生命周期状态 active/superseded/purged）；一次性写入，不随源数据实时更新。
- presentation_idempotency：父 CT-009 幂等键（教师+规范化小组集合+时间窗
  的 sha256）→ 最新快照；与快照写入同一父本地事务。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型。
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_presentation_views"
down_revision = "b9c6e3d6276a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "presentation_views",
        sa.Column("presentation_id", sa.String(64), primary_key=True),
        sa.Column("generation_key", sa.String(64), nullable=False),
        sa.Column("group_set_key", sa.String(64), nullable=False),
        sa.Column("teacher_id", sa.String(64), nullable=False),
        sa.Column("course_ids", sa.Text, nullable=False),
        sa.Column("group_ids", sa.Text, nullable=False),
        sa.Column("blocks", sa.Text, nullable=False),
        sa.Column("source_read_model_version", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_presentation_views_generation_key",
        "presentation_views",
        ["generation_key"],
    )
    op.create_index(
        "ix_presentation_views_group_set_key",
        "presentation_views",
        ["group_set_key"],
    )
    op.create_table(
        "presentation_idempotency",
        sa.Column("generation_key", sa.String(64), primary_key=True),
        sa.Column("presentation_id", sa.String(64), nullable=False),
        sa.Column("teacher_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("presentation_idempotency")
    op.drop_index(
        "ix_presentation_views_group_set_key", table_name="presentation_views"
    )
    op.drop_index(
        "ix_presentation_views_generation_key", table_name="presentation_views"
    )
    op.drop_table("presentation_views")
