"""L02 SI-CORE：Submission 聚合表（ST-01；SIC-ST-01/02/03）。

Revision ID: 0003_submission_core
Revises: 0001_baseline
Create Date: 2026-07-20

表：submissions / submission_materials / submission_integrity_reports。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型（列表快照用 sa.JSON）。
Outbox 表（ST-04）归 SI-RELAY，由 Integration Owner 在投递器 backfill 迁移中建立；
本迁移只建 SI-CORE 聚合三表。
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_submission_core"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("submission_id", sa.String(64), primary_key=True),
        sa.Column("submission_uuid", sa.String(64), nullable=False),
        sa.Column("course_id", sa.String(64), nullable=True),
        sa.Column("assignment", sa.String(255), nullable=True),
        sa.Column("student_name", sa.String(255), nullable=True),
        sa.Column("group_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scoring_terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_uuid", name="uq_submissions_uuid"),
    )
    op.create_index("ix_submissions_uuid", "submissions", ["submission_uuid"], unique=True)

    op.create_table(
        "submission_materials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "submission_id",
            sa.String(64),
            sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("material_ref", sa.String(255), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("declared", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.UniqueConstraint("submission_id", "material_ref", name="uq_materials_ref"),
    )

    op.create_table(
        "submission_integrity_reports",
        sa.Column(
            "submission_id",
            sa.String(64),
            sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("expected_categories", sa.JSON, nullable=False),
        sa.Column("received_categories", sa.JSON, nullable=False),
        sa.Column("missing_items", sa.JSON, nullable=False),
        sa.Column("report_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("submission_integrity_reports")
    op.drop_table("submission_materials")
    op.drop_index("ix_submissions_uuid", table_name="submissions")
    op.drop_table("submissions")
