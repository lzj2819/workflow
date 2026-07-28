"""T-B03b READMODEL-PROJECTOR 持久化模型（迁移见 0013_read_model.py）。

ST-READ-MODEL（03-data-and-consistency：派生、秒级滞后、可重放重建）：
- rm_courses / rm_groups / rm_students：由 CT-006 事件派生的层级目录
  （只存标识与派生时间，不同步读 L01 名单）；
- rm_submissions：提交读模型快照（状态/缺失项/材料引用/原始等级/五维依据/
  教师建议/批注/最终等级/失败原因/重试记录）；applied_adjustment_ids 供
  M05-IC-05 事件按 adjustment_id 幂等去重；
- rm_purge_tombstones：CT-012/CT-014 清除墓碑（重放守卫：旧事件重放不重建
  已清除数据）；
- projection_checkpoints：消费位点（consumer、position），与投影写入同一
  本地事务推进（ST-PROJECTION-CHECKPOINT）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型；时间列存 naive UTC。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """READMODEL-PROJECTOR 读模型 Base（独立于其他组件 Base，互不耦合）。"""


class RmCourse(Base):
    """课程目录行（CT-006 派生）。"""

    __tablename__ = "rm_courses"

    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    created_at = mapped_column(sa.DateTime, nullable=False)
    updated_at = mapped_column(sa.DateTime, nullable=False)


class RmGroup(Base):
    """小组目录行（CT-006 派生）：(course_id, group_id) 复合主键。"""

    __tablename__ = "rm_groups"

    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    created_at = mapped_column(sa.DateTime, nullable=False)
    updated_at = mapped_column(sa.DateTime, nullable=False)


class RmStudent(Base):
    """学生目录行（CT-006 派生）：(course_id, group_id, student_name) 复合主键。

    CT-006 不携带学生学号，读模型以 (课程, 小组, 姓名) 为学生身份键。
    """

    __tablename__ = "rm_students"

    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    student_name: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    created_at = mapped_column(sa.DateTime, nullable=False)
    updated_at = mapped_column(sa.DateTime, nullable=False)


class RmSubmission(Base):
    """提交读模型快照（CT-005/CT-006 投影 + M05-IC-05 复核事件投影）。"""

    __tablename__ = "rm_submissions"

    submission_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    group_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, default="")
    student_name: Mapped[str] = mapped_column(
        sa.String(128), nullable=False, default=""
    )
    assignment: Mapped[str] = mapped_column(sa.String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    missing_items = mapped_column(sa.JSON, nullable=False, default=list)
    material_refs = mapped_column(sa.JSON, nullable=False, default=list)
    original_grade: Mapped[str | None] = mapped_column(sa.String(8), nullable=True)
    dimension_rationales = mapped_column(sa.JSON, nullable=True)
    teacher_suggestions = mapped_column(sa.JSON, nullable=True)
    annotations = mapped_column(sa.JSON, nullable=False, default=list)
    final_grade: Mapped[str | None] = mapped_column(sa.String(8), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retry_record = mapped_column(sa.JSON, nullable=True)
    applied_adjustment_ids = mapped_column(sa.JSON, nullable=False, default=list)
    received_at = mapped_column(sa.DateTime, nullable=True)
    scored_at = mapped_column(sa.DateTime, nullable=True)
    created_at = mapped_column(sa.DateTime, nullable=False)
    updated_at = mapped_column(sa.DateTime, nullable=False)

    __table_args__ = (
        sa.Index("ix_rm_submissions_course", "course_id"),
        sa.Index("ix_rm_submissions_group", "course_id", "group_id"),
    )


class RmPurgeTombstone(Base):
    """清除墓碑（ST-07 读模型侧）：重放守卫依据。

    CT-012/CT-014 清除投影行后登记；后续重放同 submission_id 的旧事件
    （CT-005/CT-006）命中墓碑即跳过，不重建已清除数据。
    """

    __tablename__ = "rm_purge_tombstones"

    submission_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    purged_at = mapped_column(sa.DateTime, nullable=False)
    created_at = mapped_column(sa.DateTime, nullable=False)


class ProjectionCheckpoint(Base):
    """投影位点（ST-PROJECTION-CHECKPOINT）：与投影写入同一事务推进。"""

    __tablename__ = "projection_checkpoints"

    consumer: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    updated_at = mapped_column(sa.DateTime, nullable=False)
