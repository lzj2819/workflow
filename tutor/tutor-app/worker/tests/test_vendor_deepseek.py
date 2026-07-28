"""DeepSeek 供应商接入验收：provider 单测（MockTransport）+ kill switch/熔断降级。

覆盖：请求形状与最小化闸（业务标识绝不外发）、成功应答解析、超时/5xx/限流/
畸形应答分类、密钥不出现于任何日志、kill switch 暂停认领、熔断开/合。
"""
from __future__ import annotations

import json
import logging
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

import httpx
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "worker"), str(ROOT / "server"), str(ROOT / "shared")]

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from assessment_worker.model_provider import (  # noqa: E402
    DIMENSIONS,
    InvalidRequestError,
    ModelProviderError,
)
from assessment_worker.model_provider_deepseek import (  # noqa: E402
    DeepSeekAuthError,
    DeepSeekProvider,
)
from assessment_worker.runner import WorkerRunner  # noqa: E402
from assessment_worker.settings import Settings  # noqa: E402
from course_app.db import session_scope  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402

NOW = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
VALID_RESPONSE = {
    "grade": "B",
    "dimension_rationales": [
        {"dimension": d, "rationale": f"{d} ok"} for d in DIMENSIONS
    ],
    "suggestions": ["s1"],
}


def make_request() -> dict:
    return {
        "evaluation_prompt": "rubric text",
        "materials": {
            "dialogue_summary": "user asked; assistant replied",
            "code": "print('x')",
            "result_description": "tests passed",
        },
        "request_id": "req-1",
    }


def deepseek_response(payload: dict, status: int = 200) -> httpx.Response:
    body = {
        "choices": [{"message": {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}}]
    }
    return httpx.Response(status, json=body)


class DeepSeekProviderTestCase(unittest.TestCase):
    def provider(self, handler) -> tuple[DeepSeekProvider, list]:
        captured = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return handler(request)

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        return (
            DeepSeekProvider(api_key="sk-test-dummy", base_url="https://api.deepseek.test", http_client=client),
            captured,
        )

    def test_success_maps_to_ct010_shape(self) -> None:
        provider, captured = self.provider(lambda req: deepseek_response(VALID_RESPONSE))
        out = provider.evaluate(make_request())
        self.assertEqual(out["grade"], "B")
        self.assertEqual(len(out["dimension_rationales"]), 5)
        self.assertEqual(out["suggestions"], ["s1"])
        # 请求形状：JSON 模式 + 无业务标识
        body = json.loads(captured[0].content)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        text = captured[0].content.decode()
        for forbidden in ("submission_id", "student_name", "group_name", "invite_code", "course_id", "张三"):
            self.assertNotIn(forbidden, text)

    def test_minimization_gate_blocks_business_identifiers(self) -> None:
        provider, captured = self.provider(lambda req: deepseek_response(VALID_RESPONSE))
        bad = make_request() | {"submission_id": "sub-1"}
        with self.assertRaises(InvalidRequestError):
            provider.evaluate(bad)
        self.assertEqual(captured, [])  # 绝不外发

    def test_timeout_maps_to_timeout_error(self) -> None:
        provider, _ = self.provider(
            lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("slow"))
        )
        with self.assertRaises(TimeoutError):
            provider.evaluate(make_request())

    def test_5xx_and_429_map_to_provider_error(self) -> None:
        for status in (500, 502, 429):
            provider, _ = self.provider(lambda req, s=status: httpx.Response(s, json={}))
            with self.assertRaises(ModelProviderError):
                provider.evaluate(make_request())

    def test_401_403_map_to_auth_error(self) -> None:
        provider, _ = self.provider(lambda req: httpx.Response(401, json={}))
        with self.assertRaises(DeepSeekAuthError):
            provider.evaluate(make_request())

    def test_malformed_response_returns_unparseable(self) -> None:
        provider, _ = self.provider(
            lambda req: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        )
        out = provider.evaluate(make_request())
        self.assertEqual(out, {"unparseable": True})  # 交由 ACL 终判 INVALID_RESPONSE_SCHEMA

    def test_empty_api_key_rejected_at_construction(self) -> None:
        with self.assertRaises(DeepSeekAuthError):
            DeepSeekProvider(api_key="")

    def test_key_never_logged(self) -> None:
        provider, _ = self.provider(lambda req: deepseek_response(VALID_RESPONSE))
        logger = logging.getLogger("assessment_worker.deepseek")
        with self.assertLogs(logger, level="INFO") as captured:
            provider.evaluate(make_request())
        for line in captured.output:
            self.assertNotIn("sk-test-dummy", line)
            self.assertNotIn("print('x')", line)  # 材料内容也不入日志


class CircuitAndKillSwitchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        (tmp / "materials").mkdir()
        self.db_url = f"sqlite:///{tmp / 'vendor.db'}"
        self.engine = migrate(self.db_url)
        self.addCleanup(self.engine.dispose)
        self.data_dir = tmp / "materials"

    def make_settings(self, **overrides) -> Settings:
        base = {
            "database_url": self.db_url,
            "model_provider": "fake",
            "model_api_key": None,
            "log_level": "WARNING",
            "claim_lease_seconds": 2,
            "data_dir": str(self.data_dir),
            "worker_id": "t-vendor",
            "concurrency": 1,
            "poll_interval_seconds": 0.05,
        }
        base.update(overrides)
        return Settings(**base)

    def enqueue_ct004(self, submission_id: str) -> None:
        with session_scope(self.engine) as s:
            SqlaOutboxStore(s).enqueue(
                "CT-004",
                {
                    "submission_id": submission_id,
                    "course_id": "c-1",
                    "assignment": "hw",
                    "student_name": "张三",
                    "group_name": "第1组",
                    "material_refs": [],
                    "missing_items": [],
                    "received_at": NOW.isoformat(),
                    "v": 1,
                },
                f"ct004-{submission_id}",
            )

    @staticmethod
    def wait_until(cond, timeout: float = 20.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cond():
                return True
            time.sleep(0.05)
        return False

    def task_status(self, submission_id: str) -> str | None:
        with session_scope(self.engine) as s:
            return s.execute(
                sa.text("select status from scoring_tasks where submission_id=:sid"),
                {"sid": submission_id},
            ).scalar()

    def test_kill_switch_pauses_claiming_without_terminalizing(self) -> None:
        self.enqueue_ct004("sub-1")
        runner = WorkerRunner(
            self.make_settings(vendor_enabled=False),
            sa_engine=self.engine,
            install_signals=False,
        )
        thread = threading.Thread(target=runner.run, daemon=True)
        thread.start()
        try:
            # CT-004 仍入站（任务创建），但认领暂停：任务保持 pending（稍后重试）
            ok = self.wait_until(lambda: self.task_status("sub-1") == "pending", timeout=10)
            self.assertTrue(ok)
            time.sleep(0.5)
            self.assertEqual(self.task_status("sub-1"), "pending")  # 无自动评分、不终态化
        finally:
            runner.request_shutdown()
            thread.join(timeout=10)

    def test_circuit_opens_after_threshold_and_recovers(self) -> None:
        class AlwaysTimeoutProvider:
            def evaluate(self, request: dict) -> dict:
                raise TimeoutError("vendor down")

        runner = WorkerRunner(
            self.make_settings(circuit_threshold=2, circuit_cooldown_seconds=0.6),
            sa_engine=self.engine,
            install_signals=False,
            provider=AlwaysTimeoutProvider(),
        )
        self.assertFalse(runner._claiming_paused("w"))
        # 连续 2 次供应商失败 → 熔断开启
        runner._record_outcome_for_circuit("MODEL_TIMEOUT")
        self.assertFalse(runner._claiming_paused("w"))
        runner._record_outcome_for_circuit("MODEL_ERROR")
        self.assertTrue(runner._claiming_paused("w"))  # 熔断：暂停认领
        self.assertEqual(runner._consecutive_vendor_failures, 2)
        # 冷却后自动半开恢复
        time.sleep(0.7)
        self.assertFalse(runner._claiming_paused("w"))
        self.assertEqual(runner._consecutive_vendor_failures, 0)
        # 成功重置计数
        runner._record_outcome_for_circuit("MODEL_TIMEOUT")
        runner._record_outcome_for_circuit(None)
        self.assertEqual(runner._consecutive_vendor_failures, 0)


if __name__ == "__main__":
    unittest.main()
