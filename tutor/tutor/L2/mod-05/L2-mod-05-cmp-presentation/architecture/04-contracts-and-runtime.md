# 04 Contracts and Runtime — L2 / CMP-PRESENTATION

## 1. 继承契约清单

| parent contract | owner/provider/consumer | immutable semantics | current realization |
|---|---|---|---|
| CT-009 | owner/provider `MOD-05`；consumer 教师浏览器 | `POST /api/v1/teacher/presentations`；required `group_ids[]`；produced `presentation_id`、`blocks[]`（含 `missing_marks`）；错误 `AUTH_INVALID/FORBIDDEN/NOT_FOUND/VALIDATION_FAILED/NO_AVAILABLE_SUBMISSION`；幂等键=教师+小组集合+时间窗（父原文：教师+小组集合+时间窗）；版本 `/api/v1` | `CMP-ACCESS-GATE` 认证授权后路由至 `CMP-PRES-GENERATION-COORDINATOR`；后者编排本层 child 并经 `CMP-PRES-OUTPUT-ADAPTER` 返回父响应 |
| M05-IC-02 | owner/provider `CMP-READMODEL-PROJECTOR`；consumer `CMP-PRESENTATION` | read-only；输入 `course_id/group_id/student_id/submission_id`；输出 courses/groups/students/submissions/material_refs/status/original_grade/dimension_rationales/teacher_suggestions/annotations/final_grade/missing_marks；读模型短暂落后按最终一致处理 | `CMP-PRES-GENERATION-COORDINATOR` 作为当前节点唯一入口消费者；下发数据给本层其他 child 的方式由 PRES-IC-01/02/03 封装 |

本包不直接消费 CT-005/CT-006/CT-012；这些事件和 ST-READ-MODEL 的写入/自消费仍归父层 `CMP-READMODEL-PROJECTOR`。本包也不改变 M05-BIND-CT-009-GATE-PV 的字段和 next_hop。

### 1.1 父契约与内部契约机器可读投影

```yaml
inherited_contracts:
  - contract_id: CT-009
    provider: MOD-05
    implementation_node: CMP-PRES-GENERATION-COORDINATOR
    external_required_fields: [teacher_session, "group_ids[]"]
    implementation_inbound_required_fields: [auth_context, "group_ids[]"]
    derived_required_fields:
      teacher_id:
        source: auth_context.teacher_id
        scope: internal_context
      idempotency_key:
        source: [teacher_id, normalized_group_ids, time_window]
        alias_of: generation_key
        scope: internal_context
    outbound_produced_fields: [presentation_id, "blocks[]"]
    errors: [AUTH_INVALID, FORBIDDEN, NOT_FOUND, VALIDATION_FAILED, NO_AVAILABLE_SUBMISSION]
    side_effects: "PresentationView snapshot + idempotency record in one local transaction"
    idempotency: "teacher_id + normalized_group_ids + time_window; same key returns latest snapshot"
    version: /api/v1
  - contract_id: M05-IC-02
    provider: CMP-READMODEL-PROJECTOR
    consumer: CMP-PRES-GENERATION-COORDINATOR
    inbound_required_fields: [course_id, group_id, student_id, submission_id]
    outbound_produced_fields: [courses, groups, students, submissions, material_refs, status, original_grade, dimension_rationales, teacher_suggestions, annotations, final_grade, missing_marks]
    errors: [read_model_timeout, VALIDATION_FAILED]
    idempotency: read_only
    version: MOD-05-internal

internal_contracts:
  - contract_id: PRES-IC-01
    provider: CMP-PRES-GENERATION-COORDINATOR
    consumer: CMP-PRES-MISSING-MARKS
    inbound_required_fields: [request_id, "group_ids[]", "group_views[]", submission_status, "missing_items[]"]
    outbound_produced_fields: ["group_views[]", "eligibility_by_group[]", "missing_marks[]"]
    field_semantics: "group_views[] is preserved as read-model context for the next per-group handoff"
    errors: [VALIDATION_FAILED]
    idempotency: request_id + read_model_version
    version: CMP-PRESENTATION-internal
  - contract_id: PRES-IC-02
    provider: CMP-PRES-MISSING-MARKS
    consumer: CMP-PRES-BLOCK-ASSEMBLER
    inbound_required_fields: [group_view, eligibility, missing_marks]
    outbound_produced_fields: [group_section_input]
    field_mapping:
      group_view: group_views[group_id]
      eligibility: eligibility_by_group[group_id]
      missing_marks: missing_marks[group_id]
    errors: [VALIDATION_FAILED]
    idempotency: group_id + read_model_version
    version: CMP-PRESENTATION-internal
```

`teacher_id` 与 `idempotency_key` 仅是从父授权上下文和父幂等语义派生的内部字段，不是 CT-009 新增的公共请求字段；`generation_key` 继续由 `CMP-PRES-SNAPSHOT-STORE` 统一收敛。

## 2. 子节点内部契约（按稳定 ID 排序）

| internal_id | owner → consumer | trigger | schema | side effects | errors/timeouts/retries | idempotency | compatibility |
|---|---|---|---|---|---|---|---|
| PRES-IC-01 | CMP-PRES-GENERATION-COORDINATOR → CMP-PRES-MISSING-MARKS | M05-IC-02 返回所选小组读模型视图后 | 输入 `request_id, group_ids[], group_views[], submission_status, missing_items[]`；输出 `group_views[], eligibility_by_group[], missing_marks[]` | 无持久写；生成资格评估与显式缺失值对象，并保留按 `group_id` 关联的组视图上下文 | 读模型字段缺失→VALIDATION_FAILED；处理为纯函数，无远程重试；上游 M05-IC-02 超时按父规则整体失败/重试 | 同一 request_id + 读模型版本重复计算相同结果 | 不改变 CT-009 字段；新增缺失码只需兼容 blocks 内部值对象，不改变父错误码 |
| PRES-IC-02 | CMP-PRES-MISSING-MARKS → CMP-PRES-BLOCK-ASSEMBLER | 资格通过且每组缺失标记已计算 | 输入 `group_view, eligibility, missing_marks`，分别来自 `group_views[group_id]`、`eligibility_by_group[group_id]`、`missing_marks[group_id]`；输出 `group_section_input`，包括项目结果引用、过程摘要来源、评分、批注、missing_marks | 无持久写；不修改源读模型 | 缺少必需 GroupSection 输入→VALIDATION_FAILED；无远程调用，不重试 | 同一 group_id + read_model_version 结果稳定 | GroupSection 字段只扩展本层内部输入，不要求 CT-009 新字段 |
| PRES-IC-03 | CMP-PRES-BLOCK-ASSEMBLER → CMP-PRES-SNAPSHOT-STORE | 所有选定组的 GroupSection 装配完成 | 输入 `generation_key, selected_group_ids[], blocks[], source_read_model_version, generated_at`；输出 `presentation_id, snapshot_status, blocks[]` | 同事务写 PresentationView 与 ST-IDEMPOTENCY-PRESENTATION；旧版本可标记 superseded | 冲突/暂时写失败→事务回滚并按父调用重试；不可返回半写入 blocks | generation_key；重复调用返回同一幂等语义的最新快照 | 输出字段继续映射父 CT-009；`presentation_id` 生成策略不可被 UI 依赖其格式 |
| PRES-IC-04 | CMP-PRES-SNAPSHOT-STORE → CMP-PRES-OUTPUT-ADAPTER | 快照写入或幂等命中后 | 输入 `presentation_id, snapshot_version, blocks[], generated_at`；输出父 CT-009 `presentation_id + blocks[]` | 无持久写；只做稳定响应映射 | 映射失败→VALIDATION_FAILED；不重试已成功的父写入，调用方可按幂等键重新获取 | snapshot_version + presentation_id；相同快照输出稳定 | 具体 HTML/导出格式不在此契约；下层只能在不破坏 CT-009 的前提下演进 |
| PRES-IC-05 | CMP-READMODEL-PROJECTOR → CMP-PRES-SNAPSHOT-STORE | CT-012 自消费确认完成，需要擦除展示快照内容 | 输入 `batch_id, submission_ids[], cleared_at`；输出 `purged_presentation_ids[], already_purged[]` | 对关联快照做内容级擦除；不删除审计、不执行 MOD-02 清除 | 本地事务失败→按父事件/本地可追溯机制重放；不能用旧快照恢复 | batch_id + presentation_id；重复清除无副作用 | 仅为 MOD-05 内部契约；不新增跨模块事件或改变 CT-012 payload |

## 3. 合法运行流

### 3.1 成功流：教师生成展示视图

```yaml
flow_id: PRES-FLOW-001
from: CMP-ACCESS-GATE
to: CMP-PRES-GENERATION-COORDINATOR
contract: CT-009
entry_condition: "认证与课程范围授权通过，group_ids[] 已校验"
steps:
  - {to: CMP-READMODEL-PROJECTOR, contract: M05-IC-02, condition: "读取所选小组的教师读模型视图"}
  - {to: CMP-PRES-MISSING-MARKS, contract: PRES-IC-01, condition: "计算资格与显式缺失标记"}
  - {to: CMP-PRES-BLOCK-ASSEMBLER, contract: PRES-IC-02, condition: "所有选定小组均有可用提交"}
  - {to: CMP-PRES-SNAPSHOT-STORE, contract: PRES-IC-03, condition: "GroupSection[] 装配完成"}
  - {to: CMP-PRES-OUTPUT-ADAPTER, contract: PRES-IC-04, condition: "快照成功写入或幂等命中"}
return_to_caller: ["presentation_id + blocks[]"]
terminal_states: [completed]
```

### 3.2 失败/恢复流：无可用提交或读模型暂时不可用

```yaml
flow_id: PRES-FLOW-002
from: CMP-PRES-GENERATION-COORDINATOR
to: CMP-PRES-MISSING-MARKS
contract: PRES-IC-01
entry_condition: "M05-IC-02 已返回所选小组视图"
branches:
  - condition: "任一小组无可用提交"
    return_to_caller: [NO_AVAILABLE_SUBMISSION]
    writes: []
    terminal_state: rejected
  - condition: "材料缺失但存在可用提交"
    next_hop: CMP-PRES-BLOCK-ASSEMBLER
    return_to_caller: ["blocks[] with missing_marks"]
    terminal_state: completed
  - condition: "M05-IC-02 超时/返回字段不足"
    return_to_caller: [VALIDATION_FAILED]
    retry: "按父读端口策略整体重试，不以缺字段降级成功"
    terminal_state: retryable_failed
```

### 3.3 生命周期流：幂等再生成与删除擦除

```yaml
flow_id: PRES-FLOW-003
from: CMP-PRES-SNAPSHOT-STORE
to: CMP-PRES-SNAPSHOT-STORE
contract: [CT-009, PRES-IC-05]
entry_condition: "同一生成键再次请求，或 CT-012 自消费传入已清除 submission_ids"
steps:
  - {condition: "同键存在可用快照", action: "返回最新快照，不重复写业务副作用"}
  - {condition: "同键需重新生成", action: "写新快照并将旧快照标记 superseded"}
  - {condition: "删除批次命中展示快照", action: "按 batch_id + presentation_id 幂等擦除内容"}
return_to_caller: ["latest presentation_id + blocks[]", "purged_presentation_ids"]
terminal_states: [returned, superseded, purged]
```

## 4. 错误、重试、幂等、可观测与兼容

- 错误：`AUTH_INVALID`/`FORBIDDEN` 由 ACCESS-GATE 产生；`NO_AVAILABLE_SUBMISSION` 由本层资格策略产生；`VALIDATION_FAILED`、`NOT_FOUND` 与父 CT-009 语义保持一致。
- 超时：M05-IC-02 读超时按父策略整体失败/重试；本层纯计算不引入远程超时；快照写入失败必须回滚，不能返回半个快照。
- 重试：相同 CT-009 幂等键可安全重试；PRES-IC-05 重复擦除无副作用；不为一次请求引入多层指数重试放大。
- 幂等：父 generation key 由 Snapshot Store 统一收敛；child-only ports 的重复调用不能绕过快照状态机。
- 可观测：在 KD-003 基础运维范围内记录资格拒绝计数、生成耗时、M05-IC-02 读取耗时、快照写入/幂等命中率、缺失标记分布和 purge 重试计数；不记录材料内容。
- 兼容：CT-009 `/api/v1`、`presentation_id`、`blocks[]`、`missing_marks`、错误码和幂等语义不变；具体网页/导出渲染必须在下一层保持响应兼容。

## 5. 父契约不变性确认

本包没有改变 CT-009 的 owner、路径、字段、响应、错误、幂等、依赖、失败语义或版本；没有新增对外端点。M05-IC-02 的 owner 为 `CMP-READMODEL-PROJECTOR` 且其读模型只读语义不变。PRES-IC-01~05 是当前节点内部契约，未成为父模块公共契约。
