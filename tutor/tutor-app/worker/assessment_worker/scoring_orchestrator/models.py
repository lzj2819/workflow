"""ST-001 ScoringTask 与 ST-002 AssessmentResult 持久化模型。

约束：单测库为 SQLite（sqlite:///:memory:），禁用 PG 专有类型（用 sa.JSON）；
生产 PostgreSQL 表结构由 server/migrations/versions/0004_scoring_tasks.py 落地。
时间戳一律存 naive UTC（由编排器入口归一化）。
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OrchestratorBase(DeclarativeBase):
    """L03 聚合声明式基类（MOD-04 所有；不涉及其他聚合表）。"""


class ScoringTask(OrchestratorBase):
    """ST-001 评分任务行：pending → in_progress → scored | scoring_failed（终态不可逆）。"""

    __tablename__ = "scoring_tasks"

    task_id: Mapped[str] = mapped_column(sa.String(36), primary_key=True)
    # CT-004 消费幂等键（INV-5）：一个 submission_id 一个任务
    submission_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    course_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    assignment: Mapped[str] = mapped_column(sa.Text, nullable=False)
    student_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    group_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    material_refs: Mapped[list] = mapped_column(sa.JSON, nullable=False)
    missing_items: Mapped[list] = mapped_column(sa.JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    # REQ-012：自动重试仅一次，attempts ∈ {0,1,2}（INV-2）
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    # {first_failure: {error_kind, at}, second_failure: {error_kind, at}}
    retry_record: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    # 认领租约字段（LCD-002）：崩溃重认领不耗业务重试预算
    lease_owner: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    reclaim_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    # LCD-004：created_at + 10min，仅跟踪统计，不强杀、不伪标记
    deadline_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)


class ScoringResult(OrchestratorBase):
    """ST-002 评分结果内容：终态事务内一次性写入，写后不可变（INV-1）。"""

    __tablename__ = "scoring_results"

    task_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("scoring_tasks.task_id"), primary_key=True
    )
    submission_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    original_grade: Mapped[str] = mapped_column(sa.String(1), nullable=False)
    dimension_rationales: Mapped[list] = mapped_column(sa.JSON, nullable=False)
    teacher_suggestions: Mapped[list] = mapped_column(sa.JSON, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    missing_materials_impact: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # LCD-003：版本存证仅内部保留，不经 CT-005 外发
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    rubric_version: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    model_meta: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)


class AssessmentPurgeTombstone(OrchestratorBase):
    """CCR-001 最小墓碑：评分清除后仅留 (submission_id, batch_id, purged_at)。

    不含任何评分内容，不属于「评分记录」；用途：重放守卫（拒绝旧 CT-004 重放
    为已清除提交重建评分任务）。迁移见 server/migrations/versions/0016。
    """

    __tablename__ = "assessment_purge_tombstones"

    submission_id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    batch_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    purged_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
