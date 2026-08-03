"""Agent Core - LLM 模拟推理核心"""

import json

from mock_framework.simulator.llm_client import LLMClient, TokenBudgetExceeded
from mock_framework.models.loader import TechnicalMapping


class AgentCore:
    """Agent 核心"""

    def __init__(self, llm_client: LLMClient, token_budget: int = 4000):
        self.llm = llm_client
        self.token_budget = token_budget
        self.tokens_used = 0

    def simulate_step(
        self,
        phase: str,
        mapping: TechnicalMapping,
        current_state: dict,
        arch_summary: dict,
    ) -> dict:
        """模拟单步执行"""
        prompt = self._build_prompt(phase, mapping, current_state, arch_summary)

        try:
            response = self.llm.complete(prompt)
            self.tokens_used += 10
            # 规范化 LLM 输出：必须是 dict；如果是 list，取第一个元素或包装为 error
            if not isinstance(response, dict):
                if isinstance(response, list) and response:
                    response = response[0] if isinstance(response[0], dict) else {"raw": response}
                else:
                    response = {"raw": response}
            return response
        except TokenBudgetExceeded:
            return {
                "action": "error",
                "status": "ERROR",
                "output": {
                    "error": f"Token budget exceeded: {self.tokens_used}/{self.token_budget}"
                },
            }

    def _build_prompt(
        self, phase: str, mapping: TechnicalMapping, current_state: dict, arch_summary: dict
    ) -> str:
        """构建 LLM prompt"""
        return (
            f"你是一个架构模拟器。请严格按架构文档模拟以下 {phase.upper()} 步骤的执行。\n\n"
            f"【架构文档摘要】\n{json.dumps(arch_summary, ensure_ascii=False)}\n\n"
            f"【当前状态】\n{json.dumps(current_state, ensure_ascii=False)}\n\n"
            f"【步骤】\n{mapping.text}\n\n"
            f"【技术映射】\n{json.dumps(mapping.target, ensure_ascii=False)}\n\n"
            f"【模拟规则】\n"
            f"SIM-01: 只能执行架构文档中明确描述的行为\n"
            f"SIM-02: 只能访问架构文档中定义的数据存储\n"
            f"SIM-03: action 必须是字符串，表示动作名称（如 call、send、set_state、write）\n"
            f"SIM-04: target 必须是字符串或 null，表示目标组件名或资源名\n"
            f"SIM-05: data 必须是对象，可包含 state、records、payload 等字段\n"
            f"SIM-06: status 必须是字符串，如 SUCCESS、ERROR、PENDING\n\n"
            f"请输出 JSON，包含 action/target/data/reasoning/status 字段。"
        )
