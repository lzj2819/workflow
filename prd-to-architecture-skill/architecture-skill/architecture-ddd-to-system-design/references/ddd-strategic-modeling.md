# DDD 战略建模参考流程

## 目标

基于 PRD 或等价需求文档完成 DDD 战略建模，为后续架构映射提供稳定的业务骨架。本阶段只处理业务语义，不选择微服务、数据库、消息队列、缓存、搜索、工作流引擎或部署拓扑。

## 输入

必需：

- PRD 或等价需求文档。

可选：

- `docs/architecture/FR.md`
- `docs/architecture/assumptions.md`

如果缺少 PRD，停止并要求用户补充。

## DDD 最小概念

| 概念 | 判断标准 | 常见误用 |
|---|---|---|
| Command | 用户、外部系统或策略发出的业务意图，通常是祈使句 | 写成已经发生的事实 |
| Domain Event | 已经发生且对业务有意义的事实，必须是过去式 | 写成 API 调用、按钮点击、数据库更新 |
| Policy / Reaction | 事件发生后触发的业务规则、补偿或后续命令 | 写成消息队列、定时器等技术实现 |
| Aggregate | 保护业务不变量的一致性边界 | 把数据库表、页面或所有名词都当聚合 |
| Entity | 有业务身份和生命周期的对象 | 把只有属性值的概念写成实体 |
| Value Object | 用属性值表达的不可变业务概念，可整体替换 | 为了建表方便强行加 ID |
| Bounded Context | 一套术语、模型和数据边界保持一致的业务语义边界 | 按 CRUD 页面、技术层或数据库拆分 |
| Context Map | BC 与外部系统之间的协作关系 | 画成部署图或基础设施图 |

## DDD 流程

### 1. 提取 DDD 输入 FR

从 PRD 中识别：

- 主要参与者。
- 核心业务目标。
- 核心用例，格式为 `Actor + Goal + Business Outcome`。
- 反复出现的业务名词，作为聚合、实体、值对象候选。
- 描述业务状态变化的动词，作为领域事件候选。
- 会影响边界判断的业务不变量、生命周期规则和跨角色协作。

输出 `FR.md`：

| FR-ID | Requirement | Source | Actor | Domain Nouns | Domain Events | Business Invariants | DDD Relevance |
|---|---|---|---|---|---|---|---|

不要把纯 UI 控件、页面名称、技术组件当成领域概念。

### 2. 建立统一语言

从 `FR.md` 提取 10-30 个高价值业务术语。

输出 `ubiquitous-language.md`：

| Term | Definition | Business Context | Related Terms | Questions / Clarifications Needed |
|---|---|---|---|---|

规则：

- 定义必须是业务定义，不是技术定义。
- 同一术语在不同上下文含义不同时，标记为潜在边界。
- 只记录会影响事件、BC 或聚合判断的澄清问题。

### 3. 模拟事件风暴

把静态需求转换为业务时间线：

`Actor -> Command -> Aggregate Candidate -> Domain Event -> Policy / Reaction -> Next Command`

输出 `domain-events-catalog.md`：

| Flow / Sequence | Actor / Role | Command | Handling Aggregate Candidate | Domain Event(s) | Policy / Rule / Reaction | Next Command | Open Questions |
|---|---|---|---|---|---|---|---|

规则：

- Command 表达业务意图。
- Domain Event 表达已经发生的业务事实。
- 异常路径、补偿、并发、超时要写入流程说明或假设。
- 本步骤只记录边界线索，不正式划分 BC。
- 不写 Kafka、RabbitMQ、数据库、API Gateway、Controller。

### 4. 识别限界上下文

从统一语言差异、事件簇、命令簇、聚合候选关系、业务不变量、生命周期和外部系统协作中识别 BC。

输出 `bounded-contexts.md`：

| BC Name | Responsibility | Core Aggregate Root | Entities / Value Objects | Owned Data | Published Events | Consumed Events |
|---|---|---|---|---|---|---|

规则：

- 同一术语含义变化时，优先拆分 BC。
- 事件簇和生命周期高度内聚时，通常归入同一 BC。
- 不按数据库表、CRUD 页面、菜单或技术层拆 BC。
- 优先保证业务内聚，避免过度拆分。

### 5. 建模聚合、实体和值对象

在候选 BC 内，从命令、领域事件、业务不变量和生命周期识别聚合。

输出 `aggregates.md`：

| Aggregate Root | Candidate BC | Responsibility | Commands | Domain Events | Entities | Value Objects | Invariants | Consistency Boundary | Lifecycle Notes |
|---|---|---|---|---|---|---|---|---|---|

规则：

- 聚合根必须能接收命令并发布领域事件。
- 强一致不变量必须落在同一个聚合边界内。
- 跨聚合协作优先通过领域事件或应用层流程表达。
- 不把所有名词都建成聚合。
- 不做跨 BC 的大聚合。

### 6. 定义上下文映射

输出 `context-map.md`，包含 Mermaid 图和关系矩阵。

关系类型：

- Customer-Supplier
- Conformist
- Anti-Corruption Layer
- Shared Kernel
- Open Host Service / Published Language
- Publisher-Subscriber

规则：

- Context Map 只画 BC 和外部系统。
- 不画 API Gateway、数据库、缓存、消息队列或部署节点。
- 同步关系用实线，异步或事件关系用虚线。
- 外部系统单独分组，并标注 ACL 或 Adapter 候选。

### 7. 一致性回检并生成领域流程

输出 `domain-flow.md`，选择 2-3 条最关键端到端流程：

- 主要成功路径。
- 关键异常或恢复路径。
- 生命周期状态路径。

检查：

- 每个事件是否有发布方和消费方。
- 每个聚合是否归属一个候选 BC。
- 跨 BC 关系是否符合 Context Map。
- 术语是否与统一语言一致。
- 是否存在孤立 BC、孤立事件或无法解释的数据流。

如果发现冲突，回到对应 DDD 步骤修订，不要用架构技术方案修补 DDD 不一致。

## DDD 出口标准

进入架构映射前必须满足：

- `FR.md` 能追溯到 PRD。
- `ubiquitous-language.md` 是业务语言，不是技术语言。
- `domain-events-catalog.md` 未绑定具体消息中间件。
- `bounded-contexts.md` 中每个 BC 有清晰职责和数据边界。
- `aggregates.md` 描述聚合根、不变量和一致性边界。
- `context-map.md` 没有基础设施组件。
- `domain-flow.md` 覆盖核心流程，并通过一致性回检。
