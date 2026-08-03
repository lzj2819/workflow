"""模拟状态管理器"""

from dataclasses import dataclass, field

from mock_framework.models.arch import ArchDoc


@dataclass
class DataStore:
    """内存数据存储"""

    type: str = "table"
    records: list[dict] = field(default_factory=list)


@dataclass
class StateMachineInstance:
    """状态机实例"""

    current_state: str = ""
    transitions_executed: list[dict] = field(default_factory=list)


@dataclass
class SimulationState:
    """模拟状态"""

    data_stores: dict[str, DataStore] = field(default_factory=dict)
    component_states: dict[str, str] = field(default_factory=dict)
    state_machines: dict[str, StateMachineInstance] = field(default_factory=dict)
    audit_log: list[dict] = field(default_factory=list)
    request_context: dict = field(default_factory=dict)
    response_context: dict = field(default_factory=dict)


class SimulationStateManager:
    """模拟状态管理器"""

    def initialize(self, arch_doc: ArchDoc) -> SimulationState:
        """初始化模拟状态"""
        component_states = {}
        for comp in arch_doc.components:
            component_states[comp.name] = "idle"

        return SimulationState(
            data_stores={},
            component_states=component_states,
            state_machines={},
            audit_log=[],
        )

    def set_data_store(self, state: SimulationState, name: str, records: list[dict]) -> None:
        """设置数据存储"""
        state.data_stores[name] = DataStore(records=records)

    def set_state_machine(self, state: SimulationState, entity: str, initial: str) -> None:
        """设置状态机初始状态"""
        state.state_machines[entity] = StateMachineInstance(current_state=initial)

    def transition_state(
        self, state: SimulationState, entity: str, to_state: str, trigger: str
    ) -> bool:
        """执行状态转换"""
        if entity not in state.state_machines:
            return False

        sm = state.state_machines[entity]
        sm.transitions_executed.append(
            {"from": sm.current_state, "to": to_state, "trigger": trigger}
        )
        sm.current_state = to_state
        return True

    def append_audit_log(self, state: SimulationState, entry: dict) -> None:
        """追加审计日志"""
        state.audit_log.append(entry)
