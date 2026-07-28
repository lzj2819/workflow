# 03 State and Data — CMP-PENDING-QUEUE 状态与数据

> 本文件细化父层 `ST-04 PendingTask` 的本地实现；不转移 MOD-02 的 Submission、服务端状态机或保留治理所有权。

## 1. 状态所有权清单（按稳定状态 ID 排序）

| 状态 ID | 状态 | Owner (child_id) | 持久化协作者 | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|---|
| `ST-PQ-01` | `PendingTask`：uuid、意图快照、BundleRef、客户端状态、远端应答摘要、失败原因、时间戳 | `CMP-PENDING-QUEUE-ORCHESTRATOR` | STATE-STORE | ORCHESTRATOR、RECOVERY-SCHEDULER、CLEANUP、STATUS-PRESENTER（经 IC-M01-05） | 仅 ORCHESTRATOR | 创建→状态迁移→received/rejected 或持续 failed/confirm_required | 单任务聚合事务；迁移和原因原子提交 | 仅学生本机；终态后由 CLEANUP 协调删除 | L1 `ST-04`；REQ-DD001；D-AC-REQ-001-01 |
| `ST-PQ-02` | `TaskLease`：lease_id、task_uuid、owner、expires_at | `CMP-PENDING-QUEUE-ORCHESTRATOR` | STATE-STORE | ORCHESTRATOR、RECOVERY-SCHEDULER | ORCHESTRATOR | ready/uploading 期间存在；终态或过期释放 | 同一 uuid 单活跃 lease；获取/续期/释放原子 | 不含材料内容；随任务终态清理 | L1 `CON-1`；IC-M01-04；KD-005 |
| `ST-PQ-03` | `RecoverySchedule`：next_attempt_at、attempt_count、last_trigger、backoff_class、suppressed_reason | `CMP-PENDING-QUEUE-RECOVERY-SCHEDULER` | STATE-STORE | RECOVERY-SCHEDULER、ORCHESTRATOR | RECOVERY-SCHEDULER | failed/confirm_required 保留；成功收敛或终态后删除 | 触发去重；过期计时器只能产生一次可合并请求 | 只保留调度元数据；不复制远端状态 | L1 `LCD-005`；CT-001 Retry |
| `ST-PQ-04` | `CleanupLedger`：task_uuid、artifact_refs、terminal_state、pending_items、last_error、next_retry_at | `CMP-PENDING-QUEUE-CLEANUP` | STATE-STORE | CLEANUP、ORCHESTRATOR | CLEANUP | received/rejected 后创建；全部关联 artifact 清理完成后删除 | 清理项逐项幂等；失败不回滚远端终态 | 用于本地隐私清理；不承接服务端删除审计 | L1 `retention_boundary`；当前 PRD 终态清理 |
| `ST-PQ-05` | `StateStoreEnvelope`：schema_version、revision、task/lease/schedule/cleanup records、checksum | `CMP-PENDING-QUEUE-STATE-STORE` | 本机持久化介质（产品未定） | STATE-STORE | STATE-STORE | 进程重启后恢复；迁移完成后替换旧 revision | 写入采用 revision/CAS 或等价原子提交；校验失败拒绝加载并保留上一份有效状态 | 仅本机；不含服务端 Submission 全量内容 | L1 `A-007`、`KD-005` |

## 2. 存储意图

- 状态全部位于 DU-1 学生本机；本层不引入共享数据库、服务端队列、消息总线或独立存储服务。
- `ST-PQ-01/02/03/04/05` 均需要跨进程重启恢复；具体文件、嵌入式 KV、序列化格式和加密实现是下一层 implementation_detail。
- STATE-STORE 对外只暴露逻辑端口：`load_snapshot`、`commit_revision`、`compare_and_swap`、`list_due_tasks`、`purge_record`；不让业务节点直接依赖具体介质。
- `StateStoreEnvelope` 必须可校验、可版本化、可原子替换；发现 checksum/schema 不兼容时不覆盖最近一次有效状态，记录本地恢复错误并要求下一层定义迁移/修复策略。

## 3. 数据流

### 3.1 写入流

1. ORCHESTRATOR 收到齐全 `SubmissionIntent` 与有效配置后，生成一次性的 `submission_uuid`，创建 `ST-PQ-01=ready`。
2. ORCHESTRATOR 通过 IC-M01-03 驱动对话/材料采集；BundleRef 回来后，在同一逻辑事务内把任务推进为 `ready` 并登记 snapshot refs。
3. ORCHESTRATOR 获取 `ST-PQ-02` 后通过 IC-M01-04 驱动上传；UploadOutcome 返回后原子更新 ST-PQ-01，并按结果创建/删除恢复计划。
4. `failed` 或 `confirm_required` 时，RECOVERY-SCHEDULER 更新 ST-PQ-03；恢复触发仅产生命令，不直接写任务状态。
5. `received/rejected` 时，CLEANUP 创建 ST-PQ-04；每项清理完成后更新 ledger，全部完成才删除本地状态。

### 3.2 读取流

- 恢复扫描读取 `ST-PQ-01` 与 `ST-PQ-03`，只选择满足 `next_attempt_at` 且无活跃 lease 的任务。
- STATUS-PRESENTER 通过 IC-M01-05 读取任务视图；不读取 StateStoreEnvelope，也不维护副本。
- ORCHESTRATOR 读取 ST-PQ-01 的 `submission_uuid`、BundleRef 和 checkpoint 引用，交给 CMP-UPLOAD-CLIENT；不读取/重建父服务端状态。

### 3.3 外部化边界

- `IC-M01-03`：仅向采集器传递任务引用；采集产物回到 ORCHESTRATOR 后写入本地任务。
- `IC-M01-04`：仅向上传客户端提供冻结的 uuid、identity、BundleRef 和可选 checkpoint；上传客户端负责 CT-001/CT-002/auth-token。
- `IC-M01-05`：仅把本地任务视图提供给展示器；`confirm_required` 必须显示未知/查询中，不得显示伪造结果。

## 4. 不变量、一致性、幂等与并发规则

| 规则 | 内容 | 依据 |
|---|---|---|
| `PQ-INV-001` | 意图缺作业/姓名/小组，或配置前置检查未通过时，不创建可上传任务、不调用 IC-M01-04 | L1 `INV-1`、F1-1、D-AC-REQ-001-01 |
| `PQ-INV-002` | `submission_uuid` 在创建时生成且全生命周期不变；恢复不得生成新 uuid | L1 `INV-2`、KD-005 |
| `PQ-INV-003` | 同一 task_uuid 同时至多一个 active TaskLease；重复 recovery trigger 合并 | L1 `CON-1`；本层 LCD-002 |
| `PQ-INV-004` | recovery 只能从持久化的最新一致 revision 恢复，不从内存猜测 checkpoint 或状态 | A-007；本层 LCD-003 |
| `PQ-INV-005` | `received/rejected` 才允许创建 CleanupLedger；`failed/confirm_required` 必须保留任务及相关上传状态 | L1 retention_boundary、D-AC exceptions |
| `PQ-INV-006` | 状态、失败原因、lease/recovery 计划的相关更新必须原子提交；提交失败时对外不发布已迁移事件 | 本地一致性驱动 |
| `PQ-IDEM-001` | 相同 `submission_uuid` 的重复创建请求返回既有 PendingTask；不创建第二个任务 | KD-005、父 IC-M01-04 |
| `PQ-IDEM-002` | 清理每个 artifact ref 可重复执行；已不存在视为成功，不重复删除远端数据 | L1 retention_boundary |

## 5. 父/兄弟所有权未转移确认

- MOD-02 的 Submission 聚合、服务端提交状态机、CT-001/CT-002 权威结果和服务端保留治理仍归父层定义的 owner。
- CMP-UPLOAD-CLIENT 仍拥有 UploadCheckpoint（父 ST-05）；本层只引用 checkpoint，不持有其分片确认细节。
- CMP-DIALOGUE-COLLECTOR、CMP-MATERIAL-COLLECTOR 仍分别拥有 ST-02/ST-03 的内容和 artifact 清理执行；CLEANUP 只协调终态清理。
- 两个兄弟 L2 包的内部状态未被读取或重设计；本层只使用 L1 已公开的配置读取和 artifact 清理协作语义。
