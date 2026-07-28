"""LLM Client 抽象接口"""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional, cast


def _is_transient_error(exc: Exception) -> bool:
    """判断异常是否为可重试的瞬态错误。

    优先通过 SDK 异常类型/状态码判断，不可用则回退到消息关键词。
    """
    exc_module = type(exc).__module__
    exc_name = type(exc).__name__

    # openai / anthropic SDK 异常
    if exc_module in ("openai", "anthropic"):
        if exc_name in ("APITimeoutError", "APIConnectionError", "RateLimitError"):
            return True
        if exc_name == "APIError":
            status_code = getattr(exc, "status_code", None)
            if isinstance(status_code, int) and status_code >= 500:
                return True
            body = getattr(exc, "body", None) or {}
            if isinstance(body, dict):
                code = body.get("code") or body.get("error", {}).get("code")
                if code in ("rate_limit_exceeded", "timeout", "service_unavailable"):
                    return True

    # 兜底：消息关键词
    msg = str(exc).lower()
    transient_keywords = [
        "timeout",
        "connection",
        "reset",
        "refused",
        "temporarily",
        "rate limit",
        "too many requests",
        "503",
        "502",
        "504",
        "busy",
        "overload",
        "retry",
        "unavailable",
    ]
    return any(kw in msg for kw in transient_keywords)


class LLMClient(ABC):
    """LLM Client 抽象基类"""

    @abstractmethod
    def complete(self, prompt: str) -> dict:
        """调用 LLM 获取响应"""
        ...


class TokenBudgetExceeded(Exception):
    """Token 预算超出异常"""


class MockLLMClient(LLMClient):
    """Mock LLM Client（用于测试）"""

    def __init__(
        self,
        responses: list[Any] | None = None,
        token_budget: int = 4000,
        raise_on_call: bool = False,
    ) -> None:
        self.responses = responses or []
        self.call_index = 0
        self.token_budget = token_budget
        self.tokens_used = 0
        self.raise_on_call = raise_on_call

    def complete(self, prompt: str) -> dict:
        if self.raise_on_call:
            raise RuntimeError("MockLLMClient forced error")
        # Token budget 按单次调用限制：重置累计值，避免长运行跨场景耗尽预算
        self.tokens_used = 0
        response = self.responses[self.call_index]
        self.call_index = (self.call_index + 1) % len(self.responses)
        self.tokens_used += 10  # 模拟消耗
        if self.tokens_used >= self.token_budget:
            raise TokenBudgetExceeded(
                f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
            )
        return cast(dict, response)


class OpenAICompatibleClient(LLMClient):
    """通用 OpenAI API 兼容客户端.

    通过自定义 base_url 可接入：
    - OpenAI 官方
    - Ollama (http://localhost:11434/v1)
    - vLLM (http://localhost:8000/v1)
    - Azure OpenAI
    - 任何 OpenAI-compatible 端点
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        token_budget: int = 4000,
        base_url: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ):
        self.api_key = api_key
        self.model = model
        self.token_budget = token_budget
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.tokens_used = 0

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAICompatibleClient. "
                "Install it with: pip install openai"
            ) from exc

        kwargs: dict[str, str] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs, timeout=timeout_seconds)  # type: ignore[arg-type]

    def complete(self, prompt: str) -> dict:
        """调用 LLM 获取响应，支持超时和瞬态错误重试."""
        # Token budget 按单次调用限制：先用 prompt 估算做前置保护，然后重置累计值，
        # 避免长运行跨场景耗尽预算
        estimated_prompt_tokens = len(prompt) // 4
        if estimated_prompt_tokens >= self.token_budget:
            self.tokens_used = estimated_prompt_tokens
            raise TokenBudgetExceeded(
                f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
            )

        self.tokens_used = 0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.choices[0].message.content or "{}"
                self.tokens_used += response.usage.total_tokens if response.usage else 10

                if self.tokens_used >= self.token_budget:
                    raise TokenBudgetExceeded(
                        f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
                    )

                return self._parse_json(content)
            except TokenBudgetExceeded:
                raise  # Token 预算错误不可重试
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries or not _is_transient_error(exc):
                    raise
                sleep_time = self.retry_backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_time)

        raise last_error if last_error else RuntimeError("Unexpected: all retries failed")

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 响应为结构化数据."""
        import json

        try:
            result: dict = json.loads(content)
            return result
        except json.JSONDecodeError:
            # 尝试提取 markdown 代码块
            import re

            code_block = re.search(r"```(?:json)?\n(.*?)\n```", content, re.DOTALL)
            if code_block:
                try:
                    result = json.loads(code_block.group(1))
                    return result
                except json.JSONDecodeError:
                    pass
            return {"raw": content}


class AnthropicClient(LLMClient):
    """Anthropic Claude 客户端."""

    def __init__(
        self,
        api_key: str,
        model: str,
        token_budget: int = 4000,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ):
        self.api_key = api_key
        self.model = model
        self.token_budget = token_budget
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.tokens_used = 0

        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is required for AnthropicClient. "
                "Install it with: pip install anthropic"
            ) from exc

        self._client = Anthropic(api_key=api_key, timeout=timeout_seconds)

    def complete(self, prompt: str) -> dict:
        """调用 Claude 获取响应，支持超时和瞬态错误重试."""
        # Token budget 按单次调用限制：先用 prompt 估算做前置保护，然后重置累计值，
        # 避免长运行跨场景耗尽预算
        estimated_prompt_tokens = len(prompt) // 4
        if estimated_prompt_tokens >= self.token_budget:
            self.tokens_used = estimated_prompt_tokens
            raise TokenBudgetExceeded(
                f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
            )

        self.tokens_used = 0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text if response.content else "{}"  # type: ignore[union-attr]
                # Anthropic 不返回 token 使用量，模拟估算
                self.tokens_used += len(prompt.split()) + len(content.split())

                if self.tokens_used >= self.token_budget:
                    raise TokenBudgetExceeded(
                        f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
                    )

                return self._parse_json(content)
            except TokenBudgetExceeded:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries or not _is_transient_error(exc):
                    raise
                sleep_time = self.retry_backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_time)

        raise last_error if last_error else RuntimeError("Unexpected: all retries failed")

    def _parse_json(self, content: str) -> dict:
        """解析 LLM 响应为结构化数据."""
        import json
        import re

        try:
            result: dict = json.loads(content)
            return result
        except json.JSONDecodeError:
            code_block = re.search(r"```(?:json)?\n(.*?)\n```", content, re.DOTALL)
            if code_block:
                try:
                    result = json.loads(code_block.group(1))
                    return result
                except json.JSONDecodeError:
                    pass
            return {"raw": content}


class LLMClientFactory:
    """LLM Client 工厂，根据 provider 创建对应实例."""

    @staticmethod
    def create(
        provider: str,
        api_key: str,
        model: str,
        token_budget: int = 4000,
        base_url: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> LLMClient:
        """创建 LLM Client.

        Args:
            provider: openai | anthropic
            api_key: API Key
            model: 模型名称
            token_budget: Token 预算
            base_url: 自定义端点（仅 OpenAI-compatible 有效）
            timeout_seconds: 单次 API 请求超时（秒）
            max_retries: 瞬态错误最大重试次数
            retry_backoff_seconds: 重试基础退避（秒）

        Returns:
            LLMClient 实例

        Raises:
            ValueError: 未知 provider
        """
        if provider == "openai":
            return OpenAICompatibleClient(
                api_key,
                model,
                token_budget,
                base_url,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        elif provider == "anthropic":
            return AnthropicClient(
                api_key,
                model,
                token_budget,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Supported: openai, anthropic")
