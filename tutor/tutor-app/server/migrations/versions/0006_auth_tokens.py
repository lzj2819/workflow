"""L09 SI-API：ST-06 AuthTokenGrant 令牌签发审计表。

Revision ID: 0006_auth_tokens
Revises: 9c99fa53f9f8
Create Date: 2026-07-20

表：auth_token_grants（owner：SI-API-AUTH）。只存令牌 sha256 哈希与主体指纹，
明文令牌/姓名/邀请码不落库。目标库 PostgreSQL、单测 SQLite：仅用可移植类型。
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_auth_tokens"
down_revision = "9c99fa53f9f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_token_grants",
        sa.Column("grant_id", sa.String(64), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("subject_fingerprint", sa.String(64), nullable=False),
        sa.Column("course_id", sa.String(64), nullable=True),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_auth_token_grants_token_hash",
        "auth_token_grants",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_token_grants_token_hash", table_name="auth_token_grants")
    op.drop_table("auth_token_grants")
