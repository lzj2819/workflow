"""ST-REVIEW-RECORD / ST-IDEMPOTENCY-REVIEW 持久化模型。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型，dimension_rationales
与幂等响应快照用 sa.JSON。业务写入（ReviewRecord + GradeAdjustmentRecord +
幂等记录）在同一本地事务提交（L1 03 / L2 LCD-002/003）。

原始等级不可变：`original_grade` 复制值只在 M05-IC-01 首次成功创建时写入，
后续 CT-008 只允许写 final_grade/annotation 并追加 GradeAdjustmentRecord。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """CMP-REVIEW-COMMAND 聚合表 Base（迁移见 0007_review_records.py）。"""


#: ST-REVIEW-RECORD 生命周期（created_on_scored → annotated/adjusted → …）。
STATUS_CREATED_ON_SCORED = "created_on_scored"
STATUS_ANNOTATED = "annotated"
STATUS_ADJUSTED = "adjusted"

#: 调整记录 mutation_kind。
MUTATION_ANNOTATED = "annotated"
MUTATION_ADJUSTED = "adjusted"
MUTATION_ANNOTATED_ADJUSTED = "annotated_adjusted"

#: 幂等键类别（LCD-003：两种键分层、不互相替代）。
KEY_KIND_CT008_REQUEST = "ct008_request"
KEY_KIND_MIC01_SUBMISSION = "mic01_submission"


class ReviewRecord(Base):
    """ReviewRecord 聚合（ST-REVIEW-RECORD；唯一写方：本服务）。

    `original_grade` 为原始等级复制值（含来源 submission_id 即本表
    submission_id），创建后不可变；`final_grade`/`annotation` 后写为准。
    """

    __tablename__ = "review_records"

    review_record_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    submission_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    original_grade: Mapped[str | None] = mapped_column(sa.String(1), nullable=True)
    dimension_rationales = mapped_column(sa.JSON, nullable=True)
    scored_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    final_grade: Mapped[str | None] = mapped_column(sa.String(1), nullable=True)
    annotation: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    operator: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("submission_id", name="uq_review_records_submission"),
    )


class GradeAdjustmentRecord(Base):
    """GradeAdjustmentRecord：每次成功变更追加一条（adjustment_id 唯一）。

    留痕四元组：变更前后最终等级 + 操作者 + 时间；adjustment_reason 可选
    （TD-09/DD-007/LCD-001：可选、不强制）。历史不被覆盖（后写为准只作用于
    ReviewRecord 当前值）。
    """

    __tablename__ = "review_grade_adjustments"

    adjustment_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    review_record_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("review_records.review_record_id", ondelete="CASCADE"),
        nullable=False,
    )
    mutation_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    final_grade_before: Mapped[str | None] = mapped_column(sa.String(1), nullable=True)
    final_grade_after: Mapped[str | None] = mapped_column(sa.String(1), nullable=True)
    annotation_after: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    operator: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.Index("ix_review_adjustments_record", "review_record_id"),
    )


class ReviewIdempotencyRecord(Base):
    """ST-IDEMPOTENCY-REVIEW：CT-008 request_id 与 M05-IC-01 submission_id 键。

    与业务写入同事务；命中时回放首次响应快照（CT-008）或返回既有记录
    （M05-IC-01）。只保留最小键、结果引用和快照，不保存教师会话。
    """

    __tablename__ = "review_idempotency_keys"

    request_key: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    key_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    submission_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    review_record_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("review_records.review_record_id", ondelete="CASCADE"),
        nullable=False,
    )
    response_snapshot = mapped_column(sa.JSON, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
