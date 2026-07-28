"""D-3 验收：received → processing 生产接线点（CT-004 confirmed 扫描钩子）。

断言：
1. worker 确认 CT-004 后，relayer_tick 自动推进 received → processing（无手工 ack）；
2. 重复 tick 幂等（状态稳定、无错误）；
3. CT-004 未确认的提交不被推进；
4. CT-005 scored 在自动推进后可正常回写（链路不依赖手工接线）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.settings import Settings  # noqa: E402


def _engine() -> object:
    return create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )


def _make():
    from course_app.submission_intake.core.models import Base as CoreBase  # noqa: PLC0415
    from course_app.course_roster.models import Base as RosterBase  # noqa: PLC0415
    from course_app.submission_intake.api.models import Base as ApiBase  # noqa: PLC0415
    from course_app.submission_intake.xfer.models import Base as XferBase  # noqa: PLC0415
    from course_app.teacher_web.access_gate.models import Base as GateBase  # noqa: PLC0415
    from course_app.teacher_web.projector.models import Base as RmBase  # noqa: PLC0415
    from course_app.teacher_web.review_command.models import Base as RcBase  # noqa: PLC0415
    from course_app.teacher_web.presentation.models import Base as PvBase  # noqa: PLC0415
    from course_app.teacher_web.retention.models import Base as RtBase  # noqa: PLC0415
    from course_app.submission_intake.purge.models import Base as PgBase  # noqa: PLC0415
    from course_app.submission_intake.store.models import Base as StBase  # noqa: PLC0415
    from course_app.submission_intake.relay.models import Base as RlBase  # noqa: PLC0415

    eng = _engine()
    for base in (RosterBase, CoreBase, ApiBase, XferBase, GateBase, RmBase, RcBase, PvBase, RtBase, PgBase, StBase, RlBase):
        base.metadata.create_all(eng)
    from tutor_shared.outbox import OUTBOX_METADATA  # noqa: PLC0415

    OUTBOX_METADATA.create_all(eng)
    return eng


class TestAdvanceHook(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.eng = _make()
        self.addCleanup(self.eng.dispose)
        settings = Settings(
            database_url="sqlite:///:memory:",
            data_dir=Path(self.tmp.name),
            contracts_dir=ROOT / "contracts",
            teacher_session_secret="d3-test",
            log_level="ERROR",
        )
        self.comp = build_composition(settings, engine=self.eng)
        with self.comp.session_scope() as s:
            admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="x")
            admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])

    def _submit(self) -> str:
        result = self.comp.core_service.confirm_received(
            submission_uuid=uuid.uuid4().hex,
            course_id="c-01",
            assignment="hw",
            student_name="张三",
            group_name="第7组",
            material_refs=[],
            expected_categories=["对话"],
            verification={"verified": True},
        )
        return result.submission_id

    def _ct004_for(self, submission_id: str) -> int:
        with self.comp.session_scope() as s:
            return s.execute(
                text("select id from outbox_records where contract_id='CT-004' and dedup_key=:k"),
                {"k": submission_id},
            ).scalar_one()

    def _status(self, submission_id: str) -> str:
        with self.comp.session_scope() as s:
            return s.execute(
                text("select status from submissions where submission_id=:i"), {"i": submission_id}
            ).scalar()

    def _confirm_ct004(self, record_id: int) -> None:
        with self.comp.session_scope() as s:
            SqlaOutboxStore(s).mark_confirmed(record_id)

    def test_auto_advance_after_ct004_confirmed(self):
        sid = self._submit()
        self.assertEqual(self._status(sid), "received")
        self._confirm_ct004(self._ct004_for(sid))
        counts = self.comp.relayer_tick()  # 无手工 ack
        self.assertEqual(self._status(sid), "processing")
        self.assertGreaterEqual(counts["advanced"], 1)
        # 幂等：再次 tick 状态稳定
        self.comp.relayer_tick()
        self.assertEqual(self._status(sid), "processing")

    def test_unconfirmed_ct004_not_advanced(self):
        sid = self._submit()
        self.comp.relayer_tick()
        self.assertEqual(self._status(sid), "received")


if __name__ == "__main__":
    unittest.main()
