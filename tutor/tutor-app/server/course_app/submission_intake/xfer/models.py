"""ST-02 持久化模型（ST-XFER-01/02/03）。

约束：PostgreSQL 为目标库，单测用 SQLite —— 禁用 PG 专有类型，类别清单/
material_refs 快照用 sa.JSON。状态语义见 service.py；迁移见
server/migrations/versions/0005_upload_sessions.py。

不持久化文件内容：ChunkReceipt 只保存传输元数据与 SI-STORE 暂存引用
（ST-XFER-02）；FinalizeAttempt 只保存检查/合并摘要（ST-XFER-03）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-XFER 会话表 Base（独立于 SI-CORE Base，互不耦合）。"""


class UploadSession(Base):
    """ST-XFER-01 UploadSession：会话、断点续传进度、失败原因、重试截止时间。"""

    __tablename__ = "upload_sessions"

    session_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    submission_uuid: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    declared_categories = mapped_column(sa.JSON, nullable=False)
    # 外部状态值域（L1 ST-02 冻结）：
    # receiving / interrupted_retryable / merged / pending_verification / failed_terminal
    state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    received_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    next_expected_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retry_deadline = mapped_column(sa.DateTime(timezone=True), nullable=True)
    # 会话 TTL（LCD-006 implementation_detail）；过期由注入时钟判定
    expires_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    material_refs = mapped_column(sa.JSON, nullable=True)
    # 聚合版本：同 session 单写者串行化（L2D-001）
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("submission_uuid", name="uq_upload_sessions_uuid"),
    )


class ChunkReceipt(Base):
    """ST-XFER-02 ChunkReceipt：已确认分片清单（checkpoint 只含 accepted 分片）。"""

    __tablename__ = "upload_chunk_receipts"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("upload_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    digest: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    staged_ref: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # accepted / duplicate_ignored（重复分片不新增行，仅原行可标记重放计数语义）
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="accepted")
    accepted_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("session_id", "seq", name="uq_chunk_receipts_session_seq"),
    )


class FinalizeAttempt(Base):
    """ST-XFER-03 FinalizeAttempt：最终化持久化检查点（L2D-003，先于 promote 记录）。"""

    __tablename__ = "upload_finalize_attempts"

    attempt_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("upload_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    check_result = mapped_column(sa.JSON, nullable=True)
    # started / merged / failed
    merge_status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    material_refs = mapped_column(sa.JSON, nullable=True)
    error_category: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    started_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    completed_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
