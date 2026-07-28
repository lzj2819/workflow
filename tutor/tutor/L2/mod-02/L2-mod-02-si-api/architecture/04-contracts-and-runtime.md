# 04 Contracts and Runtime — SI-API L2

## 1. 继承契约清单

下表只摘录父包的绑定字段和语义，作为本层实现映射；字段、所有者、路径、错误、幂等、副作用和版本均不可在本层修改。

| contract_id | role/owner | path/topic | required / produced fields | side effects | failure/version |
|---|---|---|---|---|---|
| CT-001 | Provides / SI-API → MOD-01 | `POST /api/v1/submissions` | required: `submission_uuid, invite_code, student_name, group_name, assignment, material_chunks[]`; produced: `submission_id, received_at, status, missing_items[], rejection_reason?` | 创建提交、归属校验、状态推进、完整性报告、SubmissionReceived | `AUTH_INVALID, VALIDATION_FAILED, PAYLOAD_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE, REJECTED_MEMBERSHIP`; 30 秒同步确认；parent v1 |
| CT-002 | Provides / SI-API → MOD-01 | `GET /api/v1/submissions/{submission_uuid}` | produced: `submission_id, status, failure_reason?, missing_items[]` | none; read-only | `AUTH_INVALID, NOT_FOUND`; parent v1 |
| auth-token | Provides / SI-API → MOD-01 | `POST /api/v1/auth/token` | required: invitation code + name/group; produced: Bearer token | ST-06 审计；每次实时名单校验 | 沿用 CT-003 名单语义；无缓存；KD-005 |
| CT-003 | Consumes / MOD-03 → SI-VERIFY | `POST /api/v1/courses/verify-membership` | required: `invite_code, student_name, group_name`; produced: `verified, course_id?, reason?` | 无本模块持久副作用；结果给 SI-CORE | `ROSTER_UNAVAILABLE` 保持待校验并重试；不向客户端泄露内部细节 |
| CT-004 | Publishes / SI-CORE → MOD-04 | Outbox event | `submission_id, course_id, assignment, student_name, group_name, material_refs[], missing_items[], received_at, v=1` | MOD-04 持久化评分任务后确认 | Outbox 无限重试；消费者按 submission_id 幂等 |
| CT-005 | Consumes / MOD-04 → SI-RELAY | Outbox event | `submission_id, outcome=scored\|scoring_failed` + outcome fields | 回写 ST-01 状态 | 终态幂等；本层不处理评分细节 |
| CT-006 | Publishes / SI-CORE → MOD-05 | Outbox event | `submission_id, course_id, assignment, student_name, group_name, status, missing_items[], received_at, v=1` | 教师端读模型派生 | 在 `received` 或 `upload_failed` 发布；schema/consumer/version 不变 |
| CT-012 | Consumes / MOD-05 → SI-RELAY | Outbox event | `batch_id, submission_ids[], scope, operator, executed_at, audit_record_id, v=1` | 清除材料和提交记录 | 按 batch_id+payload 幂等；支撑组件处理 |
| CT-014 | Publishes / SI-PURGE → MOD-05 | Outbox event | `batch_id, purged_submission_ids[], failed_items[], purged_at, v=1` | 回传清除结果 | 部分失败可重跑；本层不处理 |

## 2. 父契约实现映射

| inherited contract | current child realization | unchanged confirmation |
|---|---|---|
| CT-001 | ROUTER 接入/错误映射 → AUTH → ORCHESTRATOR → IC-SI-01/03/04；最终响应由 ROUTER 映射 | 路径、字段、错误码、30 秒语义不变 |
| CT-002 | ROUTER 接入/错误映射 → AUTH → ORCHESTRATOR → IC-SI-04 query | 只读、字段与 NOT_FOUND 语义不变 |
| auth-token | ROUTER → AUTH → LC-SIAPI-007/IC-SI-03 → ST-06 → ROUTER | 仍是 CT-001 契约族附属端点，不单独升版本 |
| CT-003 | ORCHESTRATOR 调用 SI-VERIFY；SI-VERIFY 负责外部请求 | 每次实时校验、ROSTER_UNAVAILABLE 语义不变 |
| CT-004 | SI-CORE + SI-RELAY 负责 Outbox；API 只等待 ConfirmReceived 端口结果 | API 不成为 CT-004 owner，不改载荷 |
| CT-005 | SI-RELAY 入站去重与 SI-CORE 回写 | API 不消费评分事件，不改状态机 |
| CT-006 | SI-CORE/SI-RELAY 发布；API 仅在接收路径完成前置命令 | 触发状态和载荷不变 |
| CT-012/CT-014 | SI-RELAY/SI-PURGE 支撑链路 | API 不改变清除所有权、批次幂等或失败项语义 |

## 3. Child-only contracts（按稳定 ID 排序）

| contract_id | owner → consumer | 触发与 schema | side_effects | 错误、幂等、兼容性 |
|---|---|---|---|---|
| LC-SIAPI-001 | SI-API-ROUTER → SI-API-AUTH | 每个受保护端点进入业务 handler 前；输入: `route`, `auth_context`, `request_id`; 输出: `auth_result`, `principal`, `course_hint`, `failure_code`；CT-001/CT-002 要求有效 Bearer，auth-token 要求邀请码/姓名/小组 | 失败直接映射父 AUTH_INVALID；不写 Submission | 认证错误不重试；同一 request_id 不重复推进业务；字段只追加 |
| LC-SIAPI-002 | SI-API-ROUTER → SI-API-INTAKE-ORCHESTRATOR | CT-001/CT-002 路由完成；输入: `contract_id`, `validated_context`, `payload`, `deadline_at`; 输出: `response_payload`, `status`, `failure_code`, `submission_id`, `received_at`, `missing_items`；next_hop: `LC-SIAPI-003/004/005` | 不持久化业务状态 | deadline 到期停止后续调用；父 endpoint、字段和版本兼容 |
| LC-SIAPI-003 | SI-API-INTAKE-ORCHESTRATOR → SI-XFER | CT-001 会话/分片/合并阶段；输入: `submission_uuid`, `declared_categories`, `session_id`, `seq`, `bytes`, `abort_reason`; 输出: `session_id`, `received_bytes`, `state`, `material_refs`, `failure_reason` | 由 SI-XFER/STORE 写 ST-02/ST-03 | CHUNK_OUT_OF_ORDER 可恢复；大小/类型错误映射 413/415；submission_uuid/seq/finalize 复用父幂等 |
| LC-SIAPI-004 | SI-API-INTAKE-ORCHESTRATOR → SI-VERIFY | CT-001 合并完成后的名单校验；输入: `invite_code`, `student_name`, `group_name`; 输出: `verified`, `course_id`, `reason` | 无 API 自有业务状态副作用 | ROSTER_UNAVAILABLE 有限快速重试后转父 pending 路径；不缓存通过结论 |
| LC-SIAPI-005 | SI-API-INTAKE-ORCHESTRATOR → SI-CORE | 幂等查询、ConfirmReceived、MarkRejected/MarkUploadFailed；输入: `submission_uuid`, `submission_id`, `course_id`, `assignment`, `student_name`, `group_name`, `material_refs`, `missing_items`, `expected_state`, `failure_reason`; 输出: `submission_id`, `status`, `received_at`, `missing_items`, `transition_result` | SI-CORE 在本地事务写 ST-01 和 Outbox | DUPLICATE_UUID 返回已有结果；ILLEGAL_TRANSITION/NOT_FOUND 不改命令重试；父状态机守卫有效 |
| LC-SIAPI-006 | SI-API-ROUTER → SI-API-OBSERVABILITY | 入口、端口返回、异常和最终响应；输入: `correlation_id`, `contract_id`, `course_id`, `status`, `failure_reason`, `started_at`, `ended_at`, `valid_submission`; 输出: `metric_event_id` | 只向父基础监控面发送诊断信号 | 观测失败不得阻塞业务响应；字段只追加；SM-001 口径不变 |
| LC-SIAPI-007 | SI-API-AUTH → SI-VERIFY | auth-token 签发前的实时名单校验；输入: `invite_code`, `student_name`, `group_name`; 输出: `verified`, `course_id`, `reason` | 无 API 自有业务状态副作用；AUTH 写 ST-06 审计 | ROSTER_UNAVAILABLE 按父规则待校验/重试；不缓存通过结论；不改变 auth-token 版本 |

### 3.1 公共入口绑定（验证器入口权威）

| contract_id | owner → consumer | 触发与 schema | side_effects | 错误、幂等、兼容性 |
|---|---|---|---|---|
| ENTRY-CT-001 | MOD-01 → SI-API-ROUTER | POST /api/v1/submissions；父契约: CT-001；输入: `submission_uuid`, `invite_code`, `student_name`, `group_name`, `assignment`, `material_chunks`; 输出: `submission_id`, `received_at`, `status`, `missing_items`, `rejection_reason`；next_hop: `LC-SIAPI-001` → `LC-SIAPI-002` | ROUTER 创建 RequestContext；后续业务副作用由 ORCHESTRATOR/父 owner 承担 | 父 CT-001 错误、30 秒确认和幂等语义不变 |
| ENTRY-CT-002 | MOD-01 → SI-API-ROUTER | GET /api/v1/submissions/{submission_uuid}；父契约: CT-002；输入: `submission_uuid`, `bearer`; 输出: `submission_id`, `status`, `failure_reason`, `missing_items`；next_hop: `LC-SIAPI-001` → `LC-SIAPI-002` | 只读；不写 ST-01 | AUTH_INVALID/NOT_FOUND；无业务状态副作用 |
| ENTRY-AUTH-TOKEN | MOD-01 → SI-API-ROUTER | POST /api/v1/auth/token；输入: `invite_code`, `student_name`, `group_name`, `request_id`; 输出: `bearer_token`, `expires_at`；next_hop: `LC-SIAPI-001` → `LC-SIAPI-007` | AUTH 写 ST-06 审计 | auth-token 附属端点版本和父名单语义不变 |

## 4. 局部运行流

### RF-01 成功：CT-001 → received

1. ROUTER 接收 CT-001，创建 `RequestContext`，AUTH 校验 Bearer/端点认证。
2. ORCHESTRATOR 以 `submission_uuid` 通过 IC-SI-04 查询幂等结果；未命中则调用 IC-SI-01 建立/续传/合并会话。
3. 会话合并成功后，ORCHESTRATOR 调用 IC-SI-03；验证通过后调用 IC-SI-04 `ConfirmReceived`。
4. SI-CORE 在本地事务写入 `received`、材料清单、完整性报告并写入 CT-004/CT-006 Outbox。
5. ORCHESTRATOR 在预算内返回 CT-001 的 `submission_id/received_at/status/missing_items[]`；OBSERVABILITY 记录 SM-001 成功点。

### RF-02 失败/恢复：中断、名单不可用、幂等重试

1. 分片中断由 IC-SI-01 返回 `interrupted_retryable`，ORCHESTRATOR 不创建错误终态，调用方可沿 CT-001 续传语义恢复。
2. `ROSTER_UNAVAILABLE` 经有限快速重试仍不可用时，保持父定义的待校验/后续重试路径，不把内部错误暴露给 MOD-01。
3. 同一 `submission_uuid` 再次请求时，ORCHESTRATOR 复用 SI-CORE/SI-XFER 的既有结果；不重复创建、合并、计量或发布。
4. 不可恢复或预算耗尽时，按 CT-001 父错误/状态语义返回；不得伪造 `received`。

### RF-03 生命周期：查询与认证审计

1. auth-token 请求创建并完成 ST-06 审计；过期令牌不再通过认证。
2. CT-002 只读查询 ST-01 的父结果；不改变状态、不触发评分、不读材料内容。
3. 业务状态推进、CT-005/CT-012 入站和 CT-014 回传由兄弟/支撑组件完成；本层只保持端口兼容。

## 5. 错误、超时、观测与兼容

| 主题 | 规则 |
|---|---|
| 错误映射 | 只映射到父 CT-001/CT-002/auth-token 的已有错误码；内部 IC 错误不得泄漏为新公共码 |
| 超时 | 30 秒预算包含认证、幂等、会话完成、名单校验、ConfirmReceived 与响应；评分异步，不纳入同步等待 |
| 重试 | IC-SI-01 续传和 IC-SI-03 有限重试沿用父 LCD-001；Outbox 无限重试由 SI-RELAY 负责 |
| 幂等 | `submission_uuid`、分片 `seq`、finalize、父 command 和状态终态沿用父规则 |
| 可观测 | 入口、端口、响应均关联 correlation_id；SM-001 只统计有效提交与 30 秒内 received，分母排除项沿用 LCD-009 |
| 兼容 | 父端点、字段、事件、版本和 side effects 零变更；child-only contract 仅限 DU-2 进程内并随包发布 |

## 6. 合法流确认

本层没有新增跨模块同步调用、公共事件、消息总线、部署单元或兄弟状态写入。所有场景 hop 均落在父已定义的 CT-001/CT-002/auth-token、IC-SI-01/03/04 和父流程之内。
