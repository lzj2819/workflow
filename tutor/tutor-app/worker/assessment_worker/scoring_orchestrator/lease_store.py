"""ICT-001 ClaimScoringTask 租约存储：LeaseStore 抽象的 SQLAlchemy 实现。

租约字段持久化在 ST-001 任务行（lease_owner / lease_expires_at / reclaim_count）：

- 首次认领为原子条件更新：pending → in_progress，attempts=1，写 started_at；
- 崩溃重认领（CON-2 / LCD-002）：租约到期后同一 attempt 重跑，attempts 不增、
  reclaim_count+1；终态任务永不被重认领（状态守卫排除终态）；
- reclaim_count 达到上限（默认 3，MAX_RECLAIM_COUNT）claim 返回 None，
  由编排器负责终态化（failure_reason=REPEATED_WORKER_CRASH）。

候选 SELECT 仅为建议性读取；真正的并发互斥由条件 UPDATE 的 WHERE 守卫保证
（CON-1：同一任务同一时刻仅一个执行者）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from tutor_shared.lease import Lease, LeaseStore

from ..settings import MAX_RECLAIM_COUNT
from .models import ScoringTask

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"


def as_naive_utc(dt: datetime) -> datetime:
    """归一化为 naive UTC（SQLite DateTime 无时区）。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class SqlaTaskLeaseStore(LeaseStore):
    """基于 scoring_tasks 行条件更新的租约存储（DU-3 多副本协调）。"""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        max_reclaims: int = MAX_RECLAIM_COUNT,
    ) -> None:
        self._session_factory = session_factory
        self._max_reclaims = max_reclaims

    def claim(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> Lease | None:
        now = as_naive_utc(now)
        expires_at = now + ttl
        with self._session_factory.begin() as session:
            fresh = session.execute(
                update(ScoringTask)
                .where(ScoringTask.task_id == task_id)
                .where(ScoringTask.status == STATUS_PENDING)
                .where(ScoringTask.lease_expires_at.is_(None))
                .values(
                    status=STATUS_IN_PROGRESS,
                    attempts=1,
                    started_at=now,
                    lease_owner=owner,
                    lease_expires_at=expires_at,
                    reclaim_count=0,
                )
            )
            if fresh.rowcount == 1:
                reclaim_count = 0
            else:
                # 崩溃重认领：保留 attempts，不消耗业务重试预算
                reclaimed = session.execute(
                    update(ScoringTask)
                    .where(ScoringTask.task_id == task_id)
                    .where(ScoringTask.status == STATUS_IN_PROGRESS)
                    .where(ScoringTask.lease_expires_at.is_not(None))
                    .where(ScoringTask.lease_expires_at <= now)
                    .where(ScoringTask.reclaim_count < self._max_reclaims)
                    .values(
                        lease_owner=owner,
                        lease_expires_at=expires_at,
                        reclaim_count=ScoringTask.reclaim_count + 1,
                    )
                )
                if reclaimed.rowcount != 1:
                    return None  # 被持有且未过期，或已达重认领上限
                reclaim_count = session.scalar(
                    select(ScoringTask.reclaim_count).where(ScoringTask.task_id == task_id)
                )
        return Lease(task_id=task_id, owner=owner, expires_at=expires_at, reclaim_count=reclaim_count)

    def renew(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> bool:
        now = as_naive_utc(now)
        with self._session_factory.begin() as session:
            result = session.execute(
                update(ScoringTask)
                .where(ScoringTask.task_id == task_id)
                .where(ScoringTask.status == STATUS_IN_PROGRESS)
                .where(ScoringTask.lease_owner == owner)
                .where(ScoringTask.lease_expires_at.is_not(None))
                .where(ScoringTask.lease_expires_at > now)
                .values(lease_expires_at=now + ttl)
            )
            return result.rowcount == 1

    def release(self, task_id: str, owner: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(ScoringTask)
                .where(ScoringTask.task_id == task_id)
                .where(ScoringTask.lease_owner == owner)
                .values(lease_owner=None, lease_expires_at=None)
            )

    def get(self, task_id: str) -> Lease | None:
        with self._session_factory() as session:
            row = session.execute(
                select(
                    ScoringTask.lease_owner,
                    ScoringTask.lease_expires_at,
                    ScoringTask.reclaim_count,
                ).where(ScoringTask.task_id == task_id)
            ).one_or_none()
        if row is None or row.lease_owner is None or row.lease_expires_at is None:
            return None
        return Lease(
            task_id=task_id,
            owner=row.lease_owner,
            expires_at=row.lease_expires_at,
            reclaim_count=row.reclaim_count,
        )
