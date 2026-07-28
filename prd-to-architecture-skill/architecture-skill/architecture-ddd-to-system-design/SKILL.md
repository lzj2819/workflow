---
name: architecture-ddd-to-system-design
description: Use when an approved PRD or equivalent requirements document needs a complete DDD-first architecture workflow, including DDD strategic modeling, bounded contexts, aggregates, context map, domain flow, and DDD-to-system architecture mapping without running full ADD.
---

# DDD 到系统架构完整流程

## 核心原则

先完成 DDD 战略建模，再把 DDD 产物映射为系统架构。DDD 决定业务模型是什么；架构映射决定这些业务模型如何落成模块、数据边界、运行时协作、接口契约、外部系统隔离、技术组件和部署单元。

不要在架构阶段重做 DDD，也不要默认进入完整 ADD。阶段三只处理阶段二映射后仍无法安全决定的关键架构取舍；普通映射直接落到最终输出，不进入候选方案比较。

## 使用条件

使用本 skill 当：

- 用户提供了已认可的 PRD 或等价需求文档。
- 用户希望从 PRD 先做 DDD，再生成系统架构。
- 用户希望替代“DDD 后直接跑完整 ADD”的流程。
- 用户需要一个 DDD 主线更连贯的架构生成 skill。

不使用本 skill 当：

- 用户只想单独做 DDD；可使用 `architecture-ddd-modeling`。
- 用户明确要求完整 ADD 方法；可使用 `architecture-add-design`。
- 用户已经有完整系统架构，并要求模块内部详细设计或代码脚手架。

## 输出目录

默认在 `docs/architecture/` 下生成或更新。

DDD 产物：

- `FR.md`
- `ubiquitous-language.md`
- `domain-events-catalog.md`
- `aggregates.md`
- `bounded-contexts.md`
- `context-map.md`
- `domain-flow.md`
- `assumptions.md`

架构映射工作文件：

- `architecture-workbench.md`

最终架构输出：

- `output/README.md`
- `output/01-system-overview.md`
- `output/02-runtime-architecture.md`
- `output/03-data-and-consistency.md`
- `output/04-interface-contracts.md`
- `output/05-decisions-and-technology.md`
- `output/06-deployment.md`

不要生成完整 ADD 过程包：`QAS.md`、`ASR.md`、`constraints.md`、`ADD-iterations/*`、`ADR/*` 不属于本版默认输出。

## 总流程

1. 执行 DDD 战略建模。
2. 执行 DDD 一致性回检。
3. 建立架构映射输入包。
4. 执行 DDD 到架构的六类映射。
5. 将普通映射无法决定的重大分叉写入 `Key Decision Queue`，并记录来源产物、来源 ID 和受影响输出。
6. 如果没有必须立即确认的关键取舍，生成最终架构输出。
7. 如果存在必须立即确认的关键取舍，按阶段 3 进行候选比较、确认并回填输出。

## 阶段 1：DDD 战略建模

按 `references/ddd-strategic-modeling.md` 执行完整 DDD 流程。必须先完成以下产物：

- `FR.md`
- `ubiquitous-language.md`
- `domain-events-catalog.md`
- `bounded-contexts.md`
- `aggregates.md`
- `context-map.md`
- `domain-flow.md`

阶段 1 禁止选择微服务、数据库、消息队列、缓存、搜索、工作流引擎、部署拓扑或接口技术。

## 阶段 2：DDD 到架构的六类映射

按 `references/domain-to-architecture-mapping.md` 执行六类映射：

| Mapping | Source | Architecture Result |
|---|---|---|
| M1 | Bounded Context | Module |
| M2 | Aggregate | Data Owner / Transaction Boundary |
| M3 | Domain Flow | Runtime Interaction |
| M4 | Domain Event | Interface / Event Contract |
| M5 | External System | Adapter / ACL |
| M6 | Driver / Constraint | Technology / Deployment |

阶段 2 的主文件是 `architecture-workbench.md`。它必须包含：

- `Mapping Input Pack`
- `M1 BC to Module`
- `M2 Aggregate to Data Owner and Transaction Boundary`
- `M3 Domain Flow to Runtime Interaction`
- `M4 Domain Event to Interface / Event Contract`
- `M5 External System to Adapter / ACL`
- `M6 Driver / Constraint to Technology / Deployment`
- `Key Decision Queue`

## 阶段 3：关键架构取舍确认

按 `references/key-architecture-decisions.md` 处理 `Key Decision Queue`。`Key Decision Queue` 也可理解为旧版 `Risk Decision Queue` 的升级版：它不是收集所有风险，而是只收集会影响系统结构、部署方式、数据边界、核心协作、重要技术组件或高迁移成本的架构取舍。

如果阶段 2 的普通映射已经足够确定，不要强行进入阶段 3。只有队列中存在 `decide_now` 项时，才进行候选方案比较。

阶段 2 只负责发现并登记问题来源，不在这里做候选方案比较。队列格式：

| Decision ID | Found In Mapping | Trigger | Source Artifact | Source ID | Affected Output | Why Normal Mapping Is Not Enough | Needs Human Gate |
|---|---|---|---|---|---|---|---|

阶段 3 再为每一项补充分类，分类只能是：

- `decide_now`
- `defer_to_detail_design`
- `return_to_ddd`
- `implementation_detail`

如果存在 `decide_now` 且需要用户判断，暂停最终交付包，向用户报告可选方案和推荐方案。确认后必须把决策回填到 `architecture-workbench.md` 和 `Affected Output` 指向的最终输出文件。

`Key Decision Queue` 本身不作为最终交付。所有已确认关键架构取舍必须沉淀到 `output/05-decisions-and-technology.md`，并同步回填 `Affected Output` 指向的文件。

## 阶段 4：最终输出

只有当 DDD 一致性检查通过、六类映射完成，且 `Key Decision Queue` 中没有未完成的 `decide_now` 项时，才生成 `docs/architecture/output/`。

阶段 4 才读取 `references/final-architecture-output-templates.md`。读取后按目标 output 文件对应小节生成，不要把模板全文复制到输出中，也不要加载无关模板内容来扩写过程说明。

最终输出必须自包含。读者不应为了理解最终架构而依赖 `architecture-workbench.md`。

`output/README.md` 是架构包的交付入口。除文件索引外，必须说明本包已确认到什么程度、不同读者的建议阅读路径、可据此进入的下一阶段，以及不阻塞当前架构的暂缓事项。交付说明只做交接和后续衔接，不重复各架构文件的正文，也不新增独立交付说明文件。

## 防跑偏规则

- 不在架构映射阶段重新划分 BC。
- 不在架构映射阶段重新设计聚合、实体、值对象或业务不变量。
- 不把 `BC = Module = Microservice` 作为默认规则。
- 不因为“最佳实践”或“现代化”引入技术组件。
- 每个 Module 必须追溯到 BC。
- 每个数据所有权和事务边界必须追溯到聚合或明确查询需求。
- 每个跨 Module 交互必须有接口契约或事件契约。
- 每个技术组件必须追溯到 PRD、DDD、约束或已批准关键架构取舍。
- 每个部署单元必须追溯到扩缩容、隔离、发布、合规、团队或运行时约束。
- 图必须嵌入对应 `output/*.md` 文件，不单独作为最终产物；除非用户明确要求，不生成独立 `diagrams/` 目录。
- 图中出现的模块、数据、接口、技术组件和部署单元必须能追溯到 DDD 产物、阶段二映射或已确认关键架构取舍。

## 接口契约硬性字段

`output/04-interface-contracts.md` 中每个契约至少包含：

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

字段 `contract_id`、`contract_type`、`side_effects` 和 `dependencies` 必须保留英文 snake_case。纯查询契约的 `side_effects` 必须写为 `None; read-only`。

## 完成前检查

完成前逐项检查：

- DDD 产物是否完整。
- DDD 产物是否通过一致性回检。
- `architecture-workbench.md` 是否包含六类映射。
- `Key Decision Queue` 是否没有未完成的 `decide_now` 项。
- 最终输出文件是否只有 `output/` 下 7 个文件。
- 是否没有生成完整 ADD 过程包。
- 接口契约硬性字段是否齐全。
- `output/README.md` 是否包含架构包状态、建议阅读路径、后续工作的输入和暂缓事项。
