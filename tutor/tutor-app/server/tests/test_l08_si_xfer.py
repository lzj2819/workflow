"""L08 SI-XFER 单元测试（SQLite 内存库 + SI-STORE 端口 fake + 可注入时钟）。

覆盖 verification-checklist 语义断言：
- 建会话 → 追分片（乱序拒绝）→ 合并：checkpoint 只含已确认分片；重复分片幂等；
- 中断（STORAGE_IO_FAILED）→ interrupted_retryable 可恢复续传；failed_terminal 不可再写；
- 追加分片与合并两处 500MB 上限拒绝；材料类别/文件类型白名单拒绝；
- 合并前不产生正式材料引用（FakeStore 调用形状断言：write_stage/promote_to_final/delete）；
- finalize 幂等（重复调用同 material_refs；attempt_id 幂等；promote 只调一次）；
- 会话 TTL 过期与重试窗口耗尽（可注入时钟，惰性 + sweep 两路径）；
- 迁移文件可导入、revision/down_revision 正确。
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.xfer import (  # noqa: E402
    ACCEPTED,
    Base,
    ChunkDigestConflictError,
    ChunkOutOfOrderError,
    ChunkReceipt,
    FinalizeAttempt,
    SessionNotFoundError,
    SessionStateError,
    SizeLimitExceededError,
    StorageIoError,
    TypeNotAllowedError,
    UploadSession,
    UploadTransferService,
)


class FakeStore:
    """SI-STORE 端口 fake：记录调用形状；可注入写/提升失败。"""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.staged: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.fail_write_seqs: set[int] = set()
        self.fail_promote = False

    def write_stage(self, *, session_id, seq, category, content):
        self.calls.append(("write_stage", session_id, seq, category, len(content)))
        if seq in self.fail_write_seqs:
            raise StorageIoError("stage write failed")
        ref = f"staged/{session_id}/{seq}"
        self.staged[ref] = content
        return ref

    def promote_to_final(self, *, session_id, staged_refs):
        self.calls.append(("promote_to_final", session_id, tuple(staged_refs)))
        if self.fail_promote:
            raise StorageIoError("promote failed")
        return [f"final/{session_id}/{i}" for i, _ in enumerate(staged_refs)]

    def delete(self, material_ref):
        self.calls.append(("delete", material_ref))
        self.deleted.append(material_ref)


class MutableClock:
    def __init__(self) -> None:
        self.t = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.t

    def advance(self, **kwargs) -> None:
        self.t += timedelta(**kwargs)


def make_engine():
    # StaticPool：所有 Session 共享同一内存库连接
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


class SiXferTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        self.store = FakeStore()
        self.clock = MutableClock()
        self.service = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.eng.dispose()

    # ---- 辅助 ----

    def create(self, uuid="uuid-1", categories=("对话", "代码")):
        return self.service.create_session(
            submission_uuid=uuid, declared_categories=list(categories)
        )

    def session_row(self, session_id: str) -> UploadSession:
        with session_scope(self.eng) as s:
            row = s.get(UploadSession, session_id)
            s.expunge(row)
            return row

    def receipts(self, session_id: str) -> list[ChunkReceipt]:
        with session_scope(self.eng) as s:
            rows = s.scalars(
                sa.select(ChunkReceipt)
                .where(ChunkReceipt.session_id == session_id)
                .order_by(ChunkReceipt.seq)
            ).all()
            for r in rows:
                s.expunge(r)
            return list(rows)

    def attempts(self, session_id: str) -> list[FinalizeAttempt]:
        with session_scope(self.eng) as s:
            rows = s.scalars(
                sa.select(FinalizeAttempt).where(FinalizeAttempt.session_id == session_id)
            ).all()
            for r in rows:
                s.expunge(r)
            return list(rows)

    def promote_calls(self) -> list[tuple]:
        return [c for c in self.store.calls if c[0] == "promote_to_final"]

    def write_calls(self) -> list[tuple]:
        return [c for c in self.store.calls if c[0] == "write_stage"]


class CreateSessionTests(SiXferTestCase):
    def test_create_session_idempotent_by_submission_uuid(self):
        first = self.create()
        second = self.create()
        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(second.state, "receiving")
        self.assertEqual(second.next_expected_seq, 0)
        with session_scope(self.eng) as s:
            count = s.scalar(sa.select(sa.func.count()).select_from(UploadSession))
        self.assertEqual(count, 1)

    def test_create_session_rejects_category_outside_whitelist(self):
        with self.assertRaises(TypeNotAllowedError) as ctx:
            self.create(categories=("对话", "视频"))
        self.assertEqual(ctx.exception.code, "TYPE_NOT_ALLOWED")

    def test_get_session_unknown_uuid_raises(self):
        with self.assertRaises(SessionNotFoundError) as ctx:
            self.service.get_session(submission_uuid="nobody")
        self.assertEqual(ctx.exception.code, "SESSION_NOT_FOUND")


class AppendChunkTests(SiXferTestCase):
    def test_out_of_order_rejected_then_ordered_flow_merges(self):
        view = self.create()
        sid = view.session_id
        # 乱序：seq=1 先于 seq=0 → CHUNK_OUT_OF_ORDER，不写暂存/收据
        with self.assertRaises(ChunkOutOfOrderError) as ctx:
            self.service.append_chunk(
                session_id=sid, seq=1, category="对话", content=b"chunk-1"
            )
        self.assertEqual(ctx.exception.code, "CHUNK_OUT_OF_ORDER")
        self.assertEqual(self.receipts(sid), [])
        self.assertEqual(self.write_calls(), [])

        r0 = self.service.append_chunk(
            session_id=sid, seq=0, category="对话", content=b"chunk-0"
        )
        r1 = self.service.append_chunk(
            session_id=sid, seq=1, category="代码", content=b"chunk-1"
        )
        self.assertEqual((r0.decision, r1.decision), (ACCEPTED, ACCEPTED))
        self.assertEqual(r1.next_expected_seq, 2)
        # checkpoint 只含已确认分片
        progress = self.service.get_session(submission_uuid="uuid-1")
        self.assertEqual(progress.received_bytes, len(b"chunk-0") + len(b"chunk-1"))
        self.assertEqual(progress.next_expected_seq, 2)
        self.assertEqual(len(self.receipts(sid)), 2)

        result = self.service.finalize(session_id=sid)
        self.assertEqual(result.state, "merged")
        self.assertEqual(len(result.material_refs), 2)
        self.assertEqual(self.session_row(sid).state, "merged")

    def test_duplicate_chunk_idempotent_same_digest(self):
        sid = self.create().session_id
        content = b"payload"
        first = self.service.append_chunk(
            session_id=sid, seq=0, category="对话", content=content
        )
        second = self.service.append_chunk(
            session_id=sid, seq=0, category="对话", content=content
        )
        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(second.decision, "duplicate")
        # 不重复落盘、不重复累计字节
        self.assertEqual(len(self.write_calls()), 1)
        self.assertEqual(len(self.receipts(sid)), 1)
        row = self.session_row(sid)
        self.assertEqual(row.received_bytes, len(content))
        self.assertEqual(row.next_expected_seq, 1)

    def test_same_seq_different_digest_conflicts(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"a")
        with self.assertRaises(ChunkDigestConflictError) as ctx:
            self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"b")
        self.assertEqual(ctx.exception.code, "CHUNK_DIGEST_CONFLICT")
        # 冲突不覆盖原分片
        receipts = self.receipts(sid)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].size_bytes, 1)

    def test_append_unknown_session_raises(self):
        with self.assertRaises(SessionNotFoundError):
            self.service.append_chunk(
                session_id="missing", seq=0, category="对话", content=b"x"
            )

    def test_media_type_whitelist(self):
        sid = self.create().session_id
        ok = self.service.append_chunk(
            session_id=sid, seq=0, category="对话", content=b"x", media_type="文本"
        )
        self.assertEqual(ok.decision, ACCEPTED)
        with self.assertRaises(TypeNotAllowedError) as ctx:
            self.service.append_chunk(
                session_id=sid, seq=1, category="对话", content=b"y", media_type="可执行文件"
            )
        self.assertEqual(ctx.exception.code, "TYPE_NOT_ALLOWED")

    def test_chunk_category_outside_enum_rejected(self):
        sid = self.create().session_id
        with self.assertRaises(TypeNotAllowedError):
            self.service.append_chunk(
                session_id=sid, seq=0, category="视频", content=b"x"
            )

    def test_size_limit_checked_on_every_append(self):
        service = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            clock=self.clock,
            max_bytes=100,
        )
        sid = service.create_session(
            submission_uuid="uuid-1", declared_categories=["对话"]
        ).session_id
        service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x" * 60)
        with self.assertRaises(SizeLimitExceededError) as ctx:
            service.append_chunk(session_id=sid, seq=1, category="对话", content=b"x" * 50)
        self.assertEqual(ctx.exception.code, "SIZE_LIMIT_EXCEEDED")
        # rejected 不写收据、不改状态，会话可继续
        self.assertEqual(len(self.receipts(sid)), 1)
        row = self.session_row(sid)
        self.assertEqual(row.state, "receiving")
        self.assertEqual(row.received_bytes, 60)
        # 小分片仍可接受
        service.append_chunk(session_id=sid, seq=1, category="对话", content=b"x" * 40)

    def test_observer_failure_does_not_block_business(self):
        def bad_observer(event):
            raise RuntimeError("monitor down")

        service = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            clock=self.clock,
            observer=bad_observer,
        )
        sid = service.create_session(
            submission_uuid="uuid-1", declared_categories=["对话"]
        ).session_id
        result = service.append_chunk(
            session_id=sid, seq=0, category="对话", content=b"x"
        )
        self.assertEqual(result.decision, ACCEPTED)


class InterruptResumeTests(SiXferTestCase):
    def test_storage_failure_marks_interrupted_retryable_and_resumes(self):
        sid = self.create().session_id
        self.store.fail_write_seqs.add(0)
        with self.assertRaises(StorageIoError) as ctx:
            self.service.append_chunk(
                session_id=sid, seq=0, category="对话", content=b"x"
            )
        self.assertEqual(ctx.exception.code, "STORAGE_IO_FAILED")
        row = self.session_row(sid)
        self.assertEqual(row.state, "interrupted_retryable")
        self.assertIsNotNone(row.retry_deadline)
        self.assertEqual(row.next_expected_seq, 0)  # 进度保留，断点续传
        self.assertEqual(self.receipts(sid), [])

        # 恢复：同 submission_uuid 重建会话（ResumeUpload），从 next_expected_seq 继续
        self.store.fail_write_seqs.clear()
        resumed = self.create()
        self.assertEqual(resumed.state, "receiving")
        self.assertEqual(resumed.session_id, sid)
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")
        result = self.service.finalize(session_id=sid)
        self.assertEqual(result.state, "merged")

    def test_retry_window_expiry_goes_failed_terminal(self):
        sid = self.create().session_id
        self.store.fail_write_seqs.add(0)
        with self.assertRaises(StorageIoError):
            self.service.append_chunk(
                session_id=sid, seq=0, category="对话", content=b"x"
            )
        self.store.fail_write_seqs.clear()
        self.clock.advance(minutes=31)  # retry_window=30min，TTL=24h 未过期
        with self.assertRaises(SessionStateError):
            self.service.append_chunk(
                session_id=sid, seq=0, category="对话", content=b"x"
            )
        row = self.session_row(sid)
        self.assertEqual(row.state, "failed_terminal")
        self.assertEqual(row.failure_reason, "retry_window_expired")


class FailedTerminalTests(SiXferTestCase):
    def test_failed_terminal_not_writable(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")
        view = self.service.abort(session_id=sid, reason="user cancel")
        self.assertEqual(view.state, "failed_terminal")
        self.assertEqual(view.failure_reason, "aborted: user cancel")

        with self.assertRaises(SessionStateError):
            self.service.append_chunk(
                session_id=sid, seq=1, category="对话", content=b"y"
            )
        with self.assertRaises(SessionStateError):
            self.service.finalize(session_id=sid)
        # 终态不可逆
        self.assertEqual(self.session_row(sid).state, "failed_terminal")

    def test_abort_idempotent_and_deletes_staged_refs(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"a")
        self.service.append_chunk(session_id=sid, seq=1, category="代码", content=b"b")
        self.service.abort(session_id=sid)
        staged = {ref for ref in self.store.staged}
        self.assertEqual(set(self.store.deleted), staged)
        # 重复 abort 幂等：不再发起删除
        again = self.service.abort(session_id=sid)
        self.assertEqual(again.state, "failed_terminal")
        self.assertEqual(len(self.store.deleted), 2)

    def test_abort_merged_session_rejected(self):
        sid = self.create().session_id
        self.service.finalize(session_id=sid)
        with self.assertRaises(SessionStateError):
            self.service.abort(session_id=sid)


class FinalizeTests(SiXferTestCase):
    def test_no_formal_material_refs_before_merge(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"abc")
        # 合并前只有 write_stage，未调用 promote_to_final
        self.assertEqual(self.promote_calls(), [])
        self.assertEqual(self.session_row(sid).material_refs, None)
        # write_stage 调用形状：(session_id, seq, category, size)
        self.assertEqual(
            self.write_calls(), [("write_stage", sid, 0, "对话", 3)]
        )
        result = self.service.finalize(session_id=sid)
        self.assertEqual(
            self.promote_calls(),
            [("promote_to_final", sid, (f"staged/{sid}/0",))],
        )
        self.assertEqual(result.material_refs, (f"final/{sid}/0",))

    def test_finalize_idempotent_returns_same_refs(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")
        first = self.service.finalize(session_id=sid, attempt_id="att-1")
        second = self.service.finalize(session_id=sid, attempt_id="att-2")
        self.assertFalse(first.idempotent)
        self.assertTrue(second.idempotent)
        self.assertEqual(first.material_refs, second.material_refs)
        # 不重复 promote 产生不同正式引用
        self.assertEqual(len(self.promote_calls()), 1)
        third = self.service.finalize(session_id=sid, attempt_id="att-1")
        self.assertTrue(third.idempotent)
        self.assertEqual(third.material_refs, first.material_refs)

    def test_finalize_total_size_limit(self):
        big = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            clock=self.clock,
            max_bytes=10**6,
        )
        sid = big.create_session(
            submission_uuid="uuid-1", declared_categories=["对话"]
        ).session_id
        big.append_chunk(session_id=sid, seq=0, category="对话", content=b"x" * 80)
        big.append_chunk(session_id=sid, seq=1, category="对话", content=b"x" * 80)
        small = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            clock=self.clock,
            max_bytes=100,
        )
        with self.assertRaises(SizeLimitExceededError):
            small.finalize(session_id=sid)
        self.assertEqual(self.session_row(sid).state, "receiving")
        self.assertEqual(self.promote_calls(), [])

    def test_finalize_storage_failure_recoverable(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")
        self.store.fail_promote = True
        with self.assertRaises(StorageIoError):
            self.service.finalize(session_id=sid, attempt_id="att-1")
        row = self.session_row(sid)
        self.assertEqual(row.state, "interrupted_retryable")
        attempts = self.attempts(sid)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].merge_status, "failed")
        self.assertEqual(attempts[0].error_category, "STORAGE_IO_FAILED")
        # 重试窗口内恢复并成功合并
        self.store.fail_promote = False
        result = self.service.finalize(session_id=sid, attempt_id="att-2")
        self.assertEqual(result.state, "merged")
        self.assertEqual(len(result.material_refs), 1)

    def test_finalize_persists_attempt_before_promote(self):
        # promote 期间检查点已持久化（L2D-003）：fake 在 promote 内读库验证
        service = self.service
        sid = service.create_session(
            submission_uuid="uuid-1", declared_categories=["对话"]
        ).session_id
        service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")

        seen = {}
        original_promote = self.store.promote_to_final

        def checking_promote(*, session_id, staged_refs):
            with session_scope(self.eng) as s:
                row = s.get(FinalizeAttempt, "att-ckpt")
                seen["merge_status"] = row.merge_status if row else None
            return original_promote(session_id=session_id, staged_refs=staged_refs)

        self.store.promote_to_final = checking_promote  # type: ignore[method-assign]
        service.finalize(session_id=sid, attempt_id="att-ckpt")
        self.assertEqual(seen["merge_status"], "started")

    def test_mark_pending_verification(self):
        sid = self.create().session_id
        with self.assertRaises(SessionStateError):
            self.service.mark_pending_verification(session_id=sid)
        self.service.finalize(session_id=sid)
        view = self.service.mark_pending_verification(session_id=sid)
        self.assertEqual(view.state, "pending_verification")
        # pending_verification 不可再写
        with self.assertRaises(SessionStateError):
            self.service.append_chunk(
                session_id=sid, seq=0, category="对话", content=b"x"
            )
        # 幂等
        again = self.service.mark_pending_verification(session_id=sid)
        self.assertEqual(again.state, "pending_verification")


class TtlTests(SiXferTestCase):
    def test_ttl_expired_session_lazy_terminal(self):
        sid = self.create().session_id
        self.service.append_chunk(session_id=sid, seq=0, category="对话", content=b"x")
        self.clock.advance(hours=25)  # session_ttl=24h
        with self.assertRaises(SessionStateError):
            self.service.append_chunk(
                session_id=sid, seq=1, category="对话", content=b"y"
            )
        row = self.session_row(sid)
        self.assertEqual(row.state, "failed_terminal")
        self.assertEqual(row.failure_reason, "session_ttl_expired")

    def test_sweep_expired_sessions(self):
        sid1 = self.create(uuid="uuid-1").session_id
        sid2 = self.create(uuid="uuid-2").session_id
        self.service.append_chunk(session_id=sid1, seq=0, category="对话", content=b"x")
        self.clock.advance(hours=25)
        transitioned = self.service.sweep_expired()
        self.assertEqual(set(transitioned), {sid1, sid2})
        self.assertEqual(self.session_row(sid1).state, "failed_terminal")
        # 终止发起暂存清理
        self.assertEqual(self.store.deleted, [f"staged/{sid1}/0"])
        # merged 会话不受影响
        self.clock.t = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
        sid3 = self.create(uuid="uuid-3").session_id
        self.service.finalize(session_id=sid3)
        self.clock.advance(hours=25)
        self.assertEqual(self.service.sweep_expired(), ())
        self.assertEqual(self.session_row(sid3).state, "merged")


class MigrationTests(unittest.TestCase):
    def test_migration_importable_with_correct_revisions(self):
        path = ROOT / "server" / "migrations" / "versions" / "0005_upload_sessions.py"
        spec = importlib.util.spec_from_file_location("mig_0005", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0005_upload_sessions")
        self.assertEqual(module.down_revision, "9c99fa53f9f8")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
