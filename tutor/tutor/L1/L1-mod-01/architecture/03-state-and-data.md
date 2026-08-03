# 03 State and Data — MOD-01 codex-plugin 状态与数据

> 本文件只规定 MOD-01 内部本地状态的所有权与一致性；不转移、不复制任何父/兄弟节点的数据所有权（确认见 §6）。

## 1. 状态所有权清单（按稳定状态 ID 排序）

| 状态 ID | 状态 | Owner (child_id) | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-01 | PluginConfig（邀请码、姓名、小组、代码/截图/结果目录、completeness 缺失项） | CMP-CONFIG-STORE | INTENT-PARSER、DIALOGUE-COLLECTOR、MATERIAL-COLLECTOR、UPLOAD-CLIENT、STATUS-PRESENTER（均只读） | 仅 CONFIG-STORE（学生保存动作） | 持久；保存成功即生效直至下次有效保存；无效保存不生效 | 单写方本地事务：校验+写入同一原子步骤；读者读到的是最近一次**有效**保存 | 含姓名/邀请码等个人信息：仅存学生本机，不随材料外发（invite_code 仅用于令牌换取，KD-005） | REQ-D002；AC-REQ-002-01；组件接口卡 local_inbound |
| ST-02 | 对话导出物（完整 Codex 对话，类别=对话） | CMP-DIALOGUE-COLLECTOR | PENDING-QUEUE（编排）、UPLOAD-CLIENT（作为 material_chunks 条目上传） | 仅 DIALOGUE-COLLECTOR（任务创建时一次性采集） | 随任务：采集于任务创建时刻（LCD-002），任务进入终态（received/rejected）后随清理删除 | 采集即快照，一次性写入，不再修改；同一任务的导出物唯一 | 含对话内容（可能含个人信息/第三方代码）：仅存本机暂存，经 CT-001 加密上传（KD-003），终态后本地清除 | REQ-D003；AC-REQ-003-01 MOD-01 slice |
| ST-03 | MaterialManifest + 材料暂存引用（代码/截图/结果三类条目的路径、类别、大小） | CMP-MATERIAL-COLLECTOR | PENDING-QUEUE、UPLOAD-CLIENT、STATUS-PRESENTER（缺失/预算提示） | 仅 MATERIAL-COLLECTOR（任务创建时生成；恢复续传前可重校验存在性，不重排类别） | 随任务：与 PendingTask 同生同灭 | 清单一次性生成；条目与 CT-001 `material_chunks[]` 类别语义一一对应 | 只存路径引用与元数据，不复制文件内容；预检不产生外发 | REQ-D004；AC-REQ-003-01 MOD-01 slice；KD-004 |
| ST-04 | PendingTask 记录（submission_uuid、意图快照、清单引用、本地状态、失败原因、时间戳） | CMP-PENDING-QUEUE | STATUS-PRESENTER（展示）、UPLOAD-CLIENT（执行任务所需的任务视图） | 仅 PENDING-QUEUE（状态机迁移与失败原因记录的唯一写方） | 持久；创建 → 状态机推进 → 终态（received/rejected）后清理（含关联暂存） | 单聚合本地事务：状态迁移+原因记录原子提交；恢复后从最近一致状态继续 | 含学生姓名/小组：仅存本机；终态清理后本地不留存（服务端 Submission 归 MOD-02） | REQ-D001；AC-REQ-001-01 exceptions；KD-005；A-007 |
| ST-05 | UploadCheckpoint（上传会话标识、已确认分片索引、总分片数） | CMP-UPLOAD-CLIENT | UPLOAD-CLIENT 自身（续传恢复）、PENDING-QUEUE（进度展示数据源） | 仅 UPLOAD-CLIENT（服务端每确认一分片后更新） | 随任务上传期；任务终态后删除 | 只记录**服务端已确认**的分片；崩溃恢复后 checkpoint 与服务端会话状态可对账 | 不含材料内容，仅偏移量；无存留隐私面 | CT-001 分片协议/断点续传；KD-005 |

无持久状态的子节点：CMP-INTENT-PARSER（解析为即时计算）、CMP-STATUS-PRESENTER（纯派生展示）——二者不持有状态，故不出现在清单中（非豁免，是无状态）。

## 2. 存储意图（受父技术决策约束）

- 全部状态存于学生本机（DU-1 进程内/本机文件系统），**不引入任何服务端存储、共享数据库或独立存储服务**（符合 06 §DU-1、05 §技术组件选择「Codex Plugin 机制内实现，本地待上传队列」）。
- ST-01/ST-04/ST-05 需跨进程重启持久（断网保留、崩溃恢复）；ST-02/ST-03 为本机暂存文件与清单，随任务终态清理。
- 持久化**机制**（文件/嵌入式 KV 等）不在本层决定：父层 A-007 已标记为 implementation_detail，留待详细设计（见 `05-local-decisions.md` LCD-004）。
- 隐私底线：HTTPS 传输（KD-003）；本地暂存材料在任务终态后删除；不向除 MOD-02 外的任何方外发。

### 2.1 本地保留与删除边界

本节只定义学生本机暂存数据的生命周期，不承接服务端保留治理。`retention_due_at`、删除批次和删除审计分别由 MOD-05/MOD-02 按父架构处理，MOD-01 不新增对应 API、事件或服务端状态。

```yaml
retention_boundary:
  scope: MOD-01-local-client-state
  local_artifacts: [ST-02, ST-03, ST-04, ST-05]
  local_cleanup_owner: CMP-PENDING-QUEUE
  artifact_cleanup_owners:
    ST-02: CMP-DIALOGUE-COLLECTOR
    ST-03: CMP-MATERIAL-COLLECTOR
    ST-04: CMP-PENDING-QUEUE
    ST-05: CMP-UPLOAD-CLIENT
  cleanup_trigger:
    terminal_states: [received, rejected]
    operation: PurgeLocalTaskArtifacts
    network_effect: none
  retained_states: [uploading, failed, confirm_required]
  retry_on_cleanup_failure:
    record_field: local_cleanup_error
    retry_trigger: worker_tick_or_process_start
  server_retention_owner: MOD-05
  server_purge_executor: MOD-02
  deletion_audit_owner: MOD-05
  excluded_from_mod01: [retention_due_at, DeletionBatch, DeletionAuditRecord]
```

本地清理失败不改变服务端提交状态，也不删除 `failed`/`confirm_required` 任务；只记录本地清理错误并重试。该规则补足本地隐私生命周期，同时保持父层数据所有权不变。

## 3. 主要数据流

### 3.1 写入流

1. **配置保存**：学生保存 → CONFIG-STORE 校验（格式、目录可读性）→ 有效则原子写入 ST-01（含 completeness 标记），无效则拒绝并保留旧值（AC-REQ-002-01 exceptions）。
2. **任务创建**：INTENT-PARSER 交付齐全意图 → PENDING-QUEUE 生成 `submission_uuid` → 触发采集 → DIALOGUE-COLLECTOR 写 ST-02、MATERIAL-COLLECTOR 写 ST-03 → PENDING-QUEUE 写 ST-04（状态 ready）。
3. **上传进度**：UPLOAD-CLIENT 每获服务端分片确认 → 更新 ST-05 → 汇报 PENDING-QUEUE 更新 ST-04（uploading/进度）。

### 3.2 读取流

1. **提交前置读取**：INTENT-PARSER（默认值参考）、UPLOAD-CLIENT（invite_code）、采集节点（目录）只读 ST-01。
2. **展示读取**：STATUS-PRESENTER 只读 ST-01（配置/目录错误）与 ST-04（任务状态、失败原因、提交编号、missing_items）——展示数据全部派生自本地状态与远端应答，不另存副本。

### 3.3 派生流

- `missing_items[]`、`failure_reason` 自 CT-001/CT-002 应答到达后由 PENDING-QUEUE 记入 ST-04，再由 STATUS-PRESENTER 派生展示；本地不维护第二份「提交状态」（权威在 MOD-02）。

### 3.4 外部化流

- **CT-001 材料包** = ST-02（对话条目）+ ST-03（三类材料条目）+ ST-04 中的意图快照（invite_code 取自 ST-01）→ 由 UPLOAD-CLIENT 按分片协议编码为 `material_chunks[]`（类别标注不变）外发至 MOD-02。
- **CT-002 查询** = ST-04 的 `submission_uuid`（路径参数），应答用于收敛 confirm_required 状态。

## 4. 不变量、一致性、幂等与并发规则

| 规则 | 内容 | 依据 |
|---|---|---|
| INV-1 | 缺作业/姓名/小组的意图不创建提交、不产生网络调用 | F1-1；FLOW-001 entry_condition |
| INV-2 | `submission_uuid` 任务创建时生成，全程不变；恢复续传复用同一 uuid，服务端按幂等键去重 | KD-005；CT-001 Idempotency |
| INV-3 | 无效配置不覆盖上一次有效配置；不完整配置显式携带缺失项 | AC-REQ-002-01 exceptions/boundaries |
| INV-4 | 对话与材料采集锚定任务创建时刻（快照语义），上传重试不重采 | LCD-002；REQ-D003「完整对话」 |
| INV-5 | checkpoint 只记录服务端已确认分片；重传跳过已确认分片 | CT-001 分片协议 |
| CON-1 | 单任务同一时刻至多一个活跃上传会话（PENDING-QUEUE 串行化调度）；多任务可并行排队但令牌复用 | 本地一致性；避免同 uuid 并发分片 |
| CON-2 | ST-01 单写方；读者要么读到旧有效值要么读到新有效值，无中间态 | 本地事务 |
| IDEM-1 | 重复上传（断点续传/超时重试）以同一 uuid + checkpoint 去重，不产生重复提交 | CT-001/KD-005 |
| IDEM-2 | CT-002 为只读查询，天然幂等；重复查询不推进任何状态 | CT-002 side_effects: None |

## 5. 与父状态机的关系（重要边界）

- MOD-02 持有权威提交状态机（upload_failed/rejected/received/processing/scored/scoring_failed）；MOD-01 的本地任务状态机仅是**客户端任务视图**，其 `received`/`rejected`/失败原因全部来自 CT-001/CT-002 应答，本地绝不自行判定服务端语义结果（如：本地不预判归属校验，REJECTED_MEMBERSHIP 只能来自服务端应答）。
- 30 秒未确认期间本地状态为 confirm_required（结果未知），不向学生展示伪造的成功/失败结论（STATUS-PRESENTER 统一出口）。

## 6. 父/兄弟所有权未转移确认

- Submission 聚合、材料文件服务端存储、提交状态机、完整性报告：仍归 MOD-02（03-data-and-consistency §数据所有权原样有效）。
- Course/名单、AssessmentResult、ReviewRecord 等：归 MOD-03/04/05，本层未触碰。
- 本层新增状态（ST-01~ST-05）全部为学生本机的客户端状态，不构成对父层数据所有权图的修改，无跨父节点/兄弟节点的状态或数据所有权转移。
