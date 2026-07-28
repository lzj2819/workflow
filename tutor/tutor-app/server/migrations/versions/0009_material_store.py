"""T-B01a SI-STORE：material_files 与 course_quota_usage 表。

Revision ID: 0009_material_store
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：SI-STORE，backfill T-B01a）：
- material_files：材料登记（ref PK、session/seq、course/submission 归属、
  DATA_DIR 相对路径、size_bytes、sha256、state staged/final/deleted、时间戳）；
- course_quota_usage：课程配额用量（KD-004 单课程 200GB，promote 前检查）。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型。
并行多头纪律：down_revision 固定为 wave-3 merge head（11a22f91f4b3），
集成时由 alembic merge heads 汇合。
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_material_store"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_files",
        sa.Column("material_ref", sa.String(512), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_material_files_session_id", "material_files", ["session_id"])
    op.create_index("ix_material_files_course_id", "material_files", ["course_id"])
    op.create_table(
        "course_quota_usage",
        sa.Column("course_id", sa.String(64), primary_key=True),
        sa.Column("used_bytes", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("course_quota_usage")
    op.drop_index("ix_material_files_course_id", table_name="material_files")
    op.drop_index("ix_material_files_session_id", table_name="material_files")
    op.drop_table("material_files")
