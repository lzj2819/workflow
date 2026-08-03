"""SI-PURGE 持久化模型（ST-07 PurgeExecution；T-B01c）。

约束：PostgreSQL 为目标库、单测 SQLite —— 仅用可移植类型。
语义（03-state-and-data ST-07）：
- 批次执行创建 → 部分失败保留 → 重跑更新 → 全部成功后归档；
- 仅为执行日志（重跑定位）；删除审计记录归 MOD-05，本模块不复制。

注：本表 alembic 迁移不在 T-B01c 允许路径内，由集成阶段补迁移后合入
（单测经 metadata.create_all 建表）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SI-PURGE 登记表 Base（独立于 SI-CORE/SI-STORE Base，互不耦合）。"""


# PurgeExecutionRow.status 值域
EXECUTION_PARTIAL = "partial"
EXECUTION_COMPLETED = "completed"

# PurgeExecutionItemRow.result 值域
RESULT_PURGED = "purged"
RESULT_FAILED = "failed"


class PurgeExecutionRow(Base):
    """ST-07 批次头：batch_id 聚合一次（或多次重跑）清除执行的汇总状态。"""

    __tablename__ = "purge_executions"

    batch_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    # CT-012 指令快照（重跑定位用；审计本体归 MOD-05，此处仅存引用）
    scope: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    operator: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    audit_record_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # partial：存在失败项待重跑；completed：全部成功（可归档）
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    run_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    first_executed_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    last_executed_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)


class PurgeExecutionItemRow(Base):
    """ST-07 逐项结果：每个 submission_id 最近一次执行的终态与失败原因。"""

    __tablename__ = "purge_execution_items"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        sa.String(64),
        sa.ForeignKey("purge_executions.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    submission_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # purged / failed（重跑成功后由 failed 更新为 purged，失败原因清空）
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at = mapped_column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("batch_id", "submission_id", name="uq_purge_items_batch_sub"),
    )
