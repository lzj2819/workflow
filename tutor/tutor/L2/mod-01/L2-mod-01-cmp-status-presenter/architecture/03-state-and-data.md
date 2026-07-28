# 03 State and Data — CMP-STATUS-PRESENTER（L2）

## 1. 状态所有权注册表

本层没有持久状态，也不拥有父层的 ST-01/ST-04。下表同时登记继承的事实来源和本层的瞬时派生模型；记录按稳定 ID 排序。

| state_id | 状态/数据 | owner_child_id | readers | writers | lifecycle | consistency_boundary | retention/privacy | parent_trace |
|---|---|---|---|---|---|---|---|---|
| `DS-SP-CONFIG-VIEW-MODEL` | 配置完整性、目录错误及可展示配置事实 | CMP-SP-CONFIG-VIEW-PROJECTOR | STATUS-MESSAGE-MAPPER、RENDER-ADAPTER | CONFIG-VIEW-PROJECTOR（单次调用） | 一次展示请求内创建，渲染结束释放 | 单次 IC-M01-05 输入快照 | 不落盘；不记录邀请码、姓名等原始值 | REQ-DD002；ST-01；IC-M01-05 |
| `DS-SP-PRESENTATION-VIEW` | 状态消息、字段级提示、失败提示和渲染所需视图模型 | CMP-SP-STATUS-MESSAGE-MAPPER | RENDER-ADAPTER | STATUS-MESSAGE-MAPPER（单次调用） | `projected → mapped → rendered` 后释放 | 同一输入快照内确定性派生 | 不落盘；日志不得包含原始个人信息或完整失败载荷 | D-AC-REQ-001-01/002-01；IC-L2-SP-01/02 |
| `DS-SP-TASK-VIEW-MODEL` | 提交状态、提交编号、缺失项、失败原因、进度的任务视图 | CMP-SP-TASK-VIEW-PROJECTOR | STATUS-MESSAGE-MAPPER | TASK-VIEW-PROJECTOR（单次调用） | 一次展示请求内创建，渲染结束释放 | 单次 IC-M01-05 输入快照 | 不落盘；提交编号可展示，原始任务详情不复制 | REQ-DD001；ST-04；IC-M01-05 |
| `ST-01` | `PluginConfig`，含配置完整性和目录错误事实 | CMP-CONFIG-STORE（父节点） | CMP-SP-CONFIG-VIEW-PROJECTOR | CMP-CONFIG-STORE | 持久，按父层有效保存生命周期 | 父层本地原子保存边界 | 仅学生本机；本层不复制或外发 | L1 `03-state-and-data.md §1` |
| `ST-04` | `PendingTask`，含状态、提交编号、失败原因和时间戳 | CMP-PENDING-QUEUE（父节点） | CMP-SP-TASK-VIEW-PROJECTOR | CMP-PENDING-QUEUE | 按父层任务生命周期至终态清理 | 父层状态迁移事务边界 | 仅学生本机；本层不复制或外发 | L1 `03-state-and-data.md §1/§3.2` |

## 2. 存储意图

- 当前节点不引入文件、嵌入式 KV、数据库、缓存、消息队列或服务端存储。
- `DS-*` 均为调用级派生数据；展示结束后释放。
- 父层 `A-007` 仍适用于队列/配置/checkpoint 的持久化机制，但本节点不参与该选择。
- 不将 `submission_id`、`failure_reason`、目录路径或配置原值写入新的 presenter 存储。

## 3. 重要数据流

### 3.1 任务展示读取流

1. `CMP-PENDING-QUEUE` 提供 `IC-M01-05` 的任务字段。
2. `CMP-SP-TASK-VIEW-PROJECTOR` 形成 `DS-SP-TASK-VIEW-MODEL`。
3. `CMP-SP-STATUS-MESSAGE-MAPPER` 保留原始 `status`，并派生缺项/失败提示。
4. `CMP-SP-RENDER-ADAPTER` 输出学生侧展示结果。

### 3.2 配置展示读取流

1. `CMP-CONFIG-STORE` 提供 `completeness[]` 与 `dir_errors[]`。
2. `CMP-SP-CONFIG-VIEW-PROJECTOR` 形成 `DS-SP-CONFIG-VIEW-MODEL`。
3. mapper 将具体目录/字段问题转换为展示语义。
4. renderer 输出配置结果；本节点不保存也不覆盖配置。

### 3.3 禁止的数据流

- presenter → `CMP-PENDING-QUEUE` 的状态写回：禁止。
- presenter → `CMP-CONFIG-STORE` 的配置写回：禁止。
- presenter → MOD-02 的直接查询、上传或提交状态改变：禁止。
- presenter → 外部日志/遥测的原始 PII 输出：禁止。

### 3.4 保留与删除责任声明

- 本节点无持久状态（§1/§2），因此**无保留期、无删除任务、无删除审计能力**；这些职责对本节点为 N/A，不为展示引入任何生命周期管理接口。
- ST-04 `PendingTask` 的保留（含服务器不可达时保留本地待上传任务）与终态清理：归 `CMP-PENDING-QUEUE`（parent trace：L1 `03-state-and-data.md §1/§3.2`）。
- ST-01 上次有效配置的保留与拒绝保存语义：归 `CMP-CONFIG-STORE`（parent trace：L1 `03-state-and-data.md §1`）。
- 本节点唯一合规义务：`DS-*` 派生模型不落盘、日志不含原始个人信息或完整失败载荷（见 §1 retention/privacy 列与 §3.3）。

## 4. 不变量、一致性与并发规则

| invariant_id | 规则 | 作用 |
|---|---|---|
| `INV-SP-001` | 展示路径只读；任何视图生成不得写 ST-01/ST-04 | 防止展示逻辑改变业务状态 |
| `INV-SP-002` | 输入中的 `status`、`submission_id`、`failure_reason` 原样保留到语义映射边界 | 防止伪造或吞掉远端结论 |
| `INV-SP-003` | 缺失项按字段/目录逐项展示；缺失输入不被合并成泛化“失败” | 满足 D-AC 的具体可观察性 |
| `INV-SP-004` | `rejected`、`upload_failed`、`confirm_required` 等事实不能被映射为 `received` | 保持父层状态机语义 |
| `INV-SP-005` | 同一 IC-M01-05 输入快照产生确定性等价视图；不跨请求缓存 | 避免展示副本与父状态漂移 |
| `INV-SP-006` | 展示不可用只产生 `VIEW_NOT_AVAILABLE`，不触发上传、重试或状态迁移 | 限制故障影响范围 |

并发时以一次 `IC-M01-05` 读取到的完整输入快照为边界；本层不自行合并多个任务版本、不推断缺失版本号，也不创建跨请求顺序状态。

## 5. 父层与兄弟所有权确认

`ST-01` 仍归 `CMP-CONFIG-STORE`，`ST-04` 仍归 `CMP-PENDING-QUEUE`；远端 Submission 与远端状态仍归 MOD-02。当前节点只拥有 `DS-*` 瞬时派生模型，没有重新分配父层或兄弟节点的数据所有权。
