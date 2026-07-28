"""assessment purge tombstones + retention dual-flow columns (CCR-001 方案 A)

Revision ID: 0016_ccr001_assessment_purge
Revises: 27867c368f7e
Create Date: 2026-07-23

CCR-001（用户 2026-07-22 批准方案 A）：
- assessment_purge_tombstones：MOD-04 评分清除最小墓碑
  （submission_id / batch_id / purged_at；不含评分内容，用于 CT-005 重放守卫）；
- deletion_batches 增列：ct015_purge_marks（CT-015 幂等标记）与
  flow_states（CT-014/CT-015 双回流到达与失败项快照）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_ccr001_assessment_purge"
down_revision = "27867c368f7e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_purge_tombstones",
        sa.Column("submission_id", sa.String(128), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("deletion_batches") as batch:
        batch.add_column(sa.Column("ct015_purge_marks", sa.JSON, nullable=True))
        batch.add_column(sa.Column("flow_states", sa.JSON, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("deletion_batches") as batch:
        batch.drop_column("flow_states")
        batch.drop_column("ct015_purge_marks")
    op.drop_table("assessment_purge_tombstones")
