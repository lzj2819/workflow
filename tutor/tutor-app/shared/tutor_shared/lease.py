"""任务租约抽象（DU-3 评分任务认领；MOD-04 LCD-002 语义）。

语义（冻结）：
- claim 为原子操作；租约到期后其他 worker 可重认领；
- reclaim_count 超过上限（默认 3）的任务必须终态化，不再认领；
- PostgreSQL 实现属 Phase 2/3（L03 CMP-SCORING-ORCHESTRATOR）。
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Lease:
    task_id: str
    owner: str
    expires_at: datetime
    reclaim_count: int = 0


class LeaseStore(ABC):
    @abstractmethod
    def claim(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> Lease | None:
        """认领任务；已被持有且未过期返回 None；超过重认领上限返回 None。"""

    @abstractmethod
    def renew(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> bool: ...

    @abstractmethod
    def release(self, task_id: str, owner: str) -> None: ...

    @abstractmethod
    def get(self, task_id: str) -> Lease | None: ...


class InMemoryLeaseStore(LeaseStore):
    def __init__(self, max_reclaims: int = 3) -> None:
        self._lock = threading.Lock()
        self._leases: dict[str, Lease] = {}
        self._max_reclaims = max_reclaims

    def claim(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> Lease | None:
        with self._lock:
            lease = self._leases.get(task_id)
            if lease is not None and lease.expires_at > now:
                return None  # 被持有且未过期
            if lease is not None and lease.reclaim_count >= self._max_reclaims:
                return None  # 超过重认领上限 → 调用方负责终态化
            reclaim_count = 0 if lease is None else lease.reclaim_count + 1
            lease = Lease(task_id, owner, now + ttl, reclaim_count)
            self._leases[task_id] = lease
            return lease

    def renew(self, task_id: str, owner: str, ttl: timedelta, now: datetime) -> bool:
        with self._lock:
            lease = self._leases.get(task_id)
            if lease is None or lease.owner != owner or lease.expires_at <= now:
                return False
            lease.expires_at = now + ttl
            return True

    def release(self, task_id: str, owner: str) -> None:
        with self._lock:
            lease = self._leases.get(task_id)
            if lease is not None and lease.owner == owner:
                del self._leases[task_id]

    def get(self, task_id: str) -> Lease | None:
        with self._lock:
            return self._leases.get(task_id)
