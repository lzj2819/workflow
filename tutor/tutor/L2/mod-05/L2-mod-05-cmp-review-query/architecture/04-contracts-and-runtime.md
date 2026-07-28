# 04 Contracts and Runtime — 契约与运行时（L2 / CMP-REVIEW-QUERY）

> C3/C4/C5 落点：CT-007 外部入口保持不变；本层只细化其内部装配协作。父契约字段、所有者、错误语义、幂等和版本不可变。

## 1. 父契约 CT-007（逐字段继承）

```yaml
contract_id: CT-007
contract_type: sync_api_boundary
owner: MOD-05
provider: MOD-05
consumer: "教师浏览器"
path: GET /api/v1/teacher/courses/...
required_fields: [teacher_session]
produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, deletion_batches, failure_reason, retry_record]
inbound_required_fields: [teacher_session]
outbound_produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, deletion_batches, failure_reason, retry_record]
conditional_fields:
  - "failure_reason 与 retry_record：评分失败或存在重试记录时返回"
  - "original_grade 与 final_grade：存在有效评分结果时返回；scoring_failed 且无原始等级时不得伪造"
side_effects: "None; read-only；FORBIDDEN 时记录 AccessDeniedLogged"
dependencies: [ST-READ-MODEL, ST-DELETION-BATCH]
errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED]
idempotency: "只读天然幂等"
timeout: "查询类不超过 10 秒"
version: /api/v1
```

本层只负责 `CMP-ACCESS-GATE → CMP-REVIEW-QUERY` 之后的响应装配，不改变父 Provider/Consumer 关系，也不新增公开端点。

## 2. 父内部契约实现映射（C4/C5）

| 父契约 | 本层实现 child | 输入 | 输出 | 错误/重试 | 所有权约束 |
|---|---|---|---|---|---|
| M05-IC-02 | SCOPE-ASSEMBLER、SUBMISSION-DETAIL-ASSEMBLER | `course_id`, `group_id`, `student_id`, `submission_id` | `courses`, `groups`, `students`, `submissions`, `material_refs`, `status`, `original_grade`, `dimension_rationales`, `teacher_suggestions`, `annotations`, `final_grade`, `missing_marks` | 只读；失败时由 Facade 整体返回可重试失败，不降级缺字段 | Owner 仍为 CMP-READMODEL-PROJECTOR；本层不写 ST-READ-MODEL |
| M05-IC-06 | RETENTION-VIEW-ADAPTER | `batch_id`, `submission_id` | `batch_id`, `retention_due_at`, `scope`, `batch_status`, `exclusions`, `cleared_submission_ids` | 只读；读取失败时 CT-007 不返回不完整 `deletion_batches[]` | Owner 仍为 CMP-RETENTION-GOVERNANCE；本层不写 ST-DELETION-BATCH |

## 3. L2 内部契约

| internal_id | Owner → Consumer | 触发 | 输入 | 输出 | 失败/重试 | 幂等 |
|---|---|---|---|---|---|---|
| RQ-IC-001 | QUERY-FACADE → SCOPE-ASSEMBLER | CT-007 有层级查询选择 | `authorized_query_context`, `query_scope` | `hierarchy_view` | M05-IC-02 读取失败；由 Facade 统一失败 | 只读天然幂等 |
| RQ-IC-002 | QUERY-FACADE → SUBMISSION-DETAIL-ASSEMBLER | CT-007 请求提交详情 | `authorized_query_context`, `submission_selector` | `submission_detail_view` | 无提交/无匹配 → NOT_FOUND；端口失败 → retryable | 只读天然幂等 |
| RQ-IC-003 | SUBMISSION-DETAIL-ASSEMBLER → OUTCOME-ADAPTER | 详情中存在评分结果字段 | `status`, `original_grade`, `dimension_rationales`, `teacher_suggestions`, `failure_reason`, `retry_record` | `outcome_view` | scored/scoring_failed 分支必须显式处理 | 纯函数式转换 |
| RQ-IC-004 | QUERY-FACADE → RETENTION-VIEW-ADAPTER | CT-007 需要 `deletion_batches[]` | `course_id`, `batch_id`, `submission_id` | `deletion_batches[]` | M05-IC-06 失败 → 整体 retryable | 只读天然幂等 |
| RQ-IC-005 | 四个装配 child → QUERY-FACADE | 局部装配完成 | `hierarchy_view`, `submission_detail_view`, `outcome_view`, `deletion_batches[]` | `TeacherCourseQueryResponse` | 任一必需部分失败，禁止 partial success | 本次请求内单次组合 |

## 4. 机器可读组件绑定

```yaml
component_bindings:
  - binding_id: RQ-BIND-CT-007-GATE-FACADE
    contract_id: CT-007
    provider_component: CMP-ACCESS-GATE
    consumer_component: CMP-RQ-QUERY-FACADE
    required_fields: [auth_context, course_id]
    produced_fields: [auth_context, course_id, group_id, student_id, submission_id]
    next_hop: CMP-RQ-QUERY-FACADE
    errors: [NOT_FOUND, VALIDATION_FAILED]
  - binding_id: RQ-BIND-M05-IC-02-FACADE-SCOPE
    contract_id: RQ-IC-001
    provider_component: CMP-RQ-QUERY-FACADE
    consumer_component: CMP-RQ-SCOPE-ASSEMBLER
    required_fields: [authorized_query_context, query_scope]
    produced_fields: [hierarchy_view]
    next_hop: CMP-RQ-SCOPE-ASSEMBLER
  - binding_id: RQ-BIND-M05-IC-02-RMP-SCOPE
    contract_id: M05-IC-02
    provider_component: CMP-READMODEL-PROJECTOR
    consumer_component: CMP-RQ-SCOPE-ASSEMBLER
    required_fields: [course_id, group_id, student_id, submission_id]
    produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, missing_marks]
    next_hop: CMP-RQ-SCOPE-ASSEMBLER
  - binding_id: RQ-BIND-M05-IC-02-FACADE-DETAIL
    contract_id: RQ-IC-002
    provider_component: CMP-RQ-QUERY-FACADE
    consumer_component: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
    required_fields: [authorized_query_context, submission_selector]
    produced_fields: [submission_detail_view]
    next_hop: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
  - binding_id: RQ-BIND-M05-IC-02-RMP-DETAIL
    contract_id: M05-IC-02
    provider_component: CMP-READMODEL-PROJECTOR
    consumer_component: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
    required_fields: [course_id, group_id, student_id, submission_id]
    produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, missing_marks]
    next_hop: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
  - binding_id: RQ-BIND-M05-IC-02-DETAIL-OUTCOME
    contract_id: RQ-IC-003
    provider_component: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
    consumer_component: CMP-RQ-OUTCOME-ADAPTER
    required_fields: [status, original_grade, dimension_rationales, teacher_suggestions, failure_reason, retry_record]
    produced_fields: [outcome_view]
    next_hop: CMP-RQ-OUTCOME-ADAPTER
  - binding_id: RQ-BIND-M05-IC-06-FACADE-RETENTION
    contract_id: RQ-IC-004
    provider_component: CMP-RQ-QUERY-FACADE
    consumer_component: CMP-RQ-RETENTION-VIEW-ADAPTER
    required_fields: [course_id, batch_id, submission_id]
    produced_fields: [deletion_batches]
    next_hop: CMP-RQ-RETENTION-VIEW-ADAPTER
  - binding_id: RQ-BIND-M05-IC-06-RG-RETENTION
    contract_id: M05-IC-06
    provider_component: CMP-RETENTION-GOVERNANCE
    consumer_component: CMP-RQ-RETENTION-VIEW-ADAPTER
    required_fields: [batch_id, submission_id]
    produced_fields: [batch_id, retention_due_at, scope, batch_status, exclusions, cleared_submission_ids]
    next_hop: CMP-RQ-RETENTION-VIEW-ADAPTER
  - binding_id: RQ-BIND-LOCAL-COMPOSE-FACADE
    contract_id: RQ-IC-005
    provider_component: CMP-RQ-QUERY-FACADE
    consumer_component: CMP-ACCESS-GATE
    required_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, deletion_batches, failure_reason, retry_record]
    produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, deletion_batches, failure_reason, retry_record]
    next_hop: CMP-ACCESS-GATE
```

## 5. 机器可读组件契约登记

下表是本层组件级契约的规范化登记。`触发与 schema` 同时使用 `输入` 和 `输出` 标记，供验证器生成 `inbound_interfaces[].contract.required` 与 `response`；本层没有新增事件，所有 `event_policy` 均为 `none`。

| 契约 ID | 所有者 → 消费者 | 触发与 schema | 错误、幂等、兼容性 |
|---|---|---|---|
| RQ-CONTRACT-CT007-GATE-FACADE | CMP-ACCESS-GATE → CMP-RQ-QUERY-FACADE | 输入：`auth_context`, `course_id`；输出：`auth_context`, `course_id`, `group_id`, `student_id`, `submission_id`；next_hop：`CMP-RQ-QUERY-FACADE`；event_policy：`none` | CT-007；只读；NOT_FOUND/VALIDATION_FAILED；天然幂等 |
| RQ-CONTRACT-FACADE-SCOPE | CMP-RQ-QUERY-FACADE → CMP-RQ-SCOPE-ASSEMBLER | 输入：`authorized_query_context`, `query_scope`；输出：`hierarchy_view`；next_hop：`CMP-RQ-SCOPE-ASSEMBLER`；event_policy：`none` | RQ-IC-001；M05-IC-02 失败整体 retryable；无副作用 |
| RQ-CONTRACT-FACADE-DETAIL | CMP-RQ-QUERY-FACADE → CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER | 输入：`authorized_query_context`, `submission_selector`；输出：`submission_detail_view`；next_hop：`CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER`；event_policy：`none` | RQ-IC-002；NOT_FOUND 或 retryable；无副作用 |
| RQ-CONTRACT-DETAIL-OUTCOME | CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER → CMP-RQ-OUTCOME-ADAPTER | 输入：`status`, `original_grade`, `dimension_rationales`, `teacher_suggestions`, `failure_reason`, `retry_record`；输出：`outcome_view`；next_hop：`CMP-RQ-OUTCOME-ADAPTER`；event_policy：`none` | RQ-IC-003；scored/scoring_failed 必须显式分支；无副作用 |
| RQ-CONTRACT-FACADE-RETENTION | CMP-RQ-QUERY-FACADE → CMP-RQ-RETENTION-VIEW-ADAPTER | 输入：`course_id`, `batch_id`, `submission_id`；输出：`deletion_batches`；next_hop：`CMP-RQ-RETENTION-VIEW-ADAPTER`；event_policy：`none` | RQ-IC-004；M05-IC-06 失败整体 retryable；只读 |
| RQ-CONTRACT-RG-RETENTION | CMP-RETENTION-GOVERNANCE → CMP-RQ-RETENTION-VIEW-ADAPTER | 输入：`batch_id`, `submission_id`；输出：`batch_id`, `retention_due_at`, `scope`, `batch_status`, `exclusions`, `cleared_submission_ids`；next_hop：`CMP-RQ-RETENTION-VIEW-ADAPTER`；event_policy：`none` | M05-IC-06；不拥有/修改 DeletionBatch；只读 |
| RQ-CONTRACT-FACADE-RESPONSE | CMP-RQ-QUERY-FACADE → CMP-ACCESS-GATE | 输入：`courses`, `groups`, `students`, `submissions`, `material_refs`, `status`, `original_grade`, `dimension_rationales`, `teacher_suggestions`, `annotations`, `final_grade`, `deletion_batches`, `failure_reason`, `retry_record`；输出：`courses`, `groups`, `students`, `submissions`, `material_refs`, `status`, `original_grade`, `dimension_rationales`, `teacher_suggestions`, `annotations`, `final_grade`, `deletion_batches`, `failure_reason`, `retry_record`；next_hop：`CMP-ACCESS-GATE`；event_policy：`none` | RQ-IC-005；禁止 partial success；CT-007 字段/错误/版本不变 |

该登记只补充验证器可消费的字段表达，不改变第 1–4 节已有的父契约和内部绑定；若验证器支持直接读取 `component_bindings`，两者必须逐字段一致。

## 6. 本层合法运行流

```yaml
local_legal_flows:
  - flow_id: RQ-FLOW-001
    from: CMP-ACCESS-GATE
    to: CMP-RQ-QUERY-FACADE
    contract: CT-007
    kind: sync_internal
    entry_condition: "CT-007 已通过认证和课程范围授权，GATE 已建立 auth_context"
    next_hop:
      - {to: CMP-RQ-SCOPE-ASSEMBLER, contract: RQ-IC-001, condition: "请求包含课程/小组/学生/提交选择"}
      - {to: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER, contract: RQ-IC-002, condition: "请求需要提交详情"}
      - {to: CMP-RQ-RETENTION-VIEW-ADAPTER, contract: RQ-IC-004, condition: "CT-007 必需装配 deletion_batches[]"}
    return_to_caller: ["完整 CT-007 response", "NOT_FOUND", "VALIDATION_FAILED"]
    terminal_states: [completed, rejected, retryable]
  - flow_id: RQ-FLOW-002
    from: CMP-RQ-SCOPE-ASSEMBLER
    to: CMP-READMODEL-PROJECTOR
    contract: M05-IC-02
    kind: sync_internal_read
    entry_condition: "已授权查询范围已规范化，开始读取课程/小组/学生/提交层级视图"
    next_hop: []
    return_to_caller: [hierarchy_view]
    terminal_states: [read_completed, read_failed_retry]
  - flow_id: RQ-FLOW-003
    from: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
    to: CMP-READMODEL-PROJECTOR
    contract: M05-IC-02
    kind: sync_internal_read
    entry_condition: "提交选择已规范化，开始读取提交详情视图"
    next_hop:
      - {to: CMP-RQ-OUTCOME-ADAPTER, contract: RQ-IC-003, condition: "读模型返回评分或失败结果字段"}
    return_to_caller: [submission_detail_view, NOT_FOUND]
    terminal_states: [read_completed, read_failed_retry, rejected]
  - flow_id: RQ-FLOW-004
    from: CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER
    to: CMP-RQ-OUTCOME-ADAPTER
    contract: RQ-IC-003
    kind: sync_internal
    entry_condition: "详情视图含 status/outcome 字段"
    next_hop: []
    return_to_caller: [outcome_view]
    terminal_states: [scored_visible, scoring_failed_visible, rejected]
  - flow_id: RQ-FLOW-005
    from: CMP-RQ-RETENTION-VIEW-ADAPTER
    to: CMP-RETENTION-GOVERNANCE
    contract: M05-IC-06
    kind: sync_internal_read
    entry_condition: "CT-007 需要 deletion_batches[]，且查询范围已确定"
    next_hop: []
    return_to_caller: [deletion_batches]
    terminal_states: [read_completed, read_failed_retry]
  - flow_id: RQ-FLOW-006
    from: CMP-RQ-QUERY-FACADE
    to: CMP-ACCESS-GATE
    contract: CT-007
    kind: sync_response
    entry_condition: "所有必需局部视图均完成，或任一必需端口失败"
    next_hop: []
    return_to_caller: ["完整 CT-007 response", "NOT_FOUND", "VALIDATION_FAILED", "retryable failure"]
    terminal_states: [completed, rejected, retryable]
```

## 7. 错误、超时、重试和兼容

| 场景 | 处理 |
|---|---|
| AUTH_INVALID/FORBIDDEN | 在 GATE 终止；本层不重复授权、不写 AccessDeniedLog |
| NOT_FOUND | 目标选择已授权但读模型无对应课程/小组/学生/提交时返回父错误，不制造空对象 |
| VALIDATION_FAILED | 选择条件结构不合法或违反 CT-007 输入约束时返回父错误 |
| scoring_failed | 返回失败原因与重试记录；没有有效原始等级时不输出伪造等级/最终等级 |
| M05-IC-02 读取失败 | 整个 CT-007 查询转 retryable；不得部分返回缺失字段 |
| M05-IC-06 读取失败 | 整个 CT-007 查询转 retryable；不得省略 `deletion_batches[]` |
| 超时 | 继承 ≤10 秒查询约束；内部端口超时不通过旧缓存降级 |
| 兼容 | CT-007 `/api/v1` 和父字段/错误/版本不变；L2 内部契约演进不得外溢 |

## 8. 父契约不变性自检

- 未新增公共 API 或事件。
- CT-007 的 provider、path、required/produced fields、条件字段、错误码、只读语义、超时和版本均与 L1 一致。
- M05-IC-02/M05-IC-06 的 owner、输入输出字段、失败处理、只读语义均未改变。
- 未新增跨模块读取；未改变 MOD-02、MOD-03、MOD-04、MOD-05 兄弟节点所有权。
