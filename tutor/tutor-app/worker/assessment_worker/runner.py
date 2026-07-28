"""DU-3 worker 常驻认领循环（GAP-02）。

职责与语义：
- **CT-004 入站**：轮询 Outbox（contract_ids 过滤，只认领 CT-004，不触碰 DU-2
  契约），消费创建评分任务后确认（orchestrator 按 submission_id 幂等 + 墓碑
  重放守卫）；
- **认领执行**：N 个认领线程（可配置并发），claim_task 获取租约 → L12 真实装配
  （rubric composer + ICT-003 材料只读 + ACL provider）→ complete/fail 回调；
  执行期间按 lease_ttl/3 心跳续期，续约失败（租约已失）仅记录，完成回调将被
  orchestrator 拒绝（不产生错误状态）；
- **失败重试**：outcome.ok=False → fail_assessment(error_kind)（REQ-012 重试一次
  + 终态化归 L3）；engine 未分类异常 → 释放租约供重认领（不耗业务重试预算），
  异常本身告警可观测；
- **重启恢复**：崩溃/重启后租约自然过期，claim_task 自动重认领； reclaim 超上限
  任务由 orchestrator 终态化（LCD-002）；启动时扫描积压并记录；
- **优雅关闭**：SIGTERM/SIGINT → 停止认领与入站，在飞任务执行完毕后退出；
  强退场景租约过期即被其他副本/下次启动重认领；
- **可观测**：结构化日志 + metrics 计数（ct004 确认/认领/完成/失败/异常/续约失败/
  材料读取/拒绝）+ 积压 gauge；连续循环异常以 ERROR 级日志告警。
"""
from __future__ import annotations

import os
import signal
import socket
import threading
import time
from dataclasses import replace as dc_replace
from datetime import datetime, timedelta, timezone
from typing import Callable

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from tutor_shared.logging import get_logger
from tutor_shared.metrics import registry as metrics_registry
from tutor_shared.outbox import SqlaOutboxStore

from course_app.db import normalize_db_url, session_scope
from course_app.submission_intake.store.reader import (
    MaterialContentReader,
    MaterialContentUnreadableError,
)

from .assessment_engine.engine import AssessmentEngine
from .assessment_engine.errors import MaterialUnreadableError
from .model_acl.acl import ModelServiceAcl
from .model_provider import build_provider
from .rubric.composer import RubricPromptComposer
from .scoring_orchestrator.errors import TerminalCallbackRejected
from .scoring_orchestrator.lease_store import SqlaTaskLeaseStore
from .scoring_orchestrator.models import ScoringTask
from .scoring_orchestrator.orchestrator import ScoringOrchestrator
from .settings import Settings

CT_004 = "CT-004"


def build_engine(database_url: str):
    """worker 侧引擎（驱动归一与 DU-2 同口径：normalize_db_url）。

    池 10+20：压测突发下热表行锁等待会延长单次占用（staging NFR-002 实测默认
    5+10 出现池耗尽——可自愈但吞吐受损）；仍远小于 PG max_connections 扣除
    DU-2 池（20+30）后的余量。
    """
    return sa.create_engine(
        normalize_db_url(database_url),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


class _TaskMaterialReader:
    """engine `MaterialReadPort` 适配：绑定任务授权上下文（ICT-003 课程/提交隔离）。"""

    def __init__(self, reader: MaterialContentReader, *, course_id: str, submission_id: str) -> None:
        self._reader = reader
        self._course_id = course_id
        self._submission_id = submission_id

    def load(self, material_refs: list) -> dict:
        try:
            return self._reader.load_for(
                course_id=self._course_id,
                submission_id=self._submission_id,
                material_refs=material_refs,
            )
        except MaterialContentUnreadableError as exc:
            raise MaterialUnreadableError(str(exc)) from exc


class WorkerRunner:
    """DU-3 常驻循环（CT-004 入站 + 并发认领执行）。

    依赖注入（测试可全量替换）：
    - `sa_engine`：SQLAlchemy 引擎（默认按 settings.database_url 构建）；
    - `clock`：可注入时钟；
    - `install_signals`：测试置 False（signal 仅允许主线程）；
    - `shutdown_grace_seconds`：优雅关闭等待在飞任务的上限。
    """

    def __init__(
        self,
        settings: Settings,
        *,
        sa_engine=None,
        clock: Callable[[], datetime] | None = None,
        install_signals: bool = True,
        shutdown_grace_seconds: float = 30.0,
        provider=None,
    ) -> None:
        self._settings = settings
        self._engine = sa_engine or build_engine(settings.database_url)
        self._sm = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._session_scope = lambda: session_scope(self._engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._worker_id = settings.worker_id or f"{socket.gethostname()}-{os.getpid()}"
        self._stop = threading.Event()
        self._install_signals = install_signals
        self._shutdown_grace = shutdown_grace_seconds
        self._lease_ttl = timedelta(seconds=settings.claim_lease_seconds)
        self._log = get_logger("assessment_worker.runner", settings.log_level)

        self._lease_store = SqlaTaskLeaseStore(self._sm)
        self._outbox_factory = SqlaOutboxStore
        self._orchestrator = ScoringOrchestrator(
            session_factory=self._sm,
            lease_store=self._lease_store,
            outbox_store=SqlaOutboxStore,  # 工厂形：回调事务内按 Session 构造
            lease_ttl_seconds=settings.claim_lease_seconds,
        )
        self._material_reader = MaterialContentReader(
            self._session_scope, settings.data_dir, logger=self._log
        )
        # fail fast：不支持的 provider 在启动即失败（不接入真实供应商）；
        # provider 注入仅用于测试替换（真实装配仍走 ModelServiceAcl）
        self._provider = ModelServiceAcl(
            provider=provider if provider is not None else build_provider(settings.model_provider)
        )
        self._threads: list[threading.Thread] = []
        self._consecutive_loop_errors = 0
        # 供应商降级状态（kill switch 日志一次性、熔断计数与冷却截止）
        self._kill_switch_logged = False
        self._consecutive_vendor_failures = 0
        self._circuit_open_until = 0.0
        self._circuit_lock = threading.Lock()

    # ------------------------------------------------------------------ 公共

    def request_shutdown(self) -> None:
        """请求优雅关闭（信号处理与测试共用入口）。"""
        self._stop.set()

    def run(self) -> int:
        """主循环：启动认领线程 → CT-004 入站轮询 → 优雅关闭。返回进程退出码。"""
        if self._install_signals:
            self._install_signal_handlers()
        self._log.info(
            "worker starting",
            extra={
                "worker_id": self._worker_id,
                "concurrency": self._settings.concurrency,
                "model_provider": self._settings.model_provider,
                "claim_lease_seconds": self._settings.claim_lease_seconds,
            },
        )
        self._log_recovery_scan()
        self._threads = [
            threading.Thread(
                target=self._claim_loop, args=(slot,), name=f"claim-{slot}", daemon=True
            )
            for slot in range(self._settings.concurrency)
        ]
        for thread in self._threads:
            thread.start()
        try:
            while not self._stop.is_set():
                self._ingress_once_guarded()
                self._stop.wait(self._settings.poll_interval_seconds)
        finally:
            self._stop.set()
            for thread in self._threads:
                thread.join(timeout=self._shutdown_grace)
            alive = [t.name for t in self._threads if t.is_alive()]
            self._log.info(
                "worker stopped",
                extra={
                    "unfinished_claim_threads": alive,
                    "note": "未完成任务租约过期后由重认领恢复" if alive else "全部在飞任务已完成",
                },
            )
        return 0

    # ------------------------------------------------------------- CT-004 入站

    def _ingress_once_guarded(self) -> None:
        try:
            self._ingress_once()
            self._consecutive_loop_errors = 0
        except Exception as exc:
            self._consecutive_loop_errors += 1
            metrics_registry.inc("worker_loop_errors_total")
            self._log.error(
                "ingress loop error (consecutive=%d): %s: %s",
                self._consecutive_loop_errors, type(exc).__name__, exc,
            )
            self._stop.wait(min(30.0, self._settings.poll_interval_seconds * 5))

    def _ingress_once(self) -> int:
        """一轮 CT-004 入站：只认领 CT-004（contract_ids 过滤，不触碰 DU-2 契约）。"""
        now = self._clock()
        confirmed = 0
        with self._session_scope() as session:
            store = self._outbox_factory(session)
            for record in store.fetch_due(now, contract_ids=(CT_004,)):
                ingress = self._orchestrator.handle_submission_received(record.payload)
                store.mark_confirmed(record.record_id)
                confirmed += 1
                metrics_registry.inc("worker_ct004_confirmed_total")
                if ingress.tombstoned:
                    metrics_registry.inc("worker_ct004_tombstoned_total")
                    self._log.warning(
                        "CT-004 replay blocked by purge tombstone",
                        extra={"submission_id": ingress.submission_id},
                    )
        return confirmed

    # ------------------------------------------------------------- 认领执行

    def _claim_loop(self, slot: int) -> None:
        owner = f"{self._worker_id}-{slot}"
        while not self._stop.is_set():
            if self._claiming_paused(owner):
                self._stop.wait(self._settings.poll_interval_seconds)
                continue
            try:
                claimed = self._orchestrator.claim_task(owner=owner)
            except Exception as exc:
                metrics_registry.inc("worker_loop_errors_total")
                self._log.error("claim error: %s: %s", type(exc).__name__, exc)
                self._stop.wait(min(30.0, self._settings.poll_interval_seconds * 5))
                continue
            if claimed is None:
                self._stop.wait(self._settings.poll_interval_seconds)
                continue
            metrics_registry.inc("worker_tasks_claimed_total")
            self._execute_claimed(claimed, owner)

    def _claiming_paused(self, owner: str) -> bool:
        """降级闸门（批准策略：供应商不可用 → 无自动评分/稍后重试）。

        - kill switch：VENDOR_ENABLED=0 → 不认领，任务保持 pending；
        - 熔断：连续 circuit_threshold 次供应商失败（MODEL_TIMEOUT/MODEL_ERROR）
          → 冷却 circuit_cooldown_seconds 不认领；冷却结束自动半开恢复。
        两者都不终态化任务、不耗 REQ-012 业务重试预算——稍后自动重试。
        """
        if not self._settings.vendor_enabled:
            metrics_registry.gauge("vendor_kill_switch", 1)
            if not self._kill_switch_logged:
                self._log.warning("vendor disabled by kill switch (VENDOR_ENABLED=0); claiming paused")
                self._kill_switch_logged = True
            return True
        if self._kill_switch_logged:
            self._log.info("vendor re-enabled; claiming resumed")
            self._kill_switch_logged = False
        metrics_registry.gauge("vendor_kill_switch", 0)
        remaining = self._circuit_open_until - time.monotonic()
        if remaining > 0:
            return True
        if self._circuit_open_until > 0:
            self._log.info("vendor circuit closed after cooldown; claiming resumed")
            self._circuit_open_until = 0.0
            self._consecutive_vendor_failures = 0
        return False

    def _record_outcome_for_circuit(self, error_kind: str | None) -> None:
        """按终态结果更新熔断计数（线程间经锁串行）。"""
        with self._circuit_lock:
            if error_kind in ("MODEL_TIMEOUT", "MODEL_ERROR"):
                self._consecutive_vendor_failures += 1
                if (
                    self._consecutive_vendor_failures >= self._settings.circuit_threshold
                    and self._circuit_open_until == 0.0
                ):
                    self._circuit_open_until = (
                        time.monotonic() + self._settings.circuit_cooldown_seconds
                    )
                    metrics_registry.inc("vendor_circuit_opens_total")
                    self._log.error(
                        "vendor circuit OPEN after %d consecutive failures; cooldown %.0fs",
                        self._consecutive_vendor_failures,
                        self._settings.circuit_cooldown_seconds,
                    )
            elif error_kind is None:
                self._consecutive_vendor_failures = 0

    def _execute_claimed(self, claimed, owner: str) -> None:
        """执行一个已认领任务：心跳续期 + engine 装配 + 终态回调。"""
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(claimed.task_id, owner, heartbeat_stop),
            name=f"hb-{claimed.task_id[:8]}",
            daemon=True,
        )
        heartbeat.start()
        try:
            engine = self._build_task_engine(claimed)
            # REQ-012：任务内重试（同租约 attempt_no=2，不重新认领；L03 冒烟接线口径）
            attempt_no = claimed.attempt_no
            while True:
                outcome = engine.run(dc_replace(claimed, attempt_no=attempt_no))
                if outcome.ok:
                    payload = dict(outcome.payload)
                    payload.pop("attempt_no", None)
                    self._orchestrator.complete_assessment(
                        claimed.task_id, owner=owner, attempt_no=attempt_no, **payload
                    )
                    metrics_registry.inc("worker_tasks_completed_total")
                    self._record_outcome_for_circuit(None)
                    return
                result = self._orchestrator.fail_assessment(
                    claimed.task_id,
                    owner=owner,
                    attempt_no=attempt_no,
                    error_kind=outcome.error_kind,
                )
                metrics_registry.inc("worker_tasks_failed_total")
                self._record_outcome_for_circuit(outcome.error_kind)
                self._log.warning(
                    "assessment failed task_id=%s attempt=%d error_kind=%s",
                    claimed.task_id, attempt_no, outcome.error_kind,
                )
                if type(result).__name__ != "RetryEntered":
                    return  # 终态 scoring_failed（第二次失败）
                metrics_registry.inc("worker_tasks_retried_total")
                attempt_no = result.next_attempt_no  # 唯一一次重试，同租约继续
        except TerminalCallbackRejected as exc:
            # 租约已失/重复回调：orchestrator 已拒绝，状态未变，重认领路径接管
            metrics_registry.inc("worker_stale_callbacks_total")
            self._log.warning(
                "terminal callback rejected task_id=%s: %s", claimed.task_id, exc
            )
        except Exception as exc:  # 未分类异常：释放租约供重认领，不耗业务重试预算
            metrics_registry.inc("worker_task_exceptions_total")
            self._log.error(
                "engine uncaught error task_id=%s: %s: %s",
                claimed.task_id, type(exc).__name__, exc,
            )
            try:
                self._lease_store.release(claimed.task_id, owner)
            except Exception as rel_exc:
                self._log.error("lease release failed task_id=%s: %s", claimed.task_id, rel_exc)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)

    def _heartbeat(self, task_id: str, owner: str, stop: threading.Event) -> None:
        """执行期间按 lease_ttl/3 续期；续约失败（租约已失）停止并记录。"""
        interval = max(1.0, self._lease_ttl.total_seconds() / 3)
        while not stop.wait(interval):
            try:
                renewed = self._lease_store.renew(
                    task_id, owner, self._lease_ttl, self._clock()
                )
            except Exception as exc:
                metrics_registry.inc("worker_lease_renew_errors_total")
                self._log.error("lease renew error task_id=%s: %s", task_id, exc)
                continue
            if not renewed:
                metrics_registry.inc("worker_lease_renew_failures_total")
                self._log.warning(
                    "lease renew denied (lease lost) task_id=%s owner=%s", task_id, owner
                )
                return

    # ------------------------------------------------------------- 内部

    def _build_task_engine(self, claimed) -> AssessmentEngine:
        """L12 真实装配：rubric composer + ICT-003 授权材料读 + ACL provider。"""
        with self._sm() as session:
            composer = RubricPromptComposer(session)
        reader = _TaskMaterialReader(
            self._material_reader,
            course_id=claimed.course_id,
            submission_id=claimed.submission_id,
        )
        return AssessmentEngine(composer, reader, self._provider)

    def _log_recovery_scan(self) -> None:
        """启动恢复扫描：积压与在飞任务计数（重启恢复可观测）。"""
        now = self._clock().replace(tzinfo=None)
        with self._sm() as session:
            pending = session.query(ScoringTask).filter(ScoringTask.status == "pending").count()
            inflight = session.query(ScoringTask).filter(ScoringTask.status == "in_progress").count()
            expired = (
                session.query(ScoringTask)
                .filter(
                    ScoringTask.status == "in_progress",
                    ScoringTask.lease_expires_at.is_not(None),
                    ScoringTask.lease_expires_at <= now,
                )
                .count()
            )
        metrics_registry.gauge("worker_backlog_pending", pending)
        metrics_registry.gauge("worker_backlog_in_progress", inflight)
        self._log.info(
            "worker recovery scan",
            extra={"pending": pending, "in_progress": inflight, "reclaimable_expired": expired},
        )

    def _install_signal_handlers(self) -> None:
        def _handler(signum, _frame) -> None:
            self._log.info("shutdown signal received", extra={"signal": signum})
            self.request_shutdown()

        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
