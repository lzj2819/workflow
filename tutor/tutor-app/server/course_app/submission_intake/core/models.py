"""ST-01 持久化模型（SIC-ST-01/02/03）。

约束：PostgreSQL 为目标库，单测用 SQLite —— 禁用 PG 专有类型，类别快照/报告
列表用 sa.JSON。状态机语义见 status.py；业务写入与 Outbox 行同事务（service.py）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-CORE 聚合表 Base（迁移见 server/migrations/versions/0003_submission_core.py）。"""


class Submission(Base):
    """SIC-ST-01 SubmissionIdentityAndLifecycle。"""

    __tablename__ = "submissions"

    submission_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    submission_uuid: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # 身份关联：received 路径必填非空；rejected/upload_failed 可能缺少完整身份
    # （归属校验未通过时 course_id 未知），故可空。事件载荷由 service 层保证必填字段。
    course_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    assignment: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    student_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    group_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # 聚合版本：每次状态迁移 +1，配合唯一键串行化同一 uuid 的写入（SIC-INV-01）。
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    received_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    processing_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    scoring_terminal_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    deleted_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("submission_uuid", name="uq_submissions_uuid"),
    )


class SubmissionMaterial(Base):
    """SIC-ST-02 MaterialManifest 条目（只存 SI-STORE 元数据，不含文件内容）。"""

    __tablename__ = "submission_materials"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
    )
    material_ref: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    declared: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    filename: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("submission_id", "material_ref", name="uq_materials_ref"),
    )


class IntegrityReportRow(Base):
    """SIC-ST-03 IntegrityReport（与清单/状态同事务提交，随后只读）。"""

    __tablename__ = "submission_integrity_reports"

    submission_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("submissions.submission_id", ondelete="CASCADE"),
        primary_key=True,
    )
    expected_categories = mapped_column(sa.JSON, nullable=False)
    received_categories = mapped_column(sa.JSON, nullable=False)
    missing_items = mapped_column(sa.JSON, nullable=False)
    report_version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    generated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
