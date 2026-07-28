"""ST-PRESENTATION-VIEW / ST-IDEMPOTENCY-PRESENTATION 持久化模型。

owner：CMP-PRES-SNAPSHOT-STORE（单写方，LCD-PRES-003）。快照一次性写入，
不随源读模型实时变化；同键再生成写新快照并将旧快照标记 superseded；
快照与幂等记录在同一父本地事务写入（父 03 事务边界）。

blocks/group_ids/course_ids 以 JSON 文本落库（快照复制值，不含材料本体）。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型。迁移见
server/migrations/versions/0008_presentation_views.py。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """CMP-PRESENTATION 自有元数据（ST-PRESENTATION-VIEW/ST-IDEMPOTENCY-PRESENTATION）。"""


#: PresentationSnapshotLifecycle 值域（snapshot_created → superseded → purged）。
STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
STATUS_PURGED = "purged"


class PresentationViewRecord(Base):
    """ST-PRESENTATION-VIEW：展示视图快照（生成参数、blocks、来源读模型版本）。"""

    __tablename__ = "presentation_views"

    presentation_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    # 父 CT-009 幂等键（教师 + 规范化小组集合 + 时间窗）的 sha256 编码。
    generation_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # 教师 + 规范化小组集合（不含时间窗）的 sha256：跨窗口 supersede 定位。
    group_set_key: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    teacher_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # 生成时课程归属快照（JSON array），用于幂等命中时的 FORBIDDEN 复核。
    course_ids: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 规范化后的小组集合（JSON array，请求序去重）。
    group_ids: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # CT-009 blocks[] 快照复制值（JSON array）；写入后不随读模型变化。
    blocks: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_read_model_version: Mapped[str | None] = mapped_column(
        sa.String(64), nullable=True
    )
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.Index("ix_presentation_views_generation_key", "generation_key"),
        sa.Index("ix_presentation_views_group_set_key", "group_set_key"),
    )


class PresentationIdempotencyRecord(Base):
    """ST-IDEMPOTENCY-PRESENTATION：生成键 → 最新快照（与快照写入同事务）。"""

    __tablename__ = "presentation_idempotency"

    generation_key: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    presentation_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    teacher_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
