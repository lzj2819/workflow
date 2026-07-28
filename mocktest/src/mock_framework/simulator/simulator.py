"""Simulator 主类"""

from mock_framework.config import load_config
from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc
from mock_framework.models.loader import TestCase
from mock_framework.models.simulator import (
    ExecutionTrace,
    TraceStep,
    SideEffect,
    StateTransitionRecord,
)
from mock_framework.simulator.agent_core import AgentCore
from mock_framework.simulator.latency_calculator import LatencyCalculator
from mock_framework.simulator.llm_client import LLMClient
from mock_framework.simulator.state_manager import SimulationStateManager
from mock_framework.simulator.state_manager import SimulationState
from mock_framework.simulator.trace_assembler import TraceAssembler


class Simulator:
    """Simulator Agent 主类"""

    def __init__(self, llm_client: LLMClient, config_path: str | None = None):
        self.config = load_config(config_path).simulator
        self.logger = get_logger("simulator")
        token_budget = getattr(llm_client, "token_budget", None) or self.config.token_budget
        self.agent_core = AgentCore(llm_client, token_budget=token_budget)
        self.state_manager = SimulationStateManager()
        self.latency_calculator: LatencyCalculator | None = None
        self.trace_assembler = TraceAssembler()

    def simulate(self, test_case: TestCase, arch_doc: ArchDoc) -> ExecutionTrace:
        """模拟执行单个 TestCase"""
        self.logger.info(f"开始模拟: {test_case.test_case_id}")

        # 初始化
        state = self.state_manager.initialize(arch_doc)
        self.latency_calculator = LatencyCalculator(self.config, arch_doc.nfrs)
        trace_id = f"TRACE-{test_case.test_case_id}"

        # 准备架构摘要
        arch_summary = {
            "components": [c.name for c in arch_doc.components],
            "data_flow": [str(s) for s in arch_doc.data_flow.sequence],
            "nfrs": [{"metric": n.metric, "threshold": n.threshold} for n in arch_doc.nfrs],
        }

        all_steps: list[TraceStep] = []
        all_side_effects: list[SideEffect] = []
        all_transitions: list[StateTransitionRecord] = []
        current_time_ms = 0

        # 处理 Given / When / Then
        for phase in ("given_steps", "when_steps", "then_steps"):
            mappings = test_case.technical_mapping.get(phase, [])
            for mapping in mappings:
                result = self.agent_core.simulate_step(
                    phase.replace("_steps", ""),
                    mapping,
                    self._state_to_dict(state),
                    arch_summary,
                )

                # 计算延迟
                latency = self.latency_calculator.calculate(
                    mapping.target.get("component", "default"),
                )

                # 强制 action/target 为字符串，避免 LLM 返回 dict/list 导致 Pydantic 校验失败
                action_value = result.get("action", "unknown")
                if not isinstance(action_value, str):
                    action_value = str(action_value) if action_value is not None else "unknown"
                target_value = result.get("target")
                if target_value is not None and not isinstance(target_value, str):
                    target_value = str(target_value)

                step = TraceStep(
                    step_number=len(all_steps) + 1,
                    phase=phase.replace("_steps", ""),
                    component=mapping.target.get("component", "unknown"),
                    action=action_value,
                    target=target_value,
                    method=result.get("method"),
                    parameters=result.get("parameters"),
                    status=result.get("status"),
                    input={},
                    output=result.get("data", {}),
                    self_check=None,
                    next_hop=None,
                    timestamp_ms=current_time_ms,
                    latency_ms=latency,
                )
                all_steps.append(step)
                current_time_ms += latency

                # 更新状态
                self._apply_result(state, result)

        # 组装 ExecutionTrace
        trace = self.trace_assembler.assemble(
            test_case_id=test_case.test_case_id,
            trace_id=trace_id,
            steps=all_steps,
            side_effects=all_side_effects,
            state_transitions=all_transitions,
        )

        self.logger.info(f"模拟完成: {trace.trace_id}, 总延迟: {trace.total_latency_ms}ms")
        return trace

    def _state_to_dict(self, state: SimulationState) -> dict:
        """将 SimulationState 转为 dict"""
        return {
            "component_states": state.component_states,
            "state_machines": {
                k: {"current_state": v.current_state} for k, v in state.state_machines.items()
            },
        }

    def _apply_result(self, state: SimulationState, result: dict) -> None:
        """应用 LLM 结果到状态"""
        if not isinstance(result, dict):
            return
        action = result.get("action", "")
        target = result.get("target", "")
        data = result.get("data", {})

        if action == "set_state" and target:
            self.state_manager.set_state_machine(state, target, data.get("state", ""))
        elif action == "write" and target:
            records = data.get("records", [])
            self.state_manager.set_data_store(state, target, records)
        elif action == "append_audit":
            self.state_manager.append_audit_log(state, data)
