"""T-B01c SI-PURGE 单元测试（SQLite 内存库 + tmp 磁盘 DATA_DIR + 内存 Outbox）。

覆盖任务卡语义断言：
- 全部成功：磁盘材料删除、MaterialFile 登记 deleted、配额扣减、提交记录终态
  deleted（经 L02 query 验证不可再读为存续状态）、ST-07 批次/逐项登记 completed；
- CT-014 载荷与 contracts/ct-014.json 一致（jsonschema 校验 + 字段全集 +
  dedup_key=batch_id+purged_at + v=1）；
- 部分失败：未知 submission_id 记入 failed_items（含原因），不阻塞其他项，
  批次登记 partial、失败项保留；
- 重跑：失败项（模拟 SI-STORE IO 暂态故障）重跑成功，登记更新（run_count 递增、
  result 转 purged、reason 清空、批次转 completed），并新发 CT-014；
- 幂等：重复 CT-012（同 batch_id）对已删项为空操作（Submission.version 不变、
  材料登记保持 deleted），逐项仍计 purged 回传；
- 契约校验：缺字段/多余字段/v≠1/空 submission_id 均拒绝且无副作用（无登记、
  无 Outbox 行）；
- SQL Outbox 工厂路径：CT-014 行与 PurgeExecution 登记同事务提交（KD-002）。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import jsonschema  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core.models import (  # noqa: E402
    Base as CoreBase,
    Submission,
    SubmissionMaterial,
)
from course_app.submission_intake.core.service import (  # noqa: E402
    SubmissionCoreService,
)
from course_app.submission_intake.purge import (  # noqa: E402
    Base as PurgeBase,
    PurgeExecutionItemRow,
    PurgeExecutionRow,
    PurgeExecutor,
    PurgeValidationError,
)
from course_app.submission_intake.store import (  # noqa: E402
    Base as StoreBase,
    CourseQuotaUsage,
    FilesystemMaterialStore,
    MaterialFile,
    STATE_DELETED,
    StorageIoError,
)
from course_app.submission_intake.xfer.models import (  # noqa: E402
    Base as XferBase,
    UploadSession,
)
from tutor_shared.outbox import (  # noqa: E402
    OUTBOX_METADATA,
    OUTBOX_RECORDS_TABLE,
    InMemoryOutboxStore,
    SqlaOutboxStore,
)

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
PURGED_AT = datetime(2026, 7, 21, 13, 0, 0, tzinfo=timezone.utc)

CT014_SCHEMA = json.loads((ROOT / "contracts" / "ct-014.json").read_text(encoding="utf-8"))[
    "schemas"
]["event"]


def make_engine():
    # StaticPool：所有 Session 共享同一内存库连接
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    XferBase.metadata.create_all(eng)
    CoreBase.metadata.create_all(eng)
    StoreBase.metadata.create_all(eng)
    PurgeBase.metadata.create_all(eng)
    return eng


def ct012_payload(batch_id="batch-1", ids=("sub-1",)):
    return {
        "batch_id": batch_id,
        "submission_ids": list(ids),
        "scope": "submission",
        "operator": "retention-worker",
        "executed_at": NOW.isoformat(),
        "audit_record_id": "audit-1",
        "v": 1,
    }


class FlakyDeleteStore:
    """MaterialStorePort 包装：对指定 ref 首次 delete 抛 StorageIoError（模拟暂态故障）。"""

    def __init__(self, inner, fail_refs):
        self._inner = inner
        self._fail = set(fail_refs)

    def delete(self, material_ref: str) -> None:
        if material_ref in self._fail:
            self._fail.discard(material_ref)
            raise StorageIoError("simulated transient io failure")
        return self._inner.delete(material_ref)

    def read_metadata(self, material_ref: str):
        return self._inner.read_metadata(material_ref)


class PurgeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        self.eng = make_engine()
        self.addCleanup(self.eng.dispose)
        self.outbox = InMemoryOutboxStore()
        self.store = FilesystemMaterialStore(
            session_factory=partial(session_scope, self.eng),
            data_dir=self.data_dir,
            clock=lambda: NOW,
        )
        self.core = SubmissionCoreService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            metadata_reader=self.store,
        )
        self.executor = PurgeExecutor(
            session_factory=partial(session_scope, self.eng),
            core_service=self.core,
            material_store=self.store,
            outbox_store=self.outbox,
            clock=lambda: PURGED_AT,
        )

    # ---- 辅助 ----

    def make_submission(self, sid="sub-1", uuid=None, course_id="course-1", files=(("对话", b"dialog-1"),)):
        """造一份 received 提交：UploadSession + Submission + 正式材料（磁盘+登记+清单）。"""
        uuid = uuid or f"uuid-{sid}"
        session_id = f"sess-{sid}"
        with session_scope(self.eng) as s:
            s.add(
                UploadSession(
                    session_id=session_id,
                    submission_uuid=uuid,
                    declared_categories=[cat for cat, _ in files],
                    state="merged",
                    received_bytes=sum(len(c) for _, c in files),
                    next_expected_seq=len(files),
                    expires_at=NOW + timedelta(hours=24),
                    version=0,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            s.add(
                Submission(
                    submission_id=sid,
                    submission_uuid=uuid,
                    course_id=course_id,
                    assignment="hw1",
                    student_name="张三",
                    group_name="G1",
                    status="received",
                    version=0,
                    received_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        staged = [
            self.store.write_stage(session_id=session_id, seq=i, category=cat, content=content)
            for i, (cat, content) in enumerate(files)
        ]
        final_refs = list(self.store.promote_to_final(session_id=session_id, staged_refs=staged))
        with session_scope(self.eng) as s:
            for ref, (cat, content) in zip(final_refs, files):
                s.add(
                    SubmissionMaterial(
                        submission_id=sid,
                        material_ref=ref,
                        category=cat,
                        size_bytes=len(content),
                        declared=True,
                        filename=f"{cat}.bin",
                    )
                )
        return final_refs

    def material_row(self, ref):
        with session_scope(self.eng) as s:
            row = s.get(MaterialFile, ref)
            if row is not None:
                s.expunge(row)
            return row

    def submission_row(self, sid):
        with session_scope(self.eng) as s:
            row = s.get(Submission, sid)
            if row is not None:
                s.expunge(row)
            return row

    def batch_row(self, batch_id="batch-1"):
        with session_scope(self.eng) as s:
            row = s.get(PurgeExecutionRow, batch_id)
            if row is not None:
                s.expunge(row)
            return row

    def item_rows(self, batch_id="batch-1"):
        with session_scope(self.eng) as s:
            rows = (
                s.query(PurgeExecutionItemRow)
                .filter(PurgeExecutionItemRow.batch_id == batch_id)
                .order_by(PurgeExecutionItemRow.submission_id)
                .all()
            )
            for row in rows:
                s.expunge(row)
            return rows

    def drained_ct014(self):
        # 取数窗口基于运行时时钟（记录 next_attempt_at=真实入队时刻；固定日期会随时间失效）
        horizon = datetime.now(timezone.utc) + timedelta(days=1)
        return [
            r
            for r in self.outbox.fetch_due(horizon, limit=100)
            if r.contract_id == "CT-014"
        ]

    # ---- 全部成功 ----

    def test_execute_purges_materials_submission_and_reports(self):
        refs = self.make_submission(
            sid="sub-1", files=(("对话", b"dialog-1"), ("代码", b"code-1"))
        )
        for ref in refs:
            self.assertTrue((self.data_dir / self.material_row(ref).path).exists())

        report = self.executor.execute(ct012_payload(ids=("sub-1",)))

        # CT-014 回传：全部成功，failed_items 为空数组
        self.assertEqual(report.purged_submission_ids, ("sub-1",))
        self.assertEqual(report.failed_items, ())
        self.assertEqual(report.purged_at, PURGED_AT)
        # 磁盘文件删除、登记转 deleted、配额扣减
        for ref in refs:
            row = self.material_row(ref)
            self.assertEqual(row.state, STATE_DELETED)
            self.assertFalse((self.data_dir / row.path).exists())
        with session_scope(self.eng) as s:
            usage = s.get(CourseQuotaUsage, "course-1")
            self.assertEqual(usage.used_bytes, 0)
        # 提交记录终态 deleted（L02 query 验证：不再可读为存续状态）
        sub = self.submission_row("sub-1")
        self.assertEqual(sub.status, "deleted")
        self.assertIsNotNone(sub.deleted_at)
        view = self.core.query_by_uuid("uuid-sub-1")
        self.assertEqual(view.status, "deleted")
        # ST-07 登记：批次 completed、逐项 purged
        batch = self.batch_row()
        self.assertEqual(batch.status, "completed")
        self.assertEqual(batch.run_count, 1)
        self.assertEqual(batch.scope, "submission")
        self.assertEqual(batch.operator, "retention-worker")
        self.assertEqual(batch.audit_record_id, "audit-1")
        items = self.item_rows()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].result, "purged")
        self.assertIsNone(items[0].reason)

    def test_ct014_payload_matches_frozen_contract(self):
        self.make_submission(sid="sub-1")
        self.executor.execute(ct012_payload(ids=("sub-1",)))
        records = self.drained_ct014()
        self.assertEqual(len(records), 1)
        payload = records[0].payload
        # 字段全集与 contracts/ct-014.json 一致（additionalProperties=false）
        self.assertEqual(
            set(payload),
            {"batch_id", "purged_submission_ids", "failed_items", "purged_at", "v"},
        )
        jsonschema.validate(payload, CT014_SCHEMA)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["batch_id"], "batch-1")
        self.assertEqual(payload["purged_submission_ids"], ["sub-1"])
        self.assertEqual(payload["failed_items"], [])
        self.assertEqual(payload["purged_at"], PURGED_AT.isoformat())
        # CT-014 幂等键：batch_id + purged_at
        self.assertEqual(records[0].dedup_key, f"batch-1:{PURGED_AT.isoformat()}")

    # ---- 部分失败 ----

    def test_partial_failure_unknown_submission_kept_for_rerun(self):
        self.make_submission(sid="sub-ok")
        report = self.executor.execute(ct012_payload(ids=("sub-ok", "sub-ghost")))

        self.assertEqual(report.purged_submission_ids, ("sub-ok",))
        self.assertEqual(len(report.failed_items), 1)
        failed = report.failed_items[0]
        self.assertEqual(set(failed), {"submission_id", "reason"})
        self.assertEqual(failed["submission_id"], "sub-ghost")
        self.assertTrue(failed["reason"])
        # CT-014 同时携带成功与失败项
        jsonschema.validate(report.ct014_payload, CT014_SCHEMA)
        # 单项失败不阻塞：sub-ok 已终态 deleted
        self.assertEqual(self.submission_row("sub-ok").status, "deleted")
        # 批次 partial、失败项保留（重跑定位）
        self.assertEqual(self.batch_row().status, "partial")
        items = {row.submission_id: row for row in self.item_rows()}
        self.assertEqual(items["sub-ok"].result, "purged")
        self.assertEqual(items["sub-ghost"].result, "failed")
        self.assertTrue(items["sub-ghost"].reason)

    # ---- 重跑：失败项可成功、登记更新 ----

    def test_rerun_failed_item_succeeds_and_updates_record(self):
        refs = self.make_submission(sid="sub-1", files=(("对话", b"dialog-1"),))
        flaky = FlakyDeleteStore(self.store, fail_refs=refs)
        failing_executor = PurgeExecutor(
            session_factory=partial(session_scope, self.eng),
            core_service=self.core,
            material_store=flaky,
            outbox_store=self.outbox,
            clock=lambda: PURGED_AT,
        )
        first = failing_executor.execute(ct012_payload(ids=("sub-1",)))
        self.assertEqual(first.purged_submission_ids, ())
        self.assertEqual(first.failed_items[0]["submission_id"], "sub-1")
        self.assertIn("StorageIoError", first.failed_items[0]["reason"])
        self.assertEqual(self.submission_row("sub-1").status, "received")
        self.assertEqual(self.batch_row().status, "partial")

        # 暂态故障消除后重跑同一 CT-012：失败项成功
        second = failing_executor.execute(ct012_payload(ids=("sub-1",)))
        self.assertEqual(second.purged_submission_ids, ("sub-1",))
        self.assertEqual(second.failed_items, ())
        self.assertEqual(self.submission_row("sub-1").status, "deleted")
        self.assertEqual(self.material_row(refs[0]).state, STATE_DELETED)
        # 登记更新而非新增：run_count 递增、逐项转 purged、原因清空、批次 completed
        batch = self.batch_row()
        self.assertEqual(batch.status, "completed")
        self.assertEqual(batch.run_count, 2)
        items = self.item_rows()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].result, "purged")
        self.assertIsNone(items[0].reason)
        # 每次执行各发一条 CT-014（投递归 RELAY）
        self.assertEqual(len(self.drained_ct014()), 2)

    # ---- 幂等：重复 CT-012 对已删项为空操作 ----

    def test_rerun_same_batch_is_noop_for_purged_items(self):
        refs = self.make_submission(sid="sub-1")
        first = self.executor.execute(ct012_payload(ids=("sub-1",)))
        self.assertEqual(first.purged_submission_ids, ("sub-1",))
        version_after_first = self.submission_row("sub-1").version

        second = self.executor.execute(ct012_payload(ids=("sub-1",)))
        # 已删项仍计 purged 回传，但无副作用：version 不变、材料保持 deleted
        self.assertEqual(second.purged_submission_ids, ("sub-1",))
        self.assertEqual(second.failed_items, ())
        self.assertEqual(self.submission_row("sub-1").version, version_after_first)
        self.assertEqual(self.submission_row("sub-1").status, "deleted")
        self.assertEqual(self.material_row(refs[0]).state, STATE_DELETED)
        # 登记行不新增（逐项唯一键）
        self.assertEqual(len(self.item_rows()), 1)
        self.assertEqual(self.batch_row().run_count, 2)

    # ---- 契约校验 ----

    def test_invalid_ct012_rejected_without_side_effects(self):
        self.make_submission(sid="sub-1")
        bad_payloads = [
            {**ct012_payload(), "v": 2},
            {k: v for k, v in ct012_payload().items() if k != "batch_id"},
            {**ct012_payload(), "extra": "nope"},
            ct012_payload(ids=("",)),
            ct012_payload(ids=("sub-1", 7)),
            {**ct012_payload(), "operator": ""},
        ]
        for payload in bad_payloads:
            with self.assertRaises(PurgeValidationError):
                self.executor.execute(payload)
        # 无副作用：提交仍在、无登记、无 Outbox 行
        self.assertEqual(self.submission_row("sub-1").status, "received")
        self.assertIsNone(self.batch_row())
        self.assertEqual(self.drained_ct014(), [])

    # ---- SQL Outbox 工厂路径：同事务入队（KD-002） ----

    def test_sqla_outbox_factory_enqueues_same_transaction(self):
        OUTBOX_METADATA.create_all(self.eng)
        sqla_executor = PurgeExecutor(
            session_factory=partial(session_scope, self.eng),
            core_service=self.core,
            material_store=self.store,
            outbox_store=SqlaOutboxStore,  # 按 Session 构造：CT-014 行与登记同事务
            clock=lambda: PURGED_AT,
        )
        self.make_submission(sid="sub-1")
        report = sqla_executor.execute(ct012_payload(ids=("sub-1",)))
        self.assertGreaterEqual(report.outbox_record_id, 1)
        with session_scope(self.eng) as s:
            rows = s.execute(sa.select(OUTBOX_RECORDS_TABLE)).mappings().all()
        ct014_rows = [r for r in rows if r["contract_id"] == "CT-014"]
        self.assertEqual(len(ct014_rows), 1)
        jsonschema.validate(dict(ct014_rows[0]["payload"]), CT014_SCHEMA)
        self.assertEqual(
            ct014_rows[0]["dedup_key"], f"batch-1:{PURGED_AT.isoformat()}"
        )
        self.assertEqual(self.batch_row().status, "completed")

    # ---- 重复 submission_id 去重 ----

    def test_duplicate_ids_in_payload_deduped(self):
        self.make_submission(sid="sub-1")
        report = self.executor.execute(ct012_payload(ids=("sub-1", "sub-1")))
        self.assertEqual(report.purged_submission_ids, ("sub-1",))
        self.assertEqual(len(self.item_rows()), 1)


if __name__ == "__main__":
    unittest.main()
