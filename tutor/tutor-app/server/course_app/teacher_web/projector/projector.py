"""ReadModelProjector：CT-005/CT-006/CT-012/CT-014 + M05-IC-05 事件投影。

语义（T-B03b / 03-data-and-consistency / ST-PROJECTION-CHECKPOINT）：
- handler 注册形状：handlers() 返回 {contract_id: Callable[[OutboxRecord], None]}，
  供 SI-RELAY OutboxRelayer 注册消费（record_id 即消费位点）；
- 幂等消费（业务键去重，重复事件不改投影）：
  - CT-006 按 submission_id upsert；状态只沿单调秩前进（received < processing <
    scored/scoring_failed），旧状态重放不回退终态；
  - CT-005 按 submission_id+终态去重（冻结契约 idempotency：重复事件不改变
    终态）；scored → 经注入的 M05-IC-01（L14 create_review_record）幂等建复核
    记录（L14 侧按 submission_id 去重，重复调用返回既有记录）；scoring_failed
    → 投影 failure_reason + retry_record，不写任何等级（INV-1）；
  - M05-IC-05 复核事件按 (adjustment_id, event_type) 去重（AnnotationSaved 追加批注、
    GradeAdjusted 写最终等级；两事件可共用同一 adjustment_id）；
- CT-012 自消费 / CT-014 → 清除读模型目标行并登记墓碑；重放守卫：命中墓碑的
  旧事件（CT-005/CT-006）跳过，不重建已清除数据；
- 投影与位点同事务：每个 handler 在单个 session 事务内写投影行并推进
  projection_checkpoints（position 取 max，失败整体回滚）；
- replay()：从事件序列重建读模型（可选清空重建），位点重置为序列内各
  contract 的最大 record_id。

边界：不改 L14/L15/L16/L17 代码；不做跨模块同步读；M05-IC-01 以可调用对象
注入（组合根绑定 L14 ReviewCommandService.create_review_record）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, ContextManager, Iterable, Sequence

from sqlalchemy.orm import Session

from tutor_shared.outbox import OutboxRecord

from .models import (
    Base,
    ProjectionCheckpoint,
    RmCourse,
    RmGroup,
    RmPurgeTombstone,
    RmStudent,
    RmSubmission,
)

CT_005 = "CT-005"
CT_006 = "CT-006"
CT_012 = "CT-012"
CT_014 = "CT-014"
CT_015 = "CT-015"  # CCR-001：MOD-04 评分清除回流

OUTBOX_CONTRACTS = (CT_005, CT_006, CT_012, CT_014, CT_015)

GRADE_VALUES = frozenset({"A", "B", "C", "D", "E"})

#: 状态单调秩：旧状态事件重放不回退投影（processing 无事件源，保留给将来）。
_STATUS_RANK = {
    "upload_failed": 0,
    "rejected": 0,
    "received": 1,
    "processing": 2,
    "scored": 3,
    "scoring_failed": 3,
}
_TERMINAL_STATUSES = frozenset({"scored", "scoring_failed"})

_EVENT_ANNOTATION_SAVED = "AnnotationSaved"
_EVENT_GRADE_ADJUSTED = "GradeAdjusted"

SessionScopeFactory = Callable[[], ContextManager[Session]]

#: M05-IC-01 注入形状（L14 ReviewCommandService.create_review_record）。
CreateReviewRecord = Callable[..., dict]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_dt(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return _naive_utc(value) if isinstance(value, datetime) else None
    return _naive_utc(datetime.fromisoformat(str(value)))


class ProjectorValidationError(ValueError):
    """事件载荷不满足投影消费前置（冻结契约字段缺失/非法）。"""


class ReadModelProjector:
    """教师读模型投影器（ST-READ-MODEL 唯一写方）。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文；
    - `create_review_record`：M05-IC-01 可调用（可选；缺省时 scored 事件只投影
      不建复核记录，供投影单测与重放工具使用）；
    - `clock`：可注入时钟（测试）。
    """

    def __init__(
        self,
        session_factory: SessionScopeFactory,
        *,
        create_review_record: CreateReviewRecord | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._create_review_record = create_review_record
        self._clock = clock or _utcnow

    # ---- RELAY consumer 注册形状 ----

    def handlers(self) -> dict[str, Callable[[OutboxRecord], None]]:
        """返回 {contract_id: handler}，供 OutboxRelayer.register 使用。"""
        return {contract: self.handle for contract in OUTBOX_CONTRACTS}

    def handle(self, record: OutboxRecord) -> None:
        """消费一条 Outbox 事件：投影写入 + 位点推进同一本地事务。"""
        payload = record.payload
        with self._session_factory() as session:
            if record.contract_id == CT_005:
                self._apply_ct005(session, payload)
            elif record.contract_id == CT_006:
                self._apply_ct006(session, payload)
            elif record.contract_id == CT_012:
                self._apply_ct012(session, payload)
            elif record.contract_id == CT_014:
                self._apply_ct014(session, payload)
            elif record.contract_id == CT_015:
                self._apply_ct015(session, payload)
            else:
                raise ProjectorValidationError(
                    f"unsupported contract: {record.contract_id}"
                )
            self._advance_checkpoint(session, record.contract_id, record.record_id)

    # ---- M05-IC-05 复核模块内事件（ReviewEventPublisher 形状） ----

    def publish(self, events: Sequence) -> None:
        """消费 L14 提交后发布的复核事件（按 (adjustment_id, event_type) 幂等去重）。

        实现 `review_command.ports.ReviewEventPublisher` 协议；投影失败由
        调用方按 adjustment_id 重放，不回滚已提交的 ReviewRecord（LCD-004）。
        """
        with self._session_factory() as session:
            for event in events:
                self._apply_review_event(session, event)

    # ---- 重放重建 ----

    def replay(
        self, records: Iterable[OutboxRecord], *, reset: bool = True
    ) -> dict[str, int]:
        """从事件序列重建读模型；reset=True 先清空读模型与位点。

        序列须按投递顺序（record_id 升序）给出；每个事件的投影规则与在线
        消费一致（墓碑守卫、终态去重均生效）。返回各 contract 消费计数。
        """
        ordered = sorted(records, key=lambda r: r.record_id)
        positions: dict[str, int] = {}
        counts: dict[str, int] = {}
        with self._session_factory() as session:
            if reset:
                for model in (
                    RmSubmission,
                    RmStudent,
                    RmGroup,
                    RmCourse,
                    RmPurgeTombstone,
                    ProjectionCheckpoint,
                ):
                    session.query(model).delete()
            for record in ordered:
                if record.contract_id == CT_005:
                    self._apply_ct005(session, record.payload)
                elif record.contract_id == CT_006:
                    self._apply_ct006(session, record.payload)
                elif record.contract_id == CT_012:
                    self._apply_ct012(session, record.payload)
                elif record.contract_id == CT_014:
                    self._apply_ct014(session, record.payload)
                elif record.contract_id == CT_015:
                    self._apply_ct015(session, record.payload)
                else:
                    raise ProjectorValidationError(
                        f"unsupported contract: {record.contract_id}"
                    )
                positions[record.contract_id] = max(
                    positions.get(record.contract_id, 0), record.record_id
                )
                counts[record.contract_id] = counts.get(record.contract_id, 0) + 1
            for contract, position in positions.items():
                self._set_checkpoint(session, contract, position)
        return counts

    def checkpoint(self, consumer: str) -> int:
        """读取某 consumer（contract_id）的当前位点；无记录返回 0。"""
        with self._session_factory() as session:
            row = session.get(ProjectionCheckpoint, consumer)
            return row.position if row is not None else 0

    # ---- CT-006：列表/状态投影（submission_id upsert，单调状态秩） ----

    def _apply_ct006(self, session: Session, payload: dict) -> None:
        sid = _require_str(payload, "submission_id")
        course_id = _require_str(payload, "course_id")
        group_id = _require_str(payload, "group_name")
        student_name = _require_str(payload, "student_name")
        status = _require_str(payload, "status")
        if status not in _STATUS_RANK:
            raise ProjectorValidationError(f"CT-006 unknown status: {status!r}")
        if self._tombstoned(session, sid):
            return  # 重放守卫：已清除数据不重建
        now = _naive_utc(self._clock())
        missing_items = list(payload.get("missing_items") or [])
        received_at = _parse_dt(payload.get("received_at"))
        self._upsert_catalog(session, course_id, group_id, student_name, now)
        row = session.get(RmSubmission, sid)
        if row is None:
            row = RmSubmission(
                submission_id=sid,
                course_id=course_id,
                group_id=group_id,
                student_name=student_name,
                assignment=payload.get("assignment") or "",
                status=status,
                missing_items=missing_items,
                material_refs=[],
                annotations=[],
                applied_adjustment_ids=[],
                received_at=received_at,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return
        assignment = payload.get("assignment") or row.assignment
        if received_at is None:
            received_at = row.received_at
        keep_status = row.status
        if _STATUS_RANK[status] >= _STATUS_RANK.get(row.status, 0) and (
            row.status not in _TERMINAL_STATUSES
        ):
            keep_status = status
        if (
            row.course_id == course_id
            and row.group_id == group_id
            and row.student_name == student_name
            and row.assignment == assignment
            and list(row.missing_items or []) == missing_items
            and row.received_at == received_at
            and row.status == keep_status
        ):
            return  # 幂等：重复事件不改投影
        row.course_id = course_id
        row.group_id = group_id
        row.student_name = student_name
        row.assignment = assignment
        row.missing_items = missing_items
        row.received_at = received_at
        row.status = keep_status
        row.updated_at = now

    # ---- CT-005：终态投影（+M05-IC-01 复核记录） ----

    def _apply_ct005(self, session: Session, payload: dict) -> None:
        sid = _require_str(payload, "submission_id")
        outcome = _require_str(payload, "outcome")
        if outcome not in _TERMINAL_STATUSES:
            raise ProjectorValidationError(f"CT-005 unknown outcome: {outcome!r}")
        if self._tombstoned(session, sid):
            return  # 重放守卫：已清除数据不重建
        now = _naive_utc(self._clock())
        row = session.get(RmSubmission, sid)
        if row is None:
            # CT-006 尚未到达（跨流顺序不保证）：先建行，身份字段待 CT-006 回填。
            row = RmSubmission(
                submission_id=sid,
                status="processing",
                missing_items=[],
                material_refs=[],
                annotations=[],
                applied_adjustment_ids=[],
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
        if row.status in _TERMINAL_STATUSES:
            # 终态去重（冻结契约 idempotency：重复事件不改变终态）；
            # scored 重放仍幂等确认复核记录存在（L14 按 submission_id 去重）。
            if outcome == "scored" and row.status == "scored":
                self._ensure_review_record(payload)
            return
        if outcome == "scored":
            grade = _require_str(payload, "original_grade")
            if grade not in GRADE_VALUES:
                raise ProjectorValidationError(
                    f"CT-005 invalid original_grade: {grade!r}"
                )
            row.status = "scored"
            row.original_grade = grade
            row.dimension_rationales = list(
                payload.get("dimension_rationales") or []
            )
            row.teacher_suggestions = list(payload.get("teacher_suggestions") or [])
            row.scored_at = _parse_dt(payload.get("scored_at")) or now
            row.failure_reason = None
            row.retry_record = None
            row.updated_at = now
            session.flush()
            # M05-IC-01：复核记录创建（L14 注入，按 submission_id 幂等）；
            # 失败则本事务整体回滚，由投递器重试。
            self._ensure_review_record(payload)
        else:
            row.status = "scoring_failed"
            row.failure_reason = _require_str(payload, "failure_reason")
            retry_record = payload.get("retry_record")
            row.retry_record = dict(retry_record) if retry_record else None
            row.original_grade = None
            row.dimension_rationales = None
            row.teacher_suggestions = None
            row.scored_at = None
            row.updated_at = now
            session.flush()

    def _ensure_review_record(self, payload: dict) -> None:
        if self._create_review_record is None:
            return
        self._create_review_record(
            submission_id=payload["submission_id"],
            original_grade=payload.get("original_grade"),
            dimension_rationales=payload.get("dimension_rationales") or [],
            scored_at=_parse_dt(payload.get("scored_at")),
        )

    # ---- M05-IC-05：复核事件投影（adjustment_id 去重） ----

    def _apply_review_event(self, session: Session, event) -> None:
        row = session.get(RmSubmission, event.submission_id)
        if row is None or self._tombstoned(session, event.submission_id):
            return
        applied = list(row.applied_adjustment_ids or [])
        # 去重键 = adjustment_id + event_type：L14 一次「批注+等级」调整对两事件
        # 共用同一 adjustment_id，仅按 id 去重会跳过第二条事件（丢 final_grade）
        dedup_key = f"{event.adjustment_id}:{event.event_type}"
        if dedup_key in applied:
            return  # 幂等：同键重放不改投影
        if event.event_type == _EVENT_ANNOTATION_SAVED:
            annotations = list(row.annotations or [])
            annotations.append(
                {
                    "text": event.annotation_excerpt or "",
                    "operator": event.operator,
                    "updated_at": event.updated_at,
                }
            )
            row.annotations = annotations
        elif event.event_type == _EVENT_GRADE_ADJUSTED:
            row.final_grade = event.final_grade
        else:
            raise ProjectorValidationError(
                f"M05-IC-05 unknown event_type: {event.event_type!r}"
            )
        applied.append(dedup_key)
        row.applied_adjustment_ids = applied
        row.updated_at = _naive_utc(self._clock())

    # ---- CT-012 / CT-014：清除投影 + 墓碑（重放守卫） ----

    def _apply_ct012(self, session: Session, payload: dict) -> None:
        batch_id = _require_str(payload, "batch_id")
        purged_at = _parse_dt(payload.get("executed_at")) or _naive_utc(self._clock())
        ids = payload.get("submission_ids") or []
        if not isinstance(ids, (list, tuple)):
            raise ProjectorValidationError("CT-012 submission_ids must be a list")
        for sid in dict.fromkeys(ids):
            self._purge_row(session, str(sid), batch_id, purged_at)

    def _apply_ct014(self, session: Session, payload: dict) -> None:
        batch_id = _require_str(payload, "batch_id")
        purged_at = _parse_dt(payload.get("purged_at")) or _naive_utc(self._clock())
        ids = payload.get("purged_submission_ids") or []
        if not isinstance(ids, (list, tuple)):
            raise ProjectorValidationError(
                "CT-014 purged_submission_ids must be a list"
            )
        for sid in dict.fromkeys(ids):
            self._purge_row(session, str(sid), batch_id, purged_at)

    def _apply_ct015(self, session: Session, payload: dict) -> None:
        """CCR-001：CT-015（MOD-04 评分清除回流）投影，语义与 CT-014 相同。"""
        self._apply_ct014(session, payload)

    @staticmethod
    def _purge_row(
        session: Session, submission_id: str, batch_id: str, purged_at: datetime
    ) -> None:
        row = session.get(RmSubmission, submission_id)
        if row is not None:
            session.delete(row)
        if session.get(RmPurgeTombstone, submission_id) is None:
            session.add(
                RmPurgeTombstone(
                    submission_id=submission_id,
                    batch_id=batch_id,
                    purged_at=purged_at,
                    created_at=_naive_utc(datetime.now(timezone.utc)),
                )
            )
        session.flush()

    # ---- 位点（与投影同事务） ----

    def _advance_checkpoint(
        self, session: Session, consumer: str, position: int
    ) -> None:
        row = session.get(ProjectionCheckpoint, consumer)
        if row is None:
            row = ProjectionCheckpoint(
                consumer=consumer, position=0, updated_at=_naive_utc(self._clock())
            )
            session.add(row)
        row.position = max(row.position, int(position))
        row.updated_at = _naive_utc(self._clock())
        session.flush()

    def _set_checkpoint(self, session: Session, consumer: str, position: int) -> None:
        row = session.get(ProjectionCheckpoint, consumer)
        if row is None:
            row = ProjectionCheckpoint(
                consumer=consumer,
                position=int(position),
                updated_at=_naive_utc(self._clock()),
            )
            session.add(row)
        else:
            row.position = int(position)
            row.updated_at = _naive_utc(self._clock())
        session.flush()

    # ---- 内部 ----

    @staticmethod
    def _upsert_catalog(
        session: Session,
        course_id: str,
        group_id: str,
        student_name: str,
        now: datetime,
    ) -> None:
        course = session.get(RmCourse, course_id)
        if course is None:
            session.add(RmCourse(course_id=course_id, created_at=now, updated_at=now))
        group = session.get(RmGroup, (course_id, group_id))
        if group is None:
            session.add(
                RmGroup(course_id=course_id, group_id=group_id,
                        created_at=now, updated_at=now)
            )
        student = session.get(RmStudent, (course_id, group_id, student_name))
        if student is None:
            session.add(
                RmStudent(course_id=course_id, group_id=group_id,
                          student_name=student_name, created_at=now, updated_at=now)
            )

    @staticmethod
    def _tombstoned(session: Session, submission_id: str) -> bool:
        return session.get(RmPurgeTombstone, submission_id) is not None


def _require_str(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ProjectorValidationError(
            f"payload field must be non-empty string: {field_name}"
        )
    return value


__all__ = [
    "Base",
    "CreateReviewRecord",
    "OUTBOX_CONTRACTS",
    "ProjectorValidationError",
    "ReadModelProjector",
]
