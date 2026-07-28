# 03 State and Data — 状态与数据（L2 / CMP-REVIEW-QUERY）

> C2 结论：本节点没有持久化状态所有权。所有业务数据均由父层支撑组件拥有，本层只读消费父端口结果。

## 1. 读取状态/数据登记

| state_or_view_id | 内容 | owner | 本层读方 | 本层写方 | 生命周期/一致性 | 隐私与删除约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-READ-MODEL | 课程/小组/学生/提交详情、材料引用、处理状态、原始等级、五维依据、建议、批注、最终等级、缺失标记、失败原因、重试结果、端内通知条目 | CMP-READMODEL-PROJECTOR | Scope/Submission/Outcome 子节点，经 M05-IC-02 | 无 | 派生、秒级最终一致；可由事件重放重建；删除后不得复活 | 只含 `material_refs[]`，不含材料文件本体；遵循 KD-003 加密/备份和 CT-012 清除语义 | ST-READ-MODEL；CT-005/006/012；DF-1/DF-2；A-005 |
| ST-DELETION-BATCH | 删除批次、到期时间、范围、状态、排除项、已清除提交集合、审计关联 | CMP-RETENTION-GOVERNANCE | CMP-RQ-RETENTION-VIEW-ADAPTER，经 M05-IC-06 | 无 | 由 RG 状态机维护；审计永久；查询不改变批次状态 | 查询不得暴露超出 CT-007 的批次字段；永久审计仍由 RG 所有 | ST-DELETION-BATCH；CT-011/012/014；F5-1~F5-3 |
| RT-RQ-CONTEXT | 单次已授权 CT-007 查询的瞬时上下文与装配中间结果 | CMP-RQ-QUERY-FACADE（瞬时） | 本层 child | 请求生命周期内更新 | 请求结束即释放；不落库、不缓存、不跨请求复用 | 只保留完成当前响应所需字段；不成为教师授权或业务状态 | CT-007；M05-BIND-CT-007-GATE-RQ |

## 2. 数据流

| 流 | 路径 | 读入 | 输出 | 副作用 |
|---|---|---|---|---|
| CT-007 查询入口 | ACCESS-GATE → QUERY-FACADE | `auth_context`, `course_id`, 可选 `group_id/student_id/submission_id` | 查询上下文 | 无 |
| 层级装配 | QUERY-FACADE → SCOPE-ASSEMBLER → M05-IC-02 | selection + read-model view | `courses/groups/students/submissions` 层级视图 | 无 |
| 提交详情装配 | QUERY-FACADE → SUBMISSION-DETAIL-ASSEMBLER → M05-IC-02 | submission selector + read-model view | `material_refs/status/grades/annotations/missing_marks` | 无 |
| 结果分支 | SUBMISSION-DETAIL-ASSEMBLER → OUTCOME-ADAPTER | `status/outcome/original_grade/dimension_rationales/teacher_suggestions/failure_reason/retry_record` | 成功或失败结果视图 | 无；不调用评分服务 |
| 删除批次装配 | QUERY-FACADE → RETENTION-VIEW-ADAPTER → M05-IC-06 | `batch_id/submission_id` 或课程范围 | `deletion_batches[]` | 无；不改变批次 |
| 完整响应 | 四类局部视图 → QUERY-FACADE → GATE | 各局部视图 | CT-007 response | `None` |

## 3. 数据不变量

1. **完整性**：CT-007 必需字段由本层完整装配；`deletion_batches[]` 即使为空也返回空数组，不省略字段。
2. **结果真实性**：`scoring_failed` 时不能产生 `original_grade` 或 `final_grade` 的推导值；失败原因和重试结果按父载荷原样呈现。
3. **只读**：查询请求不写 ST-READ-MODEL、ST-DELETION-BATCH 或任何 ReviewRecord/PresentationView 状态。
4. **所有权**：本层只引用 `material_refs[]`，不读取材料文件本体；不读取 MOD-03 除父层已委托的批次视图端口之外的数据。
5. **一致性**：读模型短暂落后属于父层允许的最终一致窗口；读取失败不是“空结果”，而是可重试失败。
6. **安全**：认证授权失败在 GATE 终止；本层只接受授权后的 `auth_context`，不复制或重定义授权规则。

## 4. 查询与并发策略

- 不引入缓存、搜索引擎或独立查询数据库；ST-READ-MODEL 已是父层规定的查询优化读模型。
- 逻辑上每次 CT-007 请求使用一个 `QueryScope`，避免在同一响应中混用多个不一致的选择范围。
- 本层不维护幂等记录；CT-007 是只读天然幂等，父层写幂等规则只适用于其他 API。
- 查询超时或端口读取错误沿父错误处理路径返回并允许调用方重试；不返回部分成功的缺字段响应。

## 5. 父/兄弟所有权确认

- ReviewRecord、批注和最终等级写入仍归 `CMP-REVIEW-COMMAND`。
- PresentationView 快照仍归 `CMP-PRESENTATION`。
- 读模型唯一写方仍为 `CMP-READMODEL-PROJECTOR`。
- DeletionBatch 唯一写方仍为 `CMP-RETENTION-GOVERNANCE`；材料与提交源数据仍归 MOD-02。

## 6. 验证场景的数据责任边界

| 验证断言 | 权威状态/所有者 | 查询侧允许的证据 | 查询侧禁止的行为 |
|---|---|---|---|
| 保存批注和调整后的等级（SCENARIO-002） | `ST-REVIEW-RECORD` / `CMP-REVIEW-COMMAND`，经 M05-IC-05 投影至 `ST-READ-MODEL` | 在投影完成后通过 CT-007 读取 `annotations`、`final_grade` | 直接写 ReviewRecord、调用 CT-008、把保存结果作为 Scope 输出 |
| 原始等级、最终等级、操作者和时间留痕（SCENARIO-003） | ReviewRecord / `CMP-REVIEW-COMMAND`；读模型由 RMP 派生 | 读取已存在的教师读模型事实；可验证查询返回字段完整性 | 在查询过程中创建、更新或补造审计/留痕数据 |
| 删除批次可见性 | `ST-DELETION-BATCH` / `CMP-RETENTION-GOVERNANCE` | 通过 M05-IC-06 读取 `deletion_batches[]`，无批次返回空数组 | 计算到期、确认删除、修改批次或写删除审计 |

因此 SCENARIO-002/003 的“保存/留痕”失败不能作为本节点缺少写状态的证据；它们必须在 ReviewCommand 写侧和 RMP 投影闭环中验证，Query 包只验证投影后的读取结果。
