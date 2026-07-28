"""purge executions (T-B01c ST-07 补迁移，Integration Owner)

Revision ID: 0015_purge_execution
Revises: 11a22f91f4b3
Create Date: 2026-07-21

T-B01c 任务书未含迁移文件（协调者疏漏），本迁移由 Integration Owner 补齐：
purge_executions（批次执行登记）+ purge_execution_items（逐项结果，失败可重跑）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_purge_execution"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purge_executions",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(255), nullable=False),
        sa.Column("audit_record_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("run_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("first_executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "purge_execution_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "batch_id",
            sa.String(64),
            sa.ForeignKey("purge_executions.batch_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "submission_id", name="uq_purge_items_batch_sub"),
    )


def downgrade() -> None:
    op.drop_table("purge_execution_items")
    op.drop_table("purge_executions")
