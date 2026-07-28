"""T-B01b SI-RELAY：ST-04 OutboxRecord 与 ST-05 InboundEventDedup 表。

Revision ID: 0010_outbox
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：SI-RELAY）：
- outbox_records：待投递事件记录（KD-002）。业务写入与 Outbox 行同一本地事务；
  状态机 pending → delivering →（confirmed | retry_wait → pending）；
  投递确认由 SI-RELAY 投递器标记。
- inbound_event_dedup：入站事件消费去重记录。event_key 唯一（CT-005 按
  submission_id+终态、CT-012 按 batch_id+载荷哈希，由消费方派生）；状态机
  received → processing → applied / retry_wait / quarantined；
  去重检查与业务处理同一事务；quarantined 不阻塞后续合法事件。
目标库 PostgreSQL、单测 SQLite：仅用可移植类型（payload 用 sa.JSON）。
并行多头之一，集成时 alembic merge heads。
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_outbox"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("dedup_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_outbox_records_due",
        "outbox_records",
        ["status", "next_attempt_at"],
    )
    op.create_table(
        "inbound_event_dedup",
        sa.Column("event_key", sa.String(128), primary_key=True),
        sa.Column("contract_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("inbound_event_dedup")
    op.drop_index("ix_outbox_records_due", table_name="outbox_records")
    op.drop_table("outbox_records")
