# 05 Local Decisions — 局部决策（L2 / CMP-REVIEW-QUERY）

> 决策按稳定 ID 排序。`decide_now` 已清零；`return_to_parent` 为 0。

## 1. 本层决定（decide_now）

### LCD-RQ-001 查询装配采用单一 Facade 编排

- 来源：CT-007 完整出参；父 M05-FLOW-002；CMP-REVIEW-QUERY 的“装配单点化”责任。
- 备选：
  - (a) **采用：一个 `CMP-RQ-QUERY-FACADE` 编排局部装配并统一响应校验**。保持 CT-007 单一边界，集中处理完整性、错误和十秒预算。
  - (b) 由 Scope/Detail/Retention 各自直接向 GATE 返回部分响应。会把父契约字段和错误语义分散，容易产生缺字段成功。
  - (c) 新增独立聚合查询服务。违反父层不新增服务/部署边界。
- 后果：局部 child 之间使用内部契约组合，Facade 不拥有持久化状态。

### LCD-RQ-002 评分失败结果显式分支

- 来源：D-AC-REQ-009-01 boundaries；父 P-禁伪造等级；DF-2 步骤 6；CT-005 投影结果。
- 备选：
  - (a) **采用：`CMP-RQ-OUTCOME-ADAPTER` 显式处理 scored/scoring_failed**。失败分支只输出 failure_reason/retry_record，不生成等级。
  - (b) 在查询时把失败结果转换为空 scored 结果。会模糊失败原因并可能让 UI 误显示无效等级。
  - (c) 查询侧重新调用评分服务。越过 MOD-04 和父事件边界。
- 后果：失败可见性与真实性在本节点单点实现，评分执行仍归 MOD-04。

### LCD-RQ-003 deletion_batches[] 始终出现在响应

- 来源：CT-007 `produced_fields`；M05-IC-06；父 AC-REQ-009-01 response。
- 备选：
  - (a) **采用：有批次返回批次列表，无批次返回空数组**。字段稳定，消费者不需要猜测字段缺失含义。
  - (b) 无批次时省略字段。违反 CT-007 必需出参完整性。
  - (c) 在查询侧计算批次状态。转移 RG 所有权，违反边界。
- 后果：Retention View Adapter 失败时整体失败，不允许空数组掩盖端口错误。

### LCD-RQ-004 端口失败不做部分成功降级

- 来源：父 M05-IC-02/M05-IC-06 失败语义；L1 04 §4；NFR-001 查询结果完整性。
- 备选：
  - (a) **采用：任一必需端口失败则返回 retryable failure**。保证 CT-007 响应完整且可重试。
  - (b) 读模型失败时只返回课程骨架。会把缺字段误呈现为“无数据”。
  - (c) 使用旧缓存补齐。父层明确不引入缓存且可能复活已删除数据。
- 后果：调用方需要重试，但不会收到语义不完整的成功响应。

### LCD-RQ-005 层级与提交详情使用同一授权上下文

- 来源：M05-BIND-CT-007-GATE-RQ；CT-007 `auth_context`；父课程范围授权策略。
- 备选：
  - (a) **采用：Facade 把 GATE 传入的授权上下文只读传给所有局部 child**。本层不重新解释授权规则。
  - (b) 各 child 自己读取授权表。转移 ACCESS-GATE 的状态/职责。
  - (c) Scope child 接受无授权上下文。可能导致局部调用绕过父边界。
- 后果：本层仅消费已经授权的上下文，任何授权变化回父/GATE 处理。

### LCD-RQ-008 验证责任不改变业务所有权

- 来源：验证报告对 SCENARIO-002/003 的失败提示；父级 CT-008、ReviewRecord、M05-IC-05 和 CT-007 读侧分工。
- 采用：将“保存批注/调整等级”和“原始/最终等级及操作者时间留痕”分别归 CT-008/ReviewRecord 写侧与 RMP 投影；本层只验证投影后的 CT-007 读取结果。
- 不采用：给 `CMP-RQ-SCOPE-ASSEMBLER` 增加写状态、删除审计或 Query→Command `next_hop`。这会违反 C2 只读和父级写侧分离。
- 后果：验证场景需要按责任组件分层；查询包不因 `PRECONDITION_UNSUPPORTED` 而改变状态所有权。

### LCD-RQ-009 组件契约登记采用双重一致性

- 来源：验证器 `contract_coverage_gap` warning 与本层已存在的 `component_bindings`。
- 采用：在本文件的 `04-contracts-and-runtime.md` 中维护一张验证器可消费的契约登记表，并要求其与详细 YAML bindings 逐字段一致；本层事件策略显式为 `none`。
- 不采用：为了通过 warning 添加不存在的事件、缓存、搜索服务或持久化状态。
- 后果：契约表达可以被静态 checker 消费，同时不改变 CT-007/M05-IC-02/M05-IC-06 的业务语义。

### LCD-RQ-010 合法分支必须有覆盖场景

- 来源：Facade/Retention Adapter 被报告为 orphan component。
- 采用：将 Facade 作为 CT-007 唯一入口，将 Retention Adapter 作为 `deletion_batches[]` 必需响应分支；严格验证需有至少一个场景覆盖该分支。
- 不采用：删除组件或把“当前场景未触达”解释为架构孤儿。

## 2. 交给下一层（defer_to_next_level）

| ID | 事项 | 目标 child | 触发条件 | 本层约束 |
|---|---|---|---|---|
| LCD-RQ-006 | 具体 SQL/ORM 查询计划、索引组合与分页实现 | CMP-RQ-SCOPE-ASSEMBLER / CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER | 进入更深层实现设计 | 不新增缓存/搜索，不改变 M05-IC-02 字段与最终一致语义 |
| LCD-RQ-007 | CT-007 DTO 序列化、空数组编码和错误响应映射的具体库/框架 | CMP-RQ-QUERY-FACADE | 进入更深层接口实现设计 | 保留父字段、错误码和 `/api/v1` 版本 |

## 3. 实现细节（implementation_detail）

- 查询结果的内存对象类型、字段排序和日志脱敏格式。
- 端口调用的 tracing span 命名与基础指标标签；只遵循 KD-003 最小化日志。
- 选择条件规范化的函数组织方式；不改变 CT-007 输入语义。

## 4. 继承决策与父层专属禁止项

- 原样继承 KD-002（共部署/Outbox）、KD-003（基础运维）、KD-005（`/api/v1` 与教师会话）、LCD-001（通知由投影派生）、LCD-004（展示视图源自读模型）、LCD-005（删除后的重放守卫）、LCD-006（授权由 ACCESS-GATE 管理）。
- 不重选架构风格、运行时身份、数据库、消息平台、缓存策略或部署模式。
- 不改变 CT-007/M05-IC-02/M05-IC-06 的 owner、字段、错误、版本、依赖与副作用。

## 5. 队列关闭声明

全部发现的选择已分类：`decide_now` 5 项（LCD-RQ-001~005）已决定；`defer_to_next_level` 2 项（LCD-RQ-006~007）已登记；实现细节 3 类；`return_to_parent` 0 项。本包可以进入 Human Gate。
