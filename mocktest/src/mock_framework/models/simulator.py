"""Simulator 输出模型"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TraceStep(BaseModel):
    """执行追踪单步"""

    step_number: int = Field(..., description="步骤序号")
    phase: str = Field(..., description="阶段: given/when/then")
    component: str = Field(..., description="组件名")
    action: str = Field(..., description="动作")
    # 详细调用信息
    target: Optional[str] = Field(None, description="目标组件")
    method: Optional[str] = Field(None, description="调用方法")
    parameters: Optional[dict] = Field(None, description="调用参数")
    # 兼容字段
    input: Optional[dict] = Field(None, description="输入")
    output: Optional[dict] = Field(None, description="输出")
    # 扩展：保留单跳 subagent 的 self_check 与 next_hop，供 validator 做细粒度契约审查
    self_check: Optional[dict] = Field(None, description="组件自检结果")
    next_hop: Optional[dict] = Field(None, description="下一跳决策")
    # 状态与性能
    status: Optional[str] = Field(None, description="状态: PASS/ERROR/WARNING")
    timestamp_ms: int = Field(..., description="时间戳(ms)")
    latency_ms: int = Field(default=0, description="延迟(ms)")

    model_config = ConfigDict(frozen=True)


class SideEffect(BaseModel):
    """副作用记录"""

    type: str = Field(..., description="类型: write/read/delete/append")
    target: str = Field(..., description="目标存储")
    data: dict = Field(default_factory=dict, description="副作用数据")

    model_config = ConfigDict(frozen=True)


class StateTransitionRecord(BaseModel):
    """状态转换记录"""

    entity: str = Field(..., description="实体")
    from_state: str = Field(..., serialization_alias="from", description="源状态")
    to_state: str = Field(..., serialization_alias="to", description="目标状态")
    trigger: str = Field(..., description="触发条件")
    side_effects: list[dict] = Field(default_factory=list, description="副作用")

    model_config = ConfigDict(frozen=True)


class ExecutionTrace(BaseModel):
    """执行追踪"""

    trace_id: str = Field(..., description="追踪ID")
    test_case_id: str = Field(..., description="测试用例ID")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    total_latency_ms: int = Field(default=0, description="总延迟(ms)")
    steps: list[TraceStep] = Field(default_factory=list, description="步骤列表")
    side_effects: list[SideEffect] = Field(default_factory=list, description="副作用")
    state_transitions: list[StateTransitionRecord] = Field(
        default_factory=list, description="状态转换"
    )
    then_verifications: list[dict] = Field(default_factory=list, description="then 断言验证证据")

    model_config = ConfigDict(frozen=True)
