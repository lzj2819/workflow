"""CMP-PRES-SNAPSHOT-STORE：PresentationView 快照与幂等记录单写方。

PRES-IC-03 / LCD-PRES-003 / P-SNAPSHOT-IDEMPOTENCY：
- 父 CT-009 幂等键 = 教师 + 规范化小组集合 + 时间窗；同键命中返回最新
  快照，不产生重复视图记录；
- 新窗口再生成：写新快照、旧快照标记 superseded、幂等记录指向最新，
  三者在同一父本地事务提交，失败整体回滚、不返回半写入 blocks；
- 快照一次性写入，生成后不随 ST-READ-MODEL 实时变化。

幂等键具体编码与时间窗粒度为本层 implementation_detail（父 05 §4）：
时间窗默认 UTC 自然日，可注入以便测试与后续演进。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from .models import (
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    PresentationIdempotencyRecord,
    PresentationViewRecord,
)

def default_time_window() -> str:
    """默认时间窗：UTC 自然日（实现细节，不改变父幂等语义）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Snapshot:
    """快照读取视图（PRES-IC-04 输入）。"""

    presentation_id: str
    generation_key: str
    teacher_id: str
    course_ids: tuple[str, ...]
    group_ids: tuple[str, ...]
    blocks: tuple[dict, ...]
    source_read_model_version: str | None
    status: str
    generated_at: datetime


def normalize_group_ids(group_ids: list[str]) -> tuple[str, ...]:
    """规范化小组集合：去重保序（请求序），用于 blocks 顺序与键编码。"""
    return tuple(dict.fromkeys(group_ids))


def generation_key(
    *, teacher_id: str, group_ids: tuple[str, ...], time_window: str
) -> str:
    """父幂等键编码：教师 + 规范化小组集合（排序） + 时间窗 → sha256。"""
    canonical = "|".join([teacher_id, ",".join(sorted(group_ids)), time_window])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def group_set_key(*, teacher_id: str, group_ids: tuple[str, ...]) -> str:
    """教师 + 规范化小组集合（不含时间窗）：跨窗口 supersede 定位键。"""
    canonical = "|".join([teacher_id, ",".join(sorted(group_ids))])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _to_snapshot(record: PresentationViewRecord) -> Snapshot:
    return Snapshot(
        presentation_id=record.presentation_id,
        generation_key=record.generation_key,
        teacher_id=record.teacher_id,
        course_ids=tuple(json.loads(record.course_ids)),
        group_ids=tuple(json.loads(record.group_ids)),
        blocks=tuple(json.loads(record.blocks)),
        source_read_model_version=record.source_read_model_version,
        status=record.status,
        generated_at=record.created_at,
    )


class SnapshotStore:
    """ST-PRESENTATION-VIEW / ST-IDEMPOTENCY-PRESENTATION 唯一写方。"""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def find_latest(self, key: str) -> Snapshot | None:
        """同键幂等查找：返回幂等记录指向的仍可用最新快照。"""
        with self._session_factory() as session:
            idem = session.get(PresentationIdempotencyRecord, key)
            if idem is None:
                return None
            record = session.get(PresentationViewRecord, idem.presentation_id)
            if record is None or record.status != STATUS_ACTIVE:
                return None
            return _to_snapshot(record)

    def save(
        self,
        *,
        key: str,
        teacher_id: str,
        course_ids: tuple[str, ...],
        group_ids: tuple[str, ...],
        blocks: list[dict],
        source_read_model_version: str | None,
    ) -> Snapshot:
        """同事务写新快照 + 同组集合旧快照 superseded + 幂等记录指向最新。

        supersede 按「教师 + 规范化小组集合」跨时间窗生效：同参数再生成
        产生新版本快照，旧版本被替代（ST-PRESENTATION-VIEW 生命周期）。
        """
        now = self._clock()
        presentation_id = f"pv-{uuid.uuid4().hex}"
        set_key = group_set_key(teacher_id=teacher_id, group_ids=group_ids)
        with self._session_factory() as session:
            idem = session.get(PresentationIdempotencyRecord, key)
            if idem is not None:
                idem.presentation_id = presentation_id
                idem.updated_at = now
            else:
                session.add(
                    PresentationIdempotencyRecord(
                        generation_key=key,
                        presentation_id=presentation_id,
                        teacher_id=teacher_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            previous_active = session.scalars(
                select(PresentationViewRecord).where(
                    PresentationViewRecord.group_set_key == set_key,
                    PresentationViewRecord.status == STATUS_ACTIVE,
                )
            ).all()
            for previous in previous_active:
                previous.status = STATUS_SUPERSEDED
            record = PresentationViewRecord(
                presentation_id=presentation_id,
                generation_key=key,
                group_set_key=set_key,
                teacher_id=teacher_id,
                course_ids=json.dumps(list(course_ids), ensure_ascii=False),
                group_ids=json.dumps(list(group_ids), ensure_ascii=False),
                blocks=json.dumps(blocks, ensure_ascii=False),
                source_read_model_version=source_read_model_version,
                status=STATUS_ACTIVE,
                created_at=now,
            )
            session.add(record)
            session.flush()
            return _to_snapshot(record)

    def count_views(self) -> int:
        """视图记录总数（测试/可观测辅助）。"""
        with self._session_factory() as session:
            return len(session.scalars(select(PresentationViewRecord)).all())

    def get(self, presentation_id: str) -> Snapshot | None:
        """按 presentation_id 读取快照（含 superseded，用于生命周期断言）。"""
        with self._session_factory() as session:
            record = session.get(PresentationViewRecord, presentation_id)
            return _to_snapshot(record) if record is not None else None
