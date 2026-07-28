"""Skill LLM Client — 将 ClaudeCodeSkillGateway 适配为核心 LLMClient 接口.

核心 Simulator / Validator 使用同步的 LLMClient.complete(prompt) -> dict。
ClaudeCodeSkillGateway 是异步的、面向 Claude Code Skill 的网关。
本适配器让核心组件能够在 Skill 模式下通过当前 Claude 会话执行 prompt。
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict

from mock_framework.agents.skill_gateway import ClaudeCodeSkillGateway
from mock_framework.simulator.llm_client import LLMClient


class _AnyResponse(BaseModel):
    """通用响应模型，允许任意额外字段."""

    model_config = ConfigDict(extra="allow")


class SkillLLMClient(LLMClient):
    """通过 ClaudeCodeSkillGateway 执行 prompt 的 LLMClient 实现.

    使用方式：
        gateway = ClaudeCodeSkillGateway()
        sim_llm = SkillLLMClient(gateway, agent_type="simulator")
        validator_llm = SkillLLMClient(gateway, agent_type="validator")

        simulator = Simulator(sim_llm)
        validator = Validator(validator_llm)
    """

    def __init__(
        self,
        gateway: ClaudeCodeSkillGateway,
        agent_type: str,
        max_retries: int = 3,
        timeout_seconds: int = 300,
    ) -> None:
        """初始化 Skill LLM Client.

        Args:
            gateway: ClaudeCodeSkillGateway 实例.
            agent_type: "simulator" 或 "validator"，决定调用哪个网关方法.
            max_retries: 网关执行失败时的最大重试次数.
            timeout_seconds: 单次执行的超时时间（秒）.
        """
        if agent_type not in ("simulator", "validator"):
            raise ValueError(f"Unsupported agent_type: {agent_type}")

        self.gateway = gateway
        self.agent_type = agent_type
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> dict[str, Any]:
        """同步接口：调用异步网关执行 prompt 并返回 dict.

        兼容两种调用场景：
        1. 无运行事件循环的线程（如 Skill 通过 executor 运行 Pipeline 时）：直接使用 asyncio.run().
        2. 已有运行事件循环的线程（如 async 测试或直接 async 调用）：在独立线程中运行 asyncio.run()，避免嵌套事件循环.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._async_complete(prompt))

        # 当前线程已有事件循环，需在独立线程中执行
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, self._async_complete(prompt))
            return future.result()

    async def _async_complete(self, prompt: str) -> dict[str, Any]:
        """异步实现：根据 agent_type 调用网关对应方法."""
        if self.agent_type == "simulator":
            result = await self.gateway.execute_simulator_prompt(
                prompt,
                schema=_AnyResponse,
                max_retries=self.max_retries,
                timeout_seconds=self.timeout_seconds,
            )
        else:
            result = await self.gateway.execute_validator_prompt(
                prompt,
                schema=_AnyResponse,
                max_retries=self.max_retries,
                timeout_seconds=self.timeout_seconds,
            )
        return result.model_dump()
