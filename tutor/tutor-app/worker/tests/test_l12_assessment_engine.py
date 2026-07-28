"""L12 CMP-ASSESSMENT-ENGINE 测试。

覆盖 verification-checklist 语义断言：
- 完整链路：ClaimedTask 上下文 → ICT-002 提示组装 → ICT-003 材料加载 →
  FakeModelProvider.evaluate → CT-010 应答校验 → ICT-005 结果装配；
- CT-010 请求数据最小化：不含 submission_id/student_name/group_name/course_id；
- 非法应答 → INVALID_RESPONSE_SCHEMA（ICT-006）；
- MODEL_TIMEOUT / MODEL_ERROR / MATERIAL_UNREADABLE / PROMPT_ASSEMBLY_FAILED 分类；
- missing_items 非空 → 结果含缺失材料影响说明；
- 成功/失败输出与 L03 complete_assessment / fail_assessment 真实调用兼容（SQLite 内存库）；
- fake 来源在结果 model_meta 与日志中可追溯，不假扮真实评估。

仅使用 FakeModelProvider 与测试内 stub 端口；无网络、无真实供应商。
"""
from __future__ import annotations

import inspect
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

from assessment_worker.assessment_engine import (  # noqa: E402
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MATERIAL_UNREADABLE,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    ERROR_PROMPT_ASSEMBLY_FAILED,
    AssessmentEngine,
    MaterialUnreadableError,
    PromptAssemblyFailedError,
    build_missing_materials_impact,
)
from assessment_worker.model_provider import (  # noqa: E402
    DIMENSIONS,
    GRADES,
    FakeModelProvider,
    ModelProviderError,
    validate_request,
)
from assessment_worker.scoring_orchestrator import (  # noqa: E402
    OrchestratorBase,
    OutcomeCommitted,
    RetryEntered,
    ScoringOrchestrator,
    ScoringTask,
    SqlaTaskLeaseStore,
)

T0 = datetime(2026, 7, 20, 1, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------- stubs


class StubPromptComposer:
    """ICT-002 stub：固定输出版本化提示；可配置为抛出组装失败。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    def compose(self, assignment: str, material_refs: list, missing_items: list) -> dict:
        self.calls.append(
            {
                "assignment": assignment,
                "material_refs": material_refs,
                "missing_items": missing_items,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "evaluation_prompt": "fake prompt: 按五维度评估该提交",
            "prompt_version": "p1",
            "rubric_version": "r1",
        }


class StubMaterialReader:
    """ICT-003 stub：按类别返回材料内容；可配置为抛出不可读错误。"""

    def __init__(
        self,
        materials: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        self.materials = materials if materials is not None else {
            "对话": "学生与 Codex 的对话摘要",
            "代码": "def main(): ...",
            "结果描述": "程序输出符合预期",
        }
        self.error = error
        self.calls: list[list] = []

    def load(self, material_refs: list) -> dict:
        self.calls.append(material_refs)
        if self.error is not None:
            raise self.error
        return {"materials": dict(self.materials), "readability": ["ok"] * len(material_refs)}


class RecordingFakeProvider(FakeModelProvider):
    """记录入参的 FakeModelProvider（仍为 fake：无网络、确定性输出）。"""

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def evaluate(self, request: dict) -> dict:
        self.requests.append(request)
        return super().evaluate(request)


class InvalidSchemaProvider:
    """返回不满足 CT-010 response schema 的应答（测试用 stub，非真实供应商）。"""

    def evaluate(self, request: dict) -> dict:
        return {
            "grade": "Z",
            "dimension_rationales": [
                {"dimension": d, "rationale": "x"} for d in DIMENSIONS[:4]
            ],
            "suggestions": [],
        }


class TimeoutStubProvider:
    def evaluate(self, request: dict) -> dict:
        raise TimeoutError("simulated model timeout")


class ErrorStubProvider:
    def evaluate(self, request: dict) -> dict:
        raise ModelProviderError("simulated provider failure")


# --------------------------------------------------------------------- helpers


def make_task(missing_items: list | None = None, attempt_no: int = 1) -> SimpleNamespace:
    """L03 ClaimedTask 形状（duck-typed）；刻意携带业务标识以验证不外泄。"""
    return SimpleNamespace(
        task_id="task-1",
        submission_id="sub-1",
        course_id="course-1",
        assignment="实现命令行待办管理器",
        material_refs=[
            {"category": "代码", "ref": "materials/sub-1/main.py"},
            {"category": "对话", "ref": "materials/sub-1/dialogue.md"},
        ],
        missing_items=[] if missing_items is None else missing_items,
        attempt_no=attempt_no,
    )


def make_engine(provider=None, composer=None, reader=None) -> AssessmentEngine:
    return AssessmentEngine(
        prompt_composer=composer or StubPromptComposer(),
        material_reader=reader or StubMaterialReader(),
        model_provider=provider or FakeModelProvider(),
    )


# ----------------------------------------------------------------------- tests


class FullPipelineTests(unittest.TestCase):
    def test_full_pipeline_success(self):
        provider = RecordingFakeProvider()
        outcome = make_engine(provider=provider).run(make_task())

        self.assertTrue(outcome.ok)
        payload = outcome.payload
        self.assertIn(payload["original_grade"], GRADES)
        self.assertEqual(len(payload["dimension_rationales"]), 5)
        self.assertEqual(
            sorted(r["dimension"] for r in payload["dimension_rationales"]),
            sorted(DIMENSIONS),
        )
        self.assertTrue(all(r["rationale"] for r in payload["dimension_rationales"]))
        self.assertTrue(payload["teacher_suggestions"])
        self.assertIsInstance(payload["scored_at"], datetime)
        self.assertEqual(payload["prompt_version"], "p1")
        self.assertEqual(payload["rubric_version"], "r1")
        meta = payload["model_meta"]
        self.assertTrue(meta["request_id"])
        self.assertIn("duration_ms", meta)
        self.assertEqual(meta["attempt_no"], 1)
        # 端口被按需调用：组装先于材料加载先于模型调用
        self.assertEqual(len(provider.requests), 1)

    def test_ct010_request_data_minimization(self):
        provider = RecordingFakeProvider()
        make_engine(provider=provider).run(make_task())

        self.assertEqual(len(provider.requests), 1)
        request = provider.requests[0]
        self.assertEqual(validate_request(request), [])
        self.assertEqual(
            set(request), {"evaluation_prompt", "materials", "request_id"}
        )
        for forbidden in (
            "submission_id",
            "student_name",
            "group_name",
            "course_id",
            "invite_code",
        ):
            self.assertNotIn(forbidden, request)
        self.assertEqual(
            set(request["materials"]),
            {"dialogue_summary", "code", "result_description"},
        )
        # request_id 不携带任何业务标识
        self.assertNotIn("sub-1", request["request_id"])
        self.assertNotIn("task-1", request["request_id"])

    def test_invalid_response_schema_classification(self):
        outcome = make_engine(provider=InvalidSchemaProvider()).run(make_task())

        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error_kind, ERROR_INVALID_RESPONSE_SCHEMA)
        self.assertEqual(
            set(outcome.payload), {"error_kind", "attempt_no", "at"}
        )
        self.assertEqual(outcome.payload["error_kind"], ERROR_INVALID_RESPONSE_SCHEMA)

    def test_model_timeout_classification(self):
        outcome = make_engine(provider=TimeoutStubProvider()).run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.payload["error_kind"], ERROR_MODEL_TIMEOUT)

    def test_model_error_classification(self):
        outcome = make_engine(provider=ErrorStubProvider()).run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.payload["error_kind"], ERROR_MODEL_ERROR)

    def test_prompt_assembly_failed_classification(self):
        composer = StubPromptComposer(error=PromptAssemblyFailedError("rubric missing"))
        outcome = make_engine(composer=composer).run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.payload["error_kind"], ERROR_PROMPT_ASSEMBLY_FAILED)

    def test_material_unreadable_classification(self):
        reader = StubMaterialReader(error=MaterialUnreadableError("io error"))
        outcome = make_engine(reader=reader).run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.payload["error_kind"], ERROR_MATERIAL_UNREADABLE)

    def test_missing_items_impact_present(self):
        outcome = make_engine().run(make_task(missing_items=["截图", "结果描述"]))

        self.assertTrue(outcome.ok)
        impact = outcome.payload["missing_materials_impact"]
        self.assertIsInstance(impact, str)
        self.assertIn("截图", impact)
        self.assertIn("结果描述", impact)

    def test_missing_items_empty_impact_none(self):
        outcome = make_engine().run(make_task(missing_items=[]))
        self.assertTrue(outcome.ok)
        self.assertIsNone(outcome.payload["missing_materials_impact"])
        self.assertIsNone(build_missing_materials_impact([]))

    def test_fake_traceability_in_result_and_logs(self):
        logger_name = "assessment_worker.assessment_engine.engine"
        with self.assertLogs(logger_name, level="INFO") as captured:
            outcome = make_engine().run(make_task())

        self.assertTrue(outcome.ok)
        meta = outcome.payload["model_meta"]
        self.assertIs(meta["is_fake_provider"], True)
        self.assertEqual(meta["provider"], "FakeModelProvider")
        self.assertIn("not a real assessment", meta["provider_trace"])
        self.assertTrue(any("fake=True" in line for line in captured.output))

    def test_success_payload_shape_matches_l03_complete_assessment(self):
        outcome = make_engine().run(make_task())
        self.assertTrue(outcome.ok)
        accepted = set(
            inspect.signature(ScoringOrchestrator.complete_assessment).parameters
        ) - {"self", "task_id"}
        self.assertLessEqual(set(outcome.payload), accepted)


class L03CompatibilityTests(unittest.TestCase):
    """成功/失败输出真实喂给 L03 complete_assessment / fail_assessment（SQLite 内存库）。"""

    def setUp(self) -> None:
        self.db = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        OrchestratorBase.metadata.create_all(self.db)
        self.session_factory = sessionmaker(bind=self.db, expire_on_commit=False)
        self.orchestrator = ScoringOrchestrator(
            self.session_factory,
            SqlaTaskLeaseStore(self.session_factory),
            InMemoryOutboxStore(),
        )
        self.orchestrator.handle_submission_received(
            {
                "submission_id": "sub-1",
                "course_id": "course-1",
                "assignment": "实现命令行待办管理器",
                "student_name": "张三",
                "group_name": "G1",
                "material_refs": [
                    {"category": "代码", "ref": "materials/sub-1/main.py"},
                    {"category": "对话", "ref": "materials/sub-1/dialogue.md"},
                ],
                "missing_items": ["截图"],
                "received_at": "2026-07-20T00:59:00+00:00",
                "v": 1,
            }
        )

    def tearDown(self) -> None:
        self.db.dispose()

    def claim(self):
        claimed = self.orchestrator.claim_task("worker-1", now=T0)
        self.assertIsNotNone(claimed)
        return claimed

    def test_success_payload_feeds_complete_assessment(self):
        claimed = self.claim()
        outcome = make_engine(provider=RecordingFakeProvider()).run(claimed)
        self.assertTrue(outcome.ok)

        committed = self.orchestrator.complete_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            now=T0,
            **outcome.payload,
        )
        self.assertIsInstance(committed, OutcomeCommitted)
        with self.session_factory() as session:
            task = session.scalar(
                sa.select(ScoringTask).where(ScoringTask.task_id == claimed.task_id)
            )
            self.assertEqual(task.status, "scored")

    def test_failure_payload_feeds_fail_assessment(self):
        # 按真实时间认领，使引擎失败载荷的 at（墙钟时间）落在租约内
        claimed = self.orchestrator.claim_task("worker-1")
        self.assertIsNotNone(claimed)
        outcome = make_engine(provider=TimeoutStubProvider()).run(claimed)
        self.assertFalse(outcome.ok)

        payload = outcome.payload
        # ICT-006 的 at 对应 fail_assessment 的 now 参数
        result = self.orchestrator.fail_assessment(
            claimed.task_id,
            owner=claimed.lease_owner,
            attempt_no=payload["attempt_no"],
            error_kind=payload["error_kind"],
            now=payload["at"],
        )
        self.assertIsInstance(result, RetryEntered)
        self.assertEqual(result.error_kind, ERROR_MODEL_TIMEOUT)
        self.assertEqual(result.next_attempt_no, 2)


if __name__ == "__main__":
    unittest.main()
