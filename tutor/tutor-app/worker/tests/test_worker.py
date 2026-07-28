"""worker 测试：fake ModelProvider 对 CT-010 schema 的符合性、边界与常量。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

from assessment_worker import __main__ as worker_main  # noqa: E402
from assessment_worker import settings as ws  # noqa: E402
from assessment_worker.model_provider import (  # noqa: E402
    DIMENSIONS,
    FakeModelProvider,
    InvalidRequestError,
    UnsupportedModelProviderError,
    build_provider,
    validate_request,
)

CT010 = json.loads((ROOT / "contracts" / "ct-010.json").read_text(encoding="utf-8"))

VALID_REQUEST = {
    "evaluation_prompt": "按五维度评估该提交",
    "materials": {
        "dialogue_summary": "学生与 Codex 的迭代摘要",
        "code": "print('hello')",
        "result_description": "命令行可运行的待办管理器",
    },
    "request_id": "req-1",
}


def assert_ct010_response(test_case: unittest.TestCase, payload: dict) -> None:
    schema = CT010["schemas"]["response"]
    for key in schema["required"]:
        test_case.assertIn(key, payload)
    test_case.assertIn(payload["grade"], schema["properties"]["grade"]["enum"])
    dims = payload["dimension_rationales"]
    test_case.assertEqual(len(dims), 5)
    allowed = set(schema["properties"]["dimension_rationales"]["items"]["properties"]["dimension"]["enum"])
    for dim in dims:
        test_case.assertIn(dim["dimension"], allowed)
        test_case.assertTrue(dim["rationale"])
    test_case.assertTrue(payload["suggestions"])
    for s in payload["suggestions"]:
        test_case.assertIsInstance(s, str)


class TestFakeProvider(unittest.TestCase):
    def test_response_matches_ct010_schema(self):
        payload = FakeModelProvider().evaluate(VALID_REQUEST)
        assert_ct010_response(self, payload)
        self.assertEqual([d["dimension"] for d in payload["dimension_rationales"]], DIMENSIONS)

    def test_deterministic(self):
        provider = FakeModelProvider()
        self.assertEqual(provider.evaluate(VALID_REQUEST), provider.evaluate(VALID_REQUEST))

    def test_rejects_missing_materials(self):
        bad = {"evaluation_prompt": "x", "materials": {"code": "y"}}
        problems = validate_request(bad)
        self.assertTrue(any("dialogue_summary" in p for p in problems))
        with self.assertRaises(InvalidRequestError):
            FakeModelProvider().evaluate(bad)

    def test_rejects_business_identifiers(self):
        bad = dict(VALID_REQUEST, submission_id="s1")
        problems = validate_request(bad)
        self.assertTrue(any("data minimization" in p for p in problems))
        with self.assertRaises(InvalidRequestError):
            FakeModelProvider().evaluate(bad)

    def test_only_fake_supported_in_phase1(self):
        self.assertIsInstance(build_provider("fake"), FakeModelProvider)
        with self.assertRaises(UnsupportedModelProviderError):
            build_provider("some-real-vendor")


class TestWorkerSettings(unittest.TestCase):
    def test_frozen_constants(self):
        self.assertEqual(ws.TASK_BUDGET_SECONDS, 600)
        self.assertEqual(ws.MODEL_CALL_TIMEOUT_SECONDS, 180)
        self.assertEqual(ws.MAX_RETRY_ATTEMPTS, 1)  # REQ-012 重试一次
        self.assertEqual(ws.CLAIM_LEASE_SECONDS, 120)
        self.assertEqual(ws.MAX_RECLAIM_COUNT, 3)
        self.assertEqual(ws.WORKER_REPLICAS_BASELINE, (2, 3))

    def test_env_loading(self):
        with mock.patch.dict("os.environ", {"DATABASE_URL": "postgresql://x"}, clear=True):
            cfg = ws.Settings.from_env()
        self.assertEqual(cfg.model_provider, "fake")
        self.assertIsNone(cfg.model_api_key)
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(ws.runtime_env_present())


class TestWorkerEntry(unittest.TestCase):
    def test_main_requires_database_url(self):
        # GAP-02：入口即常驻循环，缺 DATABASE_URL 必须 fail fast（不伪造可用）
        with mock.patch.dict("os.environ", {"MODEL_PROVIDER": "fake"}, clear=True):
            with self.assertRaises(Exception):
                worker_main.main()


if __name__ == "__main__":
    unittest.main()
