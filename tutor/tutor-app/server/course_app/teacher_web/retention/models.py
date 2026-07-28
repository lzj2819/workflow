"""T-B03c RETENTION-GOVERNANCE 持久化模型（迁移见 server/migrations/versions/0014_retention.py）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型；时间列存 naive UTC
（服务层统一转换，与 ACCESS-GATE 口径一致）。

语义（NFR-004 / DF-3 / CT-011 side_effects）：
- DeletionBatch 聚合状态机：pending_mark（已标记未到期）→ awaiting_confirm
  （到期待教师确认）→ executing（已确认，CT-012 已发布）→ partially_failed
  （CT-014 回写存在失败项，保留供重跑）→ completed（全部清除）；
- deletion_audit_records 只追加不删除：审计记录永久留存不在删除范围
  （CT-012 side_effects）；审计先于任何清除动作写入（服务层顺序保证）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """RETENTION-GOVERNANCE 登记表 Base（独立于其他组件 Base，互不耦合）。"""


# DeletionBatch.status 值域（冻结：T-B03c 交付物定义）
STATUS_PENDING_MARK = "pending_mark"
STATUS_AWAITING_CONFIRM = "awaiting_confirm"
STATUS_EXECUTING = "executing"
STATUS_PARTIALLY_FAILED = "partially_failed"
STATUS_COMPLETED = "completed"

BATCH_STATUSES = (
    STATUS_PENDING_MARK,
    STATUS_AWAITING_CONFIRM,
    STATUS_EXECUTING,
    STATUS_PARTIALLY_FAILED,
    STATUS_COMPLETED,
)

#: 删除审计动作（CT-011 side_effects：DeletionConfirmed → RecordsDeleted）
ACTION_DELETION_CONFIRMED = "DeletionConfirmed"
ACTION_RECORDS_DELETED = "RecordsDeleted"


class DeletionBatch(Base):
    """DeletionBatch 聚合：课程范围保留治理与删除执行进度。"""

    __tablename__ = "deletion_batches"

    batch_id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    course_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    scope: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    retention_due_at = mapped_column(sa.DateTime, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    # 教师标记保留的 submission_id 列表（CT-011 exclusions[]）
    exclusions = mapped_column(sa.JSON, nullable=False, default=list)
    # CT-014 回写的失败项 [{submission_id, reason}]，保留供重跑
    failed_items = mapped_column(sa.JSON, nullable=False, default=list)
    # CT-014 回写累计已清除 submission_id（重跑并集累积）
    cleared_submission_ids = mapped_column(sa.JSON, nullable=False, default=list)
    # CT-014 幂等键：已应用的 purged_at 标记（batch_id + purged_at 去重）
    applied_purge_marks = mapped_column(sa.JSON, nullable=False, default=list)
    # CCR-001 双回流：CT-015 幂等标记 + 两路到达/失败快照
    # flow_states = {"CT-014": {"arrived": bool, "failed_items": [...]},
    #                "CT-015": {"arrived": bool, "failed_items": [...]}}
    ct015_purge_marks = mapped_column(sa.JSON, nullable=True)
    flow_states = mapped_column(sa.JSON, nullable=True)
    created_at = mapped_column(sa.DateTime, nullable=False)
    confirmed_at = mapped_column(sa.DateTime, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    updated_at = mapped_column(sa.DateTime, nullable=False)

    __table_args__ = (
        sa.Index("ix_deletion_batches_course", "course_id"),
        sa.Index("ix_deletion_batches_due", "status", "retention_due_at"),
    )


class DeletionAuditRecord(Base):
    """删除审计记录（ST-DELETION-AUDIT）：只追加不删除，永久留存。"""

    __tablename__ = "deletion_audit_records"

    audit_record_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    course_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    scope: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    operator: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # 动作覆盖的 submission_id 快照（审计事实，不随清除进度改写）
    submission_ids = mapped_column(sa.JSON, nullable=False, default=list)
    created_at = mapped_column(sa.DateTime, nullable=False)

    __table_args__ = (sa.Index("ix_deletion_audit_batch", "batch_id"),)
