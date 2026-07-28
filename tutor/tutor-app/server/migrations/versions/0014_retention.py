"""T-B03c RETENTION-GOVERNANCE：删除批次聚合与删除审计记录（MOD-05 / NFR-004 / DF-3）。

Revision ID: 0014_retention
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：CMP-RETENTION-GOVERNANCE，MOD-05）：
- deletion_batches：DeletionBatch 聚合（课程 + 范围 + 保留到期时间 + 状态机
  pending_mark/awaiting_confirm/executing/partially_failed/completed +
  exclusions + 清除进度 failed_items/cleared_submission_ids/applied_purge_marks）；
- deletion_audit_records：删除审计（DeletionConfirmed → RecordsDeleted，只追加
  不删除；审计记录永久留存不在删除范围，CT-012 side_effects）。

目标库 PostgreSQL、单测 SQLite：仅用可移植类型；时间列存 naive UTC。
并行多头之一，集成时 alembic merge heads。
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_retention"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deletion_batches",
        sa.Column("batch_id", sa.String(128), primary_key=True),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("retention_due_at", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("exclusions", sa.JSON, nullable=False),
        sa.Column("failed_items", sa.JSON, nullable=False),
        sa.Column("cleared_submission_ids", sa.JSON, nullable=False),
        sa.Column("applied_purge_marks", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("confirmed_by", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_deletion_batches_course", "deletion_batches", ["course_id"])
    op.create_index(
        "ix_deletion_batches_due", "deletion_batches", ["status", "retention_due_at"]
    )
    op.create_table(
        "deletion_audit_records",
        sa.Column("audit_record_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(128), nullable=False),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("operator", sa.String(64), nullable=False),
        sa.Column("submission_ids", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_deletion_audit_batch", "deletion_audit_records", ["batch_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_deletion_audit_batch", table_name="deletion_audit_records")
    op.drop_table("deletion_audit_records")
    op.drop_index("ix_deletion_batches_due", table_name="deletion_batches")
    op.drop_index("ix_deletion_batches_course", table_name="deletion_batches")
    op.drop_table("deletion_batches")
