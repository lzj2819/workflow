# 01 Design Context — CMP-PENDING-QUEUE（L2）

## 1. 本次设计范围

- **目标节点**：`CMP-PENDING-QUEUE`，父层 `MOD-01 codex-plugin` 内的本地待上传任务队列。
- **当前 PRD**：`prd/L2-PRD/mod-01/L2-mod-01-cmp-pending-queue/prd.md`。
- **模式**：`new`；输出目录为 `architecture/L2/mod-01/L2-mod-01-cmp-pending-queue`，该目录在写入前不存在，未覆盖既有兄弟包。
- **本层目标**：细化 PendingTask 的本地生命周期、持久化边界、恢复调度和终态清理；不重跑顶层 DDD，不重设计父模块或兄弟组件。

## 2. 父边界快照

| 条目 | 父层绑定 | 来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `CMP-PENDING-QUEUE`，归属 `MOD-01`、部署于 `DU-1 student-plugin` | L1 manifest、02、child-handoff | inherited-fixed |
| 职责 | 创建 PendingTask；前置检查；状态机推进；失败原因记录；恢复调度；终态清理 | L1 02 §2 | inherited-refinable |
| 排除项 | 不执行上传/查询，不解析、不采集、不展示，不持有服务端 Submission | L1 02 §2、child-handoff §1 | inherited-fixed |
| 本地状态 | `ST-04 PendingTask` 由父组件拥有；关联 ST-02/ST-03/ST-05 的清理和协作边界不得改变 | L1 03 §1/§2 | inherited-fixed |
| 输入/输出 | 消费 `IC-M01-01` 的意图解析结果与 `IC-M01-03` 的采集结果，驱动 `IC-M01-04` 上传执行，向 `IC-M01-05` 提供任务视图 | L1 04 §1–§3 | inherited-fixed |
| 外部契约 | CT-001/CT-002/auth-token 由 `CMP-UPLOAD-CLIENT` 实现；本层只通过父内部契约驱动 | L1 04 §1/§2 | inherited-fixed |
| 运行顺序 | 信息齐全→任务创建→采集→上传；中断保留；未知结果查询；终态清理 | L1 04 R1/R2 | inherited-fixed |
| 技术/部署 | 学生本机插件内逻辑组件；HTTPS、uuid 幂等、断点续传；不新增服务或存储服务 | L1 KD-003/KD-005、DU-1 | inherited-fixed |
| 委托项 | A-007 的具体持久化机制、LCD-005 的恢复触发机制委托本层细化 | L1 05 | delegated |

### 2.1 边界指纹

```yaml
parent_node_id: MOD-01
target_node_id: CMP-PENDING-QUEUE
responsibility: local_pending_task_lifecycle_and_recovery
parent_state: ST-04
parent_contracts: [IC-M01-03, IC-M01-04, IC-M01-05]
external_contracts: [CT-001, CT-002, auth-token]
fixed_decisions: [KD-003, KD-005, DU-1]
delegated_decisions: [A-007, LCD-005]
boundary_fingerprint: "MOD-01/ST-04/IC-M01-03-04-05/KD-005/A-007/LCD-005/DU-1"
```

## 3. 当前 PRD 需求分配

当前 PRD 的功能性章节为空，但 frontmatter、Problem Statement 和 D-AC-REQ-001-01 已明确目标行为。以下分配以当前 PRD 与 L1 父包共同作为需求证据，不擅自补造新的系统边界。

| 当前需求 | 分类 | 需求/父层追踪 | 本层承接 |
|---|---|---|---|
| `REQ-DD001`：承接提交任务的本地创建、推进、失败记录、恢复和终态清理 | allocated | 当前 PRD `requirement_id_mapping.REQ-D001 -> REQ-DD001`；L1 `REQ-D001`、`AC-REQ-001-01` | ORCHESTRATOR、STATE-STORE、RECOVERY-SCHEDULER、CLEANUP |
| `D-AC-REQ-001-01`：创建唯一提交任务；缺项不创建可评分提交；连接失败保留本地任务并显示失败原因 | allocated | 当前 PRD §Acceptance Contracts；父 `AC-REQ-001-01` / L1 `IC-M01-04` | PQ-INV-001/002/003/005；成功与失败/恢复流 |
| 任务终态清理 | local | 当前 PRD Problem Statement「任务终态清理」；L1 `retention_boundary` | CLEANUP 协调 ST-02/ST-03/ST-04/ST-05 清理 |
| 恢复调度触发 | local | L1 `LCD-005`、AC-REQ-001-01 exceptions、CT-001 Retry | RECOVERY-SCHEDULER；混合触发策略 |
| A-007 本地持久化机制 | delegated→local boundary | L1 `A-007` 明确委托；本层只固定原子性与恢复语义 | STATE-STORE；具体产品/序列化下沉 |
| CT-001/CT-002 字段、错误、幂等、版本 | inherited | L1 `CT-001/CT-002`、`KD-005` | 仅通过 IC-M01-04 驱动，不改外部语义 |
| 系统边界/外部依赖/明确约束 | inherited | 当前 PRD 标记「待补充；不得擅自决定」；完整内容来自 L1 | 本层只引用 L1，不新增边界 |

无 out-of-scope 需求被错误分配；兄弟组件内部不在本层范围内。

## 4. 局部驱动

1. **本地可靠性**：网络中断、进程重启或 worker 失败后，任务仍可从最近一致状态恢复。
2. **幂等与串行化**：同一个 `submission_uuid` 不得同时存在两个活跃上传作业；恢复不得生成新 uuid。
3. **未知结果收敛**：30 秒确认超时只进入 `confirm_required`，由上传客户端查询，不由队列猜测远端结论。
4. **状态原子性**：状态迁移、失败原因和恢复计数必须作为同一逻辑更新提交，避免“已调度但状态仍 failed”等裂缝。
5. **隐私生命周期**：仅在 `received/rejected` 终态协调清理；`failed/confirm_required` 任务与 checkpoint 必须保留。

## 5. 可复用能力、阻塞缺口与假设

### 可复用能力

- L1 已定义 `PendingTask`、`ST-04`、`IC-M01-03/04/05`、`INV-1~INV-5`。
- `CMP-UPLOAD-CLIENT` 已拥有 CT-001/CT-002 的网络、分片、checkpoint 和认证实现；本层不复制。
- L1 `retention_boundary` 已定义四类本地状态的清理 owner 和服务端保留边界。

### 非阻塞假设

- “网络可达性提示”可由宿主环境提供为提示信号；即使没有该信号，启动恢复、退避定时器和手动重试仍能保证可恢复性。
- 本层把 `StateStore` 定义为逻辑持久化端口，不决定文件、KV 或序列化产品。
- 任务恢复的调度优先级按创建时间和失败重试时间排序；具体队列排序参数下沉到下一层。

### 阻塞缺口

无。父职责、状态所有权、契约、部署和技术边界均可得；当前 PRD 的待补充项由父层事实覆盖并在本文件明确继承。

## 6. 拟创建文件、上下游影响与验证方法

拟创建本递归包的 7 个标准文件；无 `parent-change-request.md`。上游/下游契约仅做实现映射，不修改 producer、consumer、字段、路径、失败、重试、幂等或版本语义。

验证方法：检查四输入与唯一匹配；逐条核对 REQ-DD001/D-AC-REQ-001-01；检查四个子节点的追踪列；核对 ST-04 与父状态机边界；静态检查内部契约字段、`side_effects`、`dependencies`、`next_hop`；核对三条运行流和决策队列无 `return_to_parent`。
