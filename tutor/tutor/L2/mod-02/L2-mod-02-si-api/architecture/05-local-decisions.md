# 05 Local Decisions — SI-API L2

## 1. 局部决策记录（按稳定 ID 排序）

| decision_id | source artifact | source id | affected child artifact | classification | decision | alternatives and consequence |
|---|---|---|---|---|---|---|
| LCD-SIAPI-001 | current PRD / parent handoff | REQ-DD003, SI-API focus | AUTH/INTAKE-ORCHESTRATOR/ROUTER | decide_now | 采用四个按责任、状态、交互和变化原因划分的 child，而不是按 Controller/Service/Repository 泛化分层 | 单一 API 大组件会混合认证、编排和观测；纯技术分层会模糊 ST-06 与父端口责任 |
| LCD-SIAPI-002 | parent `04-contracts-and-runtime.md` | NFR-003, D-AC-REQ-007-01 | INTAKE-ORCHESTRATOR/OBSERVABILITY | decide_now | 固定同步预算只覆盖接收确认；评分任务持久化与 processing 推进为异步后续链路 | 等待评分会违反 30 秒确认；过早返回 received 会违反父 ConfirmReceived 前置条件 |
| LCD-SIAPI-003 | parent contract | CT-001, CT-002, auth-token | AUTH/ROUTER | decide_now | 认证失败在入口终止并映射父错误码；auth-token 的名单校验由 AUTH 经 LC-SIAPI-007 执行，上传完成后的名单校验由 ORCHESTRATOR 经 LC-SIAPI-004 执行；两条路径均不缓存通过结果 | 在 API 缓存名单结论会违反 REQ-006/CT-003；把内部错误直接返回会泄漏实现细节 |
| LCD-SIAPI-004 | parent state/contract | ST-01, ST-02, IC-SI-01/04 | INTAKE-ORCHESTRATOR | decide_now | 以 `submission_uuid` 作为入口幂等关联键，优先复用父既有结果；不在 API 建立第二份 Submission 状态 | 只在 HTTP 层去重无法覆盖会话/聚合；复制状态会制造所有权分叉 |
| LCD-SIAPI-005 | parent metric allocation | SM-001, LCD-009 | OBSERVABILITY | decide_now | 统一记录有效 CT-001 起点、30 秒内 received 成功点、课程/结果/失败标签和父分母排除 | 各端点自定义口径会导致 SM-001 漂移；将材料内容写入指标违反最小化原则 |
| LCD-SIAPI-006 | parent LCD-004 | LCD-004 | AUTH | implementation_detail | 令牌具体编码、密钥管理和框架配置留待实现阶段 | 不在架构层假设 JWT/opaque 等具体实现；不改变父端点语义 |
| LCD-SIAPI-007 | parent delegation | SI-API child handoff | SI-API-ROUTER/INTAKE-ORCHESTRATOR | defer_to_next_level | 下一层可细化中间件顺序、精确预算切片、端口适配器和字段脱敏；必须保持本文 child-only contract 与父字段不变 | 这些选择影响实现组织但不改变当前边界；若需要新增公共契约必须 return_to_parent |
| LCD-SIAPI-008 | current validation revision | ARCH-A9E8F5E62893 / ARCH-ECDE9ECD5CF0 | ROUTER/AUTH/INTAKE-ORCHESTRATOR | decide_now | 将公共入口绑定、局部状态验证与跨层评分状态验证分离；不把验证器误绑定的 AUTH 缺口扩散为架构责任 | 若继续让 L2 SI-API 直接验证 MOD-04 状态，会重复定义父状态机并制造错误 owner |

## 2. 继承决策（不在本层重开）

- `KD-002`：Outbox 保证事件不丢失，投递失败无限重试。
- `KD-003`：结构化数据与本地加密磁盘的父存储边界。
- `KD-004`：500MB 单次上限、类型白名单和课程配额。
- `KD-005`：auth-token 作为 CT-001 契约族附属端点，以及断点续传/短同步约束。
- `LCD-001`：ROSTER_UNAVAILABLE 的待校验与重试承载。
- `LCD-003`：CT-004 task_persisted 确认后 received → processing。
- `LCD-009`：SM-001 采集、聚合、分母排除与标签口径。

## 3. 父所有决策禁止本地改写

本层不得改变 CT-001/CT-002/auth-token/CT-003/CT-004/CT-005/CT-006/CT-012/CT-014 的标识、owner、路径/主题、字段、side effects、错误、重试、幂等或版本；不得转移 ST-01/ST-02/ST-03/ST-04/ST-05 所有权；不得新增独立服务、容器、数据库、消息总线或部署单元。若未来需求触及这些项目，必须创建 `parent-change-request.md` 并停止当前递归。

## 4. Local decision queue outcomes

| queue item | outcome | follow-up |
|---|---|---|
| 认证与入口职责边界 | decide_now → LCD-SIAPI-001/003 | 本包已固化 |
| 30 秒同步预算 | decide_now → LCD-SIAPI-002 | 下一层只细化预算切片，不改变成功点 |
| 幂等承载 | decide_now → LCD-SIAPI-004 | SI-CORE/SI-XFER 继续拥有业务状态 |
| 指标口径 | decide_now → LCD-SIAPI-005 | 依赖父 LCD-009 |
| token 具体形态 | implementation_detail → LCD-SIAPI-006 | 实现阶段处理 |
| 验证入口与跨层状态 | decide_now → LCD-SIAPI-008 | CT-001/CT-002/auth-token 固定从 ROUTER 进入；评分状态转由 L1/MOD-04 系统验证 |
| 中间件/端口细节 | defer_to_next_level → LCD-SIAPI-007 | 推荐 `[NEXT SI-API-INTAKE-ORCHESTRATOR]` 后再细化 |
| parent-impacting choice | none | 无 `return_to_parent`；不创建 parent-change-request.md |
