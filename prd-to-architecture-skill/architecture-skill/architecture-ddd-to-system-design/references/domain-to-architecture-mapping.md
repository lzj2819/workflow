# DDD 到系统架构映射参考流程

## 目标

把 DDD 产物转换为可实施的系统架构。架构映射是主流程；阶段三的关键架构取舍确认只是异常处理机制，用来处理普通映射无法安全决定的结构性选择。

## Mapping Input Pack

在 `docs/architecture/architecture-workbench.md` 中先整理：

| Input Type | Source | Key Items | Used By Mapping |
|---|---|---|---|
| Bounded Contexts | `bounded-contexts.md` | BC 名称、职责、上下游关系 | M1 |
| Aggregates | `aggregates.md` | 聚合、归属 BC、不变量 | M2 |
| Domain Flows | `domain-flow.md` | 核心业务流程、步骤顺序、参与 BC | M3 |
| Domain Events | `domain-events-catalog.md` | 事件、发布方、消费方、payload 线索 | M4 |
| External Systems | PRD / `context-map.md` / `domain-flow.md` | 外部系统、交互方向、语义差异 | M5 |
| Drivers / Constraints | PRD / 用户补充 / `assumptions.md` | 性能、安全、合规、可用性、团队、部署约束 | M6 |

## M1：Bounded Context → Module

目标：把业务边界落成系统模块。

输出：

- `output/01-system-overview.md`
- `architecture-workbench.md`

规则：

- 一个 Module 必须来自一个或多个 BC。
- 不默认 `一个 BC = 一个 Module`。
- 不默认 `一个 Module = 一个微服务`。
- 语义强相关、生命周期强相关、经常一起发布的 BC，可以映射到同一个 Module。
- 需要独立发布、扩缩容、团队负责、合规边界或故障隔离的 BC，倾向映射为不同 Module。
- 两个 BC 语义不同但协作频繁时，不应为了调用方便合并；应保留边界，并在 M3 / M4 定义协作。

工作表：

| BC | Module | Module Responsibility | Owner / Team Hint | Mapping Rationale | Output |
|---|---|---|---|---|---|

进入 Key Decision Queue：

- 合并或拆分 Module 会明显改变部署方式。
- 合并或拆分 Module 会影响团队、合规或故障隔离。
- BC 之间既有强一致要求，又有独立演进要求。

## M2：Aggregate → Data Owner / Transaction Boundary

目标：确定数据所有权、本地事务边界和跨边界一致性策略。

输出：

- `output/03-data-and-consistency.md`
- `architecture-workbench.md`

规则：

- 聚合先映射为数据所有权和事务边界，不直接映射为数据库产品。
- 聚合归属哪个 BC，默认由对应 Module 拥有该聚合数据。
- 聚合不变量必须在一个本地事务边界内保护。
- 跨聚合、跨 Module 的一致性默认不使用分布式事务，除非业务明确要求强一致。
- 查询模型可以跨聚合派生，但派生读模型不改变源数据所有权。
- 读侧为了性能复制数据时，必须说明复制来源、延迟接受度和失效策略。

工作表：

| Aggregate | Owning BC | Owning Module | Data Owner | Local Transaction Boundary | Cross-Boundary Consistency | Output |
|---|---|---|---|---|---|---|

进入 Key Decision Queue：

- 需要跨 Module 强一致事务。
- 数据所有权在多个 Module 之间存在争议。
- 共享数据库、模块独立数据库或服务独立数据库会影响演进、合规或运维。
- 读写分离、事件溯源、CQRS 等机制会显著改变系统结构。

## M3：Domain Flow → Runtime Interaction

目标：把领域流程转换为运行时协作方式。

输出：

- `output/02-runtime-architecture.md`
- `architecture-workbench.md`

规则：

- Domain Flow 的业务顺序不能被架构阶段改写。
- 同一 Module 内部步骤可以映射为本地调用或内部应用服务协作。
- 跨 Module 步骤必须明确同步调用、异步事件、回调、批处理、文件交换或人工流程。
- 用户必须立即获得确定结果的步骤，优先考虑同步交互。
- 可延迟、可重试、可补偿的步骤，优先考虑异步事件。
- 长流程、多状态、多补偿、多人工介入时，才考虑工作流编排。
- 每个运行时交互必须能回溯到 Domain Flow 的某个步骤。

工作表：

| Domain Flow | Step | Participating Modules | Runtime Interaction | Sync / Async | Failure Handling Hint | Source |
|---|---|---|---|---|---|---|

进入 Key Decision Queue：

- 同步和异步都会明显影响一致性、用户体验、失败补偿或基础设施。
- 是否引入工作流引擎存在明显成本和收益分歧。
- 某个流程跨多个 Module，失败补偿责任不清。
- 运行时协作方式会改变部署单元或技术组件选择。

## M4：Domain Event → Interface / Event Contract

目标：把领域事件和跨 Module 交互落成接口契约或事件契约。

输出：

- `output/04-interface-contracts.md`
- `architecture-workbench.md`

规则：

- 不重新发明 DDD 中不存在的领域事件。
- 如果架构需要技术事件，必须标明它不是领域事件。
- 跨 Module 的领域事件必须落成事件契约。
- 跨 Module 的同步调用必须落成 API 契约。
- 外部系统回调必须落成 webhook、file exchange 或 event contract。
- 查询接口也必须写明契约，并将 `side_effects` 写为 `None; read-only`。
- 每个契约必须有稳定的 `contract_id` 和 `contract_type`。
- 事件消费方副作用必须写入 `side_effects`。
- 契约依赖必须写入 `dependencies`。

每个契约至少包含：

- `contract_id`
- `contract_type`
- Provider
- Consumer
- Trigger / Protocol
- Sync / Async
- Schema
- `side_effects`
- `dependencies`
- Error / Timeout / Retry
- Idempotency
- Versioning
- Source FR / Flow / Event

工作表：

| Source Event / Interaction | contract_id | contract_type | Provider | Consumer | Sync / Async | side_effects | dependencies | Output |
|---|---|---|---|---|---|---|---|---|

进入 Key Decision Queue：

- 契约语义会反向改变 Module 边界。
- 事件是否发布、由谁发布、谁负责幂等存在重大分歧。
- 契约错误处理、补偿或重试策略会影响核心业务承诺。
- 是否引入消息队列、事件总线或 API Gateway 成为结构性选择。

## M5：External System → Adapter / ACL

目标：确定外部系统如何接入，以及是否需要语义隔离。

输出：

- `output/01-system-overview.md`
- `output/02-runtime-architecture.md`
- `output/04-interface-contracts.md`
- `architecture-workbench.md`

规则：

- 外部系统不能直接污染领域模型。
- 如果只是技术协议封装，使用 Adapter。
- 如果外部系统语义与本系统领域语言不一致，使用 ACL。
- 如果外部系统供应商可能替换，使用 Adapter / Port 隔离。
- 外部系统参与核心 Domain Flow 时，必须进入运行时架构。
- 外部系统产生回调时，必须进入接口契约。
- 外部系统不可用会影响核心流程时，必须说明失败、降级、重试或人工处理策略。

工作表：

| External System | Related BC / Module | Integration Style | Adapter / ACL | Reason | Contract / Flow Impact | Output |
|---|---|---|---|---|---|---|

进入 Key Decision Queue：

- 是否使用 ACL 会显著影响领域模型纯度、开发成本或长期演进。
- 外部系统不可用会影响核心交易链路。
- 外部系统有合规、安全、数据出境或审计要求。
- 是否引入网关、专用适配服务或异步隔离层存在重大取舍。

## M6：Driver / Constraint → Technology / Deployment

目标：把真实驱动和约束转换为技术组件、部署单元和运行时拓扑。

输出：

- `output/05-decisions-and-technology.md`
- `output/06-deployment.md`
- `architecture-workbench.md`

规则：

- 技术组件必须能追溯到 PRD、DDD、质量属性、约束或已批准关键架构取舍。
- 没有明确驱动，不引入数据库以外的复杂基础设施。
- 数据库产品选择发生在 M2 数据边界之后。
- 消息队列、缓存、搜索、工作流引擎、API Gateway、服务网格等组件属于高影响技术组件，必须说明来源驱动。
- 部署单元来自扩缩容、隔离、发布、合规、团队边界或运行时依赖，不来自“一个 Module 一个服务”的默认假设。
- 如果一个 Module 不需要独立发布、扩缩容或故障隔离，可以留在同一部署单元。
- 如果部署拆分会超过团队运维能力，优先选择更简单的部署形态。

工作表：

| Driver / Constraint | Source | Technology / Deployment Mapping | Reason | Affected Modules | Output |
|---|---|---|---|---|---|

进入 Key Decision Queue：

- 是否引入 MQ、缓存、搜索、工作流引擎等高影响组件存在取舍。
- 单体、模块化单体、分布式服务、微服务之间存在结构性分歧。
- 部署单元拆分会改变团队、运维、成本、可用性或合规策略。
- 技术选择不可逆、迁移成本高或超出团队能力。

## Architecture Workbench 结构

`architecture-workbench.md` 建议结构：

```markdown
# Architecture Workbench

## Mapping Input Pack

## M1 BC to Module

## M2 Aggregate to Data Owner and Transaction Boundary

## M3 Domain Flow to Runtime Interaction

## M4 Domain Event to Interface / Event Contract

## M5 External System to Adapter / ACL

## M6 Driver / Constraint to Technology / Deployment

## Key Decision Queue
```

`Key Decision Queue` 只记录阶段二发现但尚未确认的关键架构取舍。普通映射不要进入队列；详细候选比较发生在阶段三。

阶段二登记队列时必须写清来源，避免阶段三凭空讨论：

| Decision ID | Found In Mapping | Trigger | Source Artifact | Source ID | Affected Output | Why Normal Mapping Is Not Enough | Needs Human Gate |
|---|---|---|---|---|---|---|---|

字段说明：

- `Decision ID`：使用 `KD-001`、`KD-002` 这样的稳定编号。
- `Found In Mapping`：填写 M1 到 M6。
- `Trigger`：说明是哪条进入队列条件被触发。
- `Source Artifact`：填写来源产物，例如 `bounded-contexts.md`、`aggregates.md`、`domain-flow.md`、`domain-events-catalog.md`、`context-map.md`、PRD 或 `assumptions.md`。
- `Source ID`：填写具体来源编号，例如 BC ID、Aggregate ID、Flow ID、Event ID、System ID、FR ID 或 Constraint ID。
- `Affected Output`：填写可能受影响的最终输出文件，例如 `output/01-system-overview.md`。
- `Why Normal Mapping Is Not Enough`：说明为什么普通映射规则不能直接决定。
- `Needs Human Gate`：如果选择会明显改变系统结构、成本、合规、安全或团队职责，写 `Yes`；否则写 `No`。
