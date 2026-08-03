# 04 Interface Contracts — 接口契约

通用约定（KD-005):

- 插件/服务器间 API 统一前缀 `/api/v1`，版本通过路径演进，不兼容变更升级主版本。
- 认证：学生凭邀请码+姓名+小组经 `POST /api/v1/auth/token` 换取访问令牌（Bearer)；教师端使用教师账号会话。所有请求 HTTPS(KD-003)。
- 幂等：写操作由客户端提供幂等键（提交为客户端生成的 submission UUID)；服务端按幂等键去重，重复请求返回首次结果。
- 材料限制：单次提交 ≤500MB；文件类型白名单（代码、文本、图片、常见文档、压缩包）(KD-004)。
- 机器可读约定：每个契约末尾的 `contract_fields` YAML 块为该契约字段级信息的唯一机器可读来源（供验证器消费），与正文 bullet 同源同义；冲突时以 YAML 块为准。
- 认证端点归属：`POST /api/v1/auth/token` 由 MOD-02 提供（DU-1 仅与 DU-2 交互），名单核对语义同 CT-003；该端点视为 CT-001 契约族附属交互，不单独编号。

## API 契约

### CT-001 提交材料包上传

- `contract_id`: CT-001
- `contract_type`: api
- Provider: MOD-02 submission-intake
- Consumer: MOD-01 codex-plugin
- Trigger / Protocol: 学生发起提交；HTTPS `POST /api/v1/submissions`(multipart 分片，支持断点续传：先创建上传会话，逐分片上传，最后提交合并）
- Sync / Async: Sync（学生在 30 秒目标内等待接收确认）
- Schema:
  - 请求：`submission_uuid`(幂等键)、`invite_code`、`student_name`、`group_name`、`assignment`、材料分片（对话/代码/截图/结果，标注类别）
  - 应答：`submission_id`、`received_at`、`status`(received)、`missing_items[]`
  - 校验拒绝：`status=rejected`、`rejection_reason`
- `side_effects`: 创建提交记录与材料清单；执行归属校验；推进状态机；生成完整性报告与缺失项标记；发布 SubmissionReceived（校验通过时）
- `dependencies`: CT-003
- Error / Timeout / Retry: 上传中断 → 服务端标记 upload_failed 并记录原因；客户端断点续传重试；30 秒超时未确认时客户端用 CT-002 查询真实状态
- Idempotency: 以 `submission_uuid` 为幂等键；重复上传返回同一 `submission_id`，不产生重复提交
- Versioning: `/api/v1`；分片协议字段向后兼容追加
- Source FR / Flow / Event: FR-001~FR-005、FR-007；F1-1~F1-5;AC-REQ-001-01、AC-REQ-003-01、AC-REQ-007-01

```yaml
contract_fields:
  contract_id: CT-001
  provider: MOD-02
  consumer: MOD-01
  direction: sync_api
  inbound_required_fields: [submission_uuid, invite_code, student_name, group_name, assignment, "material_chunks[]"]   # material_chunks[] 元素须标注类别：对话/代码/截图/结果
  inbound_optional_fields: []
  outbound_produced_fields: [submission_id, received_at, status, "missing_items[]"]
  outbound_conditional_fields: [rejection_reason]   # 仅 status=rejected 时返回
  error_codes: [AUTH_INVALID, VALIDATION_FAILED, PAYLOAD_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE, REJECTED_MEMBERSHIP]
  publishes_events: [CT-004, CT-006]   # 仅归属校验通过时发布
```

### CT-002 提交状态查询

- `contract_id`: CT-002
- `contract_type`: api (query)
- Provider: MOD-02 submission-intake
- Consumer: MOD-01 codex-plugin
- Trigger / Protocol: 上传结果未知或失败展示时；`GET /api/v1/submissions/{submission_uuid}`
- Sync / Async: Sync
- Schema: 应答 `submission_id`、`status`、`failure_reason?`、`missing_items[]`
- `side_effects`: None; read-only
- `dependencies`: CT-001
- Error / Timeout / Retry: 未知 UUID → 404；客户端指数退避重试
- Idempotency: 只读，天然幂等
- Versioning: `/api/v1`
- Source FR / Flow / Event: AC-REQ-001-01 exceptions;F1-3

```yaml
contract_fields:
  contract_id: CT-002
  provider: MOD-02
  consumer: MOD-01
  direction: sync_api_query
  inbound_required_fields: [submission_uuid]   # 路径参数
  inbound_optional_fields: []
  outbound_produced_fields: [submission_id, status, "missing_items[]"]
  outbound_conditional_fields: [failure_reason]   # upload_failed / rejected / scoring_failed 时返回
  error_codes: [AUTH_INVALID, NOT_FOUND]
  publishes_events: []
```

### CT-003 课程归属校验

- `contract_id`: CT-003
- `contract_type`: api
- Provider: MOD-03 course-roster
- Consumer: MOD-02 submission-intake
- Trigger / Protocol: CT-001 处理过程中；服务间 HTTPS `POST /api/v1/courses/verify-membership`
- Sync / Async: Sync
- Schema: 请求 `invite_code`、`student_name`、`group_name`；应答 `verified: bool`、`reason?`、`course_id`
- `side_effects`: 记录校验结果（通过/拒绝原因）
- `dependencies`: 名单数据（CT-013)
- Error / Timeout / Retry: 名单服务超时 → 提交保持待校验状态并重试；不向客户端暴露内部错误细节
- Idempotency: 同一请求重复执行结果一致；每次提交必须重新调用（REQ-006)，不得缓存通过结论
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-005、FR-006;F1-4

```yaml
contract_fields:
  contract_id: CT-003
  provider: MOD-03
  consumer: MOD-02
  direction: sync_api
  inbound_required_fields: [invite_code, student_name, group_name]
  inbound_optional_fields: []
  outbound_produced_fields: [verified, course_id]
  outbound_conditional_fields: [reason]   # verified=false 时返回
  error_codes: [ROSTER_UNAVAILABLE]   # 超时/内部错误；不向客户端暴露内部细节
  publishes_events: []
```

### CT-007 教师课程数据查询

- `contract_id`: CT-007
- `contract_type`: api (query)
- Provider: MOD-05 teacher-web
- Consumer: 教师浏览器
- Trigger / Protocol: 教师打开课程/小组/学生/提交详情；`GET /api/v1/teacher/courses/...`
- Sync / Async: Sync
- Schema: 课程列表、小组列表、学生详情、提交材料清单、处理状态、Agent 原始等级/依据/建议、批注、最终等级、失败原因与重试结果、删除批次列表（batch_id、保留到期时间、待删范围、状态、教师排除标记）
- `side_effects`: None; read-only
- `dependencies`: CT-005、CT-006（读模型派生）
- Error / Timeout / Retry: 无权课程 → 403 并记录 AccessDeniedLogged；查询超时 → 前端重试
- Idempotency: 只读，天然幂等
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-009;F3-1;AC-REQ-009-01;NFR-001;FR-016、DF-3（删除批次可读：教师确认删除前经本契约查看到期批次与范围）

```yaml
contract_fields:
  contract_id: CT-007
  provider: MOD-05
  consumer: 教师浏览器
  direction: sync_api_query
  inbound_required_fields: [teacher_session]   # 教师账号会话（Bearer）
  inbound_optional_fields: [course_id, group_id, student_id, submission_id]   # 按视图层级使用的定位参数
  outbound_produced_fields: ["courses[]", "groups[]", "students[]", "submissions[]", "material_refs[]", status, original_grade, "dimension_rationales[]", "teacher_suggestions[]", "annotations[]", final_grade, "deletion_batches[]"]   # deletion_batches[] 元素：batch_id、retention_due_at、scope、batch_status、exclusions[]
  outbound_conditional_fields: [failure_reason, retry_record]   # scoring_failed 时返回
  error_codes: [AUTH_INVALID, FORBIDDEN]   # FORBIDDEN 时记录 AccessDeniedLogged
  publishes_events: []
```

### CT-008 教师批注与最终等级调整

- `contract_id`: CT-008
- `contract_type`: api
- Provider: MOD-05 teacher-web
- Consumer: 教师浏览器
- Trigger / Protocol: 教师保存批注或调整等级；`PUT /api/v1/teacher/submissions/{id}/review`
- Sync / Async: Sync
- Schema: 请求 `annotation?`、`final_grade?`(A–E);应答保存后的复核记录（含原始等级、最终等级、操作者、时间）
- `side_effects`: 写批注、最终等级与调整记录（AnnotationSaved / GradeAdjusted)
- `dependencies`: CT-007
- Error / Timeout / Retry: 提交为 scoring_failed 且无原始等级时拒绝设置最终等级（不得伪造等级）;并发修改以后写为准并完整留痕
- Idempotency: 客户端生成请求幂等键；重复提交返回同一复核记录
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-009;F3-2、F3-3;AC-REQ-009-01

```yaml
contract_fields:
  contract_id: CT-008
  provider: MOD-05
  consumer: 教师浏览器
  direction: sync_api
  inbound_required_fields: [submission_id, request_id]   # request_id 为客户端幂等键；annotation 与 final_grade 至少其一
  inbound_optional_fields: [annotation, final_grade]   # final_grade ∈ {A,B,C,D,E}
  outbound_produced_fields: ["review_record{original_grade, final_grade, annotation, operator, updated_at}"]
  outbound_conditional_fields: []
  error_codes: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_ORIGINAL_GRADE]
  publishes_events: []   # AnnotationSaved / GradeAdjusted 为模块内事件，不跨模块投递
```

### CT-009 展示视图生成

- `contract_id`: CT-009
- `contract_type`: api
- Provider: MOD-05 teacher-web
- Consumer: 教师浏览器
- Trigger / Protocol: 教师选定小组生成展示视图；`POST /api/v1/teacher/presentations`
- Sync / Async: Sync
- Schema: 请求 `group_ids[]`；应答 `presentation_id`、各小组区块（项目结果、过程摘要、评分、批注、缺失标记）
- `side_effects`: 创建展示视图快照（PresentationViewGenerated)
- `dependencies`: CT-007、CT-008
- Error / Timeout / Retry: 任一选定小组无可用提交 → 拒绝生成并说明原因；生成超时 → 重试
- Idempotency: 相同请求参数重复生成返回最新快照，不产生重复视图记录（幂等键：教师+小组集合+时间窗）
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-010;F4-1;AC-REQ-010-01

```yaml
contract_fields:
  contract_id: CT-009
  provider: MOD-05
  consumer: 教师浏览器
  direction: sync_api
  inbound_required_fields: ["group_ids[]"]
  inbound_optional_fields: []
  outbound_produced_fields: [presentation_id, "blocks[]"]   # blocks[] 元素：group_id、project_result、process_summary、grades、annotations、missing_marks
  outbound_conditional_fields: []
  error_codes: [AUTH_INVALID, FORBIDDEN, VALIDATION_FAILED, NO_AVAILABLE_SUBMISSION]
  publishes_events: []   # PresentationViewGenerated 为模块内快照事件
```

### CT-011 删除确认

- `contract_id`: CT-011
- `contract_type`: api
- Provider: MOD-05 teacher-web
- Consumer: 教师浏览器
- Trigger / Protocol: 保留期到期后教师确认删除；`POST /api/v1/teacher/deletion-batches/{id}/confirm`
- Sync / Async: Sync（确认动作）；执行为异步批处理
- Schema: 请求 `confirm: true`、`exclusions[]`（教师标记保留的记录）；应答批次状态与待删除范围
- `side_effects`: 创建删除确认记录；触发异步删除执行；写删除审计记录（DeletionConfirmed → RecordsDeleted)
- `dependencies`: 保留期到期标记（DF-3 步骤 1–2)
- Error / Timeout / Retry: 未到期批次拒绝确认；执行部分失败保留失败项供重跑
- Idempotency: 同一批次重复确认返回同一状态，不重复执行
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-016;F5-2、F5-3;AC-NFR-004-01

```yaml
contract_fields:
  contract_id: CT-011
  provider: MOD-05
  consumer: 教师浏览器
  direction: sync_api   # 确认动作同步；删除执行为异步批处理
  inbound_required_fields: [batch_id, confirm]   # 仅 confirm=true 触发执行
  inbound_optional_fields: ["exclusions[]"]   # 教师标记保留的记录
  outbound_produced_fields: [batch_id, batch_status, pending_deletion_scope]
  outbound_conditional_fields: []
  error_codes: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, BATCH_NOT_EXPIRED]
  publishes_events: [CT-012]   # 批次执行完成后经 Outbox 发布
```

### CT-013 名单导入

- `contract_id`: CT-013
- `contract_type`: api
- Provider: MOD-03 course-roster
- Consumer: 教师浏览器 / 名单文件
- Trigger / Protocol: 教师维护名单；`POST /api/v1/courses/{id}/roster`（录入或文件上传）
- Sync / Async: Sync
- Schema: 名单条目（姓名、小组）;应答导入结果与冲突项
- `side_effects`: 创建/更新名单记录
- `dependencies`: 课程已创建
- Error / Timeout / Retry: 格式错误条目逐项拒绝并报告；部分成功可见
- Idempotency: 同一文件重复导入按（姓名+小组）去重，不产生重复条目
- Versioning: `/api/v1`
- Source FR / Flow / Event: FR-005；名单维护（A-002)

```yaml
contract_fields:
  contract_id: CT-013
  provider: MOD-03
  consumer: "教师浏览器 / 名单文件"
  direction: sync_api
  inbound_required_fields: [course_id, "roster_entries[]"]   # roster_entries[] 元素：student_name、group_name
  inbound_optional_fields: []
  outbound_produced_fields: [import_result]   # 含 imported_count、skipped_duplicates[]、conflicts[]；格式错误条目逐项报告
  outbound_conditional_fields: []
  error_codes: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED]
  publishes_events: []
```

## 事件契约

事件经数据库 Outbox 投递（KD-002 技术机制）;payload 为 JSON；消费方必须幂等。

### CT-004 SubmissionReceived

- `contract_id`: CT-004
- `contract_type`: event
- Provider: MOD-02 submission-intake
- Consumer: MOD-04 assessment
- Trigger / Protocol: 提交校验通过并完成材料持久化；Outbox 投递
- Sync / Async: Async
- Schema: `submission_id`、`course_id`、`assignment`、`student_name`、`group_name`、`material_refs[]`、`missing_items[]`、`received_at`
- `side_effects`: 创建评分任务（ScoringTaskCreated)
- `dependencies`: CT-001
- Error / Timeout / Retry: 消费失败由投递器重试；任务持久化后才推进事件确认
- Idempotency: 消费方按 `submission_id` 去重，重复事件不创建重复任务
- Versioning: 事件 schema 版本字段 `v=1`；新增字段向后兼容
- Source FR / Flow / Event: SubmissionReceived;DF-1 步骤 7;F2-1

```yaml
contract_fields:
  contract_id: CT-004
  provider: MOD-02
  consumer: MOD-04
  direction: async_event
  event_required_fields: [submission_id, course_id, assignment, student_name, group_name, "material_refs[]", "missing_items[]", received_at, v]
  event_conditional_fields: []
  error_codes: []   # 事件契约无同步错误码；消费失败由 Outbox 投递器重试
```

### CT-005 SubmissionScored / ScoringFailed

- `contract_id`: CT-005
- `contract_type`: event
- Provider: MOD-04 assessment
- Consumer: MOD-02 submission-intake（状态回写）、MOD-05 teacher-web（复核记录、读模型、教师通知）
- Trigger / Protocol: 评估完成或重试后仍失败；Outbox 投递
- Sync / Async: Async
- Schema: `submission_id`、`outcome`(scored|scoring_failed)、`original_grade?`、`dimension_rationales[5]?`、`teacher_suggestions[]?`、`scored_at?`、`failure_reason?`、`retry_record?`
- `side_effects`: 回写提交状态（scored/scoring_failed)；创建复核记录；派生教师读模型；触发教师端内通知
- `dependencies`: CT-004
- Error / Timeout / Retry: 消费失败重试；读模型可通过重放重建
- Idempotency: 按 `submission_id` + 终态去重；重复事件不改变终态
- Versioning: `v=1`，向后兼容追加
- Source FR / Flow / Event: SubmissionScored、ScoringFailed;DF-1 步骤 9–11、DF-2

```yaml
contract_fields:
  contract_id: CT-005
  provider: MOD-04
  consumer: [MOD-02, MOD-05]
  direction: async_event
  event_required_fields: [submission_id, outcome, v]   # outcome ∈ {scored, scoring_failed}
  event_conditional_fields:
    "outcome=scored": [original_grade, "dimension_rationales[5]", "teacher_suggestions[]", scored_at]
    "outcome=scoring_failed": [failure_reason, retry_record]
  error_codes: []   # 评分失败以 outcome=scoring_failed + failure_reason 表达，不作传输错误
```

### CT-006 SubmissionReceived（读模型派生）

- `contract_id`: CT-006
- `contract_type`: event
- Provider: MOD-02 submission-intake
- Consumer: MOD-05 teacher-web
- Trigger / Protocol: 提交接收后派生教师侧可见列表；Outbox 投递
- Sync / Async: Async
- Schema: `submission_id`、`course_id`、`assignment`、`student_name`、`group_name`、`status`、`missing_items[]`、`received_at`
- `side_effects`: 派生教师侧提交列表与处理状态读模型
- `dependencies`: CT-001
- Error / Timeout / Retry: 消费失败重试；可全量重建
- Idempotency: 按 `submission_id` 去重
- Versioning: `v=1`
- Source FR / Flow / Event: SubmissionReceived;DF-1 步骤 11（状态可见性）

```yaml
contract_fields:
  contract_id: CT-006
  provider: MOD-02
  consumer: MOD-05
  direction: async_event
  event_required_fields: [submission_id, course_id, assignment, student_name, group_name, status, "missing_items[]", received_at, v]
  event_conditional_fields: []
  error_codes: []
```

### CT-012 RecordsDeleted

- `contract_id`: CT-012
- `contract_type`: event
- Provider: MOD-05 teacher-web
- Consumer: MOD-02 submission-intake（清除材料与提交记录）、MOD-05（清除读模型）
- Trigger / Protocol: 删除批次执行完成；Outbox 投递
- Sync / Async: Async
- Schema: `batch_id`、`submission_ids[]`、`scope`、`operator`、`executed_at`、`audit_record_id`
- `side_effects`: 清除目标提交材料与读模型数据，教师端不再可读
- `dependencies`: CT-011
- Error / Timeout / Retry: 清除失败项保留在批次中供重跑；审计记录不受影响
- Idempotency: 重复清除已删除记录为空操作
- Versioning: `v=1`
- Source FR / Flow / Event: RecordsDeleted;DF-3 步骤 4–5;AC-NFR-004-01

```yaml
contract_fields:
  contract_id: CT-012
  provider: MOD-05
  consumer: [MOD-02, MOD-05]   # MOD-05 自消费部分为模块内清除读模型
  direction: async_event
  event_required_fields: [batch_id, "submission_ids[]", scope, operator, executed_at, audit_record_id, v]
  event_conditional_fields: []
  error_codes: []
```

### CT-014 PurgeCompleted

- `contract_id`: CT-014
- `contract_type`: event
- Provider: MOD-02 submission-intake
- Consumer: MOD-05 teacher-web（更新删除批次执行状态）
- Trigger / Protocol: CT-012 消费后，目标提交的材料与提交记录清除完成（含部分失败）;Outbox 投递
- Sync / Async: Async
- Schema: `batch_id`、`purged_submission_ids[]`、`failed_items[]`（元素：`submission_id`、`reason`)、`purged_at`
- `side_effects`: 更新批次执行状态；失败项保留在批次中供重跑；审计记录不受影响
- `dependencies`: CT-012
- Error / Timeout / Retry: 消费失败由投递器重试；失败项经原批次重跑清除，重跑结果再次经本事件回传
- Idempotency: 按 `batch_id` + `purged_at` 去重；重复事件不重复更新批次状态
- Versioning: `v=1`，向后兼容追加
- Source FR / Flow / Event: FR-016;DF-3 步骤 4–5（清除结果回流）;AC-NFR-004-01

```yaml
contract_fields:
  contract_id: CT-014
  provider: MOD-02
  consumer: MOD-05
  direction: async_event
  event_required_fields: [batch_id, "purged_submission_ids[]", "failed_items[]", purged_at, v]   # failed_items[] 元素：submission_id、reason；全部成功时为空数组
  event_conditional_fields: []
  error_codes: []   # 逐项清除失败以 failed_items[] 表达，不作传输错误
```

## 外部系统契约

### CT-010 模型评估推理

- `contract_id`: CT-010
- `contract_type`: external_api
- Provider: 模型服务（外部，KD-001)
- Consumer: MOD-04 assessment（经 ACL)
- Trigger / Protocol: 评分任务执行；HTTPS 模型推理 API（具体端点由供应商适配层封装）
- Sync / Async: Sync（在异步评分任务内调用）
- Schema: 请求：`request_id`（请求级关联 ID)+ 评估提示 + 材料内容（ACL 内最小化编排：对话摘要、代码、结果描述）；应答：五维度评分 JSON（等级、各维度依据、改进建议）
- `side_effects`: 产生评估结果（原始等级、依据、教师专用建议）；材料内容发送至外部供应商（数据出境，由供应商协议与 ACL 最小化控制）
- `dependencies`: 材料包内容；供应商 API 可用性
- Error / Timeout / Retry: 调用超时（建议单次 ≤3 分钟）或解析失败 → 计入评分失败策略：自动重试一次，再失败标记 ScoringFailed(REQ-012);ACL 校验应答 schema，非法应答视为失败
- Idempotency: 同一评分任务的重复调用以任务内结果为准，不产生重复评估记录；`request_id` 仅用于单次调用关联与重试去重
- 数据最小化约定（justification)：不向外部供应商发送 `submission_id`、学生姓名等业务标识（KD-001 ACL 最小化）；业务关联由 MOD-04 在任务内部维护
- Versioning: 供应商 API 版本由 ACL 封装，升级不影响其他 Module
- Source FR / Flow / Event: FR-008、FR-012;F2-2;KD-001

```yaml
contract_fields:
  contract_id: CT-010
  provider: "模型服务（外部）"
  consumer: MOD-04
  direction: external_sync_api
  inbound_required_fields: [evaluation_prompt, materials]   # 术语对齐：evaluation_prompt ≡ Gherkin/场景中的 assessment_prompt；materials ≡ material_refs[]（经 ACL 最小化编排：dialogue_summary、code、result_description）
  inbound_optional_fields: [request_id]   # 请求级关联 ID，仅用于单次调用关联与重试去重；不携带 submission_id 等业务标识（数据最小化，KD-001）
  outbound_produced_fields: [grade, "dimension_rationales[5]", "suggestions[]"]
  outbound_conditional_fields: []
  error_codes: [MODEL_TIMEOUT, MODEL_ERROR, INVALID_RESPONSE_SCHEMA]   # 均计入评分失败策略（自动重试一次，REQ-012）
  publishes_events: []
```

## 错误码汇总（机器可读）

| 错误码 | 语义 / 触发条件 | 载体 | 适用契约 |
|---|---|---|---|
| AUTH_INVALID | 访问令牌或教师会话缺失/无效（邀请码+姓名+小组不匹配，KD-005) | HTTP 401 | 全部 API 契约 |
| BATCH_NOT_EXPIRED | 保留期未到期批次拒绝确认 | HTTP 4xx（建议 409，最终映射 defer_to_detail_design) | CT-011 |
| FORBIDDEN | 课程范围授权失败；记录 AccessDeniedLogged | HTTP 403 | CT-007、CT-008、CT-009、CT-011、CT-013 |
| INVALID_RESPONSE_SCHEMA | 模型应答 schema 非法（ACL 校验失败，视为失败） | CT-010 调用异常，计入评分失败策略（自动重试一次） | CT-010 |
| MODEL_ERROR | 模型服务不可用/调用失败 | 同 INVALID_RESPONSE_SCHEMA | CT-010 |
| MODEL_TIMEOUT | 模型调用超时（单次 ≤3 分钟） | 同 INVALID_RESPONSE_SCHEMA | CT-010 |
| NOT_FOUND | 资源不存在（未知 submission_uuid / batch_id / course_id 等） | HTTP 404 | CT-002、CT-008、CT-011、CT-013 |
| NO_AVAILABLE_SUBMISSION | 任一选定小组无可用提交，拒绝生成展示视图 | HTTP 4xx（建议 409/422,defer_to_detail_design) | CT-009 |
| NO_ORIGINAL_GRADE | scoring_failed 且无原始等级时拒绝设置最终等级（不得伪造等级） | HTTP 4xx（建议 409,defer_to_detail_design) | CT-008 |
| PAYLOAD_TOO_LARGE | 超过单次提交 500MB 上限（KD-004) | HTTP 413 | CT-001 |
| REJECTED_MEMBERSHIP | 归属校验拒绝（CT-003 verified=false) | CT-001 应答 `status=rejected` + `rejection_reason`（业务终态，非 HTTP 错误） | CT-001 |
| ROSTER_UNAVAILABLE | 名单服务超时/内部错误；提交保持待校验并重试，不向客户端暴露内部细节 | CT-003 服务间错误 | CT-003 |
| UNSUPPORTED_MEDIA_TYPE | 文件类型不在白名单（KD-004) | HTTP 415 | CT-001 |
| VALIDATION_FAILED | 请求字段校验失败（缺必填项、格式错误） | HTTP 400 | CT-001、CT-008、CT-013 |

补充约定：

- 事件契约（CT-004、CT-005、CT-006、CT-012、CT-014）无同步错误码：消费失败由 Outbox 投递器重试直至确认；业务失败以事件字段表达（CT-005 `outcome=scoring_failed` + `failure_reason`;CT-014 `failed_items[]`)，不作为传输错误。
- 上传中断不产生错误码：服务端标记 `upload_failed` 状态并记录原因，经 CT-002 可查。

## 组件接口卡（机器可读）

按 module_id 排序。字段级清单以各契约 `contract_fields` 块为唯一来源；本卡索引组件与契约的归属关系。MOD-01 不提供任何网络契约，其 inbound/outbound 字段在本卡直接给出。

```yaml
component_interfaces:
  - module_id: MOD-01
    role: "学生侧采集插件（DU-1，采集侧 ACL）"
    provides_contracts: []                    # 不提供服务端契约
    consumes_api: [CT-001, CT-002]
    consumes_events: []
    publishes_events: []
    outbound_produced_fields:                 # 作为 Consumer 向服务端产出
      CT-001: [submission_uuid, invite_code, student_name, group_name, assignment, "material_chunks[]"]
      CT-002: [submission_uuid]
    inbound_accepts_fields:                   # 自服务端应答接收
      CT-001: [submission_id, received_at, status, "missing_items[]", rejection_reason]
      CT-002: [submission_id, status, failure_reason, "missing_items[]"]
    local_inbound: "学生自然语言提交指令（assignment+student_name+group_name 必填，F1-1 缺任一项不创建提交）；Codex 对话导出与本地材料文件（采集侧 ACL）"
    local_outbound: "提交编号与接收确认展示、失败原因与缺失项展示（REQ-004）；本地待上传任务队列（KD-005）"
  - module_id: MOD-02
    provides_contracts: [CT-001, CT-002]
    provides_unnumbered: ["POST /api/v1/auth/token（令牌签发，KD-005；名单核对语义同 CT-003）"]
    consumes_api: [CT-003]
    consumes_events: [CT-005, CT-012]
    publishes_events: [CT-004, CT-006, CT-014]
    contract_fields_ref: [CT-001, CT-002, CT-004, CT-005, CT-006, CT-012, CT-014]
  - module_id: MOD-03
    provides_contracts: [CT-003, CT-013]
    consumes_api: []
    consumes_events: []
    publishes_events: []
    internal_read_by: [MOD-05]                # 课程结束时间只读引用（FLOW-011，无网络契约）
    contract_fields_ref: [CT-003, CT-013]
  - module_id: MOD-04
    provides_contracts: []
    consumes_api: []
    consumes_events: [CT-004]
    publishes_events: [CT-005]
    external_consumes: [CT-010]               # 经 ACL 调用外部模型服务
    contract_fields_ref: [CT-004, CT-005, CT-010]
  - module_id: MOD-05
    provides_contracts: [CT-007, CT-008, CT-009, CT-011]
    consumes_api: []
    consumes_events: [CT-005, CT-006, CT-014]
    self_consumes_events: [CT-012]            # 模块内清除读模型
    publishes_events: [CT-012]
    internal_reads: [MOD-03]                  # 课程结束时间只读引用（FLOW-011）
    contract_fields_ref: [CT-007, CT-008, CT-009, CT-011, CT-012, CT-014]
```

## 错误、超时、重试、幂等、版本策略汇总

| 策略 | 规则 |
|---|---|
| 超时 | CT-001 接收确认 30 秒（NFR-003);CT-010 单次 ≤3 分钟且任务总时长 ≤10 分钟；查询类 API ≤10 秒 |
| 重试 | 评分自动重试一次（REQ-012)；上传断点续传；事件投递无限重试直至确认；查询客户端指数退避 |
| 幂等 | 写操作客户端幂等键；事件消费按业务键去重；查询只读 |
| 版本 | API 路径版本 `/api/v1`；事件 schema `v` 字段向后兼容追加；破坏性变更升主版本并保留旧版本一个过渡期 |
