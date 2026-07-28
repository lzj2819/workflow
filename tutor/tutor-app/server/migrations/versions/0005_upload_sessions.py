"""L08 SI-XFER：上传会话表（ST-02；ST-XFER-01/02/03）。

Revision ID: 0005_upload_sessions
Revises: 9c99fa53f9f8
Create Date: 2026-07-20

表：upload_sessions / upload_chunk_receipts / upload_finalize_attempts。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型（类别清单/material_refs 用 sa.JSON）。
多头合并由协调者集成时处理；本迁移 down_revision 固定为 wave-1 合并头。
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_upload_sessions"
down_revision = "9c99fa53f9f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("submission_uuid", sa.String(64), nullable=False),
        sa.Column("declared_categories", sa.JSON, nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("received_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_expected_seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("retry_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("material_refs", sa.JSON, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("submission_uuid", name="uq_upload_sessions_uuid"),
    )
    op.create_index(
        "ix_upload_sessions_uuid", "upload_sessions", ["submission_uuid"], unique=True
    )

    op.create_table(
        "upload_chunk_receipts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("upload_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("digest", sa.String(128), nullable=False),
        sa.Column("staged_ref", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="accepted"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "seq", name="uq_chunk_receipts_session_seq"),
    )

    op.create_table(
        "upload_finalize_attempts",
        sa.Column("attempt_id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("upload_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_result", sa.JSON, nullable=True),
        sa.Column("merge_status", sa.String(32), nullable=False),
        sa.Column("material_refs", sa.JSON, nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("upload_finalize_attempts")
    op.drop_table("upload_chunk_receipts")
    op.drop_index("ix_upload_sessions_uuid", table_name="upload_sessions")
    op.drop_table("upload_sessions")
