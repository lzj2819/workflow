"""Outbox 抽象（KD-002）。

语义（冻结）：
- 业务写入与 Outbox 行同一本地事务提交（由调用方事务边界保证）；
- 投递器无限重试直至消费方确认；消费方按业务键幂等去重；
- 状态机：pending → delivering →（confirmed | retry_wait → pending）。

本模块定义记录结构与存储接口，并给出一个内存实现（单元测试与本地开发用）；
PostgreSQL 实现属 Phase 5 backfill（SI-RELAY / MOD-04 publisher）。
"""
from __future__ import annotations

import itertools
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable

OUTBOX_STATUSES = ("pending", "delivering", "retry_wait", "confirmed")


@dataclass
class OutboxRecord:
    record_id: int
    contract_id: str  # 如 CT-004 / CT-005 / CT-006 / CT-012 / CT-014
    payload: dict
    dedup_key: str  # 消费方幂等键（如 submission_id、batch_id+purged_at）
    status: str = "pending"
    attempts: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    next_attempt_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OutboxStore(ABC):
    """Outbox 持久化接口。实现必须保证 fetch_due 的认领语义（delivering）。"""

    @abstractmethod
    def enqueue(self, contract_id: str, payload: dict, dedup_key: str) -> OutboxRecord: ...

    @abstractmethod
    def fetch_due(
        self, now: datetime, limit: int = 50, contract_ids: Iterable[str] | None = None
    ) -> list[OutboxRecord]: ...

    @abstractmethod
    def mark_confirmed(self, record_id: int) -> None: ...

    @abstractmethod
    def mark_retry(self, record_id: int, next_attempt_at: datetime | None = None) -> None: ...


def default_backoff(attempts: int) -> timedelta:
    """指数退避：1s 起，封顶 60s（DD-006 基线）。"""
    return timedelta(seconds=min(60, 2 ** max(0, attempts - 1)))


class InMemoryOutboxStore(OutboxStore):
    def __init__(self, backoff: Callable[[int], timedelta] = default_backoff) -> None:
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._records: dict[int, OutboxRecord] = {}
        self._backoff = backoff

    def enqueue(self, contract_id: str, payload: dict, dedup_key: str) -> OutboxRecord:
        with self._lock:
            record = OutboxRecord(next(self._ids), contract_id, payload, dedup_key)
            self._records[record.record_id] = record
            return record

    def fetch_due(
        self, now: datetime, limit: int = 50, contract_ids: Iterable[str] | None = None
    ) -> list[OutboxRecord]:
        with self._lock:
            due = [
                r for r in self._records.values()
                if r.status in ("pending", "retry_wait")
                and r.next_attempt_at <= now
                and (contract_ids is None or r.contract_id in contract_ids)
            ]
            due.sort(key=lambda r: r.record_id)
            claimed = due[:limit]
            for r in claimed:
                r.status = "delivering"
                r.attempts += 1
            return claimed

    def mark_confirmed(self, record_id: int) -> None:
        with self._lock:
            self._records[record_id].status = "confirmed"

    def mark_retry(self, record_id: int, next_attempt_at: datetime | None = None) -> None:
        with self._lock:
            record = self._records[record_id]
            record.status = "retry_wait"
            record.next_attempt_at = next_attempt_at or (
                datetime.now(timezone.utc) + self._backoff(record.attempts)
            )


# ---------------------------------------------------------------------------
# Phase 5 backfill（SI-RELAY / T-B01b）：SQL 实现（追加，不改上方既有语义）。
#
# 事务边界归调用方：SqlaOutboxStore 内部不 commit/rollback；enqueue 与业务写入
# 共用调用方 Session 从而实现 KD-002 同事务语义。目标库 PostgreSQL（fetch_due
# 用 FOR UPDATE SKIP LOCKED 认领），单测 SQLite 退化为同事务内条件更新认领。
# ---------------------------------------------------------------------------

try:  # SQLAlchemy 为 server/worker 已声明依赖；缺失环境仅 SQL 实现不可用
    import sqlalchemy as sa
except ImportError:  # pragma: no cover
    sa = None  # type: ignore[assignment]

if sa is not None:
    OUTBOX_METADATA = sa.MetaData()
    OUTBOX_RECORDS_TABLE = sa.Table(
        "outbox_records",
        OUTBOX_METADATA,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("dedup_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Index("ix_outbox_records_due", "status", "next_attempt_at"),
    )
else:  # pragma: no cover
    OUTBOX_METADATA = None
    OUTBOX_RECORDS_TABLE = None


def _naive_utc(dt: datetime) -> datetime:
    """归一化为 naive UTC（SQLite DateTime(timezone=True) 读回为 naive）。"""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _aware_utc(dt: datetime) -> datetime:
    """读回的 naive 值按 UTC 解释，保证 OutboxRecord 语义与内存实现一致。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SqlaOutboxStore(OutboxStore):
    """Outbox 的 SQL 实现（ST-04；迁移见 0010_outbox.py）。

    构造接收既有 SQLAlchemy Session，**内部不 commit/rollback**——事务边界归
    调用方，业务写入与 Outbox 行在同一本地事务提交（KD-002）。
    """

    def __init__(self, session, backoff: Callable[[int], timedelta] = default_backoff) -> None:
        if sa is None:  # pragma: no cover
            raise RuntimeError("SqlaOutboxStore 需要 SQLAlchemy>=2.0")
        self._session = session
        self._backoff = backoff
        self._table = OUTBOX_RECORDS_TABLE

    def enqueue(self, contract_id: str, payload: dict, dedup_key: str) -> OutboxRecord:
        now = datetime.now(timezone.utc)
        result = self._session.execute(
            self._table.insert().values(
                contract_id=contract_id,
                payload=dict(payload),
                dedup_key=dedup_key,
                status="pending",
                attempts=0,
                created_at=_naive_utc(now),
                next_attempt_at=_naive_utc(now),
            )
        )
        record_id = int(result.inserted_primary_key[0])
        return OutboxRecord(
            record_id, contract_id, dict(payload), dedup_key,
            status="pending", attempts=0, created_at=now, next_attempt_at=now,
        )

    def fetch_due(
        self, now: datetime, limit: int = 50, contract_ids: Iterable[str] | None = None
    ) -> list[OutboxRecord]:
        t = self._table
        due_cond = sa.and_(
            t.c.status.in_(("pending", "retry_wait")),
            t.c.next_attempt_at <= _naive_utc(now),
        )
        if contract_ids is not None:
            # 跨 DU 分工过滤：DU-2 relayer 只认领已注册契约，DU-3 worker 只认领
            # CT-004——否则无消费方的契约会被退避循环反复认领，真正消费方饥饿
            due_cond = sa.and_(due_cond, t.c.contract_id.in_(tuple(contract_ids)))
        id_query = sa.select(t.c.id).where(due_cond).order_by(t.c.id).limit(limit)
        if self._session.get_bind().dialect.name == "postgresql":
            # FOR UPDATE SKIP LOCKED：多投递器并发认领互斥，不等待他方行锁
            id_query = id_query.with_for_update(skip_locked=True)
        ids = list(self._session.execute(id_query).scalars().all())
        if not ids:
            return []
        # 认领（SQLite 退化为同事务内条件更新；PG 上行锁已由 SELECT 持有）
        self._session.execute(
            t.update()
            .where(t.c.id.in_(ids), t.c.status.in_(("pending", "retry_wait")))
            .values(status="delivering", attempts=t.c.attempts + 1)
        )
        rows = self._session.execute(
            sa.select(t).where(t.c.id.in_(ids)).order_by(t.c.id)
        ).mappings().all()
        return [self._to_record(row) for row in rows]

    def mark_confirmed(self, record_id: int) -> None:
        self._session.execute(
            self._table.update()
            .where(self._table.c.id == record_id)
            .values(status="confirmed")
        )

    def mark_retry(self, record_id: int, next_attempt_at: datetime | None = None) -> None:
        if next_attempt_at is None:
            attempts = self._session.execute(
                sa.select(self._table.c.attempts).where(self._table.c.id == record_id)
            ).scalar_one()
            next_attempt_at = datetime.now(timezone.utc) + self._backoff(attempts)
        self._session.execute(
            self._table.update()
            .where(self._table.c.id == record_id)
            .values(status="retry_wait", next_attempt_at=_naive_utc(next_attempt_at))
        )

    @staticmethod
    def _to_record(row) -> OutboxRecord:
        return OutboxRecord(
            record_id=row["id"],
            contract_id=row["contract_id"],
            payload=dict(row["payload"]),
            dedup_key=row["dedup_key"],
            status=row["status"],
            attempts=row["attempts"],
            created_at=_aware_utc(row["created_at"]),
            next_attempt_at=_aware_utc(row["next_attempt_at"]),
        )
