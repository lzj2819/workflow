"""Hierarchical architecture document models."""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class InterfaceDef(BaseModel):
    """对外接口定义（每层都必须明确自己对外暴露什么）"""

    name: str
    direction: Literal["inbound", "outbound"]
    protocol: str
    contract: dict
    description: str = ""
    model_config = ConfigDict(frozen=True)


class Constraint(BaseModel):
    """约束条件（用于层间验证）"""

    type: Literal["nfr", "dependency", "invariant", "assumption"]
    description: str
    target: Optional[str] = None
    value: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class DesignArtifact(BaseModel):
    """设计产出物（该层特有的详细设计）"""

    type: Literal["openapi", "data_flow", "state_machine", "sequence", "erd", "other"]
    format: Literal["yaml", "mermaid", "table", "text"]
    content: str
    model_config = ConfigDict(frozen=True)


class OpenAPISpec(BaseModel):
    """OpenAPI 接口契约"""

    paths: dict = Field(default_factory=dict)
    components: dict = Field(default_factory=dict)
    model_config = ConfigDict(frozen=True)


class DataFlowStep(BaseModel):
    """数据流单步"""

    from_component: str
    to_component: str
    action: str
    message: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class DataFlow(BaseModel):
    """Mermaid 数据流图"""

    sequence: list[DataFlowStep] = Field(default_factory=list)
    model_config = ConfigDict(frozen=True)


class StateTransition(BaseModel):
    """状态转换"""

    from_state: str
    to_state: str
    trigger: str
    action: Optional[str] = None
    model_config = ConfigDict(frozen=True)


class StateMachine(BaseModel):
    """Mermaid 状态机"""

    states: list[str] = Field(default_factory=list)
    transitions: list[StateTransition] = Field(default_factory=list)
    model_config = ConfigDict(frozen=True)


class NFR(BaseModel):
    """非功能需求"""

    id: str
    metric: str
    threshold: float
    unit: str
    model_config = ConfigDict(frozen=True)


class ComponentSpec(BaseModel):
    """组件职责定义"""

    name: str
    responsibility: str
    tech_stack: Optional[str] = None
    # Dispatch semantics are architecture metadata, not a conclusion inferred
    # from prose.  A component may legitimately mention a "worker" or a
    # "queue" in its responsibility while still being a strict simulation
    # participant.
    dispatch_kind: Optional[
        Literal["component", "container", "datastore", "external", "heading"]
    ] = None
    model_config = ConfigDict(frozen=True)


class ArchDoc(BaseModel):
    """
    层级化架构文档。

    这是一个递归模型：每层 ArchDoc 可以引用上层(parent)和下层(children)。
    叶子节点（最底层）包含具体实现细节，非叶子节点只包含接口和约束。
    """

    # === 元信息 ===
    level_name: str = ""
    level_depth: int = 0
    parent_ref: Optional[str] = None
    children_refs: list[str] = Field(default_factory=list)

    # === 该层的职责范围 ===
    scope: str = ""
    responsibilities: list[str] = Field(default_factory=list)

    # === 对外接口（最关键的部分，用于层间一致性验证） ===
    interfaces: list[InterfaceDef] = Field(default_factory=list)

    # === 约束条件（NFR、依赖、不变量、假设） ===
    constraints: list[Constraint] = Field(default_factory=list)

    # === 内部设计（可以是子层引用，也可以是具体实现） ===
    internals: list[DesignArtifact] = Field(default_factory=list)

    # === 依赖的外部层（跨系统/跨团队的依赖） ===
    external_dependencies: list[str] = Field(default_factory=list)

    # === 关联的 Gherkin 场景文件 ===
    feature_refs: list[str] = Field(default_factory=list)

    # === 传统字段（向后兼容） ===
    openapi: OpenAPISpec = Field(default_factory=OpenAPISpec)
    data_flow: DataFlow = Field(default_factory=DataFlow)
    state_machine: StateMachine = Field(default_factory=StateMachine)
    nfrs: list[NFR] = Field(default_factory=list)
    components: list[ComponentSpec] = Field(default_factory=list)
    entity_owners: dict[str, str] = Field(default_factory=dict)
    entity_details: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
