"""L02 SI-CORE 单元测试（SQLite 内存库 + 内存 OutboxStore）。

覆盖 verification-checklist 语义断言：
- 六态迁移守卫（合法路径通过、非法迁移 ILLEGAL_TRANSITION）；
- 终态不可逆、重复 CT-005 终态事件幂等（duplicate_ignored）；
- submission_uuid 幂等创建（同一 submission_id、无重复记录、无重复事件）；
- 完整性报告 missing_items（空目录显式标记、不隐藏、不阻断 received/CT-004）；
- received/upload_failed 时 Outbox 行与业务写入同事务（CT-004/CT-006 必填字段 + dedup_key）；
- 迁移文件可导入、revision/down_revision 正确。
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core import (  # noqa: E402
    APPLIED,
    CATEGORIES,
    DUPLICATE_IGNORED,
    IDEMPOTENT_HIT,
    Base,
    IllegalTransitionError,
    MaterialMetadata,
    MaterialMetadataUnavailableError,
    NotFoundError,
    Submission,
    SubmissionCoreService,
    ValidationError,
    status as st,
)
from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

CT004_REQUIRED = {
    "submission_id", "course_id", "assignment", "student_name", "group_name",
    "material_refs", "missing_items", "received_at", "v",
}
CT006_REQUIRED = {
    "submission_id", "course_id", "assignment", "student_name", "group_name",
    "status", "missing_items", "received_at", "v",
}


class FakeMetadataReader:
    """SI-STORE 元数据端口 fake：字典命中，未知 ref 视为元数据不可用。"""

    def __init__(self, entries: dict[str, MaterialMetadata] | None = None) -> None:
        self._entries = entries or {}

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        try:
            return self._entries[material_ref]
        except KeyError as exc:
            raise MaterialMetadataUnavailableError(material_ref) from exc


def make_engine():
    # StaticPool：所有 Session 共享同一内存库连接
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


def drained(outbox: InMemoryOutboxStore) -> list:
    return outbox.fetch_due(datetime.now(timezone.utc) + timedelta(days=1), limit=100)


class SiCoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        self.outbox = InMemoryOutboxStore()
        self.reader = FakeMetadataReader(
            {
                "r-dialog": MaterialMetadata("r-dialog", "对话", 100, True, "dialog.md"),
                "r-code": MaterialMetadata("r-code", "代码", 200, True, "main.py"),
            }
        )
        self.service = SubmissionCoreService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            metadata_reader=self.reader,
        )

    def tearDown(self) -> None:
        self.eng.dispose()

    # ---- 辅助 ----

    def confirm(self, uuid="uuid-1", material_refs=("r-dialog", "r-code"), expected=CATEGORIES):
        return self.service.confirm_received(
            submission_uuid=uuid,
            course_id="course-1",
            assignment="hw-1",
            student_name="张三",
            group_name="G1",
            material_refs=list(material_refs),
            expected_categories=list(expected),
            verification={"verified": True, "course_id": "course-1"},
        )

    def row(self, submission_id: str):
        with session_scope(self.eng) as session:
            sub = session.get(Submission, submission_id)
            return SimpleNamespace(status=sub.status, version=sub.version)

    def rows(self) -> list[Submission]:
        with session_scope(self.eng) as session:
            return list(session.query(Submission).all())

    # ---- 创建 + 幂等 + Outbox 同事务 ----

    def test_confirm_received_enqueues_ct004_ct006_same_transaction(self):
        result = self.confirm()
        self.assertEqual(result.status, st.RECEIVED)
        self.assertEqual(result.transition_result.outcome, APPLIED)
        self.assertEqual(result.missing_items, ("截图", "结果"))

        records = drained(self.outbox)
        self.assertEqual(len(records), 2)
        by_contract = {r.contract_id: r for r in records}
        self.assertEqual(set(by_contract), {"CT-004", "CT-006"})
        for record in records:
            # dedup_key = submission_id（消费方幂等键）
            self.assertEqual(record.dedup_key, result.submission_id)
        ct004 = by_contract["CT-004"].payload
        self.assertTrue(CT004_REQUIRED <= set(ct004), ct004)
        self.assertEqual(ct004["v"], 1)
        self.assertEqual(ct004["submission_id"], result.submission_id)
        self.assertEqual(ct004["missing_items"], ["截图", "结果"])
        self.assertEqual(
            [m["category"] for m in ct004["material_refs"]], ["对话", "代码"]
        )
        ct006 = by_contract["CT-006"].payload
        self.assertTrue(CT006_REQUIRED <= set(ct006), ct006)
        self.assertEqual(ct006["status"], st.RECEIVED)
        self.assertEqual(ct006["v"], 1)

    def test_idempotent_create_same_uuid_returns_same_submission(self):
        first = self.confirm()
        drained(self.outbox)
        second = self.confirm()
        self.assertEqual(second.submission_id, first.submission_id)
        self.assertEqual(second.status, st.RECEIVED)
        self.assertEqual(second.transition_result.outcome, IDEMPOTENT_HIT)
        self.assertEqual(len(self.rows()), 1)  # 无重复提交记录
        self.assertEqual(drained(self.outbox), [])  # 幂等命中不重复发布事件

    def test_metadata_unavailable_rolls_back_business_and_outbox(self):
        reader = FakeMetadataReader({})  # 所有 ref 不可用
        service = SubmissionCoreService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            metadata_reader=reader,
        )
        with self.assertRaises(MaterialMetadataUnavailableError):
            service.confirm_received(
                submission_uuid="uuid-x",
                course_id="course-1",
                assignment="hw-1",
                student_name="张三",
                group_name="G1",
                material_refs=["r-missing"],
                expected_categories=list(CATEGORIES),
                verification={"verified": True, "course_id": "course-1"},
            )
        self.assertEqual(self.rows(), [])  # 无部分 Submission
        self.assertEqual(drained(self.outbox), [])  # 无孤立 Outbox 行

    def test_confirm_requires_verified(self):
        with self.assertRaises(IllegalTransitionError):
            self.service.confirm_received(
                submission_uuid="uuid-v",
                course_id="course-1",
                assignment="hw-1",
                student_name="张三",
                group_name="G1",
                material_refs=[],
                expected_categories=[],
                verification={"verified": False},
            )
        self.assertEqual(self.rows(), [])

    # ---- 完整性报告 ----

    def test_empty_material_dir_marks_missing_but_still_received(self):
        result = self.confirm(uuid="uuid-empty", material_refs=())
        self.assertEqual(result.status, st.RECEIVED)  # 缺失不阻断 received
        self.assertEqual(result.missing_items, tuple(CATEGORIES))  # 缺失显式标记
        view = self.service.query_by_uuid("uuid-empty")
        self.assertEqual(view.missing_items, tuple(CATEGORIES))  # 缺失不被隐藏
        ct004 = [r for r in drained(self.outbox) if r.contract_id == "CT-004"]
        self.assertEqual(len(ct004), 1)  # 空目录仍发布 CT-004（INV-3）
        self.assertEqual(ct004[0].payload["missing_items"], list(CATEGORIES))

    def test_integrity_report_stored_with_submission(self):
        result = self.confirm()
        view = self.service.query_by_uuid("uuid-1")
        self.assertEqual(view.submission_id, result.submission_id)
        self.assertEqual(view.status, st.RECEIVED)
        self.assertIsNone(view.failure_reason)
        self.assertEqual(view.missing_items, ("截图", "结果"))

    # ---- 状态机守卫 ----

    def test_legal_path_received_processing_scored(self):
        result = self.confirm()
        sid = result.submission_id
        advanced = self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        self.assertEqual(advanced.status, st.PROCESSING)
        self.assertEqual(advanced.transition_result.outcome, APPLIED)
        scored = self.service.apply_scoring_outcome(
            submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
        )
        self.assertEqual(scored.status, st.SCORED)
        self.assertEqual(scored.transition_result.outcome, APPLIED)

    def test_legal_path_scoring_failed_records_reason(self):
        sid = self.confirm().submission_id
        self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        failed = self.service.apply_scoring_outcome(
            submission_id=sid,
            expected_state=st.PROCESSING,
            outcome=st.SCORING_FAILED,
            failure_reason="model timeout",
        )
        self.assertEqual(failed.status, st.SCORING_FAILED)
        self.assertEqual(failed.failure_reason, "model timeout")

    def test_illegal_transitions_rejected(self):
        sid = self.confirm().submission_id
        with self.assertRaises(IllegalTransitionError):
            # received 不能跳过 processing 直接 scored
            self.service.apply_scoring_outcome(
                submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
            )
        with self.assertRaises(IllegalTransitionError):
            # 非 task_persisted 确认不得推进
            self.service.advance_to_processing(
                submission_id=sid, expected_state=st.RECEIVED, consumer_ack="payload_accepted"
            )
        self.assertEqual(self.row(sid).status, st.RECEIVED)  # 拒绝无副作用

    def test_terminal_irreversible(self):
        sid = self.confirm().submission_id
        self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        self.service.apply_scoring_outcome(
            submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
        )
        with self.assertRaises(IllegalTransitionError):
            self.service.apply_scoring_outcome(
                submission_id=sid,
                expected_state=st.PROCESSING,
                outcome=st.SCORING_FAILED,
                failure_reason="late failure",
            )
        with self.assertRaises(IllegalTransitionError):
            self.service.advance_to_processing(
                submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
            )
        self.assertEqual(self.row(sid).status, st.SCORED)

    def test_duplicate_ct005_terminal_event_is_noop(self):
        sid = self.confirm().submission_id
        self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        first = self.service.apply_scoring_outcome(
            submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
        )
        version_after_first = self.row(sid).version
        duplicate = self.service.apply_scoring_outcome(
            submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
        )
        self.assertEqual(first.transition_result.outcome, APPLIED)
        self.assertEqual(duplicate.transition_result.outcome, DUPLICATE_IGNORED)
        self.assertEqual(duplicate.status, st.SCORED)  # 重复事件不改终态
        self.assertEqual(self.row(sid).version, version_after_first)

    def test_duplicate_ack_is_noop(self):
        sid = self.confirm().submission_id
        self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        again = self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        self.assertEqual(again.transition_result.outcome, DUPLICATE_IGNORED)
        self.assertEqual(again.status, st.PROCESSING)

    def test_invalid_outcome_and_missing_failure_reason(self):
        sid = self.confirm().submission_id
        self.service.advance_to_processing(
            submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        with self.assertRaises(ValidationError):
            self.service.apply_scoring_outcome(
                submission_id=sid, expected_state=st.PROCESSING, outcome="unknown"
            )
        with self.assertRaises(ValidationError):
            self.service.apply_scoring_outcome(
                submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORING_FAILED
            )
        self.assertEqual(self.row(sid).status, st.PROCESSING)

    # ---- rejected / upload_failed ----

    def test_mark_rejected_terminal_without_outbox(self):
        result = self.service.mark_rejected(
            submission_uuid="uuid-rej",
            failure_reason="姓名不在名单中",
            verification={"verified": False, "reason": "姓名不在名单中"},
        )
        self.assertEqual(result.status, st.REJECTED)
        self.assertEqual(result.failure_reason, "姓名不在名单中")
        self.assertEqual(drained(self.outbox), [])  # rejected 不发布 CT-004/CT-006
        again = self.service.mark_rejected(
            submission_uuid="uuid-rej",
            failure_reason="姓名不在名单中",
            verification={"verified": False, "reason": "姓名不在名单中"},
        )
        self.assertEqual(again.submission_id, result.submission_id)
        self.assertEqual(again.transition_result.outcome, IDEMPOTENT_HIT)
        self.assertEqual(len(self.rows()), 1)

    def test_mark_upload_failed_enqueues_ct006(self):
        result = self.service.mark_upload_failed(
            submission_uuid="uuid-uf",
            failure_reason="重试窗口耗尽",
            upload_session_state="failed_terminal",
            material_refs=["r-dialog"],
            expected_categories=list(CATEGORIES),
            course_id="course-1",
            assignment="hw-1",
            student_name="张三",
            group_name="G1",
        )
        self.assertEqual(result.status, st.UPLOAD_FAILED)
        self.assertEqual(result.failure_reason, "重试窗口耗尽")
        records = drained(self.outbox)
        self.assertEqual([r.contract_id for r in records], ["CT-006"])  # 只发 CT-006
        payload = records[0].payload
        self.assertTrue(CT006_REQUIRED <= set(payload), payload)
        self.assertEqual(payload["status"], st.UPLOAD_FAILED)
        self.assertEqual(records[0].dedup_key, result.submission_id)
        # 教师端可见失败原因（CT-002 视图）
        view = self.service.query_by_uuid("uuid-uf")
        self.assertEqual(view.failure_reason, "重试窗口耗尽")

    def test_mark_upload_failed_requires_failed_terminal(self):
        with self.assertRaises(IllegalTransitionError):
            self.service.mark_upload_failed(
                submission_uuid="uuid-uf2",
                failure_reason="x",
                upload_session_state="interrupted_retryable",
            )
        self.assertEqual(self.rows(), [])
        self.assertEqual(drained(self.outbox), [])

    def test_upload_failed_is_terminal(self):
        result = self.service.mark_upload_failed(
            submission_uuid="uuid-uf3",
            failure_reason="重试窗口耗尽",
            upload_session_state="failed_terminal",
        )
        sid = result.submission_id
        with self.assertRaises(IllegalTransitionError):
            self.service.advance_to_processing(
                submission_id=sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
            )
        with self.assertRaises(IllegalTransitionError):
            self.service.apply_scoring_outcome(
                submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
            )
        self.assertEqual(self.row(sid).status, st.UPLOAD_FAILED)

    # ---- purge ----

    def test_purge_to_deleted_and_idempotent(self):
        sid = self.confirm().submission_id
        purged = self.service.purge_submission(submission_id=sid)
        self.assertEqual(purged.status, st.DELETED)
        self.assertEqual(purged.transition_result.outcome, APPLIED)
        again = self.service.purge_submission(submission_id=sid)
        self.assertEqual(again.transition_result.outcome, DUPLICATE_IGNORED)
        with self.assertRaises(IllegalTransitionError):
            # deleted 终态不可逆
            self.service.apply_scoring_outcome(
                submission_id=sid, expected_state=st.PROCESSING, outcome=st.SCORED
            )

    def test_purge_from_terminal_states(self):
        rejected = self.service.mark_rejected(
            submission_uuid="uuid-p1",
            failure_reason="r",
            verification={"verified": False},
        )
        self.assertEqual(
            self.service.purge_submission(submission_id=rejected.submission_id).status,
            st.DELETED,
        )
        scored_sid = self.confirm(uuid="uuid-p2").submission_id
        self.service.advance_to_processing(
            submission_id=scored_sid, expected_state=st.RECEIVED, consumer_ack="task_persisted"
        )
        self.service.apply_scoring_outcome(
            submission_id=scored_sid, expected_state=st.PROCESSING, outcome=st.SCORED
        )
        self.assertEqual(
            self.service.purge_submission(submission_id=scored_sid).status, st.DELETED
        )

    # ---- 查询 ----

    def test_query_unknown_uuid_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.query_by_uuid("no-such-uuid")

    def test_commands_unknown_submission_id_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.advance_to_processing(
                submission_id="sub-none", expected_state=st.RECEIVED, consumer_ack="task_persisted"
            )
        with self.assertRaises(NotFoundError):
            self.service.apply_scoring_outcome(
                submission_id="sub-none", expected_state=st.PROCESSING, outcome=st.SCORED
            )
        with self.assertRaises(NotFoundError):
            self.service.purge_submission(submission_id="sub-none")

    # ---- 迁移文件 ----

    def test_migration_importable_with_correct_revisions(self):
        path = ROOT / "server" / "migrations" / "versions" / "0003_submission_core.py"
        spec = importlib.util.spec_from_file_location("migration_0003", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0003_submission_core")
        self.assertEqual(module.down_revision, "0001_baseline")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
