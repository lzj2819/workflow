# Leaf Gate Override ? CMP-UPLOAD-CLIENT

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-UPLOAD-CLIENT（L2 → L3）

> 本文件是下一层递归细化的入口。Human Gate 批准后，以 `[NEXT child_id]` 选择下表一个 child 继续设计；本包不直接生成代码或实现方案。

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 当前节点 | `CMP-UPLOAD-CLIENT`（L2，父 L1 `MOD-01`，DU-1 student-plugin） |
| 职责 | 令牌获取；CT-001 创建会话/逐分片/合并；ST-05 checkpoint；30 秒超时转 CT-002；断点续传 |
| 排除项 | 不改父契约；不拥有 Submission；不决定父任务状态机；不采集材料；不创建服务/部署单元 |
| 直接父包 | `architecture/L1/L1-mod-01` |
| 当前 PRD | `prd/L2-PRD/mod-01/L2-mod-01-cmp-upload-client/prd.md` |
| 边界指纹 | manifest 中 `boundary_fingerprint`；绑定 CT-001、CT-002、auth/token、IC-M01-04、ST-05、KD-003/005、A-007 |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 推荐细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| `CMP-UPLOAD-AUTH-ADAPTER` | 管理短生命周期访问令牌租约与失效重取 | 凭据上下文、401 重放边界、租约清理与可观测字段 | REQ-DD001；auth/token；KD-005；LCD-UP-002 |
| `CMP-UPLOAD-ORCHESTRATOR` | 编排 UploadJob、单任务保护与 UploadOutcome 回调 | ActiveUploadGuard 生命周期、重复启动归并、取消/崩溃恢复入口 | REQ-DD001；IC-M01-04；LCD-UP-003 |
| `CMP-UPLOAD-OUTCOME-RESOLVER` | 收敛 CT-001/CT-002 观察结果 | unknown→查询→终态状态图、指数退避参数、错误映射 | REQ-DD001；D-AC-REQ-001-01；CT-002；LCD-UP-004/006 |
| `CMP-UPLOAD-SESSION-DRIVER` | 执行会话、分片、合并与 checkpoint | 分片编码、ack 对账、会话恢复、单分片重放 | REQ-DD001/003/004；D-AC-REQ-003-01；CT-001；ST-05；LCD-UP-001/005 |

无 `trace_exemption_reason`：所有 child 均有直接需求或父层契约/决策追踪。

## 3. 继承契约与内部契约

### 继承契约

- `CT-001`：MOD-02 Provider；字段、创建会话→逐分片→合并、错误码、30 秒超时、uuid 幂等和版本不变。
- `CT-002`：MOD-02 Provider；`GET /api/v1/submissions/{submission_uuid}`、404、指数退避、只读幂等不变。
- auth/token：属于 CT-001 契约族附属交互；AUTH_INVALID 与名单核对语义仍由 MOD-02 权威。
- `IC-M01-04`：父队列向本节点提供 `UploadJob`，本节点返回 `UploadOutcome`；不提升为跨模块契约。

### 本层内部契约

| 契约 ID | 名称 | Owner → Consumer |
|---|---|---|
| `IC-UP-001` | UploadJob 编排入口 | 父 `CMP-PENDING-QUEUE` → ORCHESTRATOR |
| `IC-UP-002` | AccessTokenLease 请求端口 | ORCHESTRATOR → AUTH-ADAPTER |
| `IC-UP-003` | ChunkSessionExecution | ORCHESTRATOR → SESSION-DRIVER |
| `IC-UP-004` | RemoteStatusQuery | OUTCOME-RESOLVER → SESSION-DRIVER |
| `IC-UP-005` | UploadOutcomeResolution | OUTCOME-RESOLVER → ORCHESTRATOR |
| `IC-UP-006` | TransferObservation 观察投递 | SESSION-DRIVER → OUTCOME-RESOLVER |

字段级 required/produced、错误、`next_hop`、副作用和兼容策略见 `04-contracts-and-runtime.md` §3.1。

## 4. 状态所有权清单

| 状态 ID | 状态 | Owner |
|---|---|---|
| `ST-05` | UploadCheckpoint（服务端已确认分片） | `CMP-UPLOAD-SESSION-DRIVER` |
| `ST-L2-01` | AccessTokenLease（仅内存） | `CMP-UPLOAD-AUTH-ADAPTER` |
| `ST-L2-02` | ActiveUploadGuard（仅内存） | `CMP-UPLOAD-ORCHESTRATOR` |

关键不变量：服务端 ack 后写 checkpoint；同 uuid 至多一个活跃执行；30 秒未知先 CT-002；AUTH_INVALID 使旧 lease 失效；MOD-02 仍拥有 Submission/服务端状态。

## 5. 继承、本地决定、委托与风险

- **继承**：`KD-003`、`KD-005`、`A-007`、DU-1、CT-001、CT-002、auth/token、IC-M01-04。
- **本层已决定**：`LCD-UP-001` ack 后写 checkpoint；`LCD-UP-002` token lease 只在内存短期复用；`LCD-UP-003` 单 uuid 单活跃执行；`LCD-UP-004` unknown 先查询不整包重传。
- **下一层/实现委托**：`LCD-UP-005` 分片大小/编码/HTTP 客户端；`LCD-UP-006` 指数退避具体参数。
- **未解决风险**：父层没有规定具体分片大小和 HTTP 客户端；只要不改变 CT-001 schema/顺序/错误/幂等/版本，可在 L3 或实现阶段决定。

## 6. 推荐下一步

1. 首选 `[NEXT CMP-UPLOAD-SESSION-DRIVER]`：它拥有 ST-05，承载协议顺序、ack 对账和断点恢复的最高风险。
2. 次选 `[NEXT CMP-UPLOAD-OUTCOME-RESOLVER]`：细化 30 秒未知、CT-002 查询和指数退避。
3. 随后细化 `[NEXT CMP-UPLOAD-AUTH-ADAPTER]` 与 `[NEXT CMP-UPLOAD-ORCHESTRATOR]`。

所需祖先上下文：本包七个文件、父 L1 `04-contracts-and-runtime.md`（CT-001/CT-002/IC-M01-04）和 `03-state-and-data.md`（ST-05/INV-5）；无需读取兄弟节点内部。

## 7. 实际输入、输出、验证与未完成项

### 实际解析输入

| 输入 | 路径 | 结果 |
|---|---|---|
| parent_architecture | `architecture/L1/L1-mod-01` | 递归父包，manifest 可读 |
| target_node_id | `CMP-UPLOAD-CLIENT` | 在父 decomposition 与 handoff 各唯一命中 |
| current_prd | `prd/L2-PRD/mod-01/L2-mod-01-cmp-upload-client/prd.md` | 已读；REQ-DD001/003/004 与两条验收契约 |
| output_dir | `architecture/L2/mod-01/L2-mod-01-cmp-upload-client` | 写入前不存在；兄弟目录未修改 |
| parent_prd | 未读取 | 父包已提供需求和契约追踪，无需补充 |

### 实际生成输出

已生成 7 个常规文件：

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

未生成 `parent-change-request.md`，因为没有 `return_to_parent` 项。

### 执行的检查及结果

| 检查 | 结果 |
|---|---|
| 四项输入与 output_dir 安全 | 通过 |
| 父包适配与目标唯一匹配 | 通过 |
| 需求/验收契约追踪 | 通过；REQ-DD001/003/004 均落到 child 或父契约 |
| 子节点清单 | 通过；4 个稳定 ID，均有职责/排除/状态/依赖/理由/追踪 |
| 状态所有权 | 通过；ST-05 只在目标内部细化，token/guard 为本机瞬态 |
| 父契约字段与机器可读绑定 | 通过；IC-UP-001~006 均声明 required/produced、错误、依赖、next_hop |
| 运行流覆盖 | 通过；成功、失败恢复、超时查询/拒绝生命周期均有流程 |
| 决策队列 | 通过；无遗留 decide_now、无 return_to_parent |
| 兄弟/父边界 | 通过；未重设计兄弟或 MOD-02，未新增部署单元 |

### 未完成项与阻塞影响

- 具体分片大小、multipart 编码和 HTTP 客户端留给 `CMP-UPLOAD-SESSION-DRIVER` L3/实现阶段。
- 指数退避具体参数留给 `CMP-UPLOAD-OUTCOME-RESOLVER` L3；本层已固定必须查询且不得伪造终态。
- 无阻塞项；当前包可进入一次 Human Gate。
