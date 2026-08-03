# 03 State and Data — 状态与数据（L2 / CMP-REVIEW-COMMAND）

## 1. 状态所有权注册表（按稳定 state_id 排序）

| state_id | state | owner_child_id | readers | writers | lifecycle | consistency_boundary | retention/privacy | parent_trace |
|---|---|---|---|---|---|---|---|---|
| ST-IDEMPOTENCY-REVIEW | CT-008 request_id 结果与 M05-IC-01 submission_id 创建键 | CMP-RC-REVIEW-IDEMPOTENCY-GUARD | GUARD；CT-008 重试入口 | GUARD，同业务写入同事务 | absent → recorded → replayed；随 ReviewRecord 删除策略处理关联键 | 与 ReviewRecord/AdjustmentRecord 同一本地事务 | 不保存完整教师会话；仅保留最小键、状态、结果引用和时间 | L1 child-handoff §4；KD-005；CT-008/M05-IC-01 |
| ST-REVIEW-RECORD | ReviewRecord、Annotation、OriginalGradeSnapshot、FinalGrade、GradeAdjustmentRecord、purge tombstone | CMP-RC-REVIEW-RECORD-WRITER | CT-008 响应；CMP-READMODEL-PROJECTOR 经 M05-IC-05；M05-IC-07 清除命令；读侧经 ST-READ-MODEL 间接读取 | WRITER；系统创建、教师更新和内容清除均走 WRITER | absent → created_on_scored → annotated/adjusted → purge_pending → purged_content | ReviewRecord、调整记录、幂等记录和局部事件提交同事务；M05-IC-07 清除与清除幂等记录同事务 | 原始等级、操作者、时间和审计留痕须保留至父级保留治理清除；DeletionAuditRecord 不进入清除范围；不得写入多余材料内容 | L1 `ST-REVIEW-RECORD`；REQ-D001；D-AC-REQ-009-01；LCD-003/005；M05-IC-07 |

`CMP-RC-REVIEW-INTEGRITY-POLICY` 不拥有持久状态；其规则输入来自已授权命令和 M05-IC-01 payload，输出验证结果。

## 2. 状态与数据流

### 2.1 评分完成后的创建

1. RMP 消费 CT-005 `outcome=scored`。
2. RMP 通过 M05-IC-01 发送 `submission_id`、`original_grade`、`dimension_rationales`、`scored_at`。
3. GUARD 以 `submission_id` 去重；重复请求返回已存在 ReviewRecord 引用。
4. POLICY 确认原始等级存在且为 scored 路径。
5. WRITER 在本地事务内固化原始等级复制值和来源 ID，写入 ST-IDEMPOTENCY-REVIEW，提交后产生 ReviewRecord 可用结果。

### 2.2 教师批注/调整

1. ACCESS-GATE 已完成会话和课程范围授权后，将 CT-008 请求路由到 GUARD。
2. GUARD 以 `request_id` 查重；命中则返回首次 `review_record`，不再执行策略或写入。
3. POLICY 验证 annotation/final_grade 至少一项；若 final_grade 写入则要求原始等级存在。
4. WRITER 同事务更新 Annotation 或 FinalGrade，追加 GradeAdjustmentRecord，保存可选理由、operator、updated_at、adjustment_id。
5. 事务提交后按 M05-IC-05 产生 AnnotationSaved/GradeAdjusted，RMP 据此更新读模型。

### 2.3 删除与重放

- 本节点不执行 DeletionBatch，不发布 CT-012；父级保留治理提交审计并发布 CT-012 后，通过 M05-IC-07 将目标 ReviewRecord 标记为 `purge_pending` 并清除内容，最终进入 `purged_content`。
- ST-IDEMPOTENCY-REVIEW 不得使已清除记录重新可读；重放由 RMP 的重放守卫过滤已清除 submission_id。
- 读模型重建不回写 ReviewRecord；本节点仍是 ReviewRecord 的唯一写方。M05-IC-07 的失败项回传父级按批次重试，重复命中返回 `already_purged`。

## 3. 不变量、一致性、幂等与并发

| 规则 | 本层实现 |
|---|---|
| 原始等级不可变 | `OriginalGradeSnapshot` 只在 M05-IC-01 首次成功创建时写入；后续 CT-008 只能写 FinalGrade 和调整记录 |
| 禁止伪造等级 | scoring_failed、original_grade 缺失或无有效 ReviewRecord 时，final_grade 写入返回 NO_ORIGINAL_GRADE；事务不产生部分写入 |
| 输入完整性 | annotation 与 final_grade 至少一项；两者都为空、字段格式不合法或目标不存在返回 VALIDATION_FAILED/NOT_FOUND，沿用父错误语义 |
| CT-008 幂等 | request_id 是客户端写幂等键；同键同目标返回首次记录；同键不同目标不复用结果，按父级校验处理 |
| M05-IC-01 幂等 | submission_id 是系统创建键；重复 scored 事件不覆盖原始等级、不追加重复记录 |
| 并发 | 同一 ReviewRecord 的并发更新遵循父级“后写为准”；每次成功更新仍追加唯一 adjustment_id，历史不被覆盖 |
| 事件提交 | M05-IC-05 事件只在业务写入提交后可见；投影失败不回滚已提交 ReviewRecord，由 RMP 按 adjustment_id 重放 |
| 内容清除 | M05-IC-07 只清除 ReviewRecord 内容，不删除 DeletionAuditRecord；按 batch_id + submission_id 幂等，失败项可重试 |

## 4. 存储意图与隐私

- 沿用父级 DU-2 共享数据库和本地事务能力；不选择新的数据库产品，不引入缓存或搜索引擎。
- 具体表名、索引、字段类型、事件记录载体属于 `implementation_detail`；至少需要以 `request_id`、`submission_id`、`adjustment_id` 支持唯一约束/查重。
- ReviewRecord 只存父契约要求的评分结果引用、批注和调整留痕；不复制材料文件或模型提示词。
- 观察日志最小化：使用 request_id、submission_id、adjustment_id、operator_id、outcome 和错误码，不记录完整 annotation、材料内容或教师会话令牌。

## 5. 所有权确认

- 未将 ReviewRecord 转移给 QUERY、RMP、UI、MOD-02、MOD-03 或 MOD-04。
- 未将教师读模型、DeletionBatch、Submission、MaterialFile 或 AssessmentResult 纳入本层所有权。
- 本层只在父节点内部细化状态与一致性边界；兄弟状态和父级清除流程保持原样。
