"""L01 MOD-03 course-roster：Course 聚合表 + 校验记录表。

Revision ID: 0002_course_roster
Revises: 0001_baseline
Create Date: 2026-07-20

ST-COURSE（courses / invite_codes / roster_entries；owner：CMP-COURSE-ROSTER-ADMIN）与
ST-VERIFICATION-RECORD（verification_records；owner：CMP-MEMBERSHIP-VERIFIER）同库分表（KD-002）。
P1：invite_codes 主键唯一（邀请码唯一映射课程）；
CT-013 幂等：uq_roster_entries_course_name_group 去重键兜底。
本模块 publishes_events=[]，不建 Outbox 表。多头由协调者集成时合并。
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_course_roster"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("course_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("course_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "invite_codes",
        sa.Column("invite_code", sa.String(64), primary_key=True),
        sa.Column("course_id", sa.String(64), sa.ForeignKey("courses.course_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invite_codes_course_id", "invite_codes", ["course_id"])
    op.create_table(
        "roster_entries",
        sa.Column("entry_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("course_id", sa.String(64), sa.ForeignKey("courses.course_id"), nullable=False),
        sa.Column("student_name", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "course_id", "student_name", "group_name", name="uq_roster_entries_course_name_group"
        ),
    )
    op.create_index(
        "ix_roster_entries_lookup",
        "roster_entries",
        ["course_id", "student_name", "group_name"],
    )
    op.create_table(
        "verification_records",
        sa.Column("verification_id", sa.String(36), primary_key=True),
        sa.Column("invite_code", sa.String(64), nullable=False),
        sa.Column("student_name", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False),
        sa.Column("reason", sa.String(64), nullable=True),
        sa.Column("course_id", sa.String(64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("verification_records")
    op.drop_index("ix_roster_entries_lookup", table_name="roster_entries")
    op.drop_table("roster_entries")
    op.drop_index("ix_invite_codes_course_id", table_name="invite_codes")
    op.drop_table("invite_codes")
    op.drop_table("courses")
