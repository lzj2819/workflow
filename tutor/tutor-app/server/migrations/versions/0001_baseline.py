"""baseline：迁移链起点（Phase 1）。

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-20

不包含任何表：各聚合表随叶子 migration 落地（L01/L02/L03/L08/L09/L14-L16 与
backfill）。Outbox 表与入站去重表由 Integration Owner 在首个发布事件的
叶子/回填 migration 中一并建立（业务行与 Outbox 行同事务写入，KD-002）。
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
