"""L14 CMP-REVIEW-COMMAND：ST-REVIEW-RECORD / ST-IDEMPOTENCY-REVIEW 表。

Revision ID: 0007_review_records
Revises: b9c6e3d6276a
Create Date: 2026-07-20

表（owner：CMP-REVIEW-COMMAND，ReviewRecord 唯一写方）：
- review_records：复核记录（original_grade 复制值创建后不可变）；
- review_grade_adjustments：调整留痕（每次成功变更一条，adjustment_id 唯一）；
- review_idempotency_keys：CT-008 request_id 与 M05-IC-01 submission_id 键，
  与业务写入同事务。

目标库 PostgreSQL、单测 SQLite：仅用可移植类型，JSON 字段用 sa.JSON。
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_review_records"
down_revision = "b9c6e3d6276a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_records",
        sa.Column("review_record_id", sa.String(64), primary_key=True),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column("original_grade", sa.String(1), nullable=True),
        sa.Column("dimension_rationales", sa.JSON, nullable=True),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_grade", sa.String(1), nullable=True),
        sa.Column("annotation", sa.Text, nullable=True),
        sa.Column("operator", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_id", name="uq_review_records_submission"),
    )
    op.create_table(
        "review_grade_adjustments",
        sa.Column("adjustment_id", sa.String(64), primary_key=True),
        sa.Column(
            "review_record_id",
            sa.String(64),
            sa.ForeignKey("review_records.review_record_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mutation_kind", sa.String(32), nullable=False),
        sa.Column("final_grade_before", sa.String(1), nullable=True),
        sa.Column("final_grade_after", sa.String(1), nullable=True),
        sa.Column("annotation_after", sa.Text, nullable=True),
        sa.Column("adjustment_reason", sa.Text, nullable=True),
        sa.Column("operator", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_review_adjustments_record",
        "review_grade_adjustments",
        ["review_record_id"],
    )
    op.create_table(
        "review_idempotency_keys",
        sa.Column("request_key", sa.String(64), primary_key=True),
        sa.Column("key_kind", sa.String(32), nullable=False),
        sa.Column("submission_id", sa.String(64), nullable=False),
        sa.Column(
            "review_record_id",
            sa.String(64),
            sa.ForeignKey("review_records.review_record_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("response_snapshot", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_idempotency_keys")
    op.drop_index(
        "ix_review_adjustments_record", table_name="review_grade_adjustments"
    )
    op.drop_table("review_grade_adjustments")
    op.drop_table("review_records")
