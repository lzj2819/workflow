"""ModelServiceAcl：包装任意 ModelProvider 的防腐层（ICT-004）。

调用顺序（evaluate）：
1. 出站最小化校验：复用 model_provider.validate_request；发现问题（含
   submission_id 等业务标识）时绝不调用供应商，归 MODEL_ERROR；
2. 计时调用：经可注入单调时钟计量；供应商抛 TimeoutError 或调用耗时
   超过预算（默认 MODEL_CALL_TIMEOUT_SECONDS=180s，NFR-003 单次 ≤3min）
   归 MODEL_TIMEOUT；供应商其他失败归 MODEL_ERROR；
3. 应答 CT-010 response schema 校验：复用 L12 validate_model_response；
   非法应答归 INVALID_RESPONSE_SCHEMA，绝不向调用方返回未校验应答。

本层不发网络请求、不读密钥；真实供应商适配为后续实现细节（DD-009）。
日志仅含耗时与错误分类，不含材料内容与业务标识。
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from assessment_worker.assessment_engine.errors import ResponseValidationError
from assessment_worker.assessment_engine.validator import validate_model_response
from assessment_worker.model_provider import (
    ModelProvider,
    ModelProviderError,
    validate_request,
)
from assessment_worker.settings import MODEL_CALL_TIMEOUT_SECONDS

from .errors import (
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    AclError,
)

logger = logging.getLogger(__name__)


class ModelServiceAcl:
    """可替换的模型调用防腐层；实现 ModelProvider 协议（evaluate(request) -> dict）。"""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        budget_seconds: float = MODEL_CALL_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if budget_seconds <= 0:
            raise ValueError("budget_seconds must be positive")
        self._provider = provider
        self._budget = float(budget_seconds)
        self._clock = clock

    @property
    def provider(self) -> ModelProvider:
        """被包装的供应商适配器（可替换；本任务仅 fake）。"""
        return self._provider

    @property
    def budget_seconds(self) -> float:
        return self._budget

    def evaluate(self, request: dict) -> dict:
        """按 ACL 顺序执行一次评估调用；失败抛 AclError（三分类 code）。"""
        problems = validate_request(request)
        if problems:
            # 数据最小化违例（KD-001）：绝不外发，供应商不可见该请求。
            logger.error("model-acl outbound request rejected problems=%s", problems)
            raise AclError(
                ERROR_MODEL_ERROR,
                "outbound request rejected by minimization validation: "
                + "; ".join(problems),
            )

        started = self._clock()
        try:
            response = self._provider.evaluate(request)
        except TimeoutError as exc:
            raise AclError(ERROR_MODEL_TIMEOUT, f"provider timeout: {exc}") from exc
        except ModelProviderError as exc:
            raise AclError(ERROR_MODEL_ERROR, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — 未知异常不得静默转成功
            logger.exception("model-acl unexpected provider error")
            raise AclError(ERROR_MODEL_ERROR, f"unexpected provider error: {exc!r}") from exc
        elapsed = self._clock() - started

        if elapsed > self._budget:
            logger.warning(
                "model-acl budget exceeded budget_s=%.3f elapsed_s=%.3f",
                self._budget,
                elapsed,
            )
            raise AclError(
                ERROR_MODEL_TIMEOUT,
                f"model call exceeded budget {self._budget:.3f}s (elapsed {elapsed:.3f}s)",
            )

        try:
            validated = validate_model_response(response)
        except ResponseValidationError as exc:
            raise AclError(ERROR_INVALID_RESPONSE_SCHEMA, str(exc)) from exc

        logger.info("model-acl call ok elapsed_s=%.3f", elapsed)
        return validated
