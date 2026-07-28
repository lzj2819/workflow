"""ST-06 AuthTokenGrant 持久化模型（owner：SI-API-AUTH）。

审计字段最小化（03-state-and-data §1）：只存令牌哈希与主体指纹，
令牌明文绝不入库；姓名/邀请码不明文落库（sha256 指纹）。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型。迁移见
server/migrations/versions/0006_auth_tokens.py。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-API 自有元数据（ST-06，模块边界内，不外溢）。"""


#: ST-06 签发结果值域。
RESULT_GRANTED = "granted"
RESULT_REJECTED = "rejected"


class AuthTokenGrant(Base):
    """ST-06 令牌签发审计：grant_id、主体/课程指纹、签发/过期时间、结果、request_id。"""

    __tablename__ = "auth_token_grants"

    grant_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    # 不透明令牌的 sha256 哈希（DD-004）；拒绝记录为空。明文令牌不落库。
    token_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    # 主体指纹：sha256(invite_code|student_name|group_name)，隐私最小化。
    subject_fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    course_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    issued_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    expires_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.Index("ix_auth_token_grants_token_hash", "token_hash", unique=True),
    )
