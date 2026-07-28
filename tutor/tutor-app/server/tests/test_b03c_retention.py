"""T-B03c RETENTION-GOVERNANCE 单元测试（SQLite 内存库 + StaticPool）。

覆盖任务验收面：
- 到期标记：retention_due_at = 课程结束 + 1 年（时钟注入；CP-COURSE-ENDTIME
  只读端口注入）；未到期 pending_mark、到期 awaiting_confirm；重复执行幂等；
  无结束时间课程跳过；2/29 归并 2/28；
- CT-011：未到期 409 BATCH_NOT_EXPIRED；确认后批次 executing 且经 OutboxStore
  发布 CT-012；审计先行顺序断言（enqueue 时审计行已在同事务可查）；同批次
  重复确认幂等（不重发 CT-012、不重复写审计）；exclusions 从待删范围剔除；
  CT-012 载荷与 contracts/ct-012.json 冻结字段一致；
- CT-014：按 batch_id + purged_at 幂等回写；completed 追加 RecordsDeleted
  审计；部分失败 partially_failed + failed_items 保留，重跑成功收敛 completed
  且 cleared 并集累积；契约校验失败抛 Ct014ValidationError；
- M05-IC-06 读端口：RetentionBatchView 形状、course/batch/submission 过滤、
  端口失败转 L15 RetentionViewUnavailableError；
- CT-011 路由：401/403/404/409/200 映射与重复确认幂等；
- 迁移 0014 可导入、revision/down_revision 正确、upgrade/downgrade 可执行。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tutor_shared.outbox import (  # noqa: E402
    OUTBOX_METADATA,
    InMemoryOutboxStore,
    OutboxRecord,
    OutboxStore,
    SqlaOutboxStore,
)

from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.course_roster.models import Course  # noqa: E402
from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core.models import (  # noqa: E402
    Base as CoreBase,
    Submission,
)
from course_app.teacher_web.access_gate import (  # noqa: E402
    AccessGateService,
    Base as GateBase,
)
from course_app.teacher_web.retention import (  # noqa: E402
    STATUS_AWAITING_CONFIRM,
    STATUS_COMPLETED,
    STATUS_EXECUTING,
    STATUS_PARTIALLY_FAILED,
    STATUS_PENDING_MARK,
    Base as RetentionBase,
    BatchNotExpiredError,
    Ct014ValidationError,
    DeletionAuditRecord,
    DeletionBatch,
    RetentionService,
    RetentionViewPortAdapter,
    create_router,
    derive_batch_id,
)
from course_app.teacher_web.review_query.errors import (  # noqa: E402
    RetentionViewUnavailableError,
)

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
COURSE = "CS101"
OTHER = "CS102"
COURSE_END = datetime(2025, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
ACCOUNT = "teacher@example.com"
PASSWORD = "s3cret-口令"

CT012_FIELDS = {
    "batch_id",
    "submission_ids",
    "scope",
    "operator",
    "executed_at",
    "audit_record_id",
    "v",
}


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    RosterBase.metadata.create_all(eng)
    CoreBase.metadata.create_all(eng)
    GateBase.metadata.create_all(eng)
    RetentionBase.metadata.create_all(eng)
    OUTBOX_METADATA.create_all(eng)
    return eng


class RetentionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        self.addCleanup(self.eng.dispose)
        self.now = NOW
        self.outbox = InMemoryOutboxStore()
        self.service = RetentionService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            clock=lambda: self.now,
        )
        self.add_course(COURSE, COURSE_END)

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)

    def add_course(self, course_id, end_time=None) -> None:
        with session_scope(self.eng) as session:
            session.add(
                Course(course_id=course_id, course_end_time=end_time, created_at=NOW)
            )

    def add_submission(self, submission_id, course_id=COURSE, *, deleted=False) -> None:
        with session_scope(self.eng) as session:
            session.add(
                Submission(
                    submission_id=submission_id,
                    submission_uuid=f"uuid-{submission_id}",
                    course_id=course_id,
                    status="scored",
                    version=0,
                    received_at=NOW,
                    deleted_at=NOW if deleted else None,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )

    def get_batch(self, batch_id) -> DeletionBatch:
        with session_scope(self.eng) as session:
            batch = session.get(DeletionBatch, batch_id)
            assert batch is not None
            session.expunge(batch)
            return batch

    def audit_rows(self) -> list[DeletionAuditRecord]:
        with session_scope(self.eng) as session:
            # 追加式审计按插入序（rowid）读取：DeletionConfirmed → RecordsDeleted
            rows = session.query(DeletionAuditRecord).order_by(
                sa.text("rowid")
            ).all()
            for row in rows:
                session.expunge(row)
            return rows

    def outbox_records(self) -> list[OutboxRecord]:
        return list(self.outbox._records.values())


class TestMarkDue(RetentionTestCase):
    def test_due_course_creates_awaiting_confirm_batch(self) -> None:
        report = self.service.mark_due_batches(self.now)
        self.assertEqual(len(report.marked), 1)
        item = report.marked[0]
        self.assertEqual(item.batch_id, derive_batch_id(COURSE, "course"))
        self.assertEqual(item.status, STATUS_AWAITING_CONFIRM)
        self.assertTrue(item.created)
        # retention_due_at = 课程结束时间 + 1 年
        self.assertEqual(item.retention_due_at, datetime(2026, 7, 1, 0, 0, 0))

    def test_not_due_course_creates_pending_mark_batch(self) -> None:
        self.add_course(OTHER, datetime(2026, 1, 1, tzinfo=timezone.utc))
        report = self.service.mark_due_batches(self.now)
        by_course = {item.course_id: item for item in report.marked}
        self.assertEqual(by_course[OTHER].status, STATUS_PENDING_MARK)
        self.assertEqual(
            by_course[OTHER].retention_due_at, datetime(2027, 1, 1, 0, 0, 0)
        )

    def test_mark_due_idempotent_and_status_flip_on_clock(self) -> None:
        self.add_course(OTHER, datetime(2026, 1, 1, tzinfo=timezone.utc))
        first = self.service.mark_due_batches(self.now)
        second = self.service.mark_due_batches(self.now)
        self.assertEqual(len(second.marked), 2)
        self.assertFalse(any(item.created for item in second.marked))
        with session_scope(self.eng) as session:
            count = session.query(DeletionBatch).count()
        self.assertEqual(count, 2)
        # 时钟越过到期时间：pending_mark → awaiting_confirm（更新既有批次不新增）
        self.advance(days=200)
        third = self.service.mark_due_batches(self.now)
        by_course = {item.course_id: item for item in third.marked}
        self.assertEqual(by_course[OTHER].status, STATUS_AWAITING_CONFIRM)
        with session_scope(self.eng) as session:
            count = session.query(DeletionBatch).count()
        self.assertEqual(count, 2)
        self.assertEqual(first.marked[0].batch_id, third.marked[0].batch_id)

    def test_course_end_time_via_injected_port(self) -> None:
        """到期计算经注入的 CP-COURSE-ENDTIME 端口（非网络调用）。"""
        seen: list[str] = []

        def port(session, course_id):
            seen.append(course_id)
            return datetime(2024, 2, 29, tzinfo=timezone.utc)  # 闰日

        service = RetentionService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            course_end_time_port=port,
            clock=lambda: self.now,
        )
        report = service.mark_due_batches(self.now, course_ids=[COURSE])
        self.assertEqual(seen, [COURSE])
        # 2024-02-29 + 1 年 → 2025-02-28（归并）
        self.assertEqual(report.marked[0].retention_due_at, datetime(2025, 2, 28))
        self.assertEqual(report.marked[0].status, STATUS_AWAITING_CONFIRM)

    def test_course_without_end_time_skipped(self) -> None:
        self.add_course(OTHER, None)
        report = self.service.mark_due_batches(self.now)
        self.assertEqual(report.skipped_course_ids, (OTHER,))
        self.assertEqual(len(report.marked), 1)

    def test_executing_batch_not_regressed_by_mark(self) -> None:
        self.service.mark_due_batches(self.now)
        self.add_submission("sub-1")
        self.service.confirm_batch(
            batch_id=derive_batch_id(COURSE, "course"), operator="teacher-x"
        )
        report = self.service.mark_due_batches(self.now)
        self.assertEqual(report.marked[0].status, STATUS_EXECUTING)


class TestConfirm(RetentionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.batch_id = derive_batch_id(COURSE, "course")
        self.service.mark_due_batches(self.now)
        for sid in ("sub-1", "sub-2", "sub-3"):
            self.add_submission(sid)

    def test_confirm_not_expired_raises(self) -> None:
        self.add_course(OTHER, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.service.mark_due_batches(self.now)
        batch_id = derive_batch_id(OTHER, "course")
        self.assertEqual(self.get_batch(batch_id).status, STATUS_PENDING_MARK)
        with self.assertRaises(BatchNotExpiredError):
            self.service.confirm_batch(batch_id=batch_id, operator="teacher-x")

    def test_confirm_success_publishes_ct012_and_executing(self) -> None:
        result = self.service.confirm_batch(
            batch_id=self.batch_id, operator="teacher-x"
        )
        self.assertFalse(result.already_confirmed)
        self.assertEqual(result.batch_status, STATUS_EXECUTING)
        self.assertEqual(
            result.pending_deletion_scope, ("sub-1", "sub-2", "sub-3")
        )
        batch = self.get_batch(self.batch_id)
        self.assertEqual(batch.status, STATUS_EXECUTING)
        self.assertEqual(batch.confirmed_by, "teacher-x")
        self.assertIsNotNone(batch.confirmed_at)
        records = self.outbox_records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.contract_id, "CT-012")
        self.assertEqual(record.dedup_key, self.batch_id)

    def test_ct012_payload_matches_contract(self) -> None:
        result = self.service.confirm_batch(
            batch_id=self.batch_id, operator="teacher-x"
        )
        payload = self.outbox_records()[0].payload
        # 与 contracts/ct-012.json event 一致：字段集合精确、v=1、additionalProperties=false
        self.assertEqual(set(payload.keys()), CT012_FIELDS)
        self.assertEqual(payload["v"], 1)
        self.assertEqual(payload["batch_id"], self.batch_id)
        self.assertEqual(payload["submission_ids"], ["sub-1", "sub-2", "sub-3"])
        self.assertEqual(payload["scope"], "course")
        self.assertEqual(payload["operator"], "teacher-x")
        self.assertEqual(payload["audit_record_id"], result.audit_record_id)
        # executed_at 为 date-time 格式
        datetime.fromisoformat(payload["executed_at"])

    def test_audit_written_before_purge_action(self) -> None:
        """顺序断言：CT-012 enqueue 时 DeletionConfirmed 审计行已在同事务可查。"""
        observed: dict = {}

        class AuditFirstSpy(OutboxStore):
            def __init__(self, session):
                self._inner = SqlaOutboxStore(session)
                self._session = session

            def enqueue(self, contract_id, payload, dedup_key):
                row = self._session.get(
                    DeletionAuditRecord, payload["audit_record_id"]
                )
                observed["audit_visible_at_enqueue"] = row is not None
                observed["action"] = None if row is None else row.action
                return self._inner.enqueue(contract_id, payload, dedup_key)

            def fetch_due(self, now, limit=50):
                return self._inner.fetch_due(now, limit)

            def mark_confirmed(self, record_id):
                return self._inner.mark_confirmed(record_id)

            def mark_retry(self, record_id, next_attempt_at=None):
                return self._inner.mark_retry(record_id, next_attempt_at)

        service = RetentionService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=AuditFirstSpy,  # 工厂：SQL 同事务入队
            clock=lambda: self.now,
        )
        service.mark_due_batches(self.now)
        result = service.confirm_batch(
            batch_id=self.batch_id, operator="teacher-x"
        )
        self.assertTrue(observed["audit_visible_at_enqueue"])
        self.assertEqual(observed["action"], "DeletionConfirmed")
        audits = self.audit_rows()
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0].audit_record_id, result.audit_record_id)
        self.assertEqual(audits[0].submission_ids, ["sub-1", "sub-2", "sub-3"])

    def test_repeat_confirm_idempotent(self) -> None:
        first = self.service.confirm_batch(
            batch_id=self.batch_id, operator="teacher-x"
        )
        second = self.service.confirm_batch(
            batch_id=self.batch_id, operator="teacher-x"
        )
        self.assertFalse(first.already_confirmed)
        self.assertTrue(second.already_confirmed)
        self.assertEqual(second.batch_status, STATUS_EXECUTING)
        self.assertIsNone(second.audit_record_id)
        # 不重复执行：CT-012 仍一条、审计仍一条
        self.assertEqual(len(self.outbox_records()), 1)
        self.assertEqual(len(self.audit_rows()), 1)

    def test_exclusions_removed_from_scope(self) -> None:
        self.add_submission("sub-deleted", deleted=True)
        result = self.service.confirm_batch(
            batch_id=self.batch_id,
            operator="teacher-x",
            exclusions=["sub-2"],
        )
        self.assertEqual(result.pending_deletion_scope, ("sub-1", "sub-3"))
        payload = self.outbox_records()[0].payload
        self.assertEqual(payload["submission_ids"], ["sub-1", "sub-3"])
        batch = self.get_batch(self.batch_id)
        self.assertEqual(batch.exclusions, ["sub-2"])


class TestCt014(RetentionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.batch_id = derive_batch_id(COURSE, "course")
        self.service.mark_due_batches(self.now)
        for sid in ("sub-1", "sub-2"):
            self.add_submission(sid)
        self.service.confirm_batch(batch_id=self.batch_id, operator="teacher-x")

    def ct014(self, *, purged=("sub-1", "sub-2"), failed=(), purged_at=None):
        return {
            "batch_id": self.batch_id,
            "purged_submission_ids": list(purged),
            "failed_items": [
                {"submission_id": sid, "reason": reason} for sid, reason in failed
            ],
            "purged_at": (purged_at or self.now).isoformat()
            if isinstance(purged_at or self.now, datetime)
            else purged_at,
            "v": 1,
        }

    def ct015(self, *, purged=("sub-1", "sub-2"), failed=(), purged_at=None):
        # CCR-001：CT-015 与 CT-014 事件形状一致（镜像）；purged_at 独立取值
        return self.ct014(purged=purged, failed=failed, purged_at=purged_at)

    def both_flows(self, **kwargs) -> None:
        """双回流到位（CT-014 + CT-015 同参数）。"""
        self.service.handle_ct014(self.ct014(**kwargs))
        self.service.handle_ct015(self.ct015(**kwargs))

    def test_dual_flow_required_for_completion(self) -> None:
        # CCR-001：单路到达不完成批次
        result = self.service.handle_ct014(self.ct014())
        self.assertTrue(result.applied)
        self.assertEqual(result.batch_status, STATUS_EXECUTING)
        actions = [row.action for row in self.audit_rows()]
        self.assertEqual(actions, ["DeletionConfirmed"])
        # CT-015 到达后双路齐全 → completed + 审计闭合
        result2 = self.service.handle_ct015(self.ct015())
        self.assertTrue(result2.applied)
        self.assertEqual(result2.batch_status, STATUS_COMPLETED)
        batch = self.get_batch(self.batch_id)
        self.assertEqual(batch.cleared_submission_ids, ["sub-1", "sub-2"])
        self.assertEqual(batch.failed_items, [])
        actions = [row.action for row in self.audit_rows()]
        self.assertEqual(actions, ["DeletionConfirmed", "RecordsDeleted"])

    def test_ct015_may_arrive_first(self) -> None:
        first = self.service.handle_ct015(self.ct015())
        self.assertEqual(first.batch_status, STATUS_EXECUTING)
        second = self.service.handle_ct014(self.ct014())
        self.assertEqual(second.batch_status, STATUS_COMPLETED)

    def test_idempotent_by_batch_and_purged_at(self) -> None:
        payload = self.ct014()
        first = self.service.handle_ct014(payload)
        second = self.service.handle_ct014(payload)
        self.assertTrue(first.applied)
        self.assertFalse(second.applied)
        self.assertEqual(second.batch_status, STATUS_EXECUTING)  # CT-015 未达
        # CT-015 同 (batch_id, purged_at) 重放同样幂等
        p15 = self.ct015()
        self.assertTrue(self.service.handle_ct015(p15).applied)
        replay = self.service.handle_ct015(p15)
        self.assertFalse(replay.applied)
        self.assertEqual(replay.batch_status, STATUS_COMPLETED)
        batch = self.get_batch(self.batch_id)
        self.assertEqual(batch.cleared_submission_ids, ["sub-1", "sub-2"])
        # 审计不重复追加
        actions = [row.action for row in self.audit_rows()]
        self.assertEqual(actions, ["DeletionConfirmed", "RecordsDeleted"])

    def test_partial_failure_keeps_failed_items_and_rerun(self) -> None:
        result = self.service.handle_ct014(
            self.ct014(
                purged=("sub-1",),
                failed=(("sub-2", "StorageIoError"),),
                purged_at=self.now,
            )
        )
        self.assertEqual(result.batch_status, STATUS_EXECUTING)  # 双回流未齐
        result15 = self.service.handle_ct015(self.ct015(purged=("sub-1",)))
        self.assertEqual(result15.batch_status, STATUS_PARTIALLY_FAILED)
        batch = self.get_batch(self.batch_id)
        self.assertEqual(
            batch.failed_items,
            [{"submission_id": "sub-2", "reason": "StorageIoError", "flow": "CT-014"}],
        )
        self.assertEqual(batch.cleared_submission_ids, ["sub-1"])
        # 重跑：失败项成功（新 purged_at）→ completed，cleared 并集累积
        self.advance(seconds=5)
        rerun = self.service.handle_ct014(
            self.ct014(purged=("sub-2",), failed=(), purged_at=self.now)
        )
        self.assertTrue(rerun.applied)
        self.assertEqual(rerun.batch_status, STATUS_COMPLETED)
        batch = self.get_batch(self.batch_id)
        self.assertEqual(batch.cleared_submission_ids, ["sub-1", "sub-2"])
        self.assertEqual(batch.failed_items, [])

    def test_invalid_payload_rejected(self) -> None:
        with self.assertRaises(Ct014ValidationError):
            self.service.handle_ct014({"batch_id": self.batch_id, "v": 1})
        with self.assertRaises(Ct014ValidationError):
            self.service.handle_ct014(self.ct014() | {"extra": 1})
        with self.assertRaises(Ct014ValidationError):
            self.service.handle_ct014(self.ct014() | {"v": 2})


class TestBatchView(RetentionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.batch_id = derive_batch_id(COURSE, "course")
        self.service.mark_due_batches(self.now)
        self.add_submission("sub-1")
        self.add_submission("sub-2")
        self.port = RetentionViewPortAdapter(self.service)

    def test_list_batches_shape(self) -> None:
        views = self.port.list_batches(course_id=COURSE)
        self.assertEqual(len(views), 1)
        view = views[0]
        self.assertEqual(view.batch_id, self.batch_id)
        self.assertEqual(view.scope, "course")
        self.assertEqual(view.batch_status, STATUS_AWAITING_CONFIRM)
        self.assertEqual(view.retention_due_at, "2026-07-01T00:00:00+00:00")
        self.assertEqual(view.exclusions, ())
        self.assertEqual(view.cleared_submission_ids, ())

    def test_filters(self) -> None:
        self.assertEqual(self.port.list_batches(course_id=OTHER), ())
        self.assertEqual(
            len(self.port.list_batches(batch_id=self.batch_id)), 1
        )
        self.assertEqual(
            len(self.port.list_batches(submission_id="sub-1")), 1
        )
        self.assertEqual(self.port.list_batches(submission_id="sub-x"), ())

    def test_cleared_ids_visible_after_dual_flow(self) -> None:
        self.service.confirm_batch(batch_id=self.batch_id, operator="teacher-x")
        for handler in (self.service.handle_ct014, self.service.handle_ct015):
            handler(
                {
                    "batch_id": self.batch_id,
                    "purged_submission_ids": ["sub-1", "sub-2"],
                    "failed_items": [],
                    "purged_at": self.now.isoformat(),
                    "v": 1,
                }
            )
        view = self.port.list_batches(batch_id=self.batch_id)[0]
        self.assertEqual(view.batch_status, STATUS_COMPLETED)
        self.assertEqual(view.cleared_submission_ids, ("sub-1", "sub-2"))

    def test_port_failure_translated(self) -> None:
        self.eng.dispose()
        with self.assertRaises(RetentionViewUnavailableError):
            self.port.list_batches(course_id=COURSE)


class TestRouter(RetentionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.batch_id = derive_batch_id(COURSE, "course")
        self.service.mark_due_batches(self.now)
        self.add_submission("sub-1")
        self.gate = AccessGateService(
            session_factory=partial(session_scope, self.eng),
            now_fn=lambda: self.now,
        )
        self.gate.provision_teacher(
            account=ACCOUNT, password=PASSWORD, course_ids=(COURSE,)
        )
        self.token = self.gate.login(account=ACCOUNT, password=PASSWORD)
        app = FastAPI()
        app.include_router(create_router(service=self.service, access_gate=self.gate))
        self.client = TestClient(app)
        self.auth = {"Authorization": f"Bearer {self.token}"}

    def confirm(self, batch_id=None, **kwargs):
        headers = kwargs.pop("headers", self.auth)
        body = {"confirm": True}
        body.update(kwargs)
        return self.client.post(
            f"/api/v1/teacher/deletion-batches/{batch_id or self.batch_id}/confirm",
            json=body,
            headers=headers,
        )

    def test_happy_path(self) -> None:
        resp = self.confirm(exclusions=[])
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["batch_id"], self.batch_id)
        self.assertEqual(body["batch_status"], STATUS_EXECUTING)
        self.assertEqual(body["pending_deletion_scope"], ["sub-1"])
        self.assertEqual(len(self.outbox_records()), 1)

    def test_repeat_confirm_returns_same_state(self) -> None:
        first = self.confirm()
        second = self.confirm()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["batch_status"], STATUS_EXECUTING)
        self.assertEqual(len(self.outbox_records()), 1)
        self.assertEqual(len(self.audit_rows()), 1)

    def test_missing_auth_401(self) -> None:
        resp = self.confirm(headers={})
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_not_found_404(self) -> None:
        resp = self.confirm(batch_id="nope:course")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_forbidden_403(self) -> None:
        self.add_course(OTHER, COURSE_END)
        self.service.mark_due_batches(self.now)
        other_batch = derive_batch_id(OTHER, "course")
        resp = self.confirm(batch_id=other_batch)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "FORBIDDEN")

    def test_not_expired_409(self) -> None:
        self.add_course(OTHER, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.service.mark_due_batches(self.now)
        other_batch = derive_batch_id(OTHER, "course")
        # 授权后未到期 → 409 BATCH_NOT_EXPIRED
        self.gate.provision_teacher(
            account=ACCOUNT, password=PASSWORD, course_ids=(COURSE, OTHER)
        )
        resp = self.confirm(batch_id=other_batch)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "BATCH_NOT_EXPIRED")


class TestMigration0014(unittest.TestCase):
    def _load_module(self):
        path = ROOT / "server" / "migrations" / "versions" / "0014_retention.py"
        spec = importlib.util.spec_from_file_location("mig_0014_retention", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_identifiers(self):
        module = self._load_module()
        self.assertEqual(module.revision, "0014_retention")
        self.assertEqual(module.down_revision, "11a22f91f4b3")

    def test_upgrade_downgrade_on_sqlite(self):
        module = self._load_module()
        tables_expected = ("deletion_batches", "deletion_audit_records")
        with tempfile.TemporaryDirectory() as tmp:
            eng = sa.create_engine(f"sqlite:///{Path(tmp) / 'mig.db'}")
            with eng.connect() as conn:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    module.upgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    for name in tables_expected:
                        self.assertIn(name, tables)
                    module.downgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    for name in tables_expected:
                        self.assertNotIn(name, tables)
            eng.dispose()


if __name__ == "__main__":
    unittest.main()
