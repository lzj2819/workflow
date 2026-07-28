# 04 Contracts and Runtime — L2 / CMP-TEACHER-UI

> C3/C4/C5 映射：父运行流 → UI 内部协作；父契约 → 五个 child 的请求/响应适配；父外部依赖 → CMP-ACCESS-GATE 唯一边界。父契约语义不可变。

## 1. 父契约实现映射

| 父契约 | UI 入口 | UI child | UI 行为 | 不可改变的父语义 |
|---|---|---|---|---|
| CT-007 | 课程、组、学生、提交列表/详情 | CMP-TUI-COURSE-SUBMISSION-BROWSER | 发送 `teacher_session` 和范围参数；装配 `courses/groups/students/submissions`、评分、批注、失败、删除批次 | read-only；FORBIDDEN 记录由 GATE 处理；出参含 `deletion_batches[]`；≤10 秒约束不被 UI 延长 |
| CT-008 | 提交详情复核工作台 | CMP-TUI-REVIEW-WORKBENCH | 编辑 annotation/final_grade；生成 `request_id`；成功显示服务端 `review_record`，失败保留草稿 | `request_id` 幂等；至少 annotation/final_grade 之一；NO_ORIGINAL_GRADE；并发后写为准 |
| CT-009 | 展示工作区 | CMP-TUI-PRESENTATION-WORKSPACE | 选择 `group_ids[]`；发送生成请求；呈现 `presentation_id`、blocks、missing_marks | 资格校验和快照写入归 CMP-PRESENTATION；NO_AVAILABLE_SUBMISSION；幂等键语义不改 |
| CT-011 | 删除批次确认台 | CMP-TUI-RETENTION-CONFIRMATION | 显示范围和状态；明确二次确认后发送 `batch_id/confirm/exclusions` | confirm=false 不触发；审计先行、异步执行、CT-012 发布由服务端实现 |
| CT-005 | CT-007 响应中的失败通知/状态 | CMP-TUI-NOTIFICATION-STATUS | 只呈现父投影后的 failure_reason/retry_record/通知条目 | UI 不消费事件、不改变 `scored/scoring_failed` 语义 |

## 2. 父绑定逐字段镜像

UI → GATE 的绑定保留 L1 的字段集合和 next hop：

```yaml
component_bindings:
  - binding_id: M05-BIND-FLOW-009-BROWSER-UI
    contract_id: FLOW-009
    provider_component: 教师浏览器
    consumer_component: CMP-TEACHER-UI
    required_fields: [teacher_session, action, payload]
    produced_fields: [teacher_session, action, payload]
    next_hop: CMP-TEACHER-UI
  - binding_id: M05-BIND-CT-007-UI-GATE
    contract_id: CT-007
    provider_component: CMP-TEACHER-UI
    consumer_component: CMP-ACCESS-GATE
    required_fields: [teacher_session]
    produced_fields: [teacher_session, course_id, group_id, student_id, submission_id]
    next_hop: CMP-ACCESS-GATE
  - binding_id: M05-BIND-CT-008-UI-GATE
    contract_id: CT-008
    provider_component: CMP-TEACHER-UI
    consumer_component: CMP-ACCESS-GATE
    required_fields: [teacher_session, submission_id, request_id]
    produced_fields: [teacher_session, submission_id, request_id, annotation, final_grade]
    next_hop: CMP-ACCESS-GATE
  - binding_id: M05-BIND-CT-009-UI-GATE
    contract_id: CT-009
    provider_component: CMP-TEACHER-UI
    consumer_component: CMP-ACCESS-GATE
    required_fields: [teacher_session, group_ids]
    produced_fields: [teacher_session, group_ids]
    next_hop: CMP-ACCESS-GATE
  - binding_id: M05-BIND-CT-011-UI-GATE
    contract_id: CT-011
    provider_component: CMP-TEACHER-UI
    consumer_component: CMP-ACCESS-GATE
    required_fields: [teacher_session, batch_id, confirm]
    produced_fields: [teacher_session, batch_id, confirm, exclusions]
    next_hop: CMP-ACCESS-GATE
```

父契约的 `required_fields`、`produced_fields`、错误、幂等、side effects、dependencies 和 version 与 L1 `04-contracts-and-runtime.md` 保持逐字语义；本层只增加浏览器内部状态字段，不把它们外溢到父 API。

### 2.1 Child 级机器可读接口契约

以下 `component_cards` 只描述 L2 child 的适配边界。`contract.required` 是该 child 的稳定入站字段；`optional`、`produced`、`response_fields` 和 `errors` 用于场景模拟与返回结果校验。它们不新增或修改 CT-007/008/009/011 的父契约字段。

```yaml
component_cards:
  CMP-TUI-COURSE-SUBMISSION-BROWSER:
    inbound_interfaces:
      - interface_id: TUI-IC-00-BROWSER-ENTRY
        provider: 教师浏览器
        consumer: CMP-TUI-COURSE-SUBMISSION-BROWSER
        contract:
          required: [teacher_session, action, payload]
          optional: [course_id, group_id, student_id, submission_id]
        produced: [teacher_session, course_id, group_id, student_id, submission_id]
        next_hop: CMP-ACCESS-GATE
        errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED]
    outbound_interfaces:
      - interface_id: TUI-IC-01-DETAIL-VIEW
        provider: CMP-TUI-COURSE-SUBMISSION-BROWSER
        consumer: CMP-TUI-REVIEW-WORKBENCH
        contract:
          required: [scope_key, submission_id]
          optional: [material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, failure_reason, retry_record]
        produced: [scope_key, submission_id, read_view_model]
        next_hop: CMP-TUI-REVIEW-WORKBENCH

  CMP-TUI-NOTIFICATION-STATUS:
    inbound_interfaces:
      - interface_id: TUI-IC-02-NOTIFICATION-INPUT
        provider: CMP-TUI-COURSE-SUBMISSION-BROWSER
        consumer: CMP-TUI-NOTIFICATION-STATUS
        contract:
          required: [submission_id]
          optional: [scoring_failed, failure_reason, retry_record]
        produced: [notification_id, visible_status, source_submission_id]
        next_hop: CMP-TUI-COURSE-SUBMISSION-BROWSER
        errors: [UNKNOWN_FAILURE_FIELDS]
    outbound_interfaces:
      - interface_id: TUI-IC-06-NOTIFICATION-VISIBLE
        provider: CMP-TUI-NOTIFICATION-STATUS
        consumer: CMP-TUI-COURSE-SUBMISSION-BROWSER
        contract:
          required: [notification_id, visible_status, source_submission_id]
        produced: [notification_id, visible_status, source_submission_id]
        next_hop: CMP-TUI-COURSE-SUBMISSION-BROWSER

  CMP-TUI-PRESENTATION-WORKSPACE:
    inbound_interfaces:
      - interface_id: TUI-IC-04-PRESENTATION-RESPONSE
        provider: CMP-ACCESS-GATE
        consumer: CMP-TUI-PRESENTATION-WORKSPACE
        contract:
          required: [presentation_id, blocks]
          optional: ["blocks[].missing_marks"]
        produced: [presentation_id, blocks]
        next_hop: CMP-TUI-PRESENTATION-WORKSPACE
        errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_AVAILABLE_SUBMISSION]
    outbound_interfaces:
      - interface_id: TUI-IC-04-PRESENTATION-REQUEST
        provider: CMP-TUI-PRESENTATION-WORKSPACE
        consumer: CMP-ACCESS-GATE
        contract:
          required: [teacher_session, group_ids]
        produced: [teacher_session, group_ids]
        next_hop: CMP-ACCESS-GATE

  CMP-TUI-RETENTION-CONFIRMATION:
    inbound_interfaces:
      - interface_id: TUI-IC-05-RETENTION-VIEW
        provider: CMP-TUI-COURSE-SUBMISSION-BROWSER
        consumer: CMP-TUI-RETENTION-CONFIRMATION
        contract:
          required: [batch_id]
          optional: [retention_due_at, scope, batch_status, exclusions]
        produced: [batch_id, confirm, exclusions]
        next_hop: CMP-ACCESS-GATE
    outbound_interfaces:
      - interface_id: TUI-IC-05-RETENTION-REQUEST
        provider: CMP-TUI-RETENTION-CONFIRMATION
        consumer: CMP-ACCESS-GATE
        contract:
          required: [teacher_session, batch_id, confirm]
          optional: [exclusions]
        produced: [teacher_session, batch_id, confirm, exclusions]
        next_hop: CMP-ACCESS-GATE
        errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, BATCH_NOT_EXPIRED]

  CMP-TUI-REVIEW-WORKBENCH:
    inbound_interfaces:
      - interface_id: TUI-IC-07-REVIEW-RESPONSE
        provider: CMP-ACCESS-GATE
        consumer: CMP-TUI-REVIEW-WORKBENCH
        contract:
          required: [submission_id]
          optional: [review_record, review_record.original_grade, review_record.final_grade, review_record.operator, review_record.updated_at]
        produced: [review_record]
        next_hop: CMP-TUI-REVIEW-WORKBENCH
        errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_ORIGINAL_GRADE]
    outbound_interfaces:
      - interface_id: TUI-IC-03-REVIEW-REQUEST
        provider: CMP-TUI-REVIEW-WORKBENCH
        consumer: CMP-ACCESS-GATE
        contract:
          required: [teacher_session, submission_id, request_id]
          optional: [annotation, final_grade]
        produced: [teacher_session, submission_id, request_id, annotation, final_grade]
        next_hop: CMP-ACCESS-GATE
```

## 3. L2 内部契约

| contract_id | owner → consumer | 输入/输出 | 错误与兼容性 |
|---|---|---|---|
| TUI-IC-01 | COURSE-SUBMISSION-BROWSER → REVIEW-WORKBENCH / PRESENTATION-WORKSPACE | `scope_key`, selected IDs, read view model | 只读传递；不改变 CT-007 字段；范围切换使旧更新失效 |
| TUI-IC-02 | COURSE-SUBMISSION-BROWSER → NOTIFICATION-STATUS | `failure_reason`, `retry_record`, notification candidates | 缺失字段显式 unknown；不得推导 scored |
| TUI-IC-03 | REVIEW-WORKBENCH → CMP-ACCESS-GATE | `teacher_session`, `submission_id`, `request_id`, `annotation`, `final_grade` | 保留 CT-008 错误和 idempotency；UI 不处理 NO_ORIGINAL_GRADE |
| TUI-IC-04 | PRESENTATION-WORKSPACE → CMP-ACCESS-GATE | `teacher_session`, `group_ids` | 保留 CT-009 错误和幂等；不实时跨模块读取 |
| TUI-IC-05 | RETENTION-CONFIRMATION → CMP-ACCESS-GATE | `teacher_session`, `batch_id`, `confirm`, `exclusions` | confirm=true 只来自明确动作；保留 BATCH_NOT_EXPIRED |
| TUI-IC-06 | NOTIFICATION-STATUS → COURSE-SUBMISSION-BROWSER / REVIEW-WORKBENCH | `notification_id`, visible status, source submission_id | 仅影响 UI 显示，不产生服务端副作用 |

## 4. 合法运行流（机器可读）

```yaml
local_legal_flows:
  - flow_id: TUI-FLOW-001
    entry_condition: "教师已持有 session，打开课程或提交范围"
    from: CMP-TUI-COURSE-SUBMISSION-BROWSER
    next_hop: CMP-ACCESS-GATE
    next_hop_condition: "CT-007 认证与课程范围授权通过"
    contract: CT-007
    provider_route_ref: M05-FLOW-002
    response_contract: CT-007.response
    return_hop:
      from: CMP-ACCESS-GATE
      to: CMP-TUI-COURSE-SUBMISSION-BROWSER
      contract: CT-007.response
      event: CT-007_RESPONSE
      produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, deletion_batches, failure_reason, retry_record]
    return_to_caller: "CT-007 response → COURSE-SUBMISSION-BROWSER → list/detail view model"
    terminal_states: [query_ready, query_empty, AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, query_timeout]
  - flow_id: TUI-FLOW-002
    entry_condition: "提交详情存在且教师编辑 annotation 或 final_grade"
    from: CMP-TUI-REVIEW-WORKBENCH
    next_hop: CMP-ACCESS-GATE
    next_hop_condition: "CT-008 认证与课程范围授权通过，request_id 已受理"
    contract: CT-008
    provider_route_ref: M05-FLOW-003
    state_transitions:
      - {from: ST-TUI-REVIEW-DRAFT.dirty, to: ST-TUI-REVIEW-DRAFT.submitting, trigger: user_submit}
      - {from: ST-TUI-REVIEW-DRAFT.submitting, to: ST-TUI-REVIEW-DRAFT.saved, trigger: CT-008.success}
    write_effects:
      owner: CMP-REVIEW-COMMAND
      records: [ReviewRecord, GradeAdjustmentRecord, idempotency_record]
      projection_event: M05-IC-05
    response_contract: CT-008.response
    return_hop:
      from: CMP-ACCESS-GATE
      to: CMP-TUI-REVIEW-WORKBENCH
      contract: CT-008.response
      event: CT-008_RESPONSE
      produced_fields: [review_record]
      response_fields: [review_record.original_grade, review_record.final_grade, review_record.operator, review_record.updated_at]
    return_to_caller: "review_record → REVIEW-WORKBENCH；错误 → draft retained + error feedback"
    terminal_states: [review_saved, AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_ORIGINAL_GRADE]
  - flow_id: TUI-FLOW-003
    entry_condition: "教师选择一个或多个 group_id 并提交生成"
    from: CMP-TUI-PRESENTATION-WORKSPACE
    next_hop: CMP-ACCESS-GATE
    next_hop_condition: "CT-009 认证与课程范围授权通过，group_ids[] 已校验"
    contract: CT-009
    provider_route_ref: M05-FLOW-004
    response_contract: CT-009.response
    return_hop:
      from: CMP-ACCESS-GATE
      to: CMP-TUI-PRESENTATION-WORKSPACE
      contract: CT-009.response
      event: CT-009_RESPONSE
      produced_fields: [presentation_id, blocks]
      response_fields: ["blocks[].missing_marks"]
    return_to_caller: "presentation_id/blocks → workspace snapshot; error → selection retained"
    terminal_states: [presentation_ready, AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_AVAILABLE_SUBMISSION]
  - flow_id: TUI-FLOW-004
    entry_condition: "教师在删除批次页完成明确二次确认"
    from: CMP-TUI-RETENTION-CONFIRMATION
    next_hop: CMP-ACCESS-GATE
    next_hop_condition: "confirm=true 由明确用户动作产生，且批次仍在当前授权范围"
    contract: CT-011
    provider_route_ref: M05-FLOW-005
    response_contract: CT-011.response
    return_hop:
      from: CMP-ACCESS-GATE
      to: CMP-TUI-RETENTION-CONFIRMATION
      contract: CT-011.response
      event: CT-011_RESPONSE
      produced_fields: [batch_id, batch_status, pending_deletion_scope]
    return_to_caller: "batch_status/pending_deletion_scope → confirmation status"
    terminal_states: [confirmation_accepted, AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, BATCH_NOT_EXPIRED]
  - flow_id: TUI-FLOW-005
    entry_condition: "CT-007 response contains scoring_failed/failure_reason/retry_record"
    from: CMP-TUI-NOTIFICATION-STATUS
    next_hop: CMP-TUI-COURSE-SUBMISSION-BROWSER
    next_hop_condition: "notification candidate belongs to the current scope"
    contract: TUI-IC-02
    response_contract: TUI-IC-06
    return_hop:
      from: CMP-TUI-NOTIFICATION-STATUS
      to: CMP-TUI-COURSE-SUBMISSION-BROWSER
      contract: TUI-IC-06
      event: NOTIFICATION_VISIBLE
      produced_fields: [notification_id, visible_status, source_submission_id]
    return_to_caller: "notification visible in list/detail; no grade mutation"
    terminal_states: [notification_visible, notification_dismissed, source_scope_changed]
  - flow_id: TUI-FLOW-006
    entry_condition: "CT-007 detail response is ready and the teacher opens the review entry"
    from: CMP-TUI-COURSE-SUBMISSION-BROWSER
    next_hop: CMP-TUI-REVIEW-WORKBENCH
    next_hop_condition: "detail_open=true and submission_id belongs to the current scope"
    contract: TUI-IC-01
    response_contract: TUI-IC-07
    return_hop:
      from: CMP-TUI-COURSE-SUBMISSION-BROWSER
      to: CMP-TUI-REVIEW-WORKBENCH
      contract: TUI-IC-01
      event: DETAIL_OPEN
      produced_fields: [scope_key, submission_id, read_view_model]
      response_fields: [material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, failure_reason, retry_record]
    return_to_caller: "read_view_model → REVIEW-WORKBENCH；missing/failed fields remain explicit"
    terminal_states: [detail_rendered, detail_closed, source_scope_changed]
```

不得从 UI 直接连接 CMP-REVIEW-QUERY、CMP-REVIEW-COMMAND、CMP-PRESENTATION 或 CMP-RETENTION-GOVERNANCE；必须命中父层声明的 GATE next hop。

`provider_route_ref` 只引用 L1 已定义的内部流，不改变 L2 的外部边界：请求仍由 child 经 `CMP-ACCESS-GATE` 发出，响应由 GATE 按父流返回。`return_hop` 用于验证器确认响应字段和终止状态，不表示新增 UI 到兄弟服务的直连。

## 5. 成功、失败、恢复与生命周期

- 查询成功：绑定当前 `scope_key` 后渲染；旧请求晚到时丢弃 UI 更新。
- 查询失败：按父错误码显示可解释失败；`FORBIDDEN` 不显示未授权数据，`NOT_FOUND` 不转换为空列表。
- CT-008 失败：保留未提交草稿和父错误；用户可显式重试，重试生成新的或父语义要求的幂等上下文。
- CT-009 失败：保留 group selection，显示 `NO_AVAILABLE_SUBMISSION` 或验证错误；不创建本地伪视图。
- CT-011 失败：保留确认页但重置提交锁；不把 accepted 当作 purge completed。
- 认证过期：清理服务端请求上下文，导向父会话处理；不在 UI 本地续签或绕过 GATE。
- 通知刷新：只合并当前 scope 的失败/重试条目，不覆盖未提交复核草稿。

## 6. 可观测性与非功能约束

每个 UI action 记录最小关联信息：`flow_id`、`contract_id`、`scope_key_hash`、`request_id`（如有）、结果类别和耗时；不得记录学生材料正文、教师 token 或完整敏感响应。沿用 KD-003 的父日志与告警设施。UI 不设置比父契约更长的同步等待，不通过缓存旧授权或旧等级掩盖失败。
