# 03 State and Data — L2 / CMP-TEACHER-UI

> C2 映射：浏览器瞬时状态 → child owner 与一致性边界。服务端状态仍归 L1 已确定的组件，本层不转移任何父/兄弟状态所有权。

## 1. 状态所有权清单（按稳定 `state_id` 排序）

| state_id | 状态内容 | owner（child_id） | 读方 | 写方 | 生命周期 | 一致性边界 | 隐私/保留约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-TUI-ACTION-STATUS | 查询、保存、生成、确认等请求的 loading/succeeded/failed、错误码和可重试上下文 | CMP-TUI-COURSE-SUBMISSION-BROWSER / CMP-TUI-NOTIFICATION-STATUS / CMP-TUI-PRESENTATION-WORKSPACE / CMP-TUI-RETENTION-CONFIRMATION / CMP-TUI-REVIEW-WORKBENCH（各自 action key） | 对应页面 child | 对应页面 child | 请求开始→终态或页面销毁 | 单浏览器会话内；不作为服务端真相 | 不持久化完整学生材料或 token；错误展示遵循 KD-003 最小化 | CT-007/008/009/011；KD-003 |
| ST-TUI-CURRENT-COURSE-SCOPE | 当前 course_id、group_id、student_id、submission_id 和路由上下文 | CMP-TUI-COURSE-SUBMISSION-BROWSER | 浏览/通知/复核/展示/删除页面 | 课程浏览 child | 会话内选择→切换课程或退出 | 仅用于请求上下文，授权仍由 GATE 判定 | 不缓存授权结论；退出/过期清除 | CT-007；REQ-DD001 |
| ST-TUI-DETAIL-SELECTION | 当前提交详情的加载结果引用与局部展开项 | CMP-TUI-COURSE-SUBMISSION-BROWSER | 查询、复核、通知 | 课程浏览 child | detail_open→detail_closed/刷新 | 读模型响应版本内一致；允许秒级落后 | 仅保存必要字段或引用，不保存材料本体 | CT-007；M05-IC-02 |
| ST-TUI-NOTIFICATION-QUEUE | 从 CT-007 返回的失败/重试/端内通知条目及其 displayed 状态 | CMP-TUI-NOTIFICATION-STATUS | 课程列表、提交详情、复核工作台 | 通知 child 根据父响应合并 | projected→displayed→dismissed（仅 UI 状态） | 事实字段只读；displayed 只影响当前浏览器 | 不得删除或改写服务端失败事实；可在页面销毁时清除 | A-005；LCD-001；CT-005 |
| ST-TUI-PRESENTATION-SELECTION | 选中的 group_ids、生成参数和本地选择校验状态 | CMP-TUI-PRESENTATION-WORKSPACE | 展示工作区 | 展示 child | selection_edit→submitted/cancelled | 同一请求内 group_ids 固定；不替代服务端资格校验 | 不保存材料内容；只保存标识符 | REQ-DD002；CT-009 |
| ST-TUI-PRESENTATION-STATUS | CT-009 loading、错误、presentation_id、blocks 和缺失标记的呈现状态 | CMP-TUI-PRESENTATION-WORKSPACE | 展示工作区 | 展示 child | idle→generating→ready/failed | 快照响应一次性呈现；重新生成由父幂等语义收敛 | 页面显示评分/学生数据时遵循父加密与会话边界 | D-AC-REQ-010-01；CT-009；LCD-004 |
| ST-TUI-QUERY-STATUS | CT-007 请求的分页/加载、响应版本、空态和错误呈现状态 | CMP-TUI-COURSE-SUBMISSION-BROWSER | 查询页面及通知 child | 课程浏览 child | idle→loading→ready/failed | 仅当前查询上下文有效；切换范围时旧响应不得覆盖新范围 | 不用空态掩盖 FORBIDDEN/NOT_FOUND；最小化保留响应 | D-AC-REQ-009-01；CT-007；AC-NFR-001-01 |
| ST-TUI-RETENTION-CONFIRMATION-DRAFT | batch_id、confirm、exclusions[] 和二次确认 UI 状态 | CMP-TUI-RETENTION-CONFIRMATION | 删除确认页 | 删除确认 child | viewing→editing→confirmed/cancelled | confirm=true 仅由明确用户动作产生；服务端再次校验过期 | 不缓存长期批次详情；不显示超出 CT-007 的范围 | CT-007 deletion_batches[]；CT-011；DF-3 |
| ST-TUI-RETENTION-STATUS | CT-011 返回的 batch_status、pending_deletion_scope、错误和重试提示 | CMP-TUI-RETENTION-CONFIRMATION | 删除确认页/课程浏览页 | 删除确认 child | idle→submitting→accepted/failed | 只显示服务端返回状态；不推测实际清除完成 | 审计记录由服务端永久持有，UI 不缓存审计全量 | CT-011；CT-012/CT-014 间接结果 |
| ST-TUI-REVIEW-DRAFT | annotation、final_grade、dirty_fields 和 request_id 生成前状态 | CMP-TUI-REVIEW-WORKBENCH | 复核工作台 | 复核 child | loaded→dirty→submitting→saved/failed/reset | 单提交详情内；保存失败保留草稿供用户修正/重试 | 不保存教师 token；原始等级只读显示，不进入可编辑字段 | REQ-DD001；CT-008；LCD-009 |
| ST-TUI-REVIEW-STATUS | CT-008 保存结果、NO_ORIGINAL_GRADE、FORBIDDEN、并发后写结果等反馈 | CMP-TUI-REVIEW-WORKBENCH | 复核工作台/通知 child | 复核 child | idle→submitting→saved/failed | 以服务端返回的 ReviewRecord 为准；不由旧页面响应覆盖新 request_id | 错误和操作者信息按父端返回最小化显示 | D-AC-REQ-009-01；CT-008；F3-2/F3-3 |

## 2. 服务端状态所有权未转移

| L1 状态 | owner 仍为 | UI 行为 |
|---|---|---|
| ST-READ-MODEL | CMP-READMODEL-PROJECTOR | 通过 CT-007 响应读取；不写、不重放、不扩展字段 |
| ST-REVIEW-RECORD | CMP-REVIEW-COMMAND | 通过 CT-008 提交；原始等级、最终等级和调整留痕由服务端决定 |
| ST-PRESENTATION-VIEW | CMP-PRESENTATION | 通过 CT-009 获取快照；UI 不拼接跨模块源数据 |
| ST-DELETION-BATCH | CMP-RETENTION-GOVERNANCE | 通过 CT-007/011 查看与确认；UI 不计算 retention_due_at |
| ST-TEACHER-ACCESS-GRANT | CMP-ACCESS-GATE | UI 不保存或推导授权关系 |
| ST-ACCESS-DENIED-LOG | CMP-ACCESS-GATE | UI 展示拒绝结果；不生成审计记录 |

## 3. 关键数据流

### 3.1 读流

`浏览器 → COURSE-SUBMISSION-BROWSER → CT-007 UI-GATE binding → CMP-ACCESS-GATE → CMP-REVIEW-QUERY → CT-007 response → PageViewModel`

返回的 `failure_reason`、`retry_record`、`missing_items`、`deletion_batches[]` 必须原样保留语义；UI 可以分组和排序展示，但不能删除缺失标记或把失败转成成功。

### 3.2 写流

- 复核：`REVIEW-WORKBENCH → request_id → GATE → CT-008 → REVIEW-COMMAND → review_record → workbench status`。
- 展示：`PRESENTATION-WORKSPACE → group_ids → GATE → CT-009 → PRESENTATION → presentation_id/blocks → workspace`。
- 删除确认：`RETENTION-CONFIRMATION → confirm/exclusions → GATE → CT-011 → RETENTION-GOVERNANCE → batch_status`。

### 3.3 复核记录字段与保留治理边界

`SCENARIO-003` 的“同时保留原始等级、最终等级、操作者和时间”属于 CT-008 复核记录的响应与投影可见性，不属于教师 UI 的数据保留生命周期。字段所有权和写入责任保持在服务端：

```yaml
review_result_boundary:
  request:
    entry_component: CMP-TUI-REVIEW-WORKBENCH
    contract: CT-008
    required_fields: [teacher_session, submission_id, request_id]
    optional_fields: [annotation, final_grade]
  write_owner: CMP-REVIEW-COMMAND
  write_records: [ReviewRecord, GradeAdjustmentRecord, idempotency_record]
  projection_contract: M05-IC-05
  response_fields: [review_record, "review_record.original_grade", "review_record.final_grade", "review_record.operator", "review_record.updated_at"]
  ui_owner: CMP-TUI-REVIEW-WORKBENCH
  ui_state: ST-TUI-REVIEW-DRAFT / ST-TUI-REVIEW-STATUS

retention_boundary:
  batch_owner: CMP-RETENTION-GOVERNANCE
  audit_owner: CMP-RETENTION-GOVERNANCE
  audit_retention: permanent_server_record
  ui_access: CT-007.deletion_batches[] and CT-011 response only
  forbidden_ui_actions: [calculate_retention_due_at, write_audit_record, execute_delete]
```

因此，浏览器只保存复核草稿、请求状态和服务端返回结果；不拥有 `ReviewRecord`、`DeletionBatch` 或删除审计，也不因页面销毁触发服务端删除。验证器若检查 SCENARIO-003，应沿 CT-007 → CT-008 → M05-IC-05 → response 的路径验证字段，而不是要求 `CMP-TUI-COURSE-SUBMISSION-BROWSER` 成为 retention owner。

### 3.4 通知流

`CT-005 → parent read-model projection → CT-007 response → NOTIFICATION-STATUS → list/detail visible state`。

UI 不直接订阅 CT-005，不把通知当作独立服务端状态，也不在失败响应缺失时自行创建“已评分”提示。

## 4. 不变量、一致性、幂等和并发

1. 任何 `FORBIDDEN`、`AUTH_INVALID`、`NOT_FOUND`、`VALIDATION_FAILED` 或父业务错误均进入对应失败状态，不降级为空列表或成功页。
2. `scoring_failed` 且没有 `original_grade` 时，最终等级编辑入口必须禁用或明确不可用；UI 不绕过 `NO_ORIGINAL_GRADE`。
3. UI 生成的 `request_id` 与展示/删除幂等上下文只在父契约允许的字段中传递；重复点击由本地 action lock 和服务端幂等共同收敛。
4. 读模型最终一致时，旧查询响应不得覆盖新课程/提交范围；响应绑定 `scope_key`，切换范围即使旧请求完成也只能丢弃其 UI 更新。
5. 用户未提交的 `REVIEW-DRAFT` 不得被通知刷新、自动刷新或旧 CT-007 响应覆盖。
6. 页面销毁只清浏览器瞬时状态，不触发服务端删除；真正删除必须由 CT-011 confirm=true 且服务端审计先行。
7. 学生材料只通过 `material_refs` 或父响应引用展示；UI 不下载、缓存或持久化材料文件本体。
