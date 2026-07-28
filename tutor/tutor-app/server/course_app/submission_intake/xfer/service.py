"""IC-SI-01 上传会话命令/查询端口实现（owner：SI-XFER，供 L09 SI-API 消费）。

命令/查询：create_session / append_chunk / finalize / abort / get_session /
mark_pending_verification / sweep_expired（TTL 扫描入口，LCD-006）。

关键语义（ST-02 / L2D-001~003 / KD-004/005）：
- submission_uuid 幂等建会话；同一 uuid 重复调用返回原会话，并承担
  ResumeUpload（interrupted_retryable → receiving）；
- 分片严格 next_expected_seq 顺序（L2D-002）：乱序报 CHUNK_OUT_OF_ORDER 且不写
  ST-XFER-02；同 seq 同摘要重放返回原结果（duplicate），摘要不同报冲突；
- checkpoint（ChunkReceipt/received_bytes/next_expected_seq）只记已确认分片，
  与进度更新同一会话事务提交（ST-XFER-01/02 原子）；
- 每次接受前检查累计大小 ≤500MB（KD-004，不只依赖最终化）；类别/类型白名单
  对齐 contracts/ct-001.json（材料类别枚举 + file_type_whitelist）；
- finalize 先持久化 FinalizeAttempt 再调 SI-STORE promote_to_final（L2D-003）；
  已 merged 重复 finalize 返回同一 material_refs；attempt_id 幂等；
- 合并前不产生正式 material_refs；SI-STORE 以抽象注入（实现归 backfill）；
- 存储 I/O 失败：会话置 interrupted_retryable 并设 retry_deadline，保留进度；
  重试窗口耗尽或 TTL 过期 → failed_terminal（映射父层 upload_failed 语义，
  MarkUploadFailed 调用归 L09/SI-CORE 编排）。

观测（ST-XFER-04 / L2D-004）：注入 observer 回调，非阻塞、失败不影响业务。
"""
from __future__ import annotations

import hashlib
import uuid as uuidlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, ContextManager, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import (
    ChunkDigestConflictError,
    ChunkOutOfOrderError,
    SessionNotFoundError,
    SessionStateError,
    SizeLimitExceededError,
    TypeNotAllowedError,
)
from .models import ChunkReceipt, FinalizeAttempt, UploadSession
from .store import MaterialStorePort, StorageIoError

# ---- 冻结值域（contracts/ct-001.json；不在本层修改） ----
MAX_SUBMISSION_BYTES = 524288000  # ct-001 limits.max_submission_bytes（500MB）
MATERIAL_CATEGORIES = ("对话", "代码", "截图", "结果")  # ct-001 material_chunks.category 枚举
FILE_TYPE_WHITELIST = ("代码", "文本", "图片", "常见文档", "压缩包")  # ct-001 limits.file_type_whitelist

# ---- 会话状态值域（L1 ST-02 冻结；不新增父状态值） ----
RECEIVING = "receiving"
INTERRUPTED_RETRYABLE = "interrupted_retryable"
MERGED = "merged"
PENDING_VERIFICATION = "pending_verification"
FAILED_TERMINAL = "failed_terminal"

# 分片操作结果（IC-XFER-02；不是父状态值）
ACCEPTED = "accepted"
DUPLICATE = "duplicate"

_TERMINAL_OR_READONLY = (MERGED, PENDING_VERIFICATION, FAILED_TERMINAL)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite 读出为 naive datetime；统一按 UTC 归一化后比较。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class SessionView:
    """IC-SI-01 会话进度/结果视图（get_session 只读，其余命令返回快照）。"""

    session_id: str
    submission_uuid: str
    state: str
    received_bytes: int
    next_expected_seq: int
    declared_categories: tuple[str, ...]
    material_refs: tuple[str, ...]
    failure_reason: str | None
    expires_at: datetime
    retry_deadline: datetime | None


@dataclass(frozen=True)
class AppendResult:
    """IC-XFER-02 分片操作输出；decision ∈ {accepted, duplicate}。

    rejected 分支以携带稳定错误码的异常表达（XferError 子类），
    不写暂存、不创建 ChunkReceipt、不改变会话状态。
    """

    decision: str
    session_id: str
    seq: int
    accepted_bytes: int
    received_bytes: int
    next_expected_seq: int
    duplicate: bool = False


@dataclass(frozen=True)
class FinalizeResult:
    """IC-XFER-04 合并结果。"""

    session_id: str
    state: str
    attempt_id: str
    material_refs: tuple[str, ...]
    idempotent: bool = False


@dataclass
class _Clock:
    """可注入时钟（TTL/重试窗口判定；默认真实 UTC 时间）。"""

    fn: Callable[[], datetime] = field(default=_utcnow)

    def now(self) -> datetime:
        return _as_utc(self.fn())


class UploadTransferService:
    """IC-SI-01 端口实现。

    依赖注入：
    - `session_factory`：返回 Session 上下文管理器（`course_app.db.session_scope`
      风格），提供单事务边界；异常回滚。
    - `store`：SI-STORE 端口抽象（IC-SI-02，实现归 backfill）。
    - `clock`：可注入时钟（TTL/retry_deadline 测试）。
    - `session_ttl` / `retry_window`：LCD-006 implementation_detail 运维参数。
    - `max_bytes`：默认 ct-001 冻结 500MB；测试可缩小注入。
    - `observer`：观测回调（TransferObservation；非阻塞，异常吞没）。
    """

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        store: MaterialStorePort,
        *,
        clock: Callable[[], datetime] | None = None,
        session_ttl: timedelta = timedelta(hours=24),
        retry_window: timedelta = timedelta(minutes=30),
        max_bytes: int = MAX_SUBMISSION_BYTES,
        observer: Callable[[dict], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._store = store
        self._clock = _Clock(clock or _utcnow)
        self._session_ttl = session_ttl
        self._retry_window = retry_window
        self._max_bytes = max_bytes
        self._observer = observer

    # ---- IC-XFER-01：建会话 / 查询 / 中止 / 恢复 ----

    def create_session(
        self, *, submission_uuid: str, declared_categories: Sequence[str]
    ) -> SessionView:
        """建会话（submission_uuid 幂等）；已存在返回原会话并承担 ResumeUpload。"""
        self._check_categories(declared_categories)
        now = self._clock.now()
        with self._session_factory() as session:
            existing = self._find_by_uuid(session, submission_uuid)
            if existing is not None:
                self._resume_if_interrupted(existing, now)
                return self._view(existing)
            row = UploadSession(
                session_id=uuidlib.uuid4().hex,
                submission_uuid=submission_uuid,
                declared_categories=list(declared_categories),
                state=RECEIVING,
                received_bytes=0,
                next_expected_seq=0,
                failure_reason=None,
                retry_deadline=None,
                expires_at=now + self._session_ttl,
                material_refs=None,
                version=0,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            view = self._view(row)
        self._observe("create_session", "ok", session_id=view.session_id)
        return view

    def get_session(self, *, submission_uuid: str) -> SessionView:
        """只读进度查询；无写副作用（内部状态不扩展父契约值域）。"""
        with self._session_factory() as session:
            row = self._find_by_uuid(session, submission_uuid)
            if row is None:
                raise SessionNotFoundError(f"unknown submission_uuid: {submission_uuid}")
            return self._view(row)

    def mark_pending_verification(self, *, session_id: str) -> SessionView:
        """merged → pending_verification（LCD-001：归属服务不可用由 SI-API 编排）。"""
        now = self._clock.now()
        with self._session_factory() as session:
            row = self._must_find(session, session_id)
            if row.state == PENDING_VERIFICATION:
                return self._view(row)
            if row.state != MERGED:
                raise SessionStateError(
                    f"cannot mark pending_verification from state={row.state}"
                )
            row.state = PENDING_VERIFICATION
            row.version += 1
            row.updated_at = now
            return self._view(row)

    def abort(self, *, session_id: str, reason: str = "") -> SessionView:
        """中止会话：置 failed_terminal 并发起暂存删除（delete 幂等）。"""
        now = self._clock.now()
        with self._session_factory() as session:
            row = self._must_find(session, session_id)
            if row.state == FAILED_TERMINAL:
                return self._view(row)
            if row.state in (MERGED, PENDING_VERIFICATION):
                raise SessionStateError(f"cannot abort session in state={row.state}")
            staged_refs = self._staged_refs(session, session_id)
            row.state = FAILED_TERMINAL
            row.failure_reason = f"aborted: {reason}" if reason else "aborted"
            row.version += 1
            row.updated_at = now
            view = self._view(row)
        self._delete_staged(staged_refs)
        self._observe("abort", "ok", session_id=session_id, reason_category="abort")
        return view

    # ---- IC-SI-01.append_chunk（XFER-CHUNK） ----

    def append_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        category: str,
        content: bytes,
        digest: str | None = None,
        media_type: str | None = None,
    ) -> AppendResult:
        """追加分片：校验 → SI-STORE 暂存 → 同事务写 ChunkReceipt + 进度。

        拒绝路径（rejected）抛携带错误码的异常，不写 ST-XFER-02、不改会话状态；
        存储 I/O 失败置 interrupted_retryable（保留进度与 retry_deadline）后抛出。
        """
        digest = digest or hashlib.sha256(content).hexdigest()
        now = self._clock.now()
        storage_error: StorageIoError | None = None
        state_error: SessionStateError | None = None
        with self._session_factory() as session:
            row = self._must_find(session, session_id)
            try:
                # 惰性终态转换（TTL/重试窗口）需先提交再抛出，故捕获后置后 raise
                self._check_ttl(row, now)
                self._check_writable(row, now)
            except SessionStateError as exc:
                state_error = exc
            else:
                result = self._append_checked(
                    session, row, now,
                    seq=seq, category=category, content=content,
                    digest=digest, media_type=media_type,
                )
                if isinstance(result, StorageIoError):
                    storage_error = result
        if state_error is not None:
            raise state_error
        if storage_error is not None:
            self._observe(
                "append_chunk", "interrupted",
                session_id=session_id, reason_category="STORAGE_IO_FAILED",
            )
            raise storage_error
        self._observe(
            "append_chunk", result.decision,
            session_id=session_id,
            reason_category="duplicate" if result.duplicate else None,
        )
        return result

    def _append_checked(
        self,
        session: Session,
        row: UploadSession,
        now: datetime,
        *,
        seq: int,
        category: str,
        content: bytes,
        digest: str,
        media_type: str | None,
    ) -> AppendResult | StorageIoError:
        """状态校验通过后的分片处理；存储失败时标记中断并返回异常对象。"""
        size = len(content)
        self._check_chunk_type(category, media_type)
        existing = self._find_receipt(session, row.session_id, seq)
        if existing is not None:
            if existing.digest != digest:
                raise ChunkDigestConflictError(
                    f"seq={seq} digest conflict for session={row.session_id}"
                )
            # 幂等重放：不重复落盘、不重复累计字节
            return AppendResult(
                decision=DUPLICATE,
                session_id=row.session_id,
                seq=seq,
                accepted_bytes=existing.size_bytes,
                received_bytes=row.received_bytes,
                next_expected_seq=row.next_expected_seq,
                duplicate=True,
            )
        if seq != row.next_expected_seq:
            raise ChunkOutOfOrderError(
                f"seq={seq} != next_expected_seq={row.next_expected_seq}"
            )
        if row.received_bytes + size > self._max_bytes:
            raise SizeLimitExceededError(
                f"received_bytes={row.received_bytes} + {size} > {self._max_bytes}"
            )
        try:
            staged_ref = self._store.write_stage(
                session_id=row.session_id, seq=seq, category=category, content=content
            )
        except StorageIoError as exc:
            self._mark_interrupted(row, now)
            return exc
        receipt = ChunkReceipt(
            session_id=row.session_id,
            seq=seq,
            category=category,
            size_bytes=size,
            digest=digest,
            staged_ref=staged_ref,
            status=ACCEPTED,
            accepted_at=now,
        )
        session.add(receipt)
        # ST-XFER-01/02 进度原子更新（同一会话事务）
        row.received_bytes += size
        row.next_expected_seq += 1
        row.version += 1
        row.updated_at = now
        return AppendResult(
            decision=ACCEPTED,
            session_id=row.session_id,
            seq=seq,
            accepted_bytes=size,
            received_bytes=row.received_bytes,
            next_expected_seq=row.next_expected_seq,
        )

    # ---- IC-SI-01.finalize（XFER-FINALIZE） ----

    def finalize(self, *, session_id: str, attempt_id: str | None = None) -> FinalizeResult:
        """合并完成：检查无缺口/总量/白名单 → 持久化尝试 → promote_to_final → merged。

        已 merged 重复调用返回同一 material_refs；同 attempt_id 幂等。
        存储失败：尝试记录 failed，会话置 interrupted_retryable 后可重试。
        """
        now = self._clock.now()
        storage_error: StorageIoError | None = None
        state_error: SessionStateError | None = None
        with self._session_factory() as session:
            row = self._must_find(session, session_id)
            if row.state == MERGED:
                # finalize 幂等：返回首次 material_refs，不产生不同正式引用
                return FinalizeResult(
                    session_id=session_id,
                    state=MERGED,
                    attempt_id=self._last_attempt_id(session, session_id) or (attempt_id or ""),
                    material_refs=tuple(row.material_refs or ()),
                    idempotent=True,
                )
            try:
                # 惰性终态转换（TTL/重试窗口）需先提交再抛出，故捕获后置后 raise
                self._check_ttl(row, now)
                self._check_writable(row, now)
            except SessionStateError as exc:
                state_error = exc
            else:
                attempt_id = attempt_id or uuidlib.uuid4().hex
                prior = session.get(FinalizeAttempt, attempt_id)
                if prior is not None:
                    if prior.session_id != session_id:
                        raise SessionStateError(
                            f"attempt_id={attempt_id} bound to another session"
                        )
                    if prior.merge_status == MERGED:
                        return FinalizeResult(
                            session_id=session_id,
                            state=row.state,
                            attempt_id=attempt_id,
                            material_refs=tuple(prior.material_refs or ()),
                            idempotent=True,
                        )

                receipts = self._ordered_receipts(session, session_id)
                self._check_no_gap(receipts)
                total = sum(r.size_bytes for r in receipts)
                if total > self._max_bytes:
                    raise SizeLimitExceededError(
                        f"total_size={total} > {self._max_bytes}"
                    )
                for r in receipts:
                    self._check_chunk_type(r.category, None)

                attempt = prior or FinalizeAttempt(
                    attempt_id=attempt_id,
                    session_id=session_id,
                    merge_status="started",
                    started_at=now,
                )
                attempt.check_result = {
                    "chunk_count": len(receipts),
                    "total_size": total,
                    "categories": sorted({r.category for r in receipts}),
                }
                session.add(attempt)
                session.flush()  # L2D-003：先持久化最终化检查点再调 SI-STORE

                try:
                    material_refs = list(
                        self._store.promote_to_final(
                            session_id=session_id,
                            staged_refs=[r.staged_ref for r in receipts],
                        )
                    )
                except StorageIoError as exc:
                    storage_error = exc
                    attempt.merge_status = "failed"
                    attempt.error_category = StorageIoError.code
                    attempt.completed_at = now
                    self._mark_interrupted(row, now)
                else:
                    attempt.merge_status = MERGED
                    attempt.material_refs = material_refs
                    attempt.completed_at = now
                    row.state = MERGED
                    row.material_refs = material_refs
                    row.version += 1
                    row.updated_at = now
                    result = FinalizeResult(
                        session_id=session_id,
                        state=MERGED,
                        attempt_id=attempt_id,
                        material_refs=tuple(material_refs),
                    )
        if state_error is not None:
            raise state_error
        if storage_error is not None:
            self._observe(
                "finalize", "interrupted",
                session_id=session_id, reason_category="STORAGE_IO_FAILED",
            )
            raise storage_error
        self._observe("finalize", "merged", session_id=session_id)
        return result

    # ---- TTL / 重试窗口扫描（LCD-006 实现参数注入） ----

    def sweep_expired(self) -> tuple[str, ...]:
        """把 TTL 过期或重试窗口耗尽的进行态会话置 failed_terminal，返回会话 id。

        终止发起暂存删除（幂等空操作）；不触碰 SI-CORE 的 Submission。
        """
        now = self._clock.now()
        transitioned: list[str] = []
        staged_refs: list[str] = []
        with self._session_factory() as session:
            rows = session.scalars(
                select(UploadSession).where(
                    UploadSession.state.in_([RECEIVING, INTERRUPTED_RETRYABLE])
                )
            ).all()
            for row in rows:
                expired = _as_utc(row.expires_at) <= now
                window_out = (
                    row.state == INTERRUPTED_RETRYABLE
                    and row.retry_deadline is not None
                    and _as_utc(row.retry_deadline) <= now
                )
                if not (expired or window_out):
                    continue
                row.state = FAILED_TERMINAL
                row.failure_reason = (
                    "session_ttl_expired" if expired else "retry_window_expired"
                )
                row.version += 1
                row.updated_at = now
                transitioned.append(row.session_id)
                staged_refs.extend(self._staged_refs(session, row.session_id))
        self._delete_staged(staged_refs)
        for sid in transitioned:
            self._observe(
                "sweep_expired", "failed_terminal",
                session_id=sid, reason_category="ttl_or_retry_window",
            )
        return tuple(transitioned)

    # ---- 内部 ----

    @staticmethod
    def _find_by_uuid(session: Session, submission_uuid: str) -> UploadSession | None:
        return session.scalars(
            select(UploadSession).where(UploadSession.submission_uuid == submission_uuid)
        ).first()

    @staticmethod
    def _must_find(session: Session, session_id: str) -> UploadSession:
        row = session.get(UploadSession, session_id)
        if row is None:
            raise SessionNotFoundError(f"unknown session_id: {session_id}")
        return row

    @staticmethod
    def _find_receipt(session: Session, session_id: str, seq: int) -> ChunkReceipt | None:
        return session.scalars(
            select(ChunkReceipt).where(
                ChunkReceipt.session_id == session_id, ChunkReceipt.seq == seq
            )
        ).first()

    @staticmethod
    def _ordered_receipts(session: Session, session_id: str) -> list[ChunkReceipt]:
        return list(
            session.scalars(
                select(ChunkReceipt)
                .where(ChunkReceipt.session_id == session_id)
                .order_by(ChunkReceipt.seq)
            ).all()
        )

    def _staged_refs(self, session: Session, session_id: str) -> list[str]:
        return [r.staged_ref for r in self._ordered_receipts(session, session_id)]

    @staticmethod
    def _last_attempt_id(session: Session, session_id: str) -> str | None:
        return session.scalars(
            select(FinalizeAttempt.attempt_id)
            .where(FinalizeAttempt.session_id == session_id)
            .order_by(FinalizeAttempt.started_at.desc())
        ).first()

    def _check_categories(self, categories: Sequence[str]) -> None:
        for c in categories:
            if c not in MATERIAL_CATEGORIES:
                raise TypeNotAllowedError(f"declared category not allowed: {c}")

    def _check_chunk_type(self, category: str, media_type: str | None) -> None:
        if category not in MATERIAL_CATEGORIES:
            raise TypeNotAllowedError(f"chunk category not allowed: {category}")
        if media_type is not None and media_type not in FILE_TYPE_WHITELIST:
            raise TypeNotAllowedError(f"media type not allowed: {media_type}")

    def _check_ttl(self, row: UploadSession, now: datetime) -> None:
        """惰性 TTL：过期会话先落 failed_terminal 再拒绝写入。"""
        if row.state in _TERMINAL_OR_READONLY:
            return
        if _as_utc(row.expires_at) <= now:
            row.state = FAILED_TERMINAL
            row.failure_reason = "session_ttl_expired"
            row.version += 1
            row.updated_at = now
            raise SessionStateError("session expired (TTL)")

    def _check_writable(self, row: UploadSession, now: datetime) -> None:
        if row.state in _TERMINAL_OR_READONLY:
            raise SessionStateError(f"session not writable in state={row.state}")
        if row.state == INTERRUPTED_RETRYABLE:
            if row.retry_deadline is not None and _as_utc(row.retry_deadline) <= now:
                row.state = FAILED_TERMINAL
                row.failure_reason = "retry_window_expired"
                row.version += 1
                row.updated_at = now
                raise SessionStateError("retry window expired")
            self._resume(row, now)

    def _resume_if_interrupted(self, row: UploadSession, now: datetime) -> None:
        if row.state != INTERRUPTED_RETRYABLE:
            return
        if _as_utc(row.expires_at) <= now:
            return  # 过期会话不恢复；写路径惰性终止
        if row.retry_deadline is not None and _as_utc(row.retry_deadline) <= now:
            return
        self._resume(row, now)

    @staticmethod
    def _resume(row: UploadSession, now: datetime) -> None:
        """ResumeUpload：interrupted_retryable → receiving（断点从 next_expected_seq 继续）。"""
        row.state = RECEIVING
        row.retry_deadline = None
        row.version += 1
        row.updated_at = now

    def _mark_interrupted(self, row: UploadSession, now: datetime) -> None:
        """UploadInterrupted：保留进度，置 interrupted_retryable 并设重试截止。"""
        row.state = INTERRUPTED_RETRYABLE
        row.retry_deadline = now + self._retry_window
        row.version += 1
        row.updated_at = now

    @staticmethod
    def _check_no_gap(receipts: Sequence[ChunkReceipt]) -> None:
        for expected, receipt in enumerate(receipts):
            if receipt.seq != expected:
                raise ChunkOutOfOrderError(
                    f"chunk manifest gap: expected seq={expected}, got {receipt.seq}"
                )

    def _delete_staged(self, staged_refs: Sequence[str]) -> None:
        """终止后暂存清理；delete 幂等，失败不阻塞业务结果（观测可诊断）。"""
        for ref in staged_refs:
            try:
                self._store.delete(ref)
            except StorageIoError:
                self._observe(
                    "cleanup", "delete_failed",
                    session_id="", reason_category="STORAGE_IO_FAILED",
                )

    def _observe(self, phase: str, result: str, **tags) -> None:
        """ST-XFER-04 TransferObservation：非阻塞，观测失败不得影响业务。"""
        if self._observer is None:
            return
        try:
            self._observer({"phase": phase, "result": result, **tags})
        except Exception:  # noqa: BLE001 — 观测不得阻塞业务（L2D-004）
            pass

    @staticmethod
    def _view(row: UploadSession) -> SessionView:
        return SessionView(
            session_id=row.session_id,
            submission_uuid=row.submission_uuid,
            state=row.state,
            received_bytes=row.received_bytes,
            next_expected_seq=row.next_expected_seq,
            declared_categories=tuple(row.declared_categories or ()),
            material_refs=tuple(row.material_refs or ()),
            failure_reason=row.failure_reason,
            expires_at=row.expires_at,
            retry_deadline=row.retry_deadline,
        )
