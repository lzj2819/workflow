# Leaf Gate Override ? CMP-PENDING-QUEUE

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-PENDING-QUEUE（L2 → 下一层）

> 本文件是下一层递归细化的唯一入口。Human Gate 通过后，以 `[NEXT child_id]` 选择一个子节点继续设计。

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 当前节点 | `CMP-PENDING-QUEUE`（L2，属于 `MOD-01`，DU-1 student-plugin） |
| 职责 | PendingTask 创建、状态机推进、失败原因、恢复调度、上传前置检查、终态清理 |
| 排除项 | 不执行上传/查询/认证；不解析、采集、展示；不持有服务端 Submission；不创建新部署单元 |
| 直接父包 | `architecture/L1/L1-mod-01` |
| 当前包 | `architecture/L2/mod-01/L2-mod-01-cmp-pending-queue` |
| 绑定决策 | KD-003、KD-005、A-007、LCD-005、DU-1 |
| 绑定契约 | IC-M01-01（消费意图解析结果）、IC-M01-03、IC-M01-04、IC-M01-05；间接受 CT-001/CT-002/auth-token 约束 |
| 边界指纹 | `MOD-01/ST-04/IC-M01-03-04-05/KD-005/A-007/LCD-005/DU-1` |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| `CMP-PENDING-QUEUE-CLEANUP` | 终态本地 artifact 与任务清理协调 | 清理顺序、幂等删除、清理失败重试、进程启动补偿 | REQ-DD001；当前 PRD 终态清理；retention_boundary |
| `CMP-PENDING-QUEUE-ORCHESTRATOR` | PendingTask 聚合与父内部契约编排 | 状态迁移表、前置检查、lease、IC-M01-03/04/05 映射 | REQ-DD001；D-AC-REQ-001-01；ST-04 |
| `CMP-PENDING-QUEUE-RECOVERY-SCHEDULER` | 多触发源恢复调度 | worker API、timer、可达性提示、backoff、trigger 去重 | LCD-005；CT-001 Retry；D-AC-REQ-001-01 exceptions |
| `CMP-PENDING-QUEUE-STATE-STORE` | 本地状态持久化逻辑端口的具体实现 | 文件/KV 选择、schema、revision/CAS、checksum、迁移与隐私 | A-007；ST-04；PQ-INV-004 |

所有子节点均有需求或父层追踪，无 `trace_exemption_reason`。

## 3. 契约清单

### 继承契约

- `IC-M01-01`：当前节点由 ORCHESTRATOR 消费 IntentParsed；SubmissionIntent/MissingFields 字段语义与缺项不建任务语义不变。
- `IC-M01-03`：当前节点由 ORCHESTRATOR 编排采集；字段、一次性快照和错误语义不变。
- `IC-M01-04`：当前节点驱动 UPLOAD-CLIENT；uuid、checkpoint、UploadOutcome、30 秒 unknown 语义不变。
- `IC-M01-05`：当前节点提供 TaskView；read-only 和不伪造远端结论语义不变。
- `CT-001`、`CT-002`、`auth/token`：只作为上游协议约束引用，当前包不直接重设计。

### 当前包内部契约

| contract_id | 名称 | Provider → Consumer |
|---|---|---|
| `IC-PQ-000` | Intent Intake Port | CMP-INTENT-PARSER → ORCHESTRATOR |
| `IC-PQ-001` | Task Lifecycle Port | ORCHESTRATOR → STATE-STORE |
| `IC-PQ-002` | Recovery Trigger Port | RECOVERY-SCHEDULER → ORCHESTRATOR |
| `IC-PQ-003` | Upload Dispatch Port | ORCHESTRATOR → CMP-UPLOAD-CLIENT |
| `IC-PQ-004` | Terminal Cleanup Port | ORCHESTRATOR → CLEANUP |
| `IC-PQ-005` | Task View Port | ORCHESTRATOR → CMP-STATUS-PRESENTER |
| `IC-PQ-006` | Cleanup Ledger Port | STATE-STORE → CLEANUP |
| `IC-PQ-007` | Dialogue Artifact Cleanup Port | CLEANUP → CMP-DIALOGUE-COLLECTOR |
| `IC-PQ-008` | Material Artifact Cleanup Port | CLEANUP → CMP-MATERIAL-COLLECTOR |
| `IC-PQ-009` | Checkpoint Cleanup Port | CLEANUP → CMP-UPLOAD-CLIENT |

字段、side_effects、dependencies、next_hop 和 return_event 详见 `04-contracts-and-runtime.md`。

## 4. 状态所有权清单

| state_id | 状态 | owner |
|---|---|---|
| `ST-PQ-01` | PendingTask | CMP-PENDING-QUEUE-ORCHESTRATOR |
| `ST-PQ-02` | TaskLease | CMP-PENDING-QUEUE-ORCHESTRATOR |
| `ST-PQ-03` | RecoverySchedule | CMP-PENDING-QUEUE-RECOVERY-SCHEDULER |
| `ST-PQ-04` | CleanupLedger | CMP-PENDING-QUEUE-CLEANUP |
| `ST-PQ-05` | StateStoreEnvelope | CMP-PENDING-QUEUE-STATE-STORE |

关键不变量：PQ-INV-001 缺项不 dispatch；PQ-INV-002 uuid 不变；PQ-INV-003 单任务单活跃 lease；PQ-INV-004 只从一致 revision 恢复；PQ-INV-005 仅终态清理；PQ-INV-006 状态更新原子提交。

## 5. 决策继承、本地决定与委托

- **继承**：KD-003、KD-005、DU-1、CT-001/CT-002 全部语义、父 ST-04 与 retention_boundary。
- **本层已决定**：LCD-PQ-001 混合恢复触发；LCD-PQ-002 持久化 TaskLease 单飞；LCD-PQ-003 StateStore revision 原子提交边界。
- **委托下一层**：LCD-PQ-004 worker/timer API；LCD-PQ-005 具体存储产品与 schema；LCD-PQ-006 清理批次与退避参数。
- **无父层变更请求**：当前设计没有改变父职责、公共契约、数据所有权、技术、部署或依赖方向。

## 6. 未解决项与风险

| 事项 | 影响 | 处置 |
|---|---|---|
| 宿主 worker 的具体调度 API 未由父层规定 | 影响 scheduler 子节点的实现方式，不影响混合触发语义 | 下一层确认 API；若需要新外部服务/部署单元，必须返回父层 |
| 本地状态介质和 schema 迁移未定 | 影响 STATE-STORE 的实现细节，不影响 StateStore 逻辑端口 | 下一层在 A-007 边界内选择；不得引入服务端存储 |
| 清理失败的具体退避参数未定 | 影响 cleanup 子节点参数，不改变终态/保留边界 | 下一层定义；清理失败不回滚远端状态 |

上述事项均为 `defer_to_next_level`，没有阻塞当前架构包。

## 7. 实际输入、输出与验证结果

### 实际输入

| 输入 | 路径 | 结果 |
|---|---|---|
| parent_architecture | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L1\L1-mod-01` | recursive_child_package，已读取 manifest、上下文、分解、状态、契约、决策、handoff |
| target_node_id | `CMP-PENDING-QUEUE` | 02 canonical child registry 唯一行匹配，并由 child-handoff 交叉确认 |
| current_prd | `C:\Users\Lenovo\Desktop\codex_plugin\prd\L2-PRD\mod-01\L2-mod-01-cmp-pending-queue\prd.md` | REQ-DD001、D-AC-REQ-001-01、终态清理目标已读取 |
| output_dir | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L2\mod-01\L2-mod-01-cmp-pending-queue` | 新建目标目录；两个兄弟包未修改 |

### 实际输出

已生成 7 个标准递归架构文件：

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

### 验证结果

| 检查 | 结果 |
|---|---|
| 四必需输入、父包类型和输出安全 | 通过 |
| 目标节点唯一匹配 | 通过 |
| REQ-DD001 / D-AC-REQ-001-01 追踪 | 通过 |
| 子节点追踪列与豁免列 | 通过，4 个子节点、0 个豁免 |
| 父状态 ST-04 与兄弟状态所有权未转移 | 通过 |
| IC-M01-03/04/05 与 CT-001/CT-002 语义未改 | 通过 |
| 成功、失败/恢复、未知结果/清理运行流 | 通过 |
| 决策队列无 `decide_now` 遗留、无 `return_to_parent` | 通过 |
| 稳定 ID 排序 | 通过 |

## 8. 推荐下一步

建议优先细化 `CMP-PENDING-QUEUE-RECOVERY-SCHEDULER`，因为它承接 L1 `LCD-005` 的核心风险；其次是 `CMP-PENDING-QUEUE-STATE-STORE`，明确 A-007 的本地持久化实现。当前包已达到 `ready_for_human_gate`，等待 `[APPROVE]` 或 `[REVISE ...]`。
