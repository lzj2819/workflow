# 05 Local Decisions — 局部决策（L2 / CMP-REVIEW-COMMAND）

> 决策只覆盖选定父节点内部。父级契约、状态所有权、技术/部署决策不能在本层改写。

## 1. 本层决定（decide_now，按稳定 ID 排序）

### LCD-001 调整理由字段采用可选语义

- **来源**：父 `LCD-009`；当前 PRD 的 D-AC-REQ-009-01 未要求理由必填。
- **备选**：
  - (a) **采用：理由可选，存在时随 GradeAdjustmentRecord 留痕**。保持 CT-008 现有必填字段不变。
  - (b) 强制理由。会改变请求校验和产品语义，需要新增父契约必填字段，必须 return_to_parent。
  - (c) 不保留理由。会丢失未来审计/解释空间，不满足父级调整记录可追溯目标。
- **结果**：POLICY 不以理由为空拒绝；WRITER 可保存 optional `adjustment_reason`；不创建 `parent-change-request.md`。

### LCD-002 ReviewRecord 由单一 writer 维护

- **来源**：LCD-003、ST-REVIEW-RECORD 单写方原则。
- **备选**：
  - (a) **采用：所有创建、批注和等级调整都进入 `CMP-RC-REVIEW-RECORD-WRITER`**。
  - (b) RMP 直接写 ReviewRecord。会产生两个写方并重复实现原始等级不可变和禁伪造规则。
  - (c) CT-008 首次打开详情时再创建。会混合读写路径，且 M05-IC-01 的创建时序被破坏。
- **后果**：M05-IC-01 和 CT-008 共用同一聚合不变量；RMP 只经端口调用，不获得状态所有权。

### LCD-003 两种幂等键分层但共享事务边界

- **来源**：CT-008 `request_id`、M05-IC-01 `submission_id`、KD-005。
- **备选**：
  - (a) **采用：GUARD 统一处理两种键，按入口类型选择键，但最终与 ReviewRecord 写入同事务**。
  - (b) 仅使用 submission_id。无法正确收敛教师客户端重复 request。
  - (c) 仅使用 request_id。无法阻止 CT-005/M05-IC-01 重复创建。
- **后果**：重复请求返回首次结果；两个键不互相替代，不修改父契约。

### LCD-004 M05-IC-05 只在业务提交后产生

- **来源**：M05-IC-05、父 04 运行流、父级本地事件可重放约束。
- **备选**：
  - (a) **采用：业务写入、幂等记录和可追溯事件记录先提交，再使 M05-IC-05 对 RMP 可见**。
  - (b) 事务内立即调用 RMP。投影失败会扩大 CT-008 事务耦合，且可能产生未提交状态的可见性问题。
  - (c) 异步独立队列。会引入父级未授权的消息边界。
- **后果**：投影失败按 adjustment_id 重放；CT-008 外部响应不被 RMP 的最终一致性改变。

## 2. 交下一层（defer_to_next_level）

| decision_id | 事项 | 目标 child | 触发条件 | 继承边界 |
|---|---|---|---|---|
| LCD-005 | 等级值域、批注长度和空白规范的具体规则集 | CMP-RC-REVIEW-INTEGRITY-POLICY | 该 child 进入下一层细化 | 必须只映射 VALIDATION_FAILED，不新增父错误码 |
| LCD-006 | 幂等记录的索引/清理和响应引用布局 | CMP-RC-REVIEW-IDEMPOTENCY-GUARD | 该 child 进入下一层细化 | 不能改变 request_id/submission_id 语义或保留边界 |
| LCD-007 | ReviewRecord 字段擦除粒度与本地事件记录载体 | CMP-RC-REVIEW-RECORD-WRITER | 该 child 进入下一层细化 | 遵守父 LCD-005 内容级清除、审计不可删和可重放约束 |

## 3. 实现细节（implementation_detail）

- 具体表名、ORM、索引实现和事务 API。
- 本地事件记录的表结构或进程内实现，只要满足提交后可见和 adjustment_id 重放。
- 具体 annotation_excerpt 截断长度；若涉及外部字段必填或错误码变化，需回父层。
- 数据库瞬时故障的指数退避参数，沿用父级基础运维策略。

## 4. 继承决策与禁止项

- 原样继承 `KD-002`（DU-2 共部署与 Outbox）、`KD-003`（基础级运维）、`KD-005`（`/api/v1`、写幂等键、教师会话）。
- 原样继承 `LCD-003`（ReviewRecord 创建路径）、`P-禁伪造等级`、父 03/04 的本地事务与契约语义。
- 不在本层选择数据库产品、消息总线、缓存、搜索引擎、独立服务、容器或部署单元。
- 不转移 ReviewRecord、读模型、DeletionBatch、Submission 或任何兄弟节点状态所有权。

## 5. 队列关闭声明

`decide_now` 已关闭：LCD-001~004；`defer_to_next_level` 已登记：LCD-005~007；`implementation_detail` 已排除；`return_to_parent` 为 0。当前包可进入 Human Gate。
