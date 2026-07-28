"""SI-STORE 持久化模型（T-B01a；迁移见 server/migrations/versions/0009_material_store.py）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型。
不存文件内容：MaterialFile 只登记磁盘路径与完整性元数据（DD-005）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-STORE 登记表 Base（独立于 SI-CORE/SI-XFER Base，互不耦合）。"""


# MaterialFile.state 值域
STATE_STAGED = "staged"
STATE_FINAL = "final"
STATE_DELETED = "deleted"


class MaterialFile(Base):
    """材料登记：暂存/正式/删除三态；ref 为对外不透明引用。"""

    __tablename__ = "material_files"

    material_ref: Mapped[str] = mapped_column(sa.String(512), primary_key=True)
    session_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    course_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    submission_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    # DATA_DIR 相对路径（不持久化绝对路径，便于 DATA_DIR 迁移）
    path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # staged / final / deleted
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.Index("ix_material_files_session_id", "session_id"),
        sa.Index("ix_material_files_course_id", "course_id"),
    )


class CourseQuotaUsage(Base):
    """课程配额用量（KD-004：单课程 200GB，promote 前检查）。"""

    __tablename__ = "course_quota_usage"

    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    used_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
