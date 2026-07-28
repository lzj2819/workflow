"""ICT-009：CT-012 RecordsDeleted 消费 → 评分记录清除 + 最小墓碑 + CT-015 回传（CCR-001 方案 A）。

语义（CCR-001 §2.2/§2.4，镜像 SI-PURGE 形态）：
- 输入 CT-012 payload（batch_id、submission_ids[]、scope、operator、executed_at、
  audit_record_id、v=1）；逐 submission_id 独立小事务清除：删除 ScoringResult
  （ST-002 评分内容：原始等级/维度依据/教师建议/模型元数据）与 ScoringTask
  （ST-001 含重试记录/租约），写入最小墓碑（submission_id、batch_id、purged_at）；
- 幂等：重复 CT-012（同 batch_id）对已删 submission 为空操作（墓碑已存在即跳过
  删除，仍计入 purged 回传）；单项失败不阻塞其他项，失败项经 CT-015
  failed_items[] 回传供重跑；
- 汇总后一次性写 Outbox：CT-015 AssessmentPurgeCompleted（batch_id、
  purged_submission_ids[]、failed_items[]、purged_at、v=1），
  dedup_key=batch_id+purged_at（CT-015 幂等键）；投递归 SI-RELAY；
- 墓碑用于 CT-004 重放守卫（orchestrator.handle_submission_received 拒绝为
  已清除提交重建评分任务）。

边界：不持有删除批次/审计（归 MOD-05）；MOD-02 材料清除归 SI-PURGE（CT-014）；
审计只经 CT-015 汇入 MOD-05 批次审计，本侧不产生独立审计。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, ContextManager

import sqlalchemy as sa
from sqlalchemy.orm import Session

from tutor_shared.outbox import OutboxStore

from .models import AssessmentPurgeTombstone, ScoringResult, ScoringTask

CT_015 = "CT-015"

_CT012_REQUIRED = frozenset(
    {"batch_id", "submission_ids", "scope", "operator", "executed_at", "audit_record_id", "v"}
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ct012ValidationError(ValueError):
    """CT-012 事件本体不满足冻结契约（additionalProperties=false）。"""


def validate_ct012_payload(payload: dict) -> tuple[str, tuple[str, ...]]:
    """校验 CT-012 事件本体，返回 (batch_id, 去重后 submission_ids)。

    MOD-04 侧只消费 batch_id 与 submission_ids；其余字段按契约校验存在性。
    """
    if not isinstance(payload, dict):
        raise Ct012ValidationError("CT-012 payload must be an object")
    missing = _CT012_REQUIRED - payload.keys()
    if missing:
        raise Ct012ValidationError(f"CT-012 missing fields: {sorted(missing)}")
    extra = payload.keys() - _CT012_REQUIRED
    if extra:
        raise Ct012ValidationError(f"CT-012 unexpected fields: {sorted(extra)}")
    if payload["v"] != 1:
        raise Ct012ValidationError(f"CT-012 unsupported v: {payload['v']!r}")
    batch_id = payload["batch_id"]
    if not isinstance(batch_id, str) or not batch_id:
        raise Ct012ValidationError("CT-012 batch_id must be a non-empty string")
    ids = payload["submission_ids"]
    if not isinstance(ids, (list, tuple)) or any(
        not isinstance(sid, str) or not sid for sid in ids
    ):
        raise Ct012ValidationError("CT-012 submission_ids must be non-empty strings")
    return batch_id, tuple(dict.fromkeys(ids))


@dataclass(frozen=True)
class AssessmentPurgeReport:
    """一次批次清除的汇总（CT-015 载荷与 Outbox 记录 id 供调用方/测试核验）。"""

    batch_id: str
    purged_submission_ids: tuple[str, ...]
    failed_items: tuple[dict, ...]
    purged_at: datetime
    ct015_payload: dict
    outbox_record_id: int


def is_tombstoned(session: Session, submission_id: str) -> bool:
    """重放守卫查询：该提交是否已评分清除（墓碑存在）。"""
    return session.get(AssessmentPurgeTombstone, submission_id) is not None


class AssessmentPurgeExecutor:
    """CT-012 消费：MOD-04 评分清除执行器（ICT-009 唯一入口；由组合根注册为消费方）。

    依赖注入：
    - `session_factory`：`course_app.db.session_scope` 风格单事务上下文；
    - `outbox_store`：OutboxStore 实例或 `Callable[[Session], OutboxStore]`
      （SQL 接线传工厂使 CT-015 行与清除同事务提交，KD-002）；
    - `clock`：可注入时钟（purged_at 取值；测试）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        outbox_store,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._outbox_provider = outbox_store
        self._clock = clock or _utcnow

    def execute(self, payload: dict) -> AssessmentPurgeReport:
        """消费一条 CT-012：逐项清除 + 墓碑 → 同事务入队 CT-015。"""
        batch_id, submission_ids = validate_ct012_payload(payload)
        purged_at = self._clock()
        purged: list[str] = []
        failed: list[dict] = []
        for sid in submission_ids:
            error = self._purge_one(sid, batch_id, purged_at)
            if error is None:
                purged.append(sid)
            else:
                failed.append({"submission_id": sid, "reason": error})
        ct015_payload = {
            "batch_id": batch_id,
            "purged_submission_ids": purged,
            "failed_items": failed,
            "purged_at": purged_at.isoformat(),
            "v": 1,
        }
        # CT-015 幂等键：batch_id + purged_at（冻结契约 idempotency）
        dedup_key = f"{batch_id}:{purged_at.isoformat()}"
        with self._session_factory() as session:
            record = self._outbox_for(session).enqueue(CT_015, ct015_payload, dedup_key)
        return AssessmentPurgeReport(
            batch_id=batch_id,
            purged_submission_ids=tuple(purged),
            failed_items=tuple(failed),
            purged_at=purged_at,
            ct015_payload=ct015_payload,
            outbox_record_id=record.record_id,
        )

    def _purge_one(self, submission_id: str, batch_id: str, purged_at: datetime) -> str | None:
        """单项独立小事务：删结果 + 删任务 + 写墓碑；幂等（墓碑已存在为空操作）。

        返回 None 表示成功（含幂等空操作）；否则返回失败原因（供 CT-015 failed_items）。
        """
        try:
            with self._session_factory() as session:
                if is_tombstoned(session, submission_id):
                    return None  # 重复 CT-012 / 重跑：已删项空操作，仍计 purged
                session.execute(
                    sa.delete(ScoringResult).where(
                        ScoringResult.submission_id == submission_id
                    )
                )
                session.execute(
                    sa.delete(ScoringTask).where(
                        ScoringTask.submission_id == submission_id
                    )
                )
                session.add(
                    AssessmentPurgeTombstone(
                        submission_id=submission_id,
                        batch_id=batch_id,
                        purged_at=purged_at.replace(tzinfo=None),
                    )
                )
            return None
        except Exception as exc:  # DB 暂态等：保留失败项供重跑
            return f"{type(exc).__name__}: {exc}"

    def _outbox_for(self, session: Session) -> OutboxStore:
        provider = self._outbox_provider
        if isinstance(provider, OutboxStore):
            return provider
        return provider(session)
