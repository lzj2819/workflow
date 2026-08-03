"""T-B03b READMODEL-PROJECTOR 单元测试（SQLite 内存库）。

覆盖任务验收面：
- 三事件投影：CT-006 列表/状态 → CT-005 scored（五维/建议/等级）→ M05-IC-05
  批注/最终等级投影；
- 幂等消费：重复 CT-006/CT-005 不改投影；旧状态事件不回退终态；M05-IC-05 按
  adjustment_id 去重；
- M05-IC-01：scored 经注入的 L14 create_review_record 幂等建复核记录
  （真实 L14 服务，重复 scored 不新增记录）；
- 失败投影：scoring_failed 投影 failure_reason + retry_record，不写等级；
- CT-014/CT-012 清除 + 重放守卫：清除后重放旧事件不重建已清除数据；
- 双侧面输出形状：query() 返回 L15 ReadModelView、group_view() 返回 L16
  GroupReadView/SubmissionView/MaterialRef/AnnotationView，字段与端口
  dataclass 对照；小组无记录返回 None；已清除提交不出现；
- 位点同事务：handler 失败投影与位点整体回滚；成功则位点等于 record_id；
- 重放：replay() 从事件序列重建投影并重置位点；
- 迁移 0013 可导入、revision/down_revision 正确、upgrade/downgrade 可执行。
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402

from tutor_shared.outbox import OutboxRecord  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.teacher_web.presentation import ports as l16_ports  # noqa: E402
from course_app.teacher_web.projector import (  # noqa: E402
    Base as ProjectorBase,
    ProjectionCheckpoint,
    ProjectorReadModel,
    ProjectorValidationError,
    ReadModelProjector,
    RmPurgeTombstone,
    RmSubmission,
)
from course_app.teacher_web.review_command.models import (  # noqa: E402
    Base as ReviewBase,
    ReviewRecord,
)
from course_app.teacher_web.review_command.ports import ReviewEvent  # noqa: E402
from course_app.teacher_web.review_command.service import (  # noqa: E402
    ReviewCommandService,
)
from course_app.teacher_web.review_query import ports as l15_ports  # noqa: E402

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
COURSE = "c-01"
GROUP = "第7组"
STUDENT = "张三"
SUB = "sub-001"
SUB2 = "sub-002"

DIMENSIONS = ("需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性")


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    ProjectorBase.metadata.create_all(eng)
    ReviewBase.metadata.create_all(eng)
    return eng


def ct006(submission_id=SUB, *, status="received", record_id=1, missing=("截图", "结果")):
    return OutboxRecord(
        record_id=record_id,
        contract_id="CT-006",
        payload={
            "submission_id": submission_id,
            "course_id": COURSE,
            "assignment": "hw-01",
            "student_name": STUDENT,
            "group_name": GROUP,
            "status": status,
            "missing_items": list(missing),
            "received_at": NOW.isoformat(),
            "v": 1,
        },
        dedup_key=submission_id,
    )


def ct005_scored(submission_id=SUB, *, record_id=2, grade="B"):
    return OutboxRecord(
        record_id=record_id,
        contract_id="CT-005",
        payload={
            "submission_id": submission_id,
            "outcome": "scored",
            "original_grade": grade,
            "dimension_rationales": [
                {"dimension": d, "rationale": f"ok {d}"} for d in DIMENSIONS
            ],
            "teacher_suggestions": ["建议一"],
            "scored_at": NOW.isoformat(),
            "v": 1,
        },
        dedup_key=f"{submission_id}:scored",
    )


def ct005_failed(submission_id=SUB2, *, record_id=3):
    return OutboxRecord(
        record_id=record_id,
        contract_id="CT-005",
        payload={
            "submission_id": submission_id,
            "outcome": "scoring_failed",
            "failure_reason": "MODEL_TIMEOUT",
            "retry_record": {
                "attempts": 2,
                "last_error": "MODEL_TIMEOUT",
                "retried_at": NOW.isoformat(),
            },
            "v": 1,
        },
        dedup_key=f"{submission_id}:scoring_failed",
    )


def ct014(submission_ids=(SUB,), *, record_id=10, batch_id="batch-1"):
    return OutboxRecord(
        record_id=record_id,
        contract_id="CT-014",
        payload={
            "batch_id": batch_id,
            "purged_submission_ids": list(submission_ids),
            "failed_items": [],
            "purged_at": NOW.isoformat(),
            "v": 1,
        },
        dedup_key=f"{batch_id}:{NOW.isoformat()}",
    )


def ct012(submission_ids=(SUB,), *, record_id=11, batch_id="batch-2"):
    return OutboxRecord(
        record_id=record_id,
        contract_id="CT-012",
        payload={
            "batch_id": batch_id,
            "submission_ids": list(submission_ids),
            "scope": "course:" + COURSE,
            "operator": "teacher-1",
            "executed_at": NOW.isoformat(),
            "audit_record_id": "audit-1",
            "v": 1,
        },
        dedup_key=batch_id,
    )


def review_events(submission_id=SUB, adjustment_id="adj-1"):
    return [
        ReviewEvent(
            event_type="AnnotationSaved",
            submission_id=submission_id,
            adjustment_id=adjustment_id,
            operator="teacher-1",
            updated_at=NOW.isoformat(),
            annotation_excerpt="过程扎实",
        ),
        ReviewEvent(
            event_type="GradeAdjusted",
            submission_id=submission_id,
            adjustment_id=adjustment_id + "-g",
            operator="teacher-1",
            updated_at=NOW.isoformat(),
            final_grade="A",
        ),
    ]


class ProjectorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        self.addCleanup(self.eng.dispose)
        self.sf = partial(session_scope, self.eng)
        self.review_svc = ReviewCommandService(self.sf)
        self.projector = ReadModelProjector(
            self.sf, create_review_record=self.review_svc.create_review_record
        )
        self.read_model = ProjectorReadModel(self.sf)

    def row(self, submission_id=SUB) -> RmSubmission | None:
        with self.sf() as session:
            row = session.get(RmSubmission, submission_id)
            if row is not None:
                session.expunge(row)
            return row

    def checkpoint(self, consumer: str) -> int:
        with self.sf() as session:
            row = session.get(ProjectionCheckpoint, consumer)
            return row.position if row is not None else 0


class TestThreeEventProjection(ProjectorTestCase):
    def test_ct006_ct005_mic05_projection(self):
        self.projector.handle(ct006())
        self.projector.handle(ct005_scored())
        self.projector.publish(review_events())

        row = self.row()
        self.assertEqual(row.status, "scored")
        self.assertEqual(row.course_id, COURSE)
        self.assertEqual(row.group_id, GROUP)
        self.assertEqual(row.student_name, STUDENT)
        self.assertEqual(tuple(row.missing_items), ("截图", "结果"))
        self.assertEqual(row.original_grade, "B")
        self.assertEqual(len(row.dimension_rationales), 5)
        self.assertEqual(tuple(row.teacher_suggestions), ("建议一",))
        self.assertEqual(row.final_grade, "A")
        self.assertEqual(len(row.annotations), 1)
        self.assertEqual(row.annotations[0]["text"], "过程扎实")
        self.assertEqual(row.annotations[0]["operator"], "teacher-1")

    def test_ct005_before_ct006_keeps_terminal_status(self):
        # 跨流顺序不保证：CT-005 先到时先建行，CT-006 回填身份且不回退终态
        self.projector.handle(ct005_scored(record_id=1))
        self.projector.handle(ct006(record_id=2))
        row = self.row()
        self.assertEqual(row.status, "scored")
        self.assertEqual(row.course_id, COURSE)
        self.assertEqual(row.group_id, GROUP)


class TestIdempotentConsumption(ProjectorTestCase):
    def test_duplicate_events_do_not_change_projection(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        first = self.row()
        # 重放同一业务事件（不同 outbox record_id）
        self.projector.handle(ct006(record_id=5))
        self.projector.handle(ct005_scored(record_id=6))
        second = self.row()
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.original_grade, second.original_grade)
        self.assertEqual(first.updated_at, second.updated_at)
        self.assertEqual(
            first.dimension_rationales, second.dimension_rationales
        )

    def test_stale_ct006_does_not_downgrade_terminal(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        self.projector.handle(ct006(record_id=3, status="received"))
        self.assertEqual(self.row().status, "scored")

    def test_conflicting_terminal_keeps_first(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        self.projector.handle(ct005_failed(SUB, record_id=3))
        row = self.row()
        self.assertEqual(row.status, "scored")
        self.assertEqual(row.original_grade, "B")
        self.assertIsNone(row.failure_reason)

    def test_mic05_duplicate_adjustment_id_ignored(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        self.projector.publish(review_events())
        self.projector.publish(review_events())  # 重放同 adjustment_id
        row = self.row()
        self.assertEqual(len(row.annotations), 1)
        self.assertEqual(row.final_grade, "A")

    def test_mic05_shared_adjustment_id_both_events_applied(self):
        # 回归（T-B03d 缺陷见证修复）：一次「批注+等级」调整的两事件共用同一
        # adjustment_id，去重键为 (adjustment_id, event_type)，两条都必须应用
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        shared = [
            ReviewEvent(
                event_type="AnnotationSaved",
                submission_id=SUB,
                adjustment_id="adj-shared",
                operator="teacher-1",
                updated_at=NOW.isoformat(),
                annotation_excerpt="过程扎实",
            ),
            ReviewEvent(
                event_type="GradeAdjusted",
                submission_id=SUB,
                adjustment_id="adj-shared",
                operator="teacher-1",
                updated_at=NOW.isoformat(),
                final_grade="A",
            ),
        ]
        self.projector.publish(shared)
        self.projector.publish(shared)  # 整组重放仍幂等
        row = self.row()
        self.assertEqual(len(row.annotations), 1)
        self.assertEqual(row.final_grade, "A")


class TestMic01ReviewRecord(ProjectorTestCase):
    def test_scored_creates_review_record_idempotently(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        self.projector.handle(ct005_scored(record_id=3))  # 重放
        with self.sf() as session:
            records = session.scalars(
                sa.select(ReviewRecord).where(ReviewRecord.submission_id == SUB)
            ).all()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].original_grade, "B")

    def test_scoring_failed_does_not_create_review_record(self):
        self.projector.handle(ct006(SUB2, record_id=1))
        self.projector.handle(ct005_failed(SUB2, record_id=2))
        with self.sf() as session:
            count = session.scalar(sa.select(sa.func.count(ReviewRecord.review_record_id)))
        self.assertEqual(count, 0)


class TestFailureProjection(ProjectorTestCase):
    def test_scoring_failed_projection(self):
        self.projector.handle(ct006(SUB2, record_id=1))
        self.projector.handle(ct005_failed(SUB2, record_id=2))
        row = self.row(SUB2)
        self.assertEqual(row.status, "scoring_failed")
        self.assertEqual(row.failure_reason, "MODEL_TIMEOUT")
        self.assertEqual(row.retry_record["attempts"], 2)
        self.assertIsNone(row.original_grade)
        self.assertIsNone(row.final_grade)

        view = self.read_model.query(submission_id=SUB2)
        self.assertEqual(view.status, "scoring_failed")
        self.assertEqual(view.failure_reason, "MODEL_TIMEOUT")
        self.assertEqual(view.retry_record["last_error"], "MODEL_TIMEOUT")
        self.assertIsNone(view.original_grade)
        self.assertIsNone(view.final_grade)


class TestPurgeAndReplayGuard(ProjectorTestCase):
    def _seed(self):
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))

    def test_ct014_clears_projection_and_tombstones(self):
        self._seed()
        self.projector.handle(ct014(record_id=10))
        self.assertIsNone(self.row())
        with self.sf() as session:
            tomb = session.get(RmPurgeTombstone, SUB)
            self.assertIsNotNone(tomb)
            self.assertEqual(tomb.batch_id, "batch-1")
        # 读模型两侧面均不可见
        self.assertEqual(self.read_model.query(submission_id=SUB).submissions, ())
        group = self.read_model.group_view(group_id=GROUP)
        self.assertEqual(group.submissions, ())

    def test_replay_guard_old_events_do_not_rebuild(self):
        self._seed()
        self.projector.handle(ct014(record_id=10))
        # 重放旧事件（同载荷、更高 record_id）：不重建已清除数据
        self.projector.handle(ct006(record_id=20))
        self.assertIsNone(self.row())
        self.projector.handle(ct005_scored(record_id=21))
        self.assertIsNone(self.row())
        self.assertEqual(self.read_model.query(submission_id=SUB).submissions, ())

    def test_ct012_self_consume_clears_rows(self):
        self._seed()
        self.projector.handle(ct012(record_id=11))
        self.assertIsNone(self.row())
        with self.sf() as session:
            self.assertIsNotNone(session.get(RmPurgeTombstone, SUB))
        # CT-012 重复消费为空操作
        self.projector.handle(ct012(record_id=12))
        self.assertIsNone(self.row())

    def test_ct014_idempotent_repeat(self):
        self._seed()
        self.projector.handle(ct014(record_id=10))
        self.projector.handle(ct014(record_id=13))
        self.assertIsNone(self.row())


class TestDualFacetShapes(ProjectorTestCase):
    def setUp(self):
        super().setUp()
        self.projector.handle(ct006(record_id=1))
        self.projector.handle(ct005_scored(record_id=2))
        self.projector.handle(ct006(SUB2, record_id=3))
        self.projector.handle(ct005_failed(SUB2, record_id=4))
        self.projector.publish(review_events())

    def test_query_returns_l15_readmodelview_shape(self):
        view = self.read_model.query(course_id=COURSE, submission_id=SUB)
        self.assertIsInstance(view, l15_ports.ReadModelView)
        # 与 L15 端口 dataclass 字段完全对照（无多无少由构造保证）
        field_names = {f.name for f in l15_ports.ReadModelView.__dataclass_fields__.values()}
        self.assertEqual(
            field_names,
            {
                "courses", "groups", "students", "submissions", "material_refs",
                "status", "original_grade", "dimension_rationales",
                "teacher_suggestions", "annotations", "final_grade",
                "missing_marks", "failure_reason", "retry_record",
            },
        )
        self.assertEqual(view.status, "scored")
        self.assertEqual(view.original_grade, "B")
        self.assertEqual(view.final_grade, "A")
        self.assertEqual(view.missing_marks, ("截图", "结果"))
        self.assertEqual(len(view.dimension_rationales), 5)
        self.assertEqual(view.teacher_suggestions, ("建议一",))
        self.assertEqual(view.annotations[0]["text"], "过程扎实")
        self.assertEqual(view.courses, ({"course_id": COURSE},))
        self.assertEqual(view.groups, ({"course_id": COURSE, "group_id": GROUP},))
        self.assertEqual(
            view.students,
            ({"course_id": COURSE, "group_id": GROUP, "student_name": STUDENT},),
        )
        sub = view.submissions[0]
        self.assertEqual(sub["submission_id"], SUB)
        self.assertEqual(sub["status"], "scored")

    def test_query_selectors_filter(self):
        view = self.read_model.query(course_id=COURSE, student_id=STUDENT)
        self.assertEqual(len(view.submissions), 2)
        empty = self.read_model.query(course_id=COURSE, student_id="不存在")
        self.assertEqual(empty.submissions, ())
        self.assertEqual(empty.students, ())

    def test_group_view_returns_l16_shape(self):
        view = self.read_model.group_view(group_id=GROUP)
        self.assertIsInstance(view, l16_ports.GroupReadView)
        self.assertEqual(view.course_id, COURSE)
        self.assertEqual(view.group_id, GROUP)
        self.assertTrue(view.read_model_version)
        self.assertEqual(len(view.submissions), 2)
        for sub in view.submissions:
            self.assertIsInstance(sub, l16_ports.SubmissionView)
        scored = next(s for s in view.submissions if s.submission_id == SUB)
        self.assertEqual(scored.original_grade, "B")
        self.assertEqual(scored.final_grade, "A")
        self.assertEqual(scored.missing_marks, ("截图", "结果"))
        self.assertEqual(scored.student_id, STUDENT)
        self.assertIsNotNone(scored.submitted_at)
        self.assertEqual(len(scored.dimension_rationales), 5)
        self.assertEqual(scored.teacher_suggestions, ("建议一",))
        self.assertIsInstance(scored.annotations[0], l16_ports.AnnotationView)
        self.assertEqual(scored.annotations[0].operator, "teacher-1")
        self.assertEqual(scored.annotations[0].excerpt, "过程扎实")
        failed = next(s for s in view.submissions if s.submission_id == SUB2)
        self.assertEqual(failed.status, "scoring_failed")
        self.assertIsNone(failed.original_grade)

    def test_group_view_unknown_group_returns_none(self):
        self.assertIsNone(self.read_model.group_view(group_id="第99组"))


class TestCheckpointTransaction(ProjectorTestCase):
    def test_checkpoint_advances_with_projection(self):
        self.projector.handle(ct006(record_id=7))
        self.assertEqual(self.checkpoint("CT-006"), 7)
        self.projector.handle(ct005_scored(record_id=9))
        self.assertEqual(self.checkpoint("CT-005"), 9)

    def test_handler_failure_rolls_back_projection_and_checkpoint(self):
        def boom(**kwargs):
            raise RuntimeError("L14 unavailable")

        projector = ReadModelProjector(self.sf, create_review_record=boom)
        with self.assertRaises(RuntimeError):
            projector.handle(ct005_scored(record_id=5))
        self.assertIsNone(self.row())
        self.assertEqual(self.checkpoint("CT-005"), 0)

    def test_invalid_payload_rejected(self):
        bad = ct005_scored(record_id=5, grade="Z")
        with self.assertRaises(ProjectorValidationError):
            self.projector.handle(bad)
        self.assertIsNone(self.row())
        self.assertEqual(self.checkpoint("CT-005"), 0)

    def test_handlers_registration_shape(self):
        handlers = self.projector.handlers()
        self.assertEqual(
            set(handlers), {"CT-005", "CT-006", "CT-012", "CT-014", "CT-015"}
        )
        for handler in handlers.values():
            self.assertTrue(callable(handler))


class TestReplay(ProjectorTestCase):
    def test_replay_rebuilds_projection_and_resets_position(self):
        events = [ct006(record_id=1), ct005_scored(record_id=2)]
        for record in events:
            self.projector.handle(record)
        self.projector.publish(review_events())
        # 破坏读模型后重放重建
        with self.sf() as session:
            session.query(RmSubmission).delete()
        counts = self.projector.replay(events)
        self.assertEqual(counts, {"CT-006": 1, "CT-005": 1})
        row = self.row()
        self.assertEqual(row.status, "scored")
        self.assertEqual(row.original_grade, "B")
        self.assertEqual(self.checkpoint("CT-006"), 1)
        self.assertEqual(self.checkpoint("CT-005"), 2)

    def test_replay_with_purge_sequence_keeps_guard(self):
        events = [
            ct006(record_id=1),
            ct005_scored(record_id=2),
            ct014(record_id=10),
            ct006(record_id=20),  # 清除后的旧事件重放
        ]
        self.projector.replay(events)
        self.assertIsNone(self.row())
        with self.sf() as session:
            self.assertIsNotNone(session.get(RmPurgeTombstone, SUB))


class TestMigration0013(unittest.TestCase):
    def _load_module(self):
        path = ROOT / "server" / "migrations" / "versions" / "0013_read_model.py"
        spec = importlib.util.spec_from_file_location("mig_0013_read_model", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_identifiers(self):
        module = self._load_module()
        self.assertEqual(module.revision, "0013_read_model")
        self.assertEqual(module.down_revision, "11a22f91f4b3")

    def test_upgrade_downgrade_on_sqlite(self):
        module = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            eng = sa.create_engine(f"sqlite:///{Path(tmp) / 'mig.db'}")
            with eng.connect() as conn:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    module.upgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    for name in (
                        "rm_courses",
                        "rm_groups",
                        "rm_students",
                        "rm_submissions",
                        "rm_purge_tombstones",
                        "projection_checkpoints",
                    ):
                        self.assertIn(name, tables)
                    module.downgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    for name in (
                        "rm_courses",
                        "rm_groups",
                        "rm_students",
                        "rm_submissions",
                        "rm_purge_tombstones",
                        "projection_checkpoints",
                    ):
                        self.assertNotIn(name, tables)
            eng.dispose()


if __name__ == "__main__":
    unittest.main()
