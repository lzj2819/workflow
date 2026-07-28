"""投递器 OutboxRelayer（ST-04 / KD-002）。

轮询 SqlaOutboxStore 取 due → 调注册的 consumer（contract_id → handler）→
成功 mark_confirmed / 异常 mark_retry（default_backoff 指数退避），无限重试
直至消费方确认。认领（delivering）与确认/重试标记各为独立小事务，由投递器
作为调用方提交（SqlaOutboxStore 内部不 commit/rollback）。

结构化日志只含 id/contract_id/attempts 与错误类型名，不记 payload 内容
（KD-003 审计合规）。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import sessionmaker

from tutor_shared.outbox import OutboxRecord, SqlaOutboxStore, default_backoff

logger = logging.getLogger("tutor.si_relay")


class UnknownContractError(Exception):
    """contract_id 无注册 consumer（视为可重试失败，留待装配补齐）。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutboxRelayer:
    """Outbox 轮询投递器（DD-006 基线：间隔 1s、批量 50）。"""

    def __init__(
        self,
        session_factory: sessionmaker,
        consumers: dict[str, Callable[[OutboxRecord], None]] | None = None,
        *,
        poll_interval: float = 1.0,
        batch_size: int = 50,
        backoff: Callable[[int], timedelta] | None = None,
        clock: Callable[[], datetime] = _utcnow,
        log: logging.Logger | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._consumers: dict[str, Callable[[OutboxRecord], None]] = dict(consumers or {})
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._backoff = backoff or default_backoff
        self._clock = clock
        self._log = log or logger
        self._stop = threading.Event()

    def register(self, contract_id: str, handler: Callable[[OutboxRecord], None]) -> None:
        self._consumers[contract_id] = handler

    def poll_once(self, now: datetime | None = None) -> dict[str, int]:
        """单轮：认领 due（一个事务）→ 逐条投递并确认/重试（各一个事务）。

        只认领已注册契约（contract_ids 过滤）：未注册契约（如 CT-004，归进程外
        DU-3 worker）留给其消费方，不做退避重试（GAP-02：退避循环会饿死真正的
        消费方）；无注册 consumer 时退化为全量认领（测试兼容）。
        """
        now = now or self._clock()
        contract_filter = tuple(self._consumers) or None
        with self._session_factory() as session:
            store = SqlaOutboxStore(session, self._backoff)
            due = store.fetch_due(now, self._batch_size, contract_ids=contract_filter)
            session.commit()
        counts = {"claimed": len(due), "confirmed": 0, "retry": 0}
        for record in due:
            handler = self._consumers.get(record.contract_id)
            try:
                if handler is None:
                    raise UnknownContractError(record.contract_id)
                handler(record)
            except Exception as exc:  # noqa: BLE001 — 任何失败均重试至确认
                with self._session_factory() as session:
                    SqlaOutboxStore(session, self._backoff).mark_retry(record.record_id)
                    session.commit()
                counts["retry"] += 1
                self._log.warning(
                    "outbox delivery retry",
                    extra={
                        "outbox_id": record.record_id,
                        "contract_id": record.contract_id,
                        "attempts": record.attempts,
                        "error_type": type(exc).__name__,
                    },
                )
            else:
                with self._session_factory() as session:
                    SqlaOutboxStore(session, self._backoff).mark_confirmed(record.record_id)
                    session.commit()
                counts["confirmed"] += 1
                self._log.info(
                    "outbox delivery confirmed",
                    extra={
                        "outbox_id": record.record_id,
                        "contract_id": record.contract_id,
                        "attempts": record.attempts,
                    },
                )
        return counts

    def run(self) -> None:
        """阻塞轮询直至 stop()；间隔 poll_interval 秒。"""
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self._poll_interval)

    def stop(self) -> None:
        self._stop.set()
