"""ST-05 InboundEventDedup 持久化模型（迁移见 0010_outbox.py）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型。去重检查与业务
处理（状态回写/清除触发）同一本地事务（ST-05 不变量）；quarantined 不阻塞
后续合法事件。本表仅含业务键、事件摘要与错误原因，不含 payload 内容。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-RELAY 消费端去重表 Base（迁移见 0010_outbox.py）。"""


#: ST-05 生命周期：received → processing → applied / retry_wait / quarantined。
DEDUP_STATUSES = ("received", "processing", "applied", "retry_wait", "quarantined")


class InboundDedupRecord(Base):
    """入站事件消费去重记录（ST-05；唯一写方：SI-RELAY 消费端）。

    event_key 由消费方按契约派生（CT-005：submission_id+终态；CT-012：
    batch_id+载荷哈希），唯一约束保证重复事件不重复应用。
    """

    __tablename__ = "inbound_event_dedup"

    event_key: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    contract_id: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
