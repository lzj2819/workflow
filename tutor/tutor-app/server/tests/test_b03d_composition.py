"""T-B03d 组合根冒烟（SQLite + StaticPool + tmp DATA_DIR + 时钟注入）。

链路：L01 预置课程/名单 → L09 auth-token → CT-001 提交（JSON 通道，真实
Xfer→SI-STORE 文件落盘）→ CT-002 received → relayer_tick 投递 CT-006 →
worker 侧手工驱动 ScoringOrchestrator 消费 CT-004（同 smoke_wave2 模式，
CT-005 写入同一 SQL Outbox）→ relayer_tick 投递 CT-005（L02 apply_scoring_outcome
+ projector + M05-IC-01 复核记录）→ 教师登录 → CT-007 详情 → CT-008 调整
（M05-IC-05 同步投影）→ CT-009 快照 → L17 SSR 页面 200 → health/metrics →
relay 重投幂等。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared"), str(ROOT / "worker")]

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import (  # noqa: E402
    OUTBOX_METADATA,
    OUTBOX_RECORDS_TABLE,
    OutboxStore,
    SqlaOutboxStore,
)

from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.models import OrchestratorBase  # noqa: E402
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import DEFAULT_CONTRACTS_DIR, Settings  # noqa: E402
from course_app.submission_intake.api.models import Base as ApiBase  # noqa: E402
from course_app.submission_intake.core.models import Base as CoreBase  # noqa: E402
from course_app.submission_intake.purge.models import Base as PurgeBase  # noqa: E402
from course_app.submission_intake.relay.models import Base as RelayBase  # noqa: E402
from course_app.submission_intake.store.models import Base as StoreBase  # noqa: E402
from course_app.submission_intake.xfer.models import Base as XferBase  # noqa: E402
from course_app.teacher_web.access_gate.models import Base as GateBase  # noqa: E402
from course_app.teacher_web.presentation.models import Base as PresentationBase  # noqa: E402
from course_app.teacher_web.projector.models import Base as ProjectorBase  # noqa: E402
from course_app.teacher_web.retention.models import Base as RetentionBase  # noqa: E402
from course_app.teacher_web.review_command.models import Base as ReviewBase  # noqa: E402

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
COURSE = "c-01"
INVITE = "INV-01"
ACCOUNT = "teacher@example.com"
PASSWORD = "s3cret-口令"
DIMENSIONS = ("需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性")


class _DirectSqlaOutbox(OutboxStore):
    """worker 侧 CT-005 入队（独立小事务提交；测试装配，模拟 result_publisher
    把终态事件写入同一 SQL Outbox 供 SI-RELAY 投递）。"""

    def __init__(self, engine) -> None:
        self._engine = engine

    def enqueue(self, contract_id, payload, dedup_key):
        with self._engine.begin() as conn:
            session = sa.orm.Session(bind=conn)
            return SqlaOutboxStore(session).enqueue(contract_id, payload, dedup_key)

    def fetch_due(self, now, limit=50):  # pragma: no cover - 测试不使用
        raise NotImplementedError

    def mark_confirmed(self, record_id):  # pragma: no cover - 测试不使用
        raise NotImplementedError

    def mark_retry(self, record_id, next_attempt_at=None):  # pragma: no cover
        raise NotImplementedError


def _make_engine():
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for base in (
        RosterBase,
        CoreBase,
        ApiBase,
        XferBase,
        StoreBase,
        RelayBase,
        PurgeBase,
        GateBase,
        ReviewBase,
        ProjectorBase,
        PresentationBase,
        RetentionBase,
        OrchestratorBase,
    ):
        base.metadata.create_all(engine)
    OUTBOX_METADATA.create_all(engine)
    return engine


class CompositionSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        data_dir = Path(self._tmp.name) / "data"
        data_dir.mkdir()
        self.engine = _make_engine()
        self.addCleanup(self.engine.dispose)
        self.now = NOW
        settings = Settings(
            database_url="sqlite:///:memory:",
            data_dir=data_dir,
            contracts_dir=DEFAULT_CONTRACTS_DIR,
            teacher_session_secret="test-secret",
        )
        self.comp = build_composition(settings, engine=self.engine, clock=lambda: self.now)
        self.client = TestClient(create_app(settings, composition=self.comp))
        with self.comp.session_scope() as session:
            admin.provision_course(
                session, course_id=COURSE, invite_code=INVITE, name="VC2026"
            )
            admin.import_roster(
                session,
                course_id=COURSE,
                entries=[{"student_name": "张三", "group_name": "第7组"}],
            )
        self.comp.access_gate.provision_teacher(
            account=ACCOUNT, password=PASSWORD, course_ids=[COURSE]
        )

    # ---- 辅助 ----

    def _tick(self) -> dict:
        """单轮 relay 驱动：now 取真实墙钟（Outbox next_attempt_at 按墙钟入队；
        注入的固定时钟仅用于业务时间戳）。"""
        return self.comp.relayer_tick(datetime.now(timezone.utc) + timedelta(seconds=2))

    def _outbox_payloads(self, contract_id: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(OUTBOX_RECORDS_TABLE.c.payload).where(
                    OUTBOX_RECORDS_TABLE.c.contract_id == contract_id
                )
            ).all()
        return [dict(row[0]) for row in rows]

    def _drive_worker_scored(self, submission_id: str) -> None:
        """worker 侧手工驱动（同 smoke_wave2）：CT-004 → 任务 → scored → CT-005。"""
        ct004 = self._outbox_payloads("CT-004")
        event = next(p for p in ct004 if p["submission_id"] == submission_id)
        sm = sessionmaker(bind=self.engine)
        orch = ScoringOrchestrator(
            session_factory=sm,
            lease_store=SqlaTaskLeaseStore(sm),
            outbox_store=_DirectSqlaOutbox(self.engine),
        )
        orch.handle_submission_received(event)
        self.comp.core_service.advance_to_processing(
            submission_id=submission_id, consumer_ack="task_persisted"
        )
        claimed = orch.claim_task(owner="worker-1")
        orch.complete_assessment(
            claimed.task_id,
            owner="worker-1",
            attempt_no=claimed.attempt_no,
            original_grade="B",
            dimension_rationales=[
                {"dimension": d, "rationale": f"ok {d}"} for d in DIMENSIONS
            ],
            teacher_suggestions=["s1"],
        )

    # ---- 主链路 ----

    def test_full_composition_flow(self) -> None:
        # 1) L01 CT-003 校验（组合根已挂载课程路由）
        verified = self.client.post(
            "/api/v1/courses/verify-membership",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "第7组"},
        )
        self.assertEqual(verified.status_code, 200)
        self.assertTrue(verified.json()["verified"])

        # 2) L09 auth-token → CT-001（JSON 通道）→ received
        token_resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "第7组"},
        )
        self.assertEqual(token_resp.status_code, 200)
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        submission_uuid = uuid.uuid4().hex
        submit = self.client.post(
            "/api/v1/submissions",
            json={
                "submission_uuid": submission_uuid,
                "invite_code": INVITE,
                "student_name": "张三",
                "group_name": "第7组",
                "assignment": "hw-01",
                "material_chunks": [
                    {"category": "对话", "filename": "dialogue.json", "content_ref": "turns"},
                    {"category": "代码", "filename": "main.py", "content_ref": "print('hw')"},
                ],
            },
            headers=headers,
        )
        self.assertEqual(submit.status_code, 200, submit.text)
        self.assertEqual(submit.json()["status"], "received")
        self.assertEqual(set(submit.json()["missing_items"]), {"截图", "结果"})
        submission_id = submit.json()["submission_id"]

        # 3) CT-002 状态查询
        query = self.client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
        self.assertEqual(query.status_code, 200)
        self.assertEqual(query.json()["status"], "received")

        # 4) relayer_tick：CT-006 投递到 projector（读模型收到 received 行）
        tick = self._tick()
        self.assertGreaterEqual(tick["confirmed"], 1)
        teacher_token = self.comp.access_gate.login(account=ACCOUNT, password=PASSWORD)
        bearer = {"Authorization": f"Bearer {teacher_token}"}
        detail_received = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{submission_id}",
            headers=bearer,
        )
        self.assertEqual(detail_received.status_code, 200, detail_received.text)
        self.assertEqual(detail_received.json()["status"], "received")

        # 5) worker 侧手工驱动 CT-004 消费链路 → CT-005 入队（同一 SQL Outbox）
        self._drive_worker_scored(submission_id)

        # 6) relayer_tick：CT-005 → L02 scored + projector + M05-IC-01 复核记录
        tick = self._tick()
        self.assertGreaterEqual(tick["confirmed"], 1)
        final_query = self.client.get(
            f"/api/v1/submissions/{submission_uuid}", headers=headers
        )
        self.assertEqual(final_query.json()["status"], "scored")

        # 7) CT-007 提交详情：original_grade=B，deletion_batches[] 完整性
        detail = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{submission_id}",
            headers=bearer,
        )
        self.assertEqual(detail.status_code, 200, detail.text)
        body = detail.json()
        self.assertEqual(body["original_grade"], "B")
        self.assertEqual(body["status"], "scored")
        self.assertEqual(body["deletion_batches"], [])

        # 8) CT-008 调整：final_grade=A + 批注（M05-IC-05 同步投影到读模型）
        review = self.client.put(
            f"/api/v1/teacher/submissions/{submission_id}/review",
            json={
                "request_id": uuid.uuid4().hex,
                "annotation": "过程扎实",
                "final_grade": "A",
            },
            headers=bearer,
        )
        self.assertEqual(review.status_code, 200, review.text)
        detail_after = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{submission_id}",
            headers=bearer,
        ).json()
        self.assertEqual(detail_after["final_grade"], "A")
        self.assertTrue(
            any("过程扎实" in (a.get("text") or "") for a in detail_after["annotations"])
        )

        # 9) CT-009 展示快照
        pres = self.client.post(
            "/api/v1/teacher/presentations",
            json={"group_ids": ["第7组"]},
            headers=bearer,
        )
        self.assertEqual(pres.status_code, 200, pres.text)
        self.assertTrue(pres.json()["presentation_id"])

        # 10) L17 SSR：登录 → 课程页 / 提交详情页 200（含批注与最终等级）
        login = self.client.post(
            "/teacher/login",
            data={"teacher_account": ACCOUNT, "password": PASSWORD},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303)
        self.assertIn("teacher_session", login.cookies)
        courses_page = self.client.get("/teacher/courses")
        self.assertEqual(courses_page.status_code, 200)
        self.assertIn(COURSE, courses_page.text)
        detail_page = self.client.get(f"/teacher/submissions/{submission_id}")
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn("过程扎实", detail_page.text)

    def test_health_and_metrics(self) -> None:
        live = self.client.get("/health/live")
        self.assertEqual(live.status_code, 200)
        self.assertEqual(live.json()["status"], "ok")
        ready = self.client.get("/health/ready")
        self.assertEqual(ready.status_code, 200)
        body = ready.json()
        self.assertEqual(body["status"], "ready", body)
        self.assertEqual(body["checks"]["database"]["status"], "ok")
        metrics = self.client.get("/metrics")
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("text/plain", metrics.headers["content-type"])

    def test_relayer_tick_idempotent_replay(self) -> None:
        """relayer_tick 驱动一轮后，重复 tick 不重复应用（InboundDedup）。"""
        token_resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "第7组"},
        )
        headers = {"Authorization": f"Bearer {token_resp.json()['access_token']}"}
        submission_uuid = uuid.uuid4().hex
        submit = self.client.post(
            "/api/v1/submissions",
            json={
                "submission_uuid": submission_uuid,
                "invite_code": INVITE,
                "student_name": "张三",
                "group_name": "第7组",
                "assignment": "hw-02",
                "material_chunks": [
                    {"category": "对话", "filename": "d.json", "content_ref": "x"},
                ],
            },
            headers=headers,
        )
        submission_id = submit.json()["submission_id"]
        self._drive_worker_scored(submission_id)
        self._tick()
        # 清空 due：第二轮 tick 应无可确认（CT-004 已在退避中，CT-005/006 已确认）
        tick = self._tick()
        self.assertEqual(tick["confirmed"], 0)
        teacher_token = self.comp.access_gate.login(account=ACCOUNT, password=PASSWORD)
        detail = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{submission_id}",
            headers={"Authorization": f"Bearer {teacher_token}"},
        ).json()
        self.assertEqual(detail["status"], "scored")
        self.assertEqual(detail["original_grade"], "B")


if __name__ == "__main__":
    unittest.main()
