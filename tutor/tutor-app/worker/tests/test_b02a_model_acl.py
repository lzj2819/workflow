"""T-B02a MODEL-SERVICE-ACL 单元测试。

覆盖任务卡语义断言：
- 出站最小化拒绝：含 submission_id 的请求被拒（MODEL_ERROR）且供应商零调用；
- 应答 schema 非法 → INVALID_RESPONSE_SCHEMA；
- 超时三分类：供应商抛 TimeoutError、注入慢时钟超预算 → MODEL_TIMEOUT；
- 供应商一般失败/未知异常 → MODEL_ERROR；
- fake 适配器端到端：L12 engine → ACL → FakeVendorAdapter 成功装配；
  ACL 分类异常经 L12 既有 error_kind 映射进入 ICT-006 三分类；
- fake 来源可追溯：FakeVendorAdapter.vendor/is_fake 标注 fake，不假扮真实供应商。

仅使用 fake/stub provider；无网络、无真实供应商、无密钥。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

from assessment_worker.assessment_engine import (  # noqa: E402
    ERROR_INVALID_RESPONSE_SCHEMA as L12_INVALID_RESPONSE_SCHEMA,
)
from assessment_worker.assessment_engine import (  # noqa: E402
    ERROR_MODEL_ERROR as L12_MODEL_ERROR,
)
from assessment_worker.assessment_engine import (  # noqa: E402
    ERROR_MODEL_TIMEOUT as L12_MODEL_TIMEOUT,
)
from assessment_worker.assessment_engine import AssessmentEngine  # noqa: E402
from assessment_worker.model_acl import (  # noqa: E402
    ACL_ERROR_CODES,
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    AclError,
    FakeVendorAdapter,
    ModelServiceAcl,
)
from assessment_worker.model_provider import (  # noqa: E402
    DIMENSIONS,
    GRADES,
    FakeModelProvider,
    ModelProviderError,
)


def valid_request() -> dict:
    return {
        "evaluation_prompt": "fake prompt: 按五维度评估",
        "materials": {
            "dialogue_summary": "对话摘要",
            "code": "def main(): ...",
            "result_description": "输出符合预期",
        },
        "request_id": "req-test-1",
    }


def valid_response() -> dict:
    return {
        "grade": "B",
        "dimension_rationales": [
            {"dimension": d, "rationale": f"{d}的依据"} for d in DIMENSIONS
        ],
        "suggestions": ["建议补充需求澄清轮次"],
    }


class SpyProvider:
    """记录调用的 stub provider（非真实供应商，无网络）。"""

    def __init__(self, response: dict | None = None, error: Exception | None = None) -> None:
        self.response = response if response is not None else valid_response()
        self.error = error
        self.calls: list[dict] = []

    def evaluate(self, request: dict) -> dict:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClock:
    """可注入单调时钟：按预设刻度推进（测试预算守卫）。"""

    def __init__(self, ticks: list[float]) -> None:
        self._ticks = list(ticks)

    def __call__(self) -> float:
        return self._ticks.pop(0) if self._ticks else 0.0


# --------------------------------------------------------------------- ACL 本体


class OutboundMinimizationTests(unittest.TestCase):
    def test_submission_id_rejected_and_provider_never_called(self):
        provider = SpyProvider()
        acl = ModelServiceAcl(provider)
        request = valid_request()
        request["submission_id"] = "sub-1"  # 业务标识：绝不外发

        with self.assertRaises(AclError) as ctx:
            acl.evaluate(request)

        self.assertEqual(ctx.exception.code, ERROR_MODEL_ERROR)
        self.assertIn("submission_id", str(ctx.exception))
        self.assertEqual(provider.calls, [])  # 最小化违例：供应商不可见该请求

    def test_each_forbidden_business_identifier_rejected(self):
        for key in ("student_name", "group_name", "invite_code", "course_id"):
            provider = SpyProvider()
            acl = ModelServiceAcl(provider)
            request = valid_request()
            request[key] = "x"
            with self.assertRaises(AclError) as ctx:
                acl.evaluate(request)
            self.assertEqual(ctx.exception.code, ERROR_MODEL_ERROR, key)
            self.assertEqual(provider.calls, [], key)

    def test_missing_material_bucket_rejected(self):
        provider = SpyProvider()
        acl = ModelServiceAcl(provider)
        request = valid_request()
        del request["materials"]["code"]
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(request)
        self.assertEqual(ctx.exception.code, ERROR_MODEL_ERROR)
        self.assertEqual(provider.calls, [])


class ResponseSchemaTests(unittest.TestCase):
    def test_invalid_response_schema_classified(self):
        bad = valid_response()
        bad["grade"] = "Z"  # 非法等级
        acl = ModelServiceAcl(SpyProvider(response=bad))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_INVALID_RESPONSE_SCHEMA)

    def test_extra_top_level_key_rejected(self):
        bad = valid_response()
        bad["debug"] = "extra"
        acl = ModelServiceAcl(SpyProvider(response=bad))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_INVALID_RESPONSE_SCHEMA)

    def test_valid_response_returned(self):
        acl = ModelServiceAcl(SpyProvider())
        response = acl.evaluate(valid_request())
        self.assertIn(response["grade"], GRADES)
        self.assertEqual(len(response["dimension_rationales"]), 5)


class TimeoutBudgetTests(unittest.TestCase):
    def test_provider_timeout_error_classified(self):
        acl = ModelServiceAcl(SpyProvider(error=TimeoutError("simulated timeout")))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_MODEL_TIMEOUT)

    def test_budget_exceeded_via_injected_clock(self):
        # 注入慢时钟：调用耗时 200s > 默认 180s 预算 → MODEL_TIMEOUT
        acl = ModelServiceAcl(SpyProvider(), clock=FakeClock([0.0, 200.0]))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_MODEL_TIMEOUT)
        self.assertIn("budget", str(ctx.exception))

    def test_within_budget_passes(self):
        acl = ModelServiceAcl(SpyProvider(), clock=FakeClock([0.0, 179.9]))
        response = acl.evaluate(valid_request())
        self.assertIn(response["grade"], GRADES)

    def test_custom_budget_enforced(self):
        acl = ModelServiceAcl(SpyProvider(), budget_seconds=10, clock=FakeClock([0.0, 10.5]))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_MODEL_TIMEOUT)


class ProviderErrorTests(unittest.TestCase):
    def test_model_provider_error_classified(self):
        acl = ModelServiceAcl(SpyProvider(error=ModelProviderError("provider down")))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_MODEL_ERROR)

    def test_unknown_exception_classified_as_model_error(self):
        acl = ModelServiceAcl(SpyProvider(error=RuntimeError("boom")))
        with self.assertRaises(AclError) as ctx:
            acl.evaluate(valid_request())
        self.assertEqual(ctx.exception.code, ERROR_MODEL_ERROR)

    def test_acl_error_codes_match_l12_taxonomy(self):
        self.assertEqual(
            set(ACL_ERROR_CODES),
            {ERROR_MODEL_TIMEOUT, ERROR_MODEL_ERROR, ERROR_INVALID_RESPONSE_SCHEMA},
        )
        err = AclError(ERROR_MODEL_TIMEOUT, "x")
        self.assertEqual(err.code, L12_MODEL_TIMEOUT)
        self.assertEqual(err.error_kind, L12_MODEL_TIMEOUT)
        self.assertIsInstance(err, ModelProviderError)
        with self.assertRaises(ValueError):
            AclError("NOT_A_CODE", "x")


# ------------------------------------------------------- fake 适配器 + L12 端到端


class StubPromptComposer:
    def compose(self, assignment: str, material_refs: list, missing_items: list) -> dict:
        return {
            "evaluation_prompt": "fake prompt: 按五维度评估该提交",
            "prompt_version": "p1",
            "rubric_version": "r1",
        }


class StubMaterialReader:
    def load(self, material_refs: list) -> dict:
        return {
            "materials": {
                "对话": "学生与 Codex 的对话摘要",
                "代码": "def main(): ...",
                "结果描述": "程序输出符合预期",
            },
            "readability": ["ok"] * len(material_refs),
        }


def make_task() -> SimpleNamespace:
    return SimpleNamespace(
        task_id="task-1",
        submission_id="sub-1",
        course_id="course-1",
        assignment="实现命令行待办管理器",
        material_refs=[
            {"category": "代码", "ref": "materials/sub-1/main.py"},
            {"category": "对话", "ref": "materials/sub-1/dialogue.md"},
        ],
        missing_items=[],
        attempt_no=1,
    )


class FakeVendorAdapterTests(unittest.TestCase):
    def test_fake_provenance_marked(self):
        adapter = FakeVendorAdapter()
        self.assertEqual(adapter.vendor, "fake")
        self.assertTrue(adapter.is_fake)
        response = adapter.evaluate(valid_request())
        # 确定性 fake 输出：满足 CT-010 schema，不表达真实评估能力
        self.assertIn(response["grade"], GRADES)

    def test_engine_acl_fake_end_to_end_success(self):
        adapter = FakeVendorAdapter()
        acl = ModelServiceAcl(adapter)
        engine = AssessmentEngine(
            prompt_composer=StubPromptComposer(),
            material_reader=StubMaterialReader(),
            model_provider=acl,
        )
        outcome = engine.run(make_task())
        self.assertTrue(outcome.ok)
        payload = outcome.payload
        self.assertIn(payload["original_grade"], GRADES)
        self.assertEqual(len(payload["dimension_rationales"]), 5)
        self.assertEqual(payload["model_meta"]["provider"], "ModelServiceAcl")

    def test_engine_maps_acl_invalid_response_to_ict006(self):
        bad = valid_response()
        bad["dimension_rationales"] = bad["dimension_rationales"][:4]
        acl = ModelServiceAcl(SpyProvider(response=bad))
        engine = AssessmentEngine(
            prompt_composer=StubPromptComposer(),
            material_reader=StubMaterialReader(),
            model_provider=acl,
        )
        outcome = engine.run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error_kind, L12_INVALID_RESPONSE_SCHEMA)

    def test_engine_maps_acl_timeout_to_ict006(self):
        acl = ModelServiceAcl(
            FakeVendorAdapter(), clock=FakeClock([0.0, 999.0])
        )
        engine = AssessmentEngine(
            prompt_composer=StubPromptComposer(),
            material_reader=StubMaterialReader(),
            model_provider=acl,
        )
        outcome = engine.run(make_task())
        self.assertFalse(outcome.ok)
        self.assertEqual(outcome.error_kind, L12_MODEL_TIMEOUT)
        self.assertNotEqual(outcome.error_kind, L12_MODEL_ERROR)

    def test_engine_minimization_defect_never_reaches_provider(self):
        """L12 组装的请求本已最小化；人为破坏最小化时 ACL 拒绝且 fake 零调用。"""

        class LeakyComposer(StubPromptComposer):
            def compose(self, assignment, material_refs, missing_items):
                composed = super().compose(assignment, material_refs, missing_items)
                composed["submission_id"] = "sub-1"  # 泄漏业务标识
                return composed

        # L12 只取 evaluation_prompt/版本字段，故直接验证 ACL 层拒绝：
        provider = SpyProvider()
        acl = ModelServiceAcl(provider)
        request = valid_request()
        request["submission_id"] = "sub-1"
        with self.assertRaises(AclError):
            acl.evaluate(request)
        self.assertEqual(provider.calls, [])

    def test_engine_success_via_acl_uses_real_fake_provider(self):
        """FakeModelProvider 直接经 ACL 包装同样可走通（适配器可替换性）。"""
        acl = ModelServiceAcl(FakeModelProvider())
        engine = AssessmentEngine(
            prompt_composer=StubPromptComposer(),
            material_reader=StubMaterialReader(),
            model_provider=acl,
        )
        outcome = engine.run(make_task())
        self.assertTrue(outcome.ok)


if __name__ == "__main__":
    unittest.main()
