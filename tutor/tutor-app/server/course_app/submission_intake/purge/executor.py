"""SI-PURGE：CT-012 RecordsDeleted 消费 → 逐项清除 → CT-014 PurgeCompleted 回传（T-B01c / IC-SI-06）。

语义（DF-3 步骤 4–5 / FLOW-010/012 / ST-07）：
- 输入 CT-012 payload（batch_id、submission_ids[]、scope、operator、executed_at、
  audit_record_id、v=1）；逐 submission_id 独立小事务清除：先删材料
  （MaterialStorePort.delete 幂等，MaterialFile 登记转 deleted），再回写提交记录
  （SI-CORE purge_submission → deleted，已删除为空操作）；单项失败不阻塞其他项；
- 逐项结果登记 PurgeExecution（ST-07：batch_id、逐项结果、失败原因）；重复 CT-012
  （同 batch_id）对已删项为空操作（仍计入 purged 回传），失败项可在重跑中成功，
  重跑更新既有登记行而非新增；
- 批次汇总后与登记行同事务一次性写 Outbox：CT-014 载荷（batch_id、
  purged_submission_ids[]、failed_items[]、purged_at、v=1），
  dedup_key=batch_id+purged_at（CT-014 幂等键）；投递归 SI-RELAY。

边界：不计算保留到期、不持有删除批次/确认/审计记录（归 MOD-05）；审计记录不在
清除范围；AssessmentResult（MOD-04）删除接线归 MOD-04（CCR-001 方案 A 已落地：
scoring_orchestrator/purge.py 消费同一 CT-012 并回传 CT-015）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, ContextManager, Sequence

from sqlalchemy.orm import Session

from tutor_shared.outbox import OutboxStore

from ..core.errors import NotFoundError
from ..core.models import SubmissionMaterial
from ..core.service import SubmissionCoreService
from ..xfer.store import MaterialStorePort

from .errors import PurgeValidationError
from .models import (
    EXECUTION_COMPLETED,
    EXECUTION_PARTIAL,
    RESULT_FAILED,
    RESULT_PURGED,
    PurgeExecutionItemRow,
    PurgeExecutionRow,
)

CT_014 = "CT-014"

_CT012_REQUIRED = frozenset(
    {"batch_id", "submission_ids", "scope", "operator", "executed_at", "audit_record_id", "v"}
)

#: OutboxStore 实例（测试/内存）或按 Session 构造的工厂（SQL 同事务入队，KD-002；
#: 组合根直接传 SqlaOutboxStore 类即可）。
OutboxProvider = OutboxStore | Callable[[Session], OutboxStore]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Ct012Command:
    """校验后的 CT-012 指令（冻结契约字段，additionalProperties=false）。"""

    batch_id: str
    submission_ids: tuple[str, ...]
    scope: str
    operator: str
    executed_at: str
    audit_record_id: str


@dataclass(frozen=True)
class PurgeItemResult:
    """单项清除结果（短生命周期返回值；持久化形态为 PurgeExecutionItemRow）。"""

    submission_id: str
    result: str  # RESULT_PURGED / RESULT_FAILED
    reason: str | None


@dataclass(frozen=True)
class PurgeReport:
    """一次批次执行的汇总（CT-014 载荷与 Outbox 记录 id 供调用方/测试核验）。"""

    batch_id: str
    purged_submission_ids: tuple[str, ...]
    failed_items: tuple[dict, ...]
    purged_at: datetime
    ct014_payload: dict
    outbox_record_id: int


def validate_ct012(payload: dict) -> Ct012Command:
    """按 contracts/ct-012.json 校验事件本体；不满足冻结契约抛 PurgeValidationError。"""
    if not isinstance(payload, dict):
        raise PurgeValidationError("CT-012 payload must be an object")
    missing = _CT012_REQUIRED - payload.keys()
    if missing:
        raise PurgeValidationError(f"CT-012 missing fields: {sorted(missing)}")
    extra = payload.keys() - _CT012_REQUIRED
    if extra:
        raise PurgeValidationError(f"CT-012 unexpected fields: {sorted(extra)}")
    if payload["v"] != 1:
        raise PurgeValidationError(f"CT-012 unsupported v: {payload['v']!r}")
    strings = {}
    for field in ("batch_id", "scope", "operator", "executed_at", "audit_record_id"):
        value = payload[field]
        if not isinstance(value, str) or not value:
            raise PurgeValidationError(f"CT-012 field must be non-empty string: {field}")
        strings[field] = value
    ids = payload["submission_ids"]
    if not isinstance(ids, (list, tuple)) or any(
        not isinstance(sid, str) or not sid for sid in ids
    ):
        raise PurgeValidationError("CT-012 submission_ids must be non-empty strings")
    # 同批次内重复 submission_id 去重（保持首次出现顺序），逐项结果唯一
    ordered = tuple(dict.fromkeys(ids))
    return Ct012Command(
        batch_id=strings["batch_id"],
        submission_ids=ordered,
        scope=strings["scope"],
        operator=strings["operator"],
        executed_at=strings["executed_at"],
        audit_record_id=strings["audit_record_id"],
    )


class PurgeExecutor:
    """CT-012 清除执行器（SI-PURGE 唯一入口；worker_job 由组合根驱动）。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文；
    - `core_service`：L02 SubmissionCoreService（purge_submission 幂等回写 deleted）；
    - `material_store`：MaterialStorePort（delete 幂等；实现归 SI-STORE）；
    - `outbox_store`：OutboxStore 实例或 `Callable[[Session], OutboxStore]`
      （SQL 接线传工厂使 CT-014 行与 PurgeExecution 登记同事务提交）；
    - `clock`：可注入时钟（purged_at 取值；测试）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        core_service: SubmissionCoreService,
        material_store: MaterialStorePort,
        outbox_store: OutboxProvider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._core = core_service
        self._material_store = material_store
        self._outbox_provider = outbox_store
        self._clock = clock or _utcnow

    # ---- CT-012 消费入口 ----

    def execute(self, payload: dict) -> PurgeReport:
        """消费一条 CT-012：逐项清除 → 登记 ST-07 → 同事务入队 CT-014。"""
        cmd = validate_ct012(payload)
        purged_at = self._clock()
        results = [self._purge_one(sid) for sid in cmd.submission_ids]
        purged_ids = tuple(
            item.submission_id for item in results if item.result == RESULT_PURGED
        )
        failed_items = tuple(
            {"submission_id": item.submission_id, "reason": item.reason or ""}
            for item in results
            if item.result == RESULT_FAILED
        )
        ct014_payload = {
            "batch_id": cmd.batch_id,
            "purged_submission_ids": list(purged_ids),
            "failed_items": [dict(item) for item in failed_items],
            "purged_at": purged_at.isoformat(),
            "v": 1,
        }
        # CT-014 幂等键：batch_id + purged_at（冻结契约 idempotency）
        dedup_key = f"{cmd.batch_id}:{purged_at.isoformat()}"
        with self._session_factory() as session:
            self._record_execution(session, cmd, results, purged_at)
            # KD-002：CT-014 Outbox 行与 PurgeExecution 登记同一本地事务提交
            record = self._outbox_for(session).enqueue(CT_014, ct014_payload, dedup_key)
        return PurgeReport(
            batch_id=cmd.batch_id,
            purged_submission_ids=purged_ids,
            failed_items=failed_items,
            purged_at=purged_at,
            ct014_payload=ct014_payload,
            outbox_record_id=record.record_id,
        )

    # ---- 逐项清除（单项失败不阻塞其他项） ----

    def _purge_one(self, submission_id: str) -> PurgeItemResult:
        """单项独立小事务序列：材料删除 → 提交记录 → deleted；任一步失败记 failed。"""
        try:
            for material_ref in self._manifest_refs(submission_id):
                # SI-STORE delete 幂等：重跑时已删 ref 为空操作
                self._material_store.delete(material_ref)
            # L02 purge_submission 幂等：已 deleted 返回 duplicate_ignored 空操作
            self._core.purge_submission(submission_id=submission_id)
            return PurgeItemResult(submission_id, RESULT_PURGED, None)
        except NotFoundError as exc:
            return PurgeItemResult(submission_id, RESULT_FAILED, str(exc))
        except Exception as exc:  # StorageIoError / DB 暂态等：保留失败项供重跑
            return PurgeItemResult(
                submission_id, RESULT_FAILED, f"{type(exc).__name__}: {exc}"
            )

    def _manifest_refs(self, submission_id: str) -> list[str]:
        with self._session_factory() as session:
            rows = (
                session.query(SubmissionMaterial)
                .filter(SubmissionMaterial.submission_id == submission_id)
                .all()
            )
            return [row.material_ref for row in rows]

    # ---- ST-07 登记（批次 upsert + 逐项 upsert；重跑更新不新增） ----

    @staticmethod
    def _record_execution(
        session: Session,
        cmd: Ct012Command,
        results: Sequence[PurgeItemResult],
        now: datetime,
    ) -> None:
        batch = session.get(PurgeExecutionRow, cmd.batch_id)
        if batch is None:
            batch = PurgeExecutionRow(
                batch_id=cmd.batch_id,
                scope=cmd.scope,
                operator=cmd.operator,
                audit_record_id=cmd.audit_record_id,
                status=EXECUTION_PARTIAL,
                run_count=0,
                first_executed_at=now,
                last_executed_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(batch)
        batch.run_count += 1
        batch.last_executed_at = now
        batch.updated_at = now
        batch.status = (
            EXECUTION_COMPLETED
            if all(item.result == RESULT_PURGED for item in results)
            else EXECUTION_PARTIAL
        )
        for item in results:
            row = (
                session.query(PurgeExecutionItemRow)
                .filter(
                    PurgeExecutionItemRow.batch_id == cmd.batch_id,
                    PurgeExecutionItemRow.submission_id == item.submission_id,
                )
                .one_or_none()
            )
            if row is None:
                row = PurgeExecutionItemRow(
                    batch_id=cmd.batch_id,
                    submission_id=item.submission_id,
                    result=item.result,
                    reason=item.reason,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.result = item.result
                row.reason = item.reason
                row.updated_at = now
        session.flush()

    def _outbox_for(self, session: Session) -> OutboxStore:
        provider = self._outbox_provider
        if isinstance(provider, OutboxStore):
            return provider
        return provider(session)
