# 03 State and Data — CMP-UPLOAD-CLIENT（L2）

> 本文件细化上传客户端内部状态；不拥有、不复制 MOD-02 的 Submission 或服务端提交状态机。

## 1. 状态所有权清单（按稳定状态 ID 排序）

| 状态 ID | 状态 | Owner (child_id) | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| `ST-05` | `UploadCheckpoint`：upload_session_id、已确认分片索引、总分片数、最后确认时间 | `CMP-UPLOAD-SESSION-DRIVER` | SESSION-DRIVER；ORCHESTRATOR 仅读取执行结果 | 仅 SESSION-DRIVER，在服务端 ack 后写入 | 任务上传期存在；父任务进入 received/rejected 后由父队列触发清理 | 单 uuid 单写；checkpoint 与服务端已确认分片集合对账；崩溃恢复从最近一致 checkpoint 继续 | 不含材料内容，仅含会话/偏移元数据；本机保存；终态清除 | 父 ST-05；CT-001；`KD-005`；`INV-5` |
| `ST-L2-01` | `AccessTokenLease`：Bearer token、过期时间、凭据上下文摘要、失效标志 | `CMP-UPLOAD-AUTH-ADAPTER` | AUTH-ADAPTER；SESSION-DRIVER 仅取当前租约 | 仅 AUTH-ADAPTER；获取成功或 401 后替换 | 单次进程运行/短期请求范围；进程结束或失效即删除 | 同一租约只服务同一 identity context；失效 lease 不可再次用于请求 | **不得落盘**；不进入 UploadJob、checkpoint 或材料包；日志不得记录 token | 父 `auth/token` 附属约定；`LCD-006` |
| `ST-L2-02` | `ActiveUploadGuard`：submission_uuid、执行租约、取消标志 | `CMP-UPLOAD-ORCHESTRATOR` | ORCHESTRATOR | 仅 ORCHESTRATOR | StartUpload/ResumeUpload 创建；Outcome 回调或取消后释放 | 同一 uuid 至多一个 active execution；重复启动返回既有执行句柄 | 仅内存；不影响服务端状态；进程崩溃由父队列依据 ST-05 恢复 | 父 `CON-1`；父 `IC-M01-04`；`INV-2` |

无持久状态的 child：`CMP-UPLOAD-OUTCOME-RESOLVER` 只处理瞬态观察，不成为状态 owner。

## 2. 存储意图

- `ST-05` 遵守父层 A-007：需要跨进程重启持久，但文件、嵌入式 KV 或其他具体机制留待实现阶段；本层只固定单写、ack 后写和终态清理边界。
- `ST-L2-01` 与 `ST-L2-02` 只在学生本机进程内存中存在；不引入服务端存储、共享数据库、消息总线或独立部署单元。
- token、identity 和材料内容均不进入 checkpoint；本层只把 `submission_uuid`、会话引用和分片确认元数据保存在 ST-05。

## 3. 数据流

### 3.1 写入流

1. 父队列通过 `IC-M01-04` 提供 `UploadJob`；ORCHESTRATOR 创建 `ST-L2-02`。
2. AUTH-ADAPTER 根据 identity 请求 token；成功后写 `ST-L2-01`，失效后替换而非复用。
3. SESSION-DRIVER 创建 CT-001 会话；每个服务端确认的分片才追加到 `ST-05`。
4. 合并结果或 CT-002 查询结果交给 OUTCOME-RESOLVER；最终 `UploadOutcome` 回到 ORCHESTRATOR，再回父队列。

### 3.2 读取流

- `ST-05` 只用于跳过已确认分片和恢复同一上传会话，不推断服务端业务状态。
- `ST-L2-01` 只用于当前 HTTPS 请求授权；AUTH_INVALID 后必须失效并重新获取。
- `ST-L2-02` 只用于本节点内并发保护，不向父队列或 MOD-02 外化。

### 3.3 外部化流

- CT-001 请求由父队列提供的 identity、assignment、bundle_ref 和 `submission_uuid` 组装；`material_chunks[]` 的类别和字段原样沿用父契约。
- CT-002 只使用父 `submission_uuid` 路径参数；响应只用于 `confirm_required` 的结果收敛。
- `ST-05` 不外化为新 API、事件或公共数据结构。

## 4. 不变量、一致性、幂等与并发规则

| 规则 | 内容 | 依据 |
|---|---|---|
| `L2-UP-INV-001` | 只有服务端确认的分片才可写入 ST-05；未确认分片不能被跳过 | 父 `INV-5`、CT-001 |
| `L2-UP-INV-002` | 同一 `submission_uuid` 的重复 Start/Resume 复用既有执行，不开第二个活跃会话 | 父 `CON-1`、`INV-2` |
| `L2-UP-INV-003` | CT-001 30 秒无确认只能产出 unknown；未经过 CT-002 不得产出 received/rejected | 父 NFR-003、CT-001 timeout |
| `L2-UP-INV-004` | AUTH_INVALID 后旧 token lease 立即失效；重取成功前不继续发送当前请求 | 父 auth/token 语义、`LCD-006` |
| `L2-UP-IDEM-001` | 断点续传复用同一 uuid + session + checkpoint，不创建新 Submission | `KD-005`、CT-001 Idempotency |
| `L2-UP-IDEM-002` | CT-002 查询无副作用，重复查询不会改变服务端状态 | CT-002 read-only |
| `L2-UP-CON-001` | ST-05 单写方为 SESSION-DRIVER；ORCHESTRATOR 不直接修改 checkpoint | 状态所有权 |

## 5. 生命周期与清理

```yaml
upload_state_boundary:
  owner_scope: CMP-UPLOAD-CLIENT
  checkpoint_owner: CMP-UPLOAD-SESSION-DRIVER
  token_lease_owner: CMP-UPLOAD-AUTH-ADAPTER
  active_guard_owner: CMP-UPLOAD-ORCHESTRATOR
  durable_state: [ST-05]
  memory_only_state: [ST-L2-01, ST-L2-02]
  cleanup_trigger:
    checkpoint: parent_task_terminal_received_or_rejected
    token_lease: process_end_or_auth_invalid
    active_guard: outcome_callback_or_cancel
  server_state_owner: MOD-02
  excluded_from_l2: [Submission, submission_status, material_server_storage, retention_due_at]
```

## 6. 父/兄弟所有权未转移确认

- `ST-05` 只是父 `CMP-UPLOAD-CLIENT` 内部的本机 checkpoint 细化；没有转移到 `MOD-02`、`CMP-PENDING-QUEUE` 或其他兄弟节点。
- Submission、服务器接收状态、`upload_failed/rejected/received/processing` 权威状态继续归 MOD-02；本层不复制状态机。
- `bundle_ref` 的材料内容所有权仍由父队列/采集器提供，本层只读并编码为 CT-001 分片。

