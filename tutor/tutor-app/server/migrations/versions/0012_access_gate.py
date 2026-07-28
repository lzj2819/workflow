"""T-B03a ACCESS-GATE：教师认证与课程授权表（MOD-05 / A-001 / KD-005 教师侧）。

Revision ID: 0012_access_gate
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：CMP-ACCESS-GATE，MOD-05）：
- teacher_accounts：教师账号（v1 运维预置单教师，DD-004）。口令只存
  PBKDF2-HMAC-SHA256 哈希 + 盐 + 迭代次数，明文口令不落库；
  status ∈ {active, disabled}。
- teacher_sessions：不透明会话令牌登记（DD-004 12h 滑动续期）。只存令牌
  sha256 哈希，明文令牌不落库；expires_at 随每次校验滑动顺延。
- teacher_access_grants：课程范围授权（LCD-006 本地持有），
  (teacher_id, course_id) 复合主键。
- access_denied_log：AccessDeniedLogged 追加式审计（ST-ACCESS-DENIED-LOG，
  只追加不随提交删除）：教师/课程/动作/来源/时间，不含口令/令牌明文。

目标库 PostgreSQL、单测 SQLite：仅用可移植类型；时间列存 naive UTC。
并行多头之一，集成时 alembic merge heads。
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_access_gate"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teacher_accounts",
        sa.Column("teacher_id", sa.String(64), primary_key=True),
        sa.Column("account", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("password_salt", sa.String(64), nullable=False),
        sa.Column("password_iterations", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("account", name="uq_teacher_accounts_account"),
    )
    op.create_table(
        "teacher_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("teacher_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_seen_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_teacher_sessions_teacher_id",
        "teacher_sessions",
        ["teacher_id"],
    )
    op.create_table(
        "teacher_access_grants",
        sa.Column("teacher_id", sa.String(64), nullable=False),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint(
            "teacher_id", "course_id", name="pk_teacher_access_grants"
        ),
    )
    op.create_table(
        "access_denied_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("teacher_id", sa.String(64), nullable=True),
        sa.Column("course_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("access_denied_log")
    op.drop_table("teacher_access_grants")
    op.drop_index("ix_teacher_sessions_teacher_id", table_name="teacher_sessions")
    op.drop_table("teacher_sessions")
    op.drop_table("teacher_accounts")
