"""T-B01b SI-RELAY 单元测试（SQLite 文件库 + 内存 handler spy）。

覆盖任务卡语义断言：
- 同事务语义（KD-002）：enqueue 后 session 未提交对其他连接不可见、提交后
  可见、回滚全消；
- fetch_due 认领互斥：已认领（delivering）记录不被再次认领，limit 生效；
- retry 退避推进：mark_retry 按 default_backoff 推进 next_attempt_at，
  到期前不可见、到期后重投；
- 确认后不再投递：relayer 确认的记录后续轮询不再交给 handler；
- 入站重复事件不重复应用：首次 applied 后重复投递跳过且不推进去重记录；
- 可重试失败进 retry_wait 交还重投；不可解析进 quarantined 且不阻塞后续
  合法事件；
- 投递器结构化日志不含 payload 内容（仅 id/contract/attempts/错误类型）；
- 迁移文件可导入、revision/down_revision 正确。
"""
from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from course_app.submission_intake.relay import (  # noqa: E402
    Base as RelayBase,
    DedupOutcome,
    InboundDedup,
    InboundDedupRecord,
    OutboxRelayer,
    QuarantineError,
)
from tutor_shared.outbox import (  # noqa: E402
    OUTBOX_METADATA,
    OUTBOX_RECORDS_TABLE,
    OutboxRecord,
    SqlaOutboxStore,
)

MIGRATION = ROOT / "server" / "migrations" / "versions" / "0010_outbox.py"

# 动态 NOW：enqueue 以真实时钟写 next_attempt_at；取运行时 +1h 保证 due 语义稳定
NOW = datetime.now(timezone.utc) + timedelta(hours=1)


class RelayTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = sa.create_engine(f"sqlite:///{Path(self._tmp.name) / 't.db'}")
        OUTBOX_METADATA.create_all(self.engine)
        RelayBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmp.cleanup()

    def _count_outbox(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count()).select_from(OUTBOX_RECORDS_TABLE)
            ).scalar_one()

    def _enqueue(self, contract_id="CT-004", payload=None, dedup_key="sub-1"):
        """以独立事务写入一条 outbox 记录（模拟业务方提交后）。"""
        with self.Session() as session:
            store = SqlaOutboxStore(session)
            record = store.enqueue(contract_id, payload or {"k": "v"}, dedup_key)
            session.commit()
        return record


class TestSqlaOutboxStoreTx(RelayTestBase):
    def test_enqueue_same_tx_visibility_and_rollback(self):
        session = self.Session()
        store = SqlaOutboxStore(session)
        store.enqueue("CT-004", {"submission_id": "sub-1"}, "sub-1")
        # 未提交：另一连接不可见
        self.assertEqual(self._count_outbox(), 0)
        session.commit()
        # 提交后：可见
        self.assertEqual(self._count_outbox(), 1)
        # 再入队后回滚：全消
        store.enqueue("CT-006", {"submission_id": "sub-2"}, "sub-2")
        session.rollback()
        self.assertEqual(self._count_outbox(), 1)
        session.close()

    def test_enqueue_returns_pending_record(self):
        record = self._enqueue()
        self.assertGreaterEqual(record.record_id, 1)
        self.assertEqual(record.status, "pending")
        self.assertEqual(record.attempts, 0)
        self.assertEqual(record.contract_id, "CT-004")
        self.assertEqual(record.dedup_key, "sub-1")


class TestFetchDue(RelayTestBase):
    def test_claim_is_exclusive_and_ordered(self):
        r1 = self._enqueue(dedup_key="a")
        r2 = self._enqueue(contract_id="CT-006", dedup_key="b")
        r3 = self._enqueue(contract_id="CT-014", dedup_key="c")
        with self.Session() as s1:
            claimed = SqlaOutboxStore(s1).fetch_due(NOW, limit=2)
            s1.commit()
        self.assertEqual([r.record_id for r in claimed], [r1.record_id, r2.record_id])
        self.assertTrue(all(r.status == "delivering" for r in claimed))
        self.assertTrue(all(r.attempts == 1 for r in claimed))
        with self.Session() as s2:
            rest = SqlaOutboxStore(s2).fetch_due(NOW, limit=50)
            s2.commit()
        # 已认领记录不会被再次认领（认领互斥）
        self.assertEqual([r.record_id for r in rest], [r3.record_id])
        with self.Session() as s3:
            self.assertEqual(SqlaOutboxStore(s3).fetch_due(NOW), [])

    def test_retry_backoff_defers_next_attempt(self):
        record = self._enqueue()
        with self.Session() as session:
            store = SqlaOutboxStore(session)
            claimed = store.fetch_due(NOW)
            session.commit()
        self.assertEqual(len(claimed), 1)
        with self.Session() as session:
            store = SqlaOutboxStore(session)
            # 不指定时间 → default_backoff(attempts=1) = 1s（锚定真实时钟）
            store.mark_retry(record.record_id)
            session.commit()
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(OUTBOX_RECORDS_TABLE).where(
                    OUTBOX_RECORDS_TABLE.c.id == record.record_id
                )
            ).mappings().one()
        self.assertEqual(row["status"], "retry_wait")
        next_attempt = row["next_attempt_at"].replace(tzinfo=timezone.utc)
        with self.Session() as session:
            # 到期前不可见
            self.assertEqual(
                SqlaOutboxStore(session).fetch_due(
                    next_attempt - timedelta(milliseconds=1)
                ),
                [],
            )
        with self.Session() as session:
            # 到期后重投，attempts 递增
            redelivered = SqlaOutboxStore(session).fetch_due(next_attempt)
            session.commit()
        self.assertEqual(len(redelivered), 1)
        self.assertEqual(redelivered[0].attempts, 2)
        self.assertEqual(redelivered[0].status, "delivering")

    def test_mark_retry_explicit_next_attempt(self):
        record = self._enqueue()
        later = NOW + timedelta(minutes=5)
        with self.Session() as session:
            store = SqlaOutboxStore(session)
            store.fetch_due(NOW)
            store.mark_retry(record.record_id, next_attempt_at=later)
            session.commit()
        with self.Session() as session:
            self.assertEqual(
                SqlaOutboxStore(session).fetch_due(NOW + timedelta(minutes=4)), []
            )
            self.assertEqual(len(SqlaOutboxStore(session).fetch_due(later)), 1)

    def test_mark_confirmed_excludes_record(self):
        record = self._enqueue()
        with self.Session() as session:
            store = SqlaOutboxStore(session)
            store.fetch_due(NOW)
            store.mark_confirmed(record.record_id)
            session.commit()
        with self.Session() as session:
            self.assertEqual(SqlaOutboxStore(session).fetch_due(NOW), [])


class _Spy:
    """内存 handler spy：记录收到的 record_id，可按需失败。"""

    def __init__(self, fail_times: int = 0):
        self.calls: list[int] = []
        self.payloads: list[dict] = []
        self._fail_times = fail_times

    def __call__(self, record: OutboxRecord) -> None:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("transient downstream error")
        self.calls.append(record.record_id)
        self.payloads.append(record.payload)


class TestOutboxRelayer(RelayTestBase):
    def _relayer(self, spy: _Spy) -> OutboxRelayer:
        return OutboxRelayer(
            self.Session,
            {"CT-004": spy},
            poll_interval=0.01,
            batch_size=50,
            clock=lambda: NOW,
        )

    def test_confirm_then_never_redelivered(self):
        record = self._enqueue(payload={"submission_id": "sub-1"})
        spy = _Spy()
        relayer = self._relayer(spy)
        counts = relayer.poll_once()
        self.assertEqual(counts, {"claimed": 1, "confirmed": 1, "retry": 0})
        self.assertEqual(spy.calls, [record.record_id])
        # 确认后后续轮询不再投递
        self.assertEqual(relayer.poll_once(), {"claimed": 0, "confirmed": 0, "retry": 0})
        self.assertEqual(len(spy.calls), 1)

    def test_failure_retries_until_confirmed(self):
        record = self._enqueue()
        spy = _Spy(fail_times=1)
        relayer = self._relayer(spy)
        first = relayer.poll_once()
        self.assertEqual((first["confirmed"], first["retry"]), (0, 1))
        self.assertEqual(spy.calls, [])
        # retry_wait 到期后重投成功 → confirmed（退避锚定真实时钟）
        second = relayer.poll_once(
            now=datetime.now(timezone.utc) + timedelta(seconds=2)
        )
        self.assertEqual((second["confirmed"], second["retry"]), (1, 0))
        self.assertEqual(spy.calls, [record.record_id])

    def test_unknown_contract_goes_retry(self):
        self._enqueue(contract_id="CT-999")
        relayer = OutboxRelayer(self.Session, {}, clock=lambda: NOW)
        counts = relayer.poll_once()
        self.assertEqual(counts["retry"], 1)

    def test_logs_exclude_payload(self):
        secret = "SECRET-PAYLOAD-学生姓名"
        self._enqueue(payload={"student": secret})
        spy = _Spy(fail_times=1)
        records: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, rec: logging.LogRecord) -> None:
                records.append(rec)

        log = logging.getLogger("tutor.si_relay.test_b01b")
        log.addHandler(_Capture())
        log.setLevel(logging.INFO)
        log.propagate = False
        relayer = OutboxRelayer(
            self.Session, {"CT-004": spy}, clock=lambda: NOW, log=log
        )
        relayer.poll_once()
        self.assertTrue(records)
        for rec in records:
            blob = rec.getMessage() + repr(
                {k: v for k, v in rec.__dict__.items() if k not in logging.makeLogRecord({}).__dict__}
            )
            self.assertNotIn(secret, blob)
            self.assertNotIn("transient downstream error", blob)
        retry_rec = records[0]
        self.assertEqual(retry_rec.contract_id, "CT-004")
        self.assertEqual(retry_rec.attempts, 1)
        self.assertEqual(retry_rec.error_type, "RuntimeError")
        self.assertGreaterEqual(retry_rec.outbox_id, 1)


class TestInboundDedup(RelayTestBase):
    def test_duplicate_not_reapplied_and_state_not_advanced(self):
        applied: list[str] = []
        with self.Session() as session:
            dedup = InboundDedup(session, clock=lambda: NOW)
            first = dedup.handle("ct005:sub-1:scored", "CT-005", lambda: applied.append("x"))
            session.commit()
        self.assertEqual(first, DedupOutcome.APPLIED)
        with self.Session() as session:
            dedup = InboundDedup(session, clock=lambda: NOW)
            second = dedup.handle("ct005:sub-1:scored", "CT-005", lambda: applied.append("x"))
            row = session.get(InboundDedupRecord, "ct005:sub-1:scored")
        self.assertEqual(second, DedupOutcome.DUPLICATE)
        self.assertEqual(applied, ["x"])  # 不重复应用
        # 去重记录不推进（终态 applied、attempts 不变）
        self.assertEqual(row.status, "applied")
        self.assertEqual(row.attempts, 1)

    def test_retryable_failure_then_success(self):
        applied: list[str] = []

        def flaky() -> None:
            if not applied:
                raise ValueError("downstream not ready")
            applied.append("x")

        with self.Session() as session:
            outcome = InboundDedup(session, clock=lambda: NOW).handle(
                "ct012:batch-1:hash", "CT-012", flaky
            )
            session.commit()
        self.assertEqual(outcome, DedupOutcome.RETRY)
        with self.Session() as session:
            row = session.get(InboundDedupRecord, "ct012:batch-1:hash")
            self.assertEqual(row.status, "retry_wait")
            self.assertEqual(row.attempts, 1)
            self.assertIn("ValueError", row.last_error)
        # 交还重投：retry_wait 记录可再次处理直至 applied
        with self.Session() as session:
            applied.append("x")  # 使 flaky 成功
            outcome = InboundDedup(session, clock=lambda: NOW).handle(
                "ct012:batch-1:hash", "CT-012", flaky
            )
            row = session.get(InboundDedupRecord, "ct012:batch-1:hash")
            session.commit()
        self.assertEqual(outcome, DedupOutcome.APPLIED)
        self.assertEqual(row.status, "applied")
        self.assertEqual(row.attempts, 2)

    def test_quarantine_path_does_not_block_others(self):
        calls: list[str] = []

        def bad() -> None:
            raise QuarantineError("schema invalid: missing submission_id")

        with self.Session() as session:
            dedup = InboundDedup(session, clock=lambda: NOW)
            outcome = dedup.handle("ct005:bad", "CT-005", bad)
            session.commit()
        self.assertEqual(outcome, DedupOutcome.QUARANTINED)
        with self.Session() as session:
            # quarantined 重投不再应用、不改变终态
            again = InboundDedup(session, clock=lambda: NOW).handle(
                "ct005:bad", "CT-005", lambda: calls.append("bad")
            )
            row = session.get(InboundDedupRecord, "ct005:bad")
        self.assertEqual(again, DedupOutcome.DUPLICATE)
        self.assertEqual(calls, [])
        self.assertEqual(row.status, "quarantined")
        self.assertIn("schema invalid", row.last_error)
        # quarantined 不阻塞后续合法事件
        with self.Session() as session:
            ok = InboundDedup(session, clock=lambda: NOW).handle(
                "ct005:sub-2:scored", "CT-005", lambda: calls.append("ok")
            )
            session.commit()
        self.assertEqual(ok, DedupOutcome.APPLIED)
        self.assertEqual(calls, ["ok"])

    def test_dedup_and_business_share_caller_transaction(self):
        # 去重记录与业务写入同一事务：回滚则全消
        session = self.Session()
        session.execute(
            OUTBOX_RECORDS_TABLE.insert().values(
                contract_id="CT-014",
                payload={"batch_id": "b-1"},
                dedup_key="b-1",
                status="pending",
                attempts=0,
                next_attempt_at=NOW.replace(tzinfo=None),
                created_at=NOW.replace(tzinfo=None),
            )
        )
        InboundDedup(session, clock=lambda: NOW).handle(
            "ct012:b-1:hash", "CT-012", lambda: None
        )
        session.rollback()
        self.assertEqual(self._count_outbox(), 0)
        with self.Session() as check:
            self.assertIsNone(check.get(InboundDedupRecord, "ct012:b-1:hash"))
        session.close()


class TestMigration(unittest.TestCase):
    def test_migration_importable_with_correct_linkage(self):
        spec = importlib.util.spec_from_file_location("migration_0010", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0010_outbox")
        self.assertEqual(module.down_revision, "11a22f91f4b3")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
