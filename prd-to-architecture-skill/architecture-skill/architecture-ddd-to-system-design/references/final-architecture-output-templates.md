# 最终架构输出轻模板

## 使用规则

本文件只在阶段 4 生成最终输出时读取。按目标 `output/` 文件对应小节使用，不要把模板当范文全文复制。

每个最终输出文件必须：

- 自包含，读者不依赖 `architecture-workbench.md` 才能理解。
- 追溯到 PRD、DDD 产物、阶段二映射或已确认关键架构取舍。
- 只写最终结论和必要理由，不保留过程性讨论。
- 不引入没有来源的数据库、消息队列、缓存、搜索、工作流、网关或部署拆分。

## `output/README.md`

必填栏目：

- 架构包范围。
- 适用读者。
- 文件索引。
- 关键架构结论。
- 已确认关键取舍摘要。
- 暂缓事项摘要。
- 交付说明与后续衔接。

`交付说明与后续衔接` 必须包含：

- **本包状态**：架构范围、已确认的系统级关键取舍，以及当前可进入的下一阶段。
- **建议阅读路径**：至少分别说明业务/产品负责人、架构/技术负责人、模块详细设计人员应优先阅读哪些文件。
- **后续工作的输入**：说明模块详细设计、实施或部署规划分别应以哪些最终输出为输入；后续阶段不得无来源地推翻已确认边界或关键取舍，确需调整时必须回溯到相关 DDD 产物、映射记录或决策记录。
- **暂缓与跟踪事项**：用 `事项 | 原因 | 后续负责阶段 | 触发条件` 表记录，不得把未确认的 `decide_now` 项伪装成暂缓事项。

追溯要求：

- 关键结论必须指向对应输出文件。
- 暂缓事项必须来自 `defer_to_detail_design` 或用户确认的范围外事项。
- 本包状态、下一阶段和暂缓事项必须与 `output/05-decisions-and-technology.md` 中已确认决策及暂缓问题一致。

禁止：

- 重复完整架构正文。
- 放入未确认的 `decide_now` 决策。
- 将交付说明写成新的架构决策、验收报告或独立流程文档。

## `output/01-system-overview.md`

必填栏目：

- 系统目标与范围。
- 系统上下文图。
- 模块清单。
- 模块职责。
- BC 到 Module 映射。
- 外部系统边界。

图要求：

- 使用 Mermaid `flowchart` 生成 System Context Diagram，展示用户角色、本系统、外部系统和主要交互方向。
- 使用 Mermaid `flowchart` 生成 Module Relationship Diagram，展示逻辑 Module、主要依赖方向和可选 BC 来源。
- 图中不要画内部数据库、缓存、消息队列，除非它们已经作为外部依赖或已确认技术组件出现。

追溯要求：

- Module 必须追溯到 BC。
- External System 必须追溯到 PRD、`context-map.md` 或 `domain-flow.md`。

禁止：

- 默认 `一个 BC = 一个微服务`。
- 在本文件展开数据库、消息队列、缓存等基础设施细节。

## `output/02-runtime-architecture.md`

必填栏目：

- 核心运行时流程。
- 同步、异步、回调、批处理或人工流程说明。
- 失败处理。
- 补偿策略。
- Domain Flow 追溯表。

图要求：

- 使用 Mermaid `sequenceDiagram` 生成至少一张 Runtime Sequence Diagram，展示一条核心成功路径。
- 如果存在关键失败、重试、降级或补偿路径，在同一图或补充图中体现。
- 图中的每个交互必须能追溯到 `domain-flow.md`、Domain Event、接口契约或已确认关键取舍。

追溯要求：

- 每个运行时交互必须追溯到 Domain Flow 步骤、Domain Event 或已确认关键取舍。
- 跨 Module 交互必须指向 `output/04-interface-contracts.md` 中的契约。

禁止：

- 改写 DDD 阶段确定的业务顺序。
- 为了技术方便新增无法追溯的业务流程。

## `output/03-data-and-consistency.md`

必填栏目：

- 数据所有权。
- Aggregate 到数据边界映射。
- 本地事务边界。
- 跨边界一致性策略。
- 读模型、复制数据或查询模型说明。

图要求：

- 使用 Mermaid `flowchart` 生成 Data Ownership Diagram，展示 Module、Aggregate / Data Owner、Read Model 和复制或派生关系。
- 图的重点是数据归属和一致性边界，不是数据库表结构。
- 不要画数据库产品，除非数据库选择已经在 `output/05-decisions-and-technology.md` 中确认。

追溯要求：

- 数据所有权必须追溯到 Aggregate、BC 或明确查询需求。
- 跨边界一致性策略必须追溯到 Domain Flow、业务不变量或已确认关键取舍。

禁止：

- 直接从聚合推导数据库产品。
- 没有业务强一致要求时默认使用分布式事务。

## `output/04-interface-contracts.md`

必填栏目：

- API 契约。
- 事件契约。
- 外部系统契约。
- 错误、超时、重试、幂等和版本策略。

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

追溯要求：

- API 契约必须追溯到 Runtime Interaction、Domain Flow 或 External System。
- 事件契约必须追溯到 Domain Event 或已标明的技术事件。

禁止：

- 缺少 `contract_id` 或 `contract_type`。
- 查询契约写入副作用；纯查询的 `side_effects` 必须为 `None; read-only`。

## `output/05-decisions-and-technology.md`

必填栏目：

- 已确认关键架构取舍。
- 技术组件选择。
- 不采用方案。
- 决策理由。
- 来源追溯。
- 暂缓到详细设计的问题。

追溯要求：

- 已确认关键取舍必须来自 `Key Decision Queue` 的 `decide_now` 项或用户明确确认。
- 所有已确认关键取舍必须在本文件沉淀为最终结论，而不是保留为队列项。
- 技术组件必须追溯到 PRD、DDD、约束、阶段二映射或已确认关键取舍。

禁止：

- 把 `Key Decision Queue` 原表直接当最终输出。
- 引入“最佳实践”式但没有来源的技术组件。

## `output/06-deployment.md`

必填栏目：

- 部署单元。
- Module 到部署单元映射。
- 扩缩容策略。
- 故障隔离。
- 发布和运维约束。
- 合规、安全或团队边界影响。

图要求：

- 使用 Mermaid `flowchart` 生成 Deployment Diagram，展示 Deployment Unit、Module 归属、外部依赖和隔离边界。
- 如果部署拆分来自关键取舍，在图注或节点说明中标注对应 Decision ID。
- 不要默认 `一个 Module = 一个服务`；图中每个 Deployment Unit 都必须有来源理由。

追溯要求：

- 部署单元必须追溯到扩缩容、隔离、发布、合规、团队或运行时依赖。
- 如果部署拆分来自关键取舍，必须引用对应 Decision ID。

禁止：

- 默认 `一个 Module = 一个服务`。
- 忽略团队维护能力和运维成本。
