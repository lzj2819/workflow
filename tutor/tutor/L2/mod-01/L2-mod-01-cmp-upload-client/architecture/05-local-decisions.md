# 05 Local Decisions — CMP-UPLOAD-CLIENT（L2）

> 本层只决定上传客户端内部结构；父层 KD-003/KD-005/A-007 与 CT-001/CT-002 语义原样继承。

## 1. 本层已决定（decide_now，按稳定决策 ID 排序）

### LCD-UP-001 分片确认后的 checkpoint 写入

- **来源**：父 `ST-05`、`INV-5`、CT-001 分片协议。
- **问题**：checkpoint 在发送前、发送后，还是服务端确认后写入？
- **方案比较**：
  1. **（选定）服务端 ack 后写入**：只记录服务端确认的分片，崩溃后最多重传当前未确认分片，保持幂等。
  2. 发送前写入：可能跳过服务端未收到的分片，违反 `INV-5`，弃用。
  3. 请求返回即写入但不区分 ack：无法表达分片确认边界，弃用。
- **后果**：`CMP-UPLOAD-SESSION-DRIVER` 成为 ST-05 唯一写方；精确落盘机制留实现细节。
- **分类**：decide_now。

### LCD-UP-002 令牌租约：短生命周期、内存持有、失效重取

- **来源**：父 auth/token、`KD-005`、`LCD-006`。
- **问题**：如何在不泄露凭据的前提下减少重复 token 请求？
- **方案比较**：
  1. **（选定）进程内短期 lease**：按 identity context 复用未过期 token；AUTH_INVALID/过期立即失效并重取；永不落盘。
  2. 每个分片都换 token：安全边界简单，但增加网络依赖和失败面，弃用。
  3. 持久化 token：跨重启便捷，但扩大隐私/凭据泄露面，且超出父 A-007/DU-1 约束，弃用。
- **后果**：新增 `ST-L2-01` 仅为本机瞬态状态，不进入 CT-001、checkpoint 或日志。
- **分类**：decide_now；具体缓存结构为 implementation_detail。

### LCD-UP-003 单任务单活跃执行

- **来源**：父 `CON-1`、`INV-2`、`IC-M01-04`。
- **问题**：重复 Start/Resume 如何避免同 uuid 并发分片？
- **方案比较**：
  1. **（选定）ORCHESTRATOR 持有 ActiveUploadGuard**：同 uuid 重复启动归并到既有执行，checkpoint 只由 SESSION-DRIVER 更新。
  2. 允许并发、依赖服务端幂等：可能造成会话竞争和重复分片，弃用。
  3. 由父队列全局串行：把目标内部不变量泄漏到兄弟节点，且不能保护直接重复调用，弃用。
- **后果**：新增 `ST-L2-02` 为进程内协调状态；不改变父队列的多任务调度能力。
- **分类**：decide_now。

### LCD-UP-004 未知结果先查询，不重发整包

- **来源**：父 NFR-003、CT-001 timeout、CT-002、父 R2。
- **问题**：CT-001 30 秒无确认后，直接重传还是先查询？
- **方案比较**：
  1. **（选定）先 CT-002 查询**：把 unknown 与服务端真实状态分离；查询到 upload_failed 后才回到父队列恢复流程。
  2. 立即重发整包：可能创建重复接收或浪费带宽，违反父超时语义，弃用。
  3. 本地直接标记 failed：无法区分服务端已接收但响应丢失，弃用。
- **后果**：OUTCOME-RESOLVER 拥有 unknown→query→outcome 的局部流程；不拥有服务端状态。
- **分类**：decide_now。

## 2. 委托下一层或实现阶段

| 决策 ID | 事项 | 分类 | 后续目标 | 触发条件 |
|---|---|---|---|---|
| `LCD-UP-005` | 具体分片大小、multipart 编码和 HTTP 客户端实现 | implementation_detail | `CMP-UPLOAD-SESSION-DRIVER` L3/实现 | 不改变 CT-001 字段、顺序、错误、幂等和版本 |
| `LCD-UP-006` | 指数退避的具体初始间隔、最大间隔和停止条件 | defer_to_next_level | `CMP-UPLOAD-OUTCOME-RESOLVER` L3 | 父契约要求指数退避；本层只固定必须重试且不得伪造终态 |

## 3. 继承决策显式登记

| 父决策/约束 | 本层行为 |
|---|---|
| `KD-003` | 所有外部请求使用 HTTPS；本层不引入明文通道 |
| `KD-005` | token、submission UUID 幂等键、分片断点续传、`/api/v1` 是四个 child 的实现基线 |
| `A-007` | ST-05 需要持久化，但具体文件/KV 机制不在本层决定 |
| `IC-M01-04` | UploadJob/UploadOutcome 只作为父内部契约使用，不提升为公共 API |
| DU-1 | 所有 child_id 为学生本机进程内逻辑，不创建服务/容器/部署单元 |

## 4. 父层专属禁止项

- 不修改 CT-001/CT-002/auth-token 的字段、路径、owner、错误码、失败/重试/幂等/版本。
- 不把 `unknown` 映射成 received/rejected；不在客户端预判 `REJECTED_MEMBERSHIP`。
- 不把 token、材料正文或 Submission 状态写入新的公共状态或跨模块事件。
- 不增加新的服务端 API、消息主题、数据库或兄弟节点依赖。
- 若未来要求新增外部必填字段、改变分片类别、改变 owner 或部署形态，必须 `return_to_parent`，不能归类为本地决定。

## 5. 局部决策队列汇总

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| `LCD-UP-001` | 父 L1 03 / 当前契约 | ST-05 / INV-5 | SESSION-DRIVER、03 状态 | 写入时点决定恢复安全性与 checkpoint 所有权 | decide_now | — |
| `LCD-UP-002` | 父 L1 04/05 | auth/token / LCD-006 | AUTH-ADAPTER、03 ST-L2-01 | 令牌复用与隐私边界需显式固定 | decide_now | — |
| `LCD-UP-003` | 父 L1 03/04 | CON-1 / IC-M01-04 | ORCHESTRATOR、03 ST-L2-02 | 并发保护不能只依赖服务端幂等 | decide_now | — |
| `LCD-UP-004` | 父 L1 04 | NFR-003 / R2 | OUTCOME-RESOLVER、04 R-UP-03 | unknown 的处理顺序决定是否误报和重复提交 | decide_now | — |
| `LCD-UP-005` | 当前 PRD / 父 CT-001 | D-AC-REQ-003-01 / CT-001 | SESSION-DRIVER | 编码细节不改变架构边界 | implementation_detail | L3/实现 |
| `LCD-UP-006` | 父 CT-002 | Retry | OUTCOME-RESOLVER | 参数可留给下一层且不影响本层契约 | defer_to_next_level | CMP-UPLOAD-OUTCOME-RESOLVER |

**队列结论**：无遗留 `decide_now`；无 `return_to_parent`；当前包可进入交接。

