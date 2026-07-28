"""T-B03b READMODEL-PROJECTOR：教师读模型表与投影位点（MOD-05 / ST-READ-MODEL）。

Revision ID: 0013_read_model
Revises: 11a22f91f4b3
Create Date: 2026-07-21

表（owner：CMP-READMODEL-PROJECTOR，MOD-05）：
- rm_courses / rm_groups / rm_students：CT-006 派生的课程/小组/学生目录；
- rm_submissions：提交读模型快照（状态/缺失项/材料引用/原始等级/五维依据/
  教师建议/批注/最终等级/失败原因/重试记录 + M05-IC-05 幂等键）；
- rm_purge_tombstones：CT-012/CT-014 清除墓碑（重放守卫：旧事件重放不重建
  已清除数据）；
- projection_checkpoints：消费位点（consumer、position），与投影写入同一
  本地事务推进（ST-PROJECTION-CHECKPOINT）。

目标库 PostgreSQL、单测 SQLite：仅用可移植类型；时间列存 naive UTC。
并行多头之一，集成时 alembic merge heads。
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_read_model"
down_revision = "11a22f91f4b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rm_courses",
        sa.Column("course_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "rm_groups",
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("group_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint("course_id", "group_id", name="pk_rm_groups"),
    )
    op.create_table(
        "rm_students",
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("group_id", sa.String(128), nullable=False),
        sa.Column("student_name", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.PrimaryKeyConstraint(
            "course_id", "group_id", "student_name", name="pk_rm_students"
        ),
    )
    op.create_table(
        "rm_submissions",
        sa.Column("submission_id", sa.String(64), primary_key=True),
        sa.Column("course_id", sa.String(64), nullable=False),
        sa.Column("group_id", sa.String(128), nullable=False),
        sa.Column("student_name", sa.String(128), nullable=False),
        sa.Column("assignment", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("missing_items", sa.JSON, nullable=False),
        sa.Column("material_refs", sa.JSON, nullable=False),
        sa.Column("original_grade", sa.String(8), nullable=True),
        sa.Column("dimension_rationales", sa.JSON, nullable=True),
        sa.Column("teacher_suggestions", sa.JSON, nullable=True),
        sa.Column("annotations", sa.JSON, nullable=False),
        sa.Column("final_grade", sa.String(8), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("retry_record", sa.JSON, nullable=True),
        sa.Column("applied_adjustment_ids", sa.JSON, nullable=False),
        sa.Column("received_at", sa.DateTime, nullable=True),
        sa.Column("scored_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_rm_submissions_course", "rm_submissions", ["course_id"]
    )
    op.create_index(
        "ix_rm_submissions_group", "rm_submissions", ["course_id", "group_id"]
    )
    op.create_table(
        "rm_purge_tombstones",
        sa.Column("submission_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("purged_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "projection_checkpoints",
        sa.Column("consumer", sa.String(64), primary_key=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("projection_checkpoints")
    op.drop_table("rm_purge_tombstones")
    op.drop_index("ix_rm_submissions_group", table_name="rm_submissions")
    op.drop_index("ix_rm_submissions_course", table_name="rm_submissions")
    op.drop_table("rm_submissions")
    op.drop_table("rm_students")
    op.drop_table("rm_groups")
    op.drop_table("rm_courses")
