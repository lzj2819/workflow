"""入站去重 InboundDedup（ST-05 / CT-005、CT-012 幂等语义）。

handler 包装器：按 event_key 首次 applied 后跳过重复投递（重复事件不重复
应用、不改变终态）；可重试业务失败进 retry_wait 交还投递方重投；不可解析
（schema 无效）进 quarantined，不阻塞后续合法事件。

事务边界归调用方：去重检查与业务处理共用调用方 Session，同一本地事务提交
（ST-05 不变量）；本类内部不 commit/rollback。
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from .models import InboundDedupRecord


class DedupOutcome(enum.Enum):
    """一次入站投递的处理结果。"""

    APPLIED = "applied"  # 首次应用成功（received → processing → applied）
    DUPLICATE = "duplicate_ignored"  # 已 applied/quarantined 的重复投递，未再应用
    RETRY = "retry_wait"  # 可重试业务失败，交还投递方重投
    QUARANTINED = "quarantined"  # 不可解析/schema 无效，需告警与人工重放


class QuarantineError(Exception):
    """业务 handler 抛出以声明事件不可解析/schema 无效（不可重试）。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InboundDedup:
    """入站事件幂等消费（构造接收既有 Session，不自建事务）。"""

    def __init__(
        self,
        session: Session,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._session = session
        self._clock = clock

    def handle(
        self,
        event_key: str,
        contract_id: str,
        apply: Callable[[], None],
    ) -> DedupOutcome:
        """按 event_key 幂等执行 apply（业务回写闭包，捕获 payload）。

        - 已 applied/quarantined：跳过，不调 apply，记录不推进（DUPLICATE）；
        - 首次或 retry_wait/processing 重投：置 processing 并执行 apply；
          成功 → applied（APPLIED）；QuarantineError → quarantined
          （QUARANTINED）；其他异常 → retry_wait（RETRY），交还投递方。
        """
        row = self._session.get(InboundDedupRecord, event_key)
        if row is not None and row.status in ("applied", "quarantined"):
            return DedupOutcome.DUPLICATE
        now = self._clock()
        if row is None:
            row = InboundDedupRecord(
                event_key=event_key,
                contract_id=contract_id,
                status="received",
                attempts=0,
                last_error=None,
                updated_at=now,
            )
            self._session.add(row)
            self._session.flush()
        row.status = "processing"
        row.attempts += 1
        row.updated_at = now
        self._session.flush()
        try:
            apply()
        except QuarantineError as exc:
            row.status = "quarantined"
            row.last_error = str(exc) or type(exc).__name__
            row.updated_at = self._clock()
            self._session.flush()
            return DedupOutcome.QUARANTINED
        except Exception as exc:  # noqa: BLE001 — 可重试业务失败统一进 retry_wait
            row.status = "retry_wait"
            row.last_error = f"{type(exc).__name__}: {exc}"[:500]
            row.updated_at = self._clock()
            self._session.flush()
            return DedupOutcome.RETRY
        row.status = "applied"
        row.last_error = None
        row.updated_at = self._clock()
        self._session.flush()
        return DedupOutcome.APPLIED
