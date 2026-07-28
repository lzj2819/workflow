# Leaf Gate Override ? CMP-STATUS-PRESENTER

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-STATUS-PRESENTER（L2 → L3）

> 本文件是下一层组件细化的入口。Human Gate 批准后，可使用 `[NEXT child_id]` 继续递归细化一个 L3 子节点。

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 节点 | `CMP-STATUS-PRESENTER`（L2，MOD-01 内部展示组件） |
| 职责 | 将任务/配置事实转换为学生可理解的只读展示结果 |
| 排除项 | 不持有 ST-01/ST-04；不网络调用、不上传、不重试、不查询远端、不改变状态 |
| 直接父包 | `architecture/L1/L1-mod-01`；目标匹配证据见 manifest |
| 祖先边界 | `MOD-01` / DU-1 student-plugin；父包不得被本层改写 |
| 绑定契约 | `IC-M01-05`，只读，字段和错误语义不可变 |
| 绑定状态 | ST-01 归 CONFIG-STORE；ST-04 归 PENDING-QUEUE；本层只产生 DS-SP-* |
| 边界指纹 | manifest `boundary_fingerprint` 全量条目 |

## 2. 下一层可选 child_id

| child_id | 一句话职责 | 建议细化焦点 | 需求/父层追踪 | trace_exemption_reason |
|---|---|---|---|---|
| `CMP-SP-CONFIG-VIEW-PROJECTOR` | 配置完整性和目录错误事实投影 | config view 字段/版本、目录错误映射入口 | REQ-DD002；D-AC-REQ-002-01；ST-01；IC-M01-05 | — |
| `CMP-SP-RENDER-ADAPTER` | 标准展示视图接入宿主交互面 | 宿主 Codex 渲染 API、交互载体、VIEW_NOT_AVAILABLE 处理 | REQ-DD001/002；父层 local_outbound；LCD-SP-004 | — |
| `CMP-SP-STATUS-MESSAGE-MAPPER` | 状态、缺项、失败原因到可读消息的映射 | message_key、文案资源、多语言与未知状态策略 | D-AC-REQ-001-01/002-01；FLOW-M01-001~003；LCD-SP-003/005 | — |
| `CMP-SP-TASK-VIEW-PROJECTOR` | 提交任务事实投影 | task view 字段校验、提交编号/状态/进度投影 | REQ-DD001；D-AC-REQ-001-01；ST-04；IC-M01-05 | — |

## 3. 契约清单

### 3.1 继承契约

| contract_id | owner → consumer | 语义 |
|---|---|---|
| `IC-M01-05` | CMP-PENDING-QUEUE / CMP-CONFIG-STORE → CMP-STATUS-PRESENTER | 只读任务/配置展示数据；失败为 `VIEW_NOT_AVAILABLE` |

### 3.2 当前层内部契约

| contract_id | provider → consumer | 语义 |
|---|---|---|
| `IC-L2-SP-01` | TASK-VIEW-PROJECTOR → STATUS-MESSAGE-MAPPER | 任务事实投影 |
| `IC-L2-SP-02` | CONFIG-VIEW-PROJECTOR → STATUS-MESSAGE-MAPPER | 配置事实投影 |
| `IC-L2-SP-03` | STATUS-MESSAGE-MAPPER → RENDER-ADAPTER | 标准展示视图 |

这些契约均限定在当前组件内，不能替代或升级 `IC-M01-05`。

## 4. 状态所有权清单

| state_id | 状态 | owner |
|---|---|---|
| `DS-SP-CONFIG-VIEW-MODEL` | 配置展示派生模型（瞬时） | CMP-SP-CONFIG-VIEW-PROJECTOR |
| `DS-SP-PRESENTATION-VIEW` | 统一展示派生模型（瞬时） | CMP-SP-STATUS-MESSAGE-MAPPER |
| `DS-SP-TASK-VIEW-MODEL` | 任务展示派生模型（瞬时） | CMP-SP-TASK-VIEW-PROJECTOR |
| `ST-01` | PluginConfig（父层持久状态） | CMP-CONFIG-STORE |
| `ST-04` | PendingTask（父层持久状态） | CMP-PENDING-QUEUE |

关键不变量：`INV-SP-001` 只读；`INV-SP-002` 保留事实；`INV-SP-003` 缺项具体；`INV-SP-004` 不将失败/未知改成成功；`INV-SP-005` 单快照确定性；`INV-SP-006` 展示失败无业务副作用。

## 5. 决策继承、本地决定与委托

- **继承**：`KD-003`、`KD-004`、`KD-005`、`A-007`、`IC-M01-05`、DU-1。
- **本层已决定**：`LCD-SP-001` 无状态投影；`LCD-SP-002` 任务/配置分开投影；`LCD-SP-003` 保留状态事实并中性呈现未知结果。
- **委托下一层**：`LCD-SP-004` 宿主渲染 API与交互载体；`LCD-SP-005` 文案资源与多语言组织。
- **实现细节**：`LCD-SP-006` UI/模板实现；`LCD-SP-007` 非敏感诊断日志。
- **未决但不阻塞**：无父层影响项，无 `parent-change-request.md`。

## 6. 推荐下一步

1. 首选 `[NEXT CMP-SP-RENDER-ADAPTER]`：它承接当前唯一尚未具体化的宿主交互边界。
2. 次选 `[NEXT CMP-SP-STATUS-MESSAGE-MAPPER]`：落实状态/错误文案目录与未知状态策略。
3. `CMP-SP-TASK-VIEW-PROJECTOR` 与 `CMP-SP-CONFIG-VIEW-PROJECTOR` 可在需要字段级 schema 细化时进入下一轮。

所需祖先上下文：本包七个文件、L1 `04-contracts-and-runtime.md` 的 IC-M01-05 与 FLOW-M01-001~003；无需读取兄弟组件内部。

## 7. 实际输入/输出、验证证据与未完成项

### 7.1 实际解析输入

| 输入 | 路径 | 状态 |
|---|---|---|
| parent_architecture | `architecture/L1/L1-mod-01` | 递归子架构包，已解析 |
| target_node_id | `CMP-STATUS-PRESENTER` | `child-handoff.md` 与 `IC-M01-05` 唯一匹配 |
| current_prd | `prd/L2-PRD/mod-01/L2-mod-01-cmp-status-presenter/prd.md` | 已解析；REQ-DD001/002 与两条 D-AC |
| output_dir | `architecture/L2/mod-01/L2-mod-01-cmp-status-presenter` | 新建目标包，未覆盖兄弟目录 |

### 7.2 实际生成输出

本包生成七个文件：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。未生成 `parent-change-request.md`，因为没有 `return_to_parent`。

### 7.3 已执行检查

| 检查 | 结果 |
|---|---|
| 四项输入解析和目标唯一匹配 | 通过 |
| 输出目录安全与兄弟目录隔离 | 通过 |
| 需求/验收契约追踪 | 通过；REQ-DD001/002 和 D-AC-REQ-001-01/002-01 均有承接 |
| 子节点追踪列与豁免列 | 通过；4 个 child 均有需求/父层追踪，豁免数 0 |
| 父契约 IC-M01-05 字段/owner/side effects/version | 通过；未修改 |
| 状态所有权与无持久状态 | 通过；ST-01/ST-04 未转移，DS-SP-* 均瞬时 |
| 成功、失败/恢复、配置生命周期 | 通过；R1/R2/R3 已记录 |
| 局部决策队列 | 通过；无遗留 decide_now/return_to_parent |

### 7.4 未完成项与阻塞影响

- 宿主 Codex 的具体渲染 API、交互载体和文案资源组织留给下一层；不阻塞当前包交接。
- 当前无阻塞项；状态为 `ready_for_human_gate`。
