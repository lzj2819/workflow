"""DeepSeek 供应商适配器（DD-009；用户 2026-07-25 批准接入，**仅限 deepseek**）。

边界（批准范围，硬性遵守）：
- 仅发送经 CT-010/KD-001 最小化的请求（evaluation_prompt + 三桶材料 +
  request_id；validate_request 拦截一切业务标识，违例绝不外发）；
- 密钥只经环境变量（.env/compose env_file）注入；**绝不记录密钥、绝不记录
  请求/应答内容**——日志仅含 model/status/duration/request_id；
- 强制超时：httpx 客户端超时 ≤ MODEL_CALL_TIMEOUT_SECONDS（180s，CT-010 单次
  上限），与 ACL 预算层双重约束；超时映射 MODEL_TIMEOUT（TimeoutError），
  传输/5xx/限流映射 MODEL_ERROR，应答 JSON 畸形映射 INVALID_RESPONSE_SCHEMA
  （经 ACL validate_model_response 终判）；
- 审计：每次调用计 metrics（vendor_calls_total / vendor_failures_total /
  vendor_timeouts_total），失败含 status_code 分类，不含内容。

API：DeepSeek 兼容 OpenAI Chat Completions（POST {base_url}/chat/completions，
response_format=json_object）。数据地域：api.deepseek.com 为境内服务（符合
「数据不出境」合规口径，见 vendor-compliance-memo 决策节）。
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from tutor_shared.metrics import registry as metrics_registry

from .model_provider import (
    DIMENSIONS,
    InvalidRequestError,
    ModelProviderError,
    validate_request,
)
from .settings import MODEL_CALL_TIMEOUT_SECONDS

_logger = logging.getLogger("assessment_worker.deepseek")

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

_SYSTEM_PROMPT = (
    "你是高校编程课程作业的五维评估助手。按用户给出的评估准则（rubric）与材料，"
    "只输出一个 JSON 对象，不要输出任何其他文字。JSON 形状："
    '{"grade": "A|B|C|D|E", "dimension_rationales": [{"dimension": <维度名>, '
    '"rationale": <该维度评分依据>} ×5], "suggestions": [<教师专用改进建议>]}。'
    "dimension_rationales 必须恰好覆盖五个维度各一次：" + "、".join(DIMENSIONS) + "。"
)


def _build_user_prompt(evaluation_prompt: str, materials: dict) -> str:
    return (
        "【评估准则】\n" + evaluation_prompt
        + "\n\n【学生对话摘要】\n" + str(materials.get("dialogue_summary", ""))
        + "\n\n【学生代码】\n" + str(materials.get("code", ""))
        + "\n\n【运行结果描述】\n" + str(materials.get("result_description", ""))
    )


class DeepSeekAuthError(ModelProviderError):
    """密钥缺失/被拒（401/403）；属配置类失败，重试无意义但分类仍走 MODEL_ERROR。"""


class DeepSeekProvider:
    """DeepSeek Chat Completions 适配器。

    依赖注入：`http_client` 可替换（测试用 httpx.MockTransport）；
    `timeout_seconds` 强制封顶 MODEL_CALL_TIMEOUT_SECONDS。
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = float(MODEL_CALL_TIMEOUT_SECONDS),
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise DeepSeekAuthError("MODEL_API_KEY is required for deepseek provider")
        if timeout_seconds <= 0 or timeout_seconds > MODEL_CALL_TIMEOUT_SECONDS:
            raise ValueError(
                f"timeout_seconds must be in (0, {MODEL_CALL_TIMEOUT_SECONDS}]"
            )
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(cls) -> "DeepSeekProvider":
        import os  # noqa: PLC0415

        return cls(
            api_key=os.environ.get("MODEL_API_KEY", ""),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        )

    def evaluate(self, request: dict) -> dict:
        """执行一次真实评估调用；返回 CT-010 应答形状 dict（由 ACL 终验）。"""
        problems = validate_request(request)
        if problems:  # 数据最小化闸：违例绝不外发
            raise InvalidRequestError("; ".join(problems))

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        request["evaluation_prompt"], request["materials"]
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        started = time.monotonic()
        try:
            resp = self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            metrics_registry.inc("vendor_timeouts_total")
            raise TimeoutError(f"deepseek call timeout: {type(exc).__name__}") from exc
        except httpx.HTTPError as exc:
            metrics_registry.inc("vendor_failures_total")
            raise ModelProviderError(
                f"deepseek transport error: {type(exc).__name__}"
            ) from exc
        duration_ms = int((time.monotonic() - started) * 1000)

        if resp.status_code in (401, 403):
            metrics_registry.inc("vendor_failures_total")
            raise DeepSeekAuthError(f"deepseek auth rejected: HTTP {resp.status_code}")
        if resp.status_code != 200:
            metrics_registry.inc("vendor_failures_total")
            raise ModelProviderError(
                f"deepseek HTTP {resp.status_code}"
            )

        metrics_registry.inc("vendor_calls_total")
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as exc:
            # 应答形状异常：返回原样交由 ACL validate_model_response 终判为
            # INVALID_RESPONSE_SCHEMA（不伪造、不猜测修补）
            _logger.warning(
                "deepseek response parse failed request_id=%s error=%s",
                request.get("request_id"), type(exc).__name__,
            )
            metrics_registry.inc("vendor_failures_total")
            return {"unparseable": True}
        _logger.info(
            "deepseek call ok model=%s status=%d duration_ms=%d request_id=%s",
            self._model, resp.status_code, duration_ms, request.get("request_id"),
        )
        if not isinstance(parsed, dict):
            return {"unparseable": True}
        return {
            "grade": parsed.get("grade"),
            "dimension_rationales": parsed.get("dimension_rationales"),
            "suggestions": parsed.get("suggestions"),
        }
