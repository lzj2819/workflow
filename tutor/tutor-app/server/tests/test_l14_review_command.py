"""L14 CMP-REVIEW-COMMAND 单元测试（fastapi TestClient + SQLite 内存库）。

覆盖 verification-checklist 语义断言：
- 保存批注（仅 annotation）与调整等级（仅 final_grade）均可；两者皆缺 →
  400 VALIDATION_FAILED；
- 同一 request_id 重复请求 → 同一复核记录（幂等，无重复写入/调整记录）；
- scoring_failed 且无原始等级 → 设置 final_grade 被拒（NO_ORIGINAL_GRADE，
  无部分写入），批注仍可保存；
- 复核记录同时保留 original_grade/final_grade/operator/updated_at；原始等级
  复制值不被后续调整改写；
- 连续两次调整 → 后写为准且两次调整记录均可追溯（adjustment_id 唯一）；
- adjustment_reason 缺失时正常保存（可选不强制，TD-09/DD-007）；
- 应答字段与 contracts/ct-008.json 一致；未授权 → 403（ACCESS-GATE 注入
  断言被调用）；目标不存在 → 404 NOT_FOUND；
- M05-IC-01 创建端口：按 submission_id 幂等，重复创建不覆盖原始等级；
- M05-IC-05 事件在业务提交后发布（AnnotationSaved/GradeAdjusted）；
- 迁移文件可导入、revision/down_revision 正确。

注入（DD-004，进程内）：ACCESS-GATE / L02 状态查询 / M05-IC-05 均注入 stub；
真实实现归 backfill/兄弟叶子。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import datetime
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.teacher_web.review_command import (  # noqa: E402
    AccessGrant,
    ForbiddenError,
    InMemoryReviewEventPublisher,
    ReviewCommandService,
    SubmissionStatus,
    create_router,
)
from course_app.teacher_web.review_command.errors import (  # noqa: E402
    ValidationFailedError,
)
from course_app.teacher_web.review_command.models import (  # noqa: E402
    Base,
    GradeAdjustmentRecord,
    ReviewIdempotencyRecord,
    ReviewRecord,
)

CONTRACTS_DIR = ROOT / "contracts"
MIGRATION = ROOT / "server" / "migrations" / "versions" / "0007_review_records.py"

SUB = "sub-1"
SUB_FAILED = "sub-failed"
TEACHER = "teacher-1"
HEADERS = {"Authorization": "Bearer teacher-session-1"}


def load_contract(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


class StubAccessGate:
    """ACCESS-GATE 端口 stub：记录调用；可切换为拒绝（403）。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.deny = False

    def authorize(self, *, teacher_session, submission_id):
        self.calls.append(
            {"teacher_session": teacher_session, "submission_id": submission_id}
        )
        if self.deny:
            raise ForbiddenError("teacher not granted for this course")
        return AccessGrant(operator=TEACHER)


class StubSubmissionStatus:
    """L02 状态查询端口 stub：dict 驱动的 submission 存在性/状态。"""

    def __init__(self, statuses: dict[str, str]) -> None:
        self._statuses = statuses

    def get_submission_status(self, submission_id: str):
        status = self._statuses.get(submission_id)
        if status is None:
            return None
        return SubmissionStatus(submission_id=submission_id, status=status)


def make_client(eng, gate, statuses=None, publisher=None):
    service = ReviewCommandService(
        partial(session_scope, eng),
        submission_status=StubSubmissionStatus(
            statuses if statuses is not None else {SUB: "scored"}
        ),
    )
    router = create_router(
        service=service, access_gate=gate, event_publisher=publisher
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), service


def put_review(client, submission_id=SUB, **body):
    return client.put(
        f"/api/v1/teacher/submissions/{submission_id}/review",
        json=body,
        headers=HEADERS,
    )


def adjustments_for(eng, review_record_id):
    """调整记录快照（session 内取值，避免 detached 访问）。"""
    with session_scope(eng) as session:
        rows = (
            session.query(GradeAdjustmentRecord)
            .filter(GradeAdjustmentRecord.review_record_id == review_record_id)
            .order_by(GradeAdjustmentRecord.created_at, GradeAdjustmentRecord.adjustment_id)
            .all()
        )
        return [
            (
                r.adjustment_id,
                r.final_grade_before,
                r.final_grade_after,
                r.operator,
                r.created_at,
                r.adjustment_reason,
            )
            for r in rows
        ]


class TestCt008HappyPath(unittest.TestCase):
    def setUp(self):
        self.eng = make_engine()
        self.gate = StubAccessGate()
        self.publisher = InMemoryReviewEventPublisher()
        self.client, self.service = make_client(
            self.eng, self.gate, publisher=self.publisher
        )
        # M05-IC-01：scored 路径创建复核记录（原始等级 B）。
        self.service.create_review_record(
            submission_id=SUB, original_grade="B", scored_at=datetime(2026, 7, 20)
        )

    def test_save_annotation_only(self):
        resp = put_review(self.client, request_id="req-a1", annotation="论证充分")
        self.assertEqual(resp.status_code, 200)
        record = resp.json()["review_record"]
        self.assertEqual(record["annotation"], "论证充分")
        self.assertEqual(record["original_grade"], "B")
        self.assertIsNone(record["final_grade"])
        self.assertEqual(record["operator"], TEACHER)
        datetime.fromisoformat(record["updated_at"])
        event_types = [e.event_type for e in self.publisher.events]
        self.assertEqual(event_types, ["AnnotationSaved"])

    def test_adjust_final_grade_only(self):
        resp = put_review(self.client, request_id="req-g1", final_grade="A")
        self.assertEqual(resp.status_code, 200)
        record = resp.json()["review_record"]
        self.assertEqual(record["final_grade"], "A")
        self.assertEqual(record["original_grade"], "B")
        self.assertIsNone(record["annotation"])
        event_types = [e.event_type for e in self.publisher.events]
        self.assertEqual(event_types, ["GradeAdjusted"])
        self.assertEqual(self.publisher.events[0].final_grade, "A")

    def test_missing_both_annotation_and_final_grade(self):
        resp = put_review(self.client, request_id="req-v1")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    def test_invalid_final_grade_value(self):
        resp = put_review(self.client, request_id="req-v2", final_grade="F")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    def test_adjustment_reason_optional(self):
        # 缺失理由：正常保存（TD-09/DD-007 可选不强制）。
        resp = put_review(self.client, request_id="req-r1", final_grade="C")
        self.assertEqual(resp.status_code, 200)
        with session_scope(self.eng) as session:
            reason = session.query(GradeAdjustmentRecord).one().adjustment_reason
        self.assertIsNone(reason)
        # 提供理由：随调整记录留痕。
        resp = put_review(
            self.client,
            request_id="req-r2",
            final_grade="A",
            adjustment_reason="复核后上调",
        )
        self.assertEqual(resp.status_code, 200)
        with session_scope(self.eng) as session:
            reasons = [
                r.adjustment_reason
                for r in session.query(GradeAdjustmentRecord)
                .order_by(GradeAdjustmentRecord.created_at)
                .all()
            ]
        self.assertEqual(reasons[-1], "复核后上调")

    def test_response_matches_contract(self):
        contract = load_contract("ct-008.json")
        resp = put_review(
            self.client, request_id="req-c1", annotation="ok", final_grade="A"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body), {"review_record"})
        required = contract["schemas"]["response"]["properties"]["review_record"][
            "required"
        ]
        record = body["review_record"]
        for key in required:
            self.assertIn(key, record)
        self.assertIn(record["final_grade"], ["A", "B", "C", "D", "E"])
        self.assertIsInstance(record["operator"], str)
        self.assertTrue(record["operator"])
        datetime.fromisoformat(record["updated_at"])


class TestCt008Idempotency(unittest.TestCase):
    def setUp(self):
        self.eng = make_engine()
        self.gate = StubAccessGate()
        self.client, self.service = make_client(self.eng, self.gate)
        self.service.create_review_record(submission_id=SUB, original_grade="B")

    def test_same_request_id_returns_same_record(self):
        first = put_review(
            self.client, request_id="req-i1", annotation="批注", final_grade="A"
        )
        self.assertEqual(first.status_code, 200)
        second = put_review(
            self.client, request_id="req-i1", annotation="批注", final_grade="A"
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json(), second.json())
        with session_scope(self.eng) as session:
            self.assertEqual(session.query(ReviewRecord).count(), 1)
            self.assertEqual(session.query(GradeAdjustmentRecord).count(), 1)
            self.assertEqual(session.query(ReviewIdempotencyRecord).count(), 2)

    def test_request_id_reused_on_other_submission_rejected(self):
        self.service.create_review_record(
            submission_id="sub-2", original_grade="C"
        )
        resp = put_review(self.client, request_id="req-x1", annotation="批注")
        self.assertEqual(resp.status_code, 200)
        resp = put_review(
            self.client, submission_id="sub-2", request_id="req-x1", annotation="改"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")


class TestNoOriginalGrade(unittest.TestCase):
    """scoring_failed 且无原始等级：拒设最终等级（禁伪造）；批注仍可保存。"""

    def setUp(self):
        self.eng = make_engine()
        self.gate = StubAccessGate()
        # scoring_failed 路径：PROJECTOR 不调用 M05-IC-01，无 ReviewRecord。
        self.client, self.service = make_client(
            self.eng, self.gate, statuses={SUB_FAILED: "scoring_failed"}
        )

    def test_final_grade_rejected_without_original_grade(self):
        resp = put_review(
            self.client, submission_id=SUB_FAILED, request_id="req-n1",
            final_grade="A",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "NO_ORIGINAL_GRADE")
        # 无部分写入：不产生 ReviewRecord / 调整记录 / 幂等记录。
        with session_scope(self.eng) as session:
            self.assertEqual(session.query(ReviewRecord).count(), 0)
            self.assertEqual(session.query(GradeAdjustmentRecord).count(), 0)
            self.assertEqual(session.query(ReviewIdempotencyRecord).count(), 0)

    def test_annotation_still_saved_without_original_grade(self):
        resp = put_review(
            self.client, submission_id=SUB_FAILED, request_id="req-n2",
            annotation="评分失败，待重试",
        )
        self.assertEqual(resp.status_code, 200)
        record = resp.json()["review_record"]
        self.assertIsNone(record["original_grade"])
        self.assertIsNone(record["final_grade"])
        self.assertEqual(record["annotation"], "评分失败，待重试")
        # 之后仍不得补写最终等级（无原始等级，禁伪造）。
        resp = put_review(
            self.client, submission_id=SUB_FAILED, request_id="req-n3",
            final_grade="B",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "NO_ORIGINAL_GRADE")
        with session_scope(self.eng) as session:
            row = session.query(ReviewRecord).one()
            self.assertIsNone(row.final_grade)

    def test_unknown_submission_not_found(self):
        resp = put_review(
            self.client, submission_id="sub-unknown", request_id="req-n4",
            annotation="批注",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")


class TestAuditTrail(unittest.TestCase):
    """四元组留痕：原始等级复制值不可变；后写为准且调整历史可追。"""

    def setUp(self):
        self.eng = make_engine()
        self.gate = StubAccessGate()
        self.client, self.service = make_client(self.eng, self.gate)
        self.service.create_review_record(submission_id=SUB, original_grade="B")

    def test_original_grade_immutable_and_full_trace(self):
        resp1 = put_review(self.client, request_id="req-t1", final_grade="A")
        self.assertEqual(resp1.status_code, 200)
        resp2 = put_review(self.client, request_id="req-t2", final_grade="C")
        self.assertEqual(resp2.status_code, 200)
        record = resp2.json()["review_record"]
        # 后写为准。
        self.assertEqual(record["final_grade"], "C")
        # 原始等级复制值不被改写；操作者与时间同时保留。
        self.assertEqual(record["original_grade"], "B")
        self.assertEqual(record["operator"], TEACHER)
        datetime.fromisoformat(record["updated_at"])
        # 两次调整记录均可追溯（唯一 adjustment_id + 前后值）。
        rows = adjustments_for(self.eng, record["review_record_id"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r[0] for r in rows}), 2)
        self.assertEqual(
            [(r[1], r[2]) for r in rows],
            [(None, "A"), ("A", "C")],
        )
        for row in rows:
            self.assertEqual(row[3], TEACHER)
            self.assertIsNotNone(row[4])
        with session_scope(self.eng) as session:
            stored = session.query(ReviewRecord).one()
            self.assertEqual(stored.original_grade, "B")


class TestAccessGate(unittest.TestCase):
    def setUp(self):
        self.eng = make_engine()
        self.gate = StubAccessGate()
        self.client, self.service = make_client(self.eng, self.gate)

    def test_forbidden_returns_403_and_gate_called(self):
        self.gate.deny = True
        resp = put_review(self.client, request_id="req-f1", annotation="批注")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "FORBIDDEN")
        self.assertEqual(len(self.gate.calls), 1)
        self.assertEqual(
            self.gate.calls[0]["teacher_session"], "teacher-session-1"
        )
        # 未授权不产生任何写入。
        with session_scope(self.eng) as session:
            self.assertEqual(session.query(ReviewRecord).count(), 0)

    def test_teacher_session_forwarded_to_gate(self):
        self.service.create_review_record(submission_id=SUB, original_grade="B")
        resp = put_review(self.client, request_id="req-f2", annotation="批注")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.gate.calls[0]["submission_id"], SUB)


class TestMic01CreatePort(unittest.TestCase):
    """M05-IC-01：PROJECTOR 幂等创建复核记录端口（本叶子实现）。"""

    def setUp(self):
        self.eng = make_engine()
        self.service = ReviewCommandService(partial(session_scope, self.eng))

    def test_create_is_idempotent_by_submission_id(self):
        first = self.service.create_review_record(
            submission_id=SUB, original_grade="B",
            dimension_rationales=[{"dimension": "论证", "rationale": "充分"}],
        )
        self.assertEqual(first["original_grade"], "B")
        # 重复 scored 事件：返回既有记录，不覆盖原始等级、不追加调整记录。
        second = self.service.create_review_record(
            submission_id=SUB, original_grade="E"
        )
        self.assertEqual(second["review_record_id"], first["review_record_id"])
        self.assertEqual(second["original_grade"], "B")
        with session_scope(self.eng) as session:
            self.assertEqual(session.query(ReviewRecord).count(), 1)
            self.assertEqual(session.query(GradeAdjustmentRecord).count(), 0)
            row = session.query(ReviewRecord).one()
            self.assertEqual(row.original_grade, "B")
            self.assertEqual(
                row.dimension_rationales,
                [{"dimension": "论证", "rationale": "充分"}],
            )

    def test_create_requires_original_grade(self):
        with self.assertRaises(ValidationFailedError):
            self.service.create_review_record(submission_id=SUB, original_grade="")
        with session_scope(self.eng) as session:
            self.assertEqual(session.query(ReviewRecord).count(), 0)


class TestMigration(unittest.TestCase):
    def test_migration_importable_and_revisions(self):
        spec = importlib.util.spec_from_file_location(
            "migration_0007_review_records", MIGRATION
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0007_review_records")
        self.assertEqual(module.down_revision, "b9c6e3d6276a")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
