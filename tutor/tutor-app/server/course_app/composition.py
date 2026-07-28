"""DU-2 组合根（T-B03d）：真实组件装配 + relay 消费注册。

只装配，不实现任何业务语义；所有业务行为归各叶子/组件。

装配面：
- engine（settings.database_url）+ scoped session 事务边界；启动不自动迁移
  （运维先跑 alembic upgrade heads，缺模式只告警）；
- SI-STORE FilesystemMaterialStore（settings.data_dir）兼作 L02 MaterialMetadataReader；
- Outbox：`_ScopedOutboxStore` 把 SqlaOutboxStore 解析到调用方 scoped session，
  使 L02 聚合写入与 Outbox 行同一本地事务提交（KD-002）；RetentionService /
  PurgeExecutor 经工厂形（SqlaOutboxStore 类）同事务入队；
- SI-RELAY OutboxRelayer 消费注册（每 consumer 经 InboundDedup 包装，ST-05）：
  CT-005 → [L02 apply_scoring_outcome, projector]；CT-006 → projector；
  CT-012 → [purge executor, MOD-04 assessment purge（CCR-001）, projector]；
  CT-014 → [retention handle_ct014, projector]；CT-015 → [retention handle_ct015,
  projector]（CCR-001 双回流）；
  CT-004 消费方是进程外 worker（本组合根不注册，UnknownContract 留待重试可观测）；
- L08 UploadTransferService + XferTransferAdapter（IC-SI-01 真实接线）+ L09
  create_router / create_multipart_router（verifier 进程内包装 L01 verify_membership）；
- ACCESS-GATE：AccessGateService + 三种冻结端口适配（L14/L15/L16）；
- ReadModelProjector（M05-IC-01 绑定 L14 create_review_record）+ ProjectorReadModel
  （M05-IC-02 双侧面，供 L15/L16）；L14 ReviewCommandService（M05-IC-05 经
  projector.publish）；RetentionService + CT-011 router + M05-IC-06 读端口；
  PurgeExecutor（CT-012 消费）；
- L17 api_client：进程内实现 InProcessTeacherApiClient（直接调用本组合根服务，
  v1 单进程形态；HttpTeacherApiClient 留给真实部署）。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any, Callable, ContextManager, Iterator, Sequence

from sqlalchemy.orm import Session, scoped_session, sessionmaker

from tutor_shared.outbox import OutboxRecord, OutboxStore, SqlaOutboxStore

from course_app import db
from course_app.course_roster import verifier as roster_verifier
from course_app.settings import Settings
from course_app.submission_intake.api.multipart import create_multipart_router
from course_app.submission_intake.api.orchestrator import IntakeOrchestrator
from course_app.submission_intake.api.ports import MembershipResult
from course_app.submission_intake.api.router import create_router as create_l09_router
from course_app.submission_intake.core.models import Submission
from course_app.submission_intake.core.service import SubmissionCoreService
from course_app.submission_intake.purge.executor import PurgeExecutor
from course_app.submission_intake.relay.dedup import DedupOutcome, InboundDedup
from course_app.submission_intake.relay.relayer import OutboxRelayer
from course_app.submission_intake.store.filesystem import FilesystemMaterialStore
from course_app.submission_intake.wiring import XferTransferAdapter
from course_app.submission_intake.xfer.service import UploadTransferService
from course_app.teacher_web.access_gate import errors as gate_errors
from course_app.teacher_web.access_gate.adapters import (
    PresentationAccessGate,
    ReviewCommandAccessGate,
    ReviewQueryAccessGate,
)
from course_app.teacher_web.access_gate.service import AccessGateService
from course_app.teacher_web.presentation.coordinator import PresentationCoordinator
from course_app.teacher_web.presentation.errors import PresentationError
from course_app.teacher_web.presentation.output import to_response
from course_app.teacher_web.presentation.store import SnapshotStore
from course_app.teacher_web.projector.projector import ReadModelProjector
from course_app.teacher_web.projector.read_model import ProjectorReadModel
from course_app.teacher_web.retention.errors import (
    BatchNotExpiredError,
    BatchNotFoundError,
)
from course_app.teacher_web.retention.read_port import RetentionViewPortAdapter
from course_app.teacher_web.retention.service import RetentionService
from course_app.teacher_web.review_command.errors import ReviewCommandError
from course_app.teacher_web.review_command.ports import SubmissionStatus
from course_app.teacher_web.review_command.service import ReviewCommandService
from course_app.teacher_web.review_query.errors import RqError
from course_app.teacher_web.review_query.facade import ReviewQueryService, create_facade
from course_app.teacher_web.ui.client import (
    AUTH_INVALID,
    BATCH_NOT_EXPIRED,
    FORBIDDEN,
    NOT_FOUND,
    TeacherApiError,
    TeacherSession,
)

logger = logging.getLogger("tutor.composition")

CT_005 = "CT-005"
CT_006 = "CT-006"
CT_012 = "CT-012"
CT_014 = "CT-014"
CT_015 = "CT-015"

ClockFn = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _ConsumerRetryError(Exception):
    """dedup 判 RETRY（可重试业务失败）→ 交还投递器按退避重投。"""


class _ScopedOutboxStore(OutboxStore):
    """KD-002 同事务 Outbox：每次调用把 SqlaOutboxStore 解析到当前线程的
    scoped session——调用方（L02 等）的事务内入队与业务写入同 commit。"""

    def __init__(self, scoped: scoped_session) -> None:
        self._scoped = scoped

    def _store(self) -> SqlaOutboxStore:
        return SqlaOutboxStore(self._scoped())

    def enqueue(self, contract_id: str, payload: dict, dedup_key: str) -> OutboxRecord:
        return self._store().enqueue(contract_id, payload, dedup_key)

    def fetch_due(self, now: datetime, limit: int = 50) -> list[OutboxRecord]:
        return self._store().fetch_due(now, limit)

    def mark_confirmed(self, record_id: int) -> None:
        self._store().mark_confirmed(record_id)

    def mark_retry(self, record_id: int, next_attempt_at: datetime | None = None) -> None:
        self._store().mark_retry(record_id, next_attempt_at)


class _CoreSubmissionStatusPort:
    """L14 SubmissionStatusPort 绑定：直读 SI-CORE 提交登记（同库只读）。"""

    def __init__(self, session_factory: Callable[[], ContextManager[Session]]) -> None:
        self._session_factory = session_factory

    def get_submission_status(self, submission_id: str) -> SubmissionStatus | None:
        with self._session_factory() as session:
            row = session.get(Submission, submission_id)
            if row is None:
                return None
            return SubmissionStatus(submission_id=row.submission_id, status=row.status)


def _event_key(record: OutboxRecord) -> str:
    """入站去重业务键（ST-05：重复事件不重复应用；不同逻辑事件键不同）。"""
    payload = record.payload or {}
    if record.contract_id == CT_005:
        return f"{payload.get('submission_id')}:{payload.get('outcome')}"
    if record.contract_id == CT_006:
        return f"{payload.get('submission_id')}:{payload.get('status')}"
    if record.contract_id == CT_012:
        return str(payload.get("batch_id"))
    if record.contract_id == CT_014:
        return f"{payload.get('batch_id')}:{payload.get('purged_at')}"
    return f"record:{record.record_id}"


def _dedup_handler(
    sm: sessionmaker,
    clock: ClockFn,
    contract_id: str,
    consumers: Sequence[tuple[str, Callable[[OutboxRecord], None]]],
) -> Callable[[OutboxRecord], None]:
    """consumer 列表按 InboundDedup 逐个包装：applied/quarantined 重投跳过；
    RETRY 抛 _ConsumerRetryError 交还 OutboxRelayer 退避重投（ST-04/05）。
    消费者自身管理业务事务（均按业务键幂等），dedup 行在全部成功后统一提交。
    """

    def handler(record: OutboxRecord) -> None:
        key = _event_key(record)
        with sm() as session:
            dedup = InboundDedup(session, clock=clock)
            try:
                for name, apply_fn in consumers:
                    outcome = dedup.handle(
                        f"{contract_id}:{name}:{key}",
                        contract_id,
                        lambda af=apply_fn: af(record),
                    )
                    if outcome is DedupOutcome.RETRY:
                        raise _ConsumerRetryError(f"{contract_id}:{name}:{key}")
            except Exception:
                session.rollback()
                raise
            session.commit()

    return handler


class InProcessTeacherApiClient:
    """L17 TeacherApiClient 进程内实现（v1 单进程形态；只装配调用，不新增语义）。

    错误映射只使用各叶子已冻结错误码（与 HTTP 部署形态一致），不改写业务结论。
    """

    def __init__(
        self,
        *,
        access_gate: AccessGateService,
        query_service: ReviewQueryService,
        review_gate: ReviewCommandAccessGate,
        review_service: ReviewCommandService,
        event_publisher,
        presentation_gate: PresentationAccessGate,
        coordinator: PresentationCoordinator,
        retention: RetentionService,
    ) -> None:
        self._access_gate = access_gate
        self._query = query_service
        self._review_gate = review_gate
        self._review = review_service
        self._event_publisher = event_publisher
        self._presentation_gate = presentation_gate
        self._coordinator = coordinator
        self._retention = retention

    def create_session(self, *, teacher_account: str, password: str) -> TeacherSession:
        try:
            token = self._access_gate.login(account=teacher_account, password=password)
        except gate_errors.AuthInvalidError as exc:
            raise TeacherApiError(AUTH_INVALID, str(exc)) from exc
        return TeacherSession(token=token)

    def query_view(
        self,
        *,
        teacher_session: str,
        course_id: str | None = None,
        group_id: str | None = None,
        student_id: str | None = None,
        submission_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            if submission_id is not None:
                return self._query.submission_detail(
                    teacher_session=teacher_session,
                    course_id=course_id,
                    submission_id=submission_id,
                )
            if student_id is not None and course_id is not None:
                return self._query.student_detail(
                    teacher_session=teacher_session,
                    course_id=course_id,
                    student_id=student_id,
                )
            if course_id is not None:
                return self._query.group_list(
                    teacher_session=teacher_session,
                    course_id=course_id,
                    group_id=group_id,
                )
            return self._query.course_list(teacher_session=teacher_session)
        except RqError as exc:
            raise TeacherApiError(exc.code, str(exc)) from exc

    def save_review(
        self,
        *,
        teacher_session: str,
        submission_id: str,
        request_id: str,
        annotation: str | None = None,
        final_grade: str | None = None,
        adjustment_reason: str | None = None,
    ) -> dict[str, Any]:
        try:
            grant = self._review_gate.authorize(
                teacher_session=teacher_session, submission_id=submission_id
            )
            outcome = self._review.apply_review(
                operator=grant.operator,
                submission_id=submission_id,
                request_id=request_id,
                annotation=annotation,
                final_grade=final_grade,
                adjustment_reason=adjustment_reason,
            )
        except ReviewCommandError as exc:
            raise TeacherApiError(exc.code, str(exc)) from exc
        # M05-IC-05：业务提交后发布；投影失败按 adjustment_id 重放（LCD-004）。
        if outcome.events:
            self._event_publisher.publish(outcome.events)
        return {"review_record": outcome.payload}

    def generate_presentation(
        self, *, teacher_session: str, group_ids: Sequence[str]
    ) -> dict[str, Any]:
        authorization = f"Bearer {teacher_session}" if teacher_session else None
        try:
            auth = self._presentation_gate.authorize(authorization=authorization)
            snapshot = self._coordinator.generate(auth=auth, group_ids=list(group_ids))
        except PresentationError as exc:
            raise TeacherApiError(exc.code, str(exc)) from exc
        return to_response(snapshot)

    def confirm_deletion_batch(
        self,
        *,
        teacher_session: str,
        batch_id: str,
        confirm: bool = True,
        exclusions: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        del confirm  # CT-011 请求 confirm 恒 true（冻结契约）
        try:
            identity = self._access_gate.verify_session(teacher_session)
        except gate_errors.AuthInvalidError as exc:
            raise TeacherApiError(AUTH_INVALID, str(exc)) from exc
        course_id = self._retention.batch_course_id(batch_id)
        if course_id is None:
            raise TeacherApiError(NOT_FOUND, f"deletion batch {batch_id!r} not found")
        try:
            self._access_gate.require_grant(
                identity,
                course_id=course_id,
                action="confirm.deletion",
                source="L17-inprocess",
            )
        except gate_errors.AccessDeniedError as exc:
            raise TeacherApiError(FORBIDDEN, str(exc)) from exc
        try:
            result = self._retention.confirm_batch(
                batch_id=batch_id,
                operator=identity.teacher_id,
                exclusions=list(exclusions or ()),
            )
        except BatchNotFoundError as exc:
            raise TeacherApiError(NOT_FOUND, str(exc)) from exc
        except BatchNotExpiredError as exc:
            raise TeacherApiError(BATCH_NOT_EXPIRED, str(exc)) from exc
        return {
            "batch_id": result.batch_id,
            "batch_status": result.batch_status,
            "pending_deletion_scope": list(result.pending_deletion_scope),
        }


@dataclass
class Composition:
    """组合根：全部已装配组件与挂载顺序固定的 router 列表。"""

    settings: Settings
    engine: Any
    session_scope: Callable[[], ContextManager[Session]]
    session_factory: sessionmaker
    material_store: FilesystemMaterialStore
    outbox_store: OutboxStore
    relayer: OutboxRelayer
    core_service: SubmissionCoreService
    xfer_service: UploadTransferService
    access_gate: AccessGateService
    review_service: ReviewCommandService
    query_service: ReviewQueryService
    coordinator: PresentationCoordinator
    retention: RetentionService
    purge_executor: PurgeExecutor
    projector: ReadModelProjector
    read_model: ProjectorReadModel
    api_client: InProcessTeacherApiClient
    routers: list

    def relayer_tick(self, now: datetime | None = None) -> dict[str, int]:
        """relay 驱动钩子：单轮 Outbox 轮询投递（供进程内调度器/测试调用；
        不在请求路径上阻塞）。返回 {claimed, confirmed, retry, advanced} 计数。"""
        counts = self.relayer.poll_once(now)
        counts["advanced"] = self._advance_confirmed_submissions()
        return counts

    def _advance_confirmed_submissions(self) -> int:
        """D-3（LCD-003）：CT-004 消费确认（评分任务持久化）后 received → processing。

        扫描 status='received' 且其 CT-004 outbox 记录已 confirmed 的提交并推进；
        L02 advance 对已 processing 为空操作（重复扫描天然幂等）。
        失败不阻塞其他记录：计数 advance_processing_failed_total 并告警。
        """
        import sqlalchemy as sa  # noqa: PLC0415

        from tutor_shared.metrics import registry as metrics_registry  # noqa: PLC0415
        from tutor_shared.outbox import OUTBOX_RECORDS_TABLE  # noqa: PLC0415

        from course_app.submission_intake.core.models import Submission  # noqa: PLC0415

        advanced = 0
        with self.session_scope() as session:
            rows = session.execute(
                sa.select(Submission.submission_id)
                .where(Submission.status == "received")
                .where(
                    sa.exists(
                        sa.select(OUTBOX_RECORDS_TABLE.c.id).where(
                            OUTBOX_RECORDS_TABLE.c.contract_id == "CT-004",
                            OUTBOX_RECORDS_TABLE.c.status == "confirmed",
                            OUTBOX_RECORDS_TABLE.c.dedup_key == Submission.submission_id,
                        )
                    )
                )
            ).scalars().all()
        for submission_id in rows:
            try:
                self.core_service.advance_to_processing(
                    submission_id=submission_id, consumer_ack="task_persisted"
                )
                advanced += 1
            except Exception as exc:  # noqa: BLE001 — 单条失败不阻塞整批
                metrics_registry.inc("advance_processing_failed_total")
                logger.warning(
                    "advance_to_processing failed",
                    extra={"submission_id": submission_id, "error_type": type(exc).__name__},
                )
        return advanced


def _make_membership_verifier(
    session_scope: Callable[[], ContextManager[Session]],
) -> Callable[..., MembershipResult]:
    """IC-SI-03 进程内包装：L09 MembershipVerifierPort ← L01 verify_membership。"""

    def verify(*, invite_code: str, student_name: str, group_name: str) -> MembershipResult:
        with session_scope() as session:
            outcome = roster_verifier.verify_membership(
                session,
                invite_code=invite_code,
                student_name=student_name,
                group_name=group_name,
            )
        return MembershipResult(
            verified=outcome.verified,
            course_id=outcome.course_id or None,
            reason=outcome.reason,
        )

    return verify


def _warn_if_schema_missing(engine) -> None:
    """迁移提示：启动不自动迁移（运维跑 alembic）；缺模式只告警不伪装就绪。"""
    try:
        import sqlalchemy as sa  # noqa: PLC0415

        inspector = sa.inspect(engine)
        if not inspector.has_table("outbox_records"):
            logger.warning(
                "数据库模式未就绪：组合根启动不自动迁移；"
                "请先执行 alembic upgrade heads（并行多头先 alembic merge heads）"
            )
    except Exception as exc:  # 检查本身失败不阻断启动；readiness 会如实反映
        logger.warning("schema 检查失败（%s）：启动继续，readiness 以实际检查为准", exc)


def build_composition(
    settings: Settings,
    *,
    engine=None,
    clock: ClockFn | None = None,
) -> Composition:
    """装配 DU-2 全部组件（只接线，不改任何叶子实现）。

    - `engine`：测试可注入（如 SQLite + StaticPool）；缺省按 settings.database_url
      经 `course_app.db.engine` 创建；
    - `clock`：可注入时钟（测试固定时间），贯穿 relay/dedup/projector/purge/
      retention/access-gate/xfer/material-store。
    """
    eng = engine if engine is not None else db.engine(settings)
    sm = sessionmaker(bind=eng, expire_on_commit=False)
    scoped = scoped_session(sm)
    clock = clock or _utcnow

    # 默认事务边界：每次调用新建 Session（与既有组件测试接线一致；
    # store/xfer 等组件各自管理独立小事务，禁止嵌套共享同一会话）。
    session_scope = partial(db.session_scope, eng)

    @contextmanager
    def core_tx() -> Iterator[Session]:
        """L02 聚合事务作用域（scoped session）：聚合写入 + Outbox 行同一线程
        本地会话、同一 commit（KD-002）；异常回滚；退出时归还线程本地会话。"""
        session = scoped()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            scoped.remove()

    _warn_if_schema_missing(eng)

    # ---- SI：存储 / Outbox / 聚合 / 传输 ----
    material_store = FilesystemMaterialStore(session_scope, settings.data_dir, clock=clock)
    outbox_store = _ScopedOutboxStore(scoped)
    core_service = SubmissionCoreService(
        session_factory=core_tx,
        outbox_store=outbox_store,
        metadata_reader=material_store,
    )
    xfer_service = UploadTransferService(
        session_factory=session_scope, store=material_store, clock=clock
    )
    adapter = XferTransferAdapter(xfer_service)
    membership_verifier = _make_membership_verifier(session_scope)
    orchestrator = IntakeOrchestrator(
        core_service=core_service,
        transfer_port=adapter,
        membership_verifier=membership_verifier,
    )

    # ---- ACCESS-GATE + 三种冻结端口适配 ----
    access_gate = AccessGateService(session_factory=session_scope, now_fn=clock)
    gate_l14 = ReviewCommandAccessGate(service=access_gate, session_factory=session_scope)
    gate_l15 = ReviewQueryAccessGate(service=access_gate)
    gate_l16 = PresentationAccessGate(service=access_gate)

    # ---- 教师端：复核 / 投影 / 保留治理 / 清除 ----
    review_service = ReviewCommandService(
        session_scope, submission_status=_CoreSubmissionStatusPort(session_scope)
    )
    projector = ReadModelProjector(
        session_scope,
        create_review_record=review_service.create_review_record,
        clock=clock,
    )
    read_model = ProjectorReadModel(session_scope)
    retention = RetentionService(session_scope, SqlaOutboxStore, clock=clock)
    retention_view = RetentionViewPortAdapter(retention)
    purge_executor = PurgeExecutor(
        session_scope,
        core_service=core_service,
        material_store=material_store,
        outbox_store=SqlaOutboxStore,
        clock=clock,
    )
    # CCR-001：MOD-04 评分清除消费（ICT-009）——同库共部署（KD-002），经 DU-2 relay
    # 注册为 CT-012 第三消费方；DU-3 常驻循环落地后迁回 worker 进程（GAP-02）。
    from assessment_worker.scoring_orchestrator.purge import (  # noqa: PLC0415
        AssessmentPurgeExecutor,
    )

    assessment_purge = AssessmentPurgeExecutor(
        session_scope, SqlaOutboxStore, clock=clock
    )
    query_service = create_facade(
        access_gate=gate_l15, read_model=read_model, retention_view=retention_view
    )
    coordinator = PresentationCoordinator(
        read_model=read_model, store=SnapshotStore(session_scope)
    )

    # ---- SI-RELAY：消费注册（CT-004 归进程外 worker，不在此注册） ----
    consumers: dict[str, list[tuple[str, Callable[[OutboxRecord], None]]]] = {
        CT_005: [
            (
                "si-core.apply_scoring_outcome",
                lambda record: core_service.apply_scoring_outcome(
                    submission_id=record.payload["submission_id"],
                    outcome=record.payload["outcome"],
                    failure_reason=record.payload.get("failure_reason"),
                ),
            ),
            ("readmodel-projector", projector.handle),
        ],
        CT_006: [("readmodel-projector", projector.handle)],
        CT_012: [
            ("si-purge.execute", lambda record: purge_executor.execute(record.payload)),
            ("mod04.assessment_purge", lambda record: assessment_purge.execute(record.payload)),
            ("readmodel-projector", projector.handle),
        ],
        CT_014: [
            ("retention.handle_ct014", lambda record: retention.handle_ct014(record.payload)),
            ("readmodel-projector", projector.handle),
        ],
        CT_015: [
            ("retention.handle_ct015", lambda record: retention.handle_ct015(record.payload)),
            ("readmodel-projector", projector.handle),
        ],
    }
    relayer = OutboxRelayer(session_factory=sm, clock=clock)
    for contract_id, handlers in consumers.items():
        relayer.register(contract_id, _dedup_handler(sm, clock, contract_id, handlers))

    # ---- L17 进程内 api_client ----
    api_client = InProcessTeacherApiClient(
        access_gate=access_gate,
        query_service=query_service,
        review_gate=gate_l14,
        review_service=review_service,
        event_publisher=projector,
        presentation_gate=gate_l16,
        coordinator=coordinator,
        retention=retention,
    )

    # ---- router 装配（挂载顺序固定：multipart 先，统一分发 CT-001） ----
    from course_app.course_roster.api import create_router as create_l01_router  # noqa: PLC0415
    from course_app.teacher_web.presentation.router import (  # noqa: PLC0415
        create_router as create_l16_router,
    )
    from course_app.teacher_web.retention.api import (  # noqa: PLC0415
        create_router as create_ct011_router,
    )
    from course_app.teacher_web.review_command.router import (  # noqa: PLC0415
        create_router as create_l14_router,
    )
    from course_app.teacher_web.review_query.router import (  # noqa: PLC0415
        create_router as create_l15_router,
    )
    from course_app.teacher_web.ui.views import create_router as create_l17_router  # noqa: PLC0415

    routers = [
        create_multipart_router(
            session_factory=session_scope, xfer=xfer_service, orchestrator=orchestrator
        ),
        create_l09_router(
            session_factory=session_scope,
            membership_verifier=membership_verifier,
            transfer_port=adapter,
            core_service=core_service,
        ),
        create_l01_router(session_scope_factory=session_scope),
        create_l14_router(
            service=review_service, access_gate=gate_l14, event_publisher=projector
        ),
        create_l15_router(
            access_gate=gate_l15, read_model=read_model, retention_view=retention_view
        ),
        create_l16_router(
            session_factory=session_scope, access_gate=gate_l16, read_model=read_model
        ),
        create_ct011_router(service=retention, access_gate=access_gate),
        create_l17_router(api_client=api_client),
    ]

    return Composition(
        settings=settings,
        engine=eng,
        session_scope=session_scope,
        session_factory=sm,
        material_store=material_store,
        outbox_store=outbox_store,
        relayer=relayer,
        core_service=core_service,
        xfer_service=xfer_service,
        access_gate=access_gate,
        review_service=review_service,
        query_service=query_service,
        coordinator=coordinator,
        retention=retention,
        purge_executor=purge_executor,
        projector=projector,
        read_model=read_model,
        api_client=api_client,
        routers=routers,
    )


__all__ = [
    "Composition",
    "InProcessTeacherApiClient",
    "build_composition",
]
