"""scoring_tasks + scoring_results（L03 CMP-SCORING-ORCHESTRATOR；ST-001/ST-002）。

Revision ID: 0004_scoring_tasks
Revises: 0001_baseline
Create Date: 2026-07-20

KD-002 任务表 + Outbox 安排：本迁移仅落地 MOD-04 所有的 ST-001（任务行）与
ST-002（结果内容）两表；共享 Outbox 表由 Integration Owner 在发布链路迁移中
统一建立（见 0001_baseline 说明），L03 终态事务经 shared/tutor_shared/outbox.py
抽象同事务入队。列类型与 worker/assessment_worker/scoring_orchestrator/models.py
保持一致（sa.JSON，SQLite 可测）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_scoring_tasks"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scoring_tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.String(128), nullable=False),
        sa.Column("course_id", sa.String(128), nullable=False),
        sa.Column("assignment", sa.Text, nullable=False),
        sa.Column("student_name", sa.String(128), nullable=False),
        sa.Column("group_name", sa.String(128), nullable=False),
        sa.Column("material_refs", sa.JSON, nullable=False),
        sa.Column("missing_items", sa.JSON, nullable=False),
        sa.Column("received_at", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.String(64), nullable=True),
        sa.Column("retry_record", sa.JSON, nullable=True),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime, nullable=True),
        sa.Column("reclaim_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("deadline_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("submission_id", name="uq_scoring_tasks_submission_id"),
    )
    op.create_index("ix_scoring_tasks_status", "scoring_tasks", ["status"])
    op.create_table(
        "scoring_results",
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("scoring_tasks.task_id"),
            primary_key=True,
        ),
        sa.Column("submission_id", sa.String(128), nullable=False),
        sa.Column("original_grade", sa.String(1), nullable=False),
        sa.Column("dimension_rationales", sa.JSON, nullable=False),
        sa.Column("teacher_suggestions", sa.JSON, nullable=False),
        sa.Column("scored_at", sa.DateTime, nullable=False),
        sa.Column("missing_materials_impact", sa.Text, nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("rubric_version", sa.String(64), nullable=True),
        sa.Column("model_meta", sa.JSON, nullable=True),
        sa.UniqueConstraint("submission_id", name="uq_scoring_results_submission_id"),
    )


def downgrade() -> None:
    op.drop_table("scoring_results")
    op.drop_index("ix_scoring_tasks_status", table_name="scoring_tasks")
    op.drop_table("scoring_tasks")
