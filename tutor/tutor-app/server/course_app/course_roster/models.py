"""L01 状态模型：ST-COURSE 聚合 + ST-VERIFICATION-RECORD（03-state-and-data §1）。

同库分表（KD-002），各表仅由其 owner 组件写入：
- courses / invite_codes / roster_entries → CMP-COURSE-ROSTER-ADMIN
- verification_records → CMP-MEMBERSHIP-VERIFIER

生产目标 PostgreSQL；单元测试 SQLite（sqlite:///:memory:）。禁用 PG 专有类型。
时间戳一律 UTC（timezone=True；SQLite 读取为 naive，按 UTC 解释）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """MOD-03 自有元数据（模块边界内，不外溢）。"""


class Course(Base):
    """Course 聚合根：课程 + 课程结束时间（FLOW-011 只读引用目标）。"""

    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    course_end_time: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, nullable=False)


class InviteCode(Base):
    """邀请码：P1 唯一映射课程（主键唯一约束兜底）。"""

    __tablename__ = "invite_codes"

    invite_code: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(sa.ForeignKey("courses.course_id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, nullable=False)


class RosterEntry(Base):
    """名单条目：导入去重键 (course_id, student_name, group_name)（CT-013 幂等条款）。"""

    __tablename__ = "roster_entries"
    __table_args__ = (
        sa.UniqueConstraint("course_id", "student_name", "group_name", name="uq_roster_entries_course_name_group"),
    )

    entry_id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(sa.ForeignKey("courses.course_id"), nullable=False)
    student_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, nullable=False)


class VerificationRecord(Base):
    """校验记录（ST-VERIFICATION-RECORD，append-only，LCD-003）。

    不含 submission_id：与提交的关联由调用方 MOD-02 侧持有（CT-003 契约无该字段，不得新增）。
    """

    __tablename__ = "verification_records"

    verification_id: Mapped[str] = mapped_column(
        sa.String(36), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    invite_code: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    student_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    group_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    verified: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    course_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=_utcnow, nullable=False)
