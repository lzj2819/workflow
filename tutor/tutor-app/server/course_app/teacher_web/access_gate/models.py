"""T-B03a ACCESS-GATE 持久化模型（迁移见 server/migrations/versions/0012_access_gate.py）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型。
安全口径（DD-004）：
- 口令只存 PBKDF2-HMAC-SHA256 哈希 + 盐 + 迭代次数，明文口令不入库；
- 会话为不透明令牌，只存 sha256 哈希，明文令牌不入库；
- 时间列存 naive UTC（服务层统一转换，避免 SQLite 时区回读歧义）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """ACCESS-GATE 登记表 Base（独立于其他组件 Base，互不耦合）。"""


# TeacherAccount.status 值域
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"


class TeacherAccount(Base):
    """教师账号（v1 运维预置单教师，DD-004）：口令只存哈希。"""

    __tablename__ = "teacher_accounts"

    teacher_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    account: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    password_salt: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    password_iterations: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default=STATUS_ACTIVE)
    created_at = mapped_column(sa.DateTime, nullable=False)
    updated_at = mapped_column(sa.DateTime, nullable=False)


class TeacherSession(Base):
    """教师会话：不透明令牌的服务端登记（只存 sha256 哈希，12h 滑动续期）。"""

    __tablename__ = "teacher_sessions"

    token_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at = mapped_column(sa.DateTime, nullable=False)
    last_seen_at = mapped_column(sa.DateTime, nullable=False)
    expires_at = mapped_column(sa.DateTime, nullable=False)

    __table_args__ = (sa.Index("ix_teacher_sessions_teacher_id", "teacher_id"),)


class TeacherAccessGrant(Base):
    """课程范围授权（LCD-006 本地持有）：(teacher_id, course_id) 二元组。"""

    __tablename__ = "teacher_access_grants"

    teacher_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    created_at = mapped_column(sa.DateTime, nullable=False)


class AccessDeniedLog(Base):
    """AccessDeniedLogged 追加式审计（ST-ACCESS-DENIED-LOG）：只追加不删除。

    不含口令/令牌明文：仅教师标识、课程、动作、来源与时间。
    """

    __tablename__ = "access_denied_log"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    course_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at = mapped_column(sa.DateTime, nullable=False)
