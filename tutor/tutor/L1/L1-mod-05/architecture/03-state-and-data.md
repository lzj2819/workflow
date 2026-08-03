# 03 State and Data — 状态与数据（L1 / MOD-05 teacher-web）

> C2 映射：局部聚合/状态 → 子节点所有权与一致性边界。父/兄弟数据所有权不发生转移（§5 确认）。
> 清单按稳定状态 ID 排序。

## 1. 状态所有权清单

| state_id | 状态内容 | owner（child_id） | 读方 | 写方 | 生命周期 | 一致性边界 | 保留 / 隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-ACCESS-DENIED-LOG | 访问拒绝留痕（教师、目标课程、时间、请求入口） | CMP-ACCESS-GATE | 安全审计（运维侧只读，KD-003 监控面） | CMP-ACCESS-GATE（每次 FORBIDDEN 写入） | 追加式，不修改不删除 | 单次写入即一致（本地事务） | 安全审计数据，不随提交删除批次清除；含教师标识，按 KD-003 加密存储 | F3-1（AccessDeniedLogged）；FR-009 不变量；06-deployment 合规节 |
| ST-DELETION-BATCH | DeletionBatch 聚合：批次（范围、retention_due_at、状态机）、确认记录、教师排除标记、执行结果 failed_items[]、DeletionAuditRecord（范围/操作者/时间） | CMP-RETENTION-GOVERNANCE | CMP-REVIEW-QUERY（M05-IC-06，CT-007 `deletion_batches[]`）；CMP-READMODEL-PROJECTOR（M05-IC-06，重放守卫） | CMP-RETENTION-GOVERNANCE（唯一写方） | marking → pending_confirmation → confirmed → executing → completed / partial_failed（重跑回路）；审计记录永久 | 单批次确认+执行记录+审计记录同一本地事务（父 03）；审计先于清除写入 | 审计记录永久留存、不在删除范围内（FR-016）；批次数据含课程范围标识，按 KD-003 加密与每日备份 | DeletionBatch（aggregates.md）；F5-1~F5-3；DF-3；CT-011/012/014；AC-NFR-004-01 |
| ST-IDEMPOTENCY-DELETION | CT-011 确认幂等记录（batch_id 维度） | CMP-RETENTION-GOVERNANCE | CMP-RETENTION-GOVERNANCE | CMP-RETENTION-GOVERNANCE | 随批次生命周期保留 | 与批次状态同事务 | 无个人数据 | CT-011 Idempotency（重复确认返回同一状态，不重复执行） |
| ST-IDEMPOTENCY-PRESENTATION | CT-009 幂等键（教师+小组集合+时间窗 → presentation_id） | CMP-PRESENTATION | CMP-PRESENTATION | CMP-PRESENTATION | 随最新快照保留；键过期后可清理（实现细节） | 与快照写入同事务 | 无个人数据 | CT-009 Idempotency（相同请求参数重复生成返回最新快照） |
| ST-IDEMPOTENCY-REVIEW | CT-008 写幂等键（request_id → review_record） | CMP-REVIEW-COMMAND | CMP-REVIEW-COMMAND | CMP-REVIEW-COMMAND | 随复核记录保留 | 与复核写入同事务 | 无个人数据 | CT-008 inbound `request_id`（KD-005 写幂等） |
| ST-PRESENTATION-VIEW | PresentationView 聚合：GroupSection 区块（项目结果引用、过程摘要、评分、批注、missing_marks）、生成参数、生成时间 | CMP-PRESENTATION | CMP-PRESENTATION（幂等再生成）；CMP-TEACHER-UI（经 CT-009 应答渲染） | CMP-PRESENTATION（一次性写入；同参数再生成产生新版本快照） | snapshot_created → superseded（被更新快照替代）→ purged（随清除批次擦除，LCD-005） | 一次生成的视图内容快照同一事务写入（父 03） | 含学生作业内容与评分，随所属提交进入删除范围；教师端不可读保证同 ST-READ-MODEL | PresentationView（aggregates.md）；F4-1；CT-009；AC-REQ-010-01 |
| ST-PROJECTION-CHECKPOINT | 事件消费位点与去重记录（按契约：CT-005 按 submission_id+终态；CT-006 按 submission_id；CT-012 按 batch_id+业务键） | CMP-READMODEL-PROJECTOR | CMP-READMODEL-PROJECTOR | CMP-READMODEL-PROJECTOR | 随消费推进；重放时按重建计划重置 | 位点更新与读模型写入同一事务（消费原子性） | 无个人数据 | CT-005/006/012 幂等条款；父 04「消费方必须幂等」 |
| ST-READ-MODEL | 教师读模型：课程/小组/学生列表、提交详情聚合视图（材料引用、处理状态、原始等级、五维依据、教师建议、批注、最终等级、缺失标记、失败原因与重试结果、端内通知条目） | CMP-READMODEL-PROJECTOR（唯一写方） | CMP-REVIEW-QUERY（M05-IC-02）；CMP-PRESENTATION（M05-IC-02） | CMP-READMODEL-PROJECTOR | projected → updated（本地复核事件）→ purged（CT-012 自消费）；可事件重放全量重建（受 P-重放守卫约束） | 派生数据，秒级最终一致（父 03）；重建期间允许短暂落后，不允许复活已清除数据 | 仅存 material_refs 引用，不存材料文件本体（MOD-02 所有权）；含学生数据，KD-003 加密+每日备份；删除批次确认后清除 | 父 03 读模型说明；CT-005/CT-006/CT-012；DF-1 步骤 11、DF-2 步骤 6；A-005 |
| ST-REVIEW-RECORD | ReviewRecord 聚合：Annotation、FinalGrade、GradeAdjustmentRecord（原始等级复制值+来源 submission_id、最终等级、操作者、时间） | CMP-REVIEW-COMMAND（唯一写方） | CMP-REVIEW-COMMAND（CT-008 应答）；CMP-READMODEL-PROJECTOR（M05-IC-05 投影） | CMP-REVIEW-COMMAND | created_on_scored → annotated/adjusted（可多次，后写为准+全量留痕）→ purged（随清除批次内容擦除，LCD-005） | 单提交复核记录同一事务（批注+最终等级+调整记录） | 属「评分记录」，课程结束 1 年后随确认批次删除（NFR-004）；调整记录全量保留至 purged | ReviewRecord（aggregates.md）；FR-009；F3-2/F3-3；CT-008 |
| ST-TEACHER-ACCESS-GRANT | 教师账号-课程授权关系（管理员发放，A-001） | CMP-ACCESS-GATE | CMP-ACCESS-GATE（每次请求鉴权） | 管理流程写入（A-001；本层不实现自助管理界面） | 发放 → 生效 → 撤销；低频变更 | 单记录写入即一致 | 含教师标识；KD-003 加密存储；不在提交删除范围内 | A-001；FR-009 课程范围授权；CT-007~CT-011 FORBIDDEN 语义 |

## 2. 存储意图（受父技术决策约束）

- 全部状态存于 DU-2 共享关系型数据库（KD-002 同组共部署）；数据库产品选型保持父层 defer_to_detail_design，本层仅要求事务与备份能力，不做产品决定。
- 不引入缓存、搜索引擎、独立消息中间件（父 03/05 不采用方案）；读模型即查询优化层。
- 材料文件不进入 MOD-05 存储（MOD-02 所有权）；读模型仅保存 `material_refs[]` 引用（CT-006 载荷）。
- 静态加密（KD-003）覆盖全部含学生/教师数据的表；每日备份保留 30 天；审计类数据（ST-DELETION-BATCH 审计记录、ST-ACCESS-DENIED-LOG）随备份可恢复且不被业务删除流程触碰。

## 3. 关键数据流

### 3.1 写入流

| 流 | 路径 | 事务与幂等 |
|---|---|---|
| 保存批注 / 调整最终等级 | UI → GATE（认证+授权+幂等受理）→ CMP-REVIEW-COMMAND → ST-REVIEW-RECORD + ST-IDEMPOTENCY-REVIEW（同事务）→ M05-IC-05 模块内事件 | request_id 重复 → 返回首次复核记录；NO_ORIGINAL_GRADE 校验在写前 |
| 生成展示视图 | UI → GATE → CMP-PRESENTATION →（M05-IC-02 读装配）→ ST-PRESENTATION-VIEW + ST-IDEMPOTENCY-PRESENTATION（一次性写入） | 同键再生成 → 返回最新快照；资格校验失败不落库 |
| 删除确认 | UI → GATE → CMP-RETENTION-GOVERNANCE → ST-DELETION-BATCH（确认+审计，审计先行）→ M05-IC-04 发布 CT-012（Outbox 同事务） | 重复确认返回同一状态；BATCH_NOT_EXPIRED 拒绝 |
| 复核记录创建（系统） | CT-005 消费 → CMP-READMODEL-PROJECTOR → M05-IC-01 → CMP-REVIEW-COMMAND → ST-REVIEW-RECORD（原始等级复制值固化） | submission_id 幂等，重复事件不重复创建 |

### 3.2 读取流

| 流 | 路径 |
|---|---|
| CT-007 课程数据查询 | UI → GATE → CMP-REVIEW-QUERY → M05-IC-02（ST-READ-MODEL）+ M05-IC-06（ST-DELETION-BATCH 批次视图）→ 装配出参 |
| CT-009 视图打开/再获取 | UI → GATE → CMP-PRESENTATION → 同参数幂等再生成 → 返回最新快照（不新增父 API 端点，见 01 Q-02 同原则） |

### 3.3 派生流（事件驱动，秒级最终一致）

| 流 | 路径 | 去重键 |
|---|---|---|
| CT-006 投影 | MOD-02 → Outbox → CMP-READMODEL-PROJECTOR → ST-READ-MODEL（提交列表/状态/缺失标记） | submission_id |
| CT-005 投影 | MOD-04 → Outbox → CMP-READMODEL-PROJECTOR → ST-READ-MODEL（等级/依据/建议/失败原因/重试结果/端内通知条目）+ M05-IC-01 | submission_id + 终态 |
| 本地复核投影 | CMP-REVIEW-COMMAND → M05-IC-05（AnnotationSaved/GradeAdjusted）→ CMP-READMODEL-PROJECTOR → ST-READ-MODEL | 调整记录 ID |
| CT-012 自消费清除 | CMP-RETENTION-GOVERNANCE 发布 → Outbox → CMP-READMODEL-PROJECTOR → ST-READ-MODEL 清除目标 submission | batch_id + submission_id |
| CT-014 回流 | MOD-02 → Outbox → CMP-RETENTION-GOVERNANCE → ST-DELETION-BATCH（执行状态/failed_items[]） | batch_id + purged_at |

### 3.4 外部化流

- 出向唯一跨模块事件：CT-012（M05-IC-04，Outbox 发布）。
- 入向跨界读取唯一通道：M05-IC-03 / FLOW-011（MOD-03 课程结束时间只读引用，同 DU-2 进程内）。
- 除以上两条，MOD-05 不与父/兄弟发生任何其他数据交换（FLOW-007~012 完整覆盖）。

## 4. 不变量、一致性、幂等与并发规则

1. **ReviewRecord**：原始等级复制值一经写入不可变；每次调整产生完整 GradeAdjustmentRecord（原始/最终/操作者/时间四元组缺一不可）；scoring_failed 且无原始等级 → 拒绝最终等级（NO_ORIGINAL_GRADE，P-禁伪造等级）。
2. **PresentationView**：快照一次性写入；任一选定小组无可用提交 → 整体拒绝（NO_AVAILABLE_SUBMISSION）；缺失材料显式 missing_marks，不得以任何形式隐藏缺口。
3. **DeletionBatch**：未确认不执行；审计记录先于任何清除动作写入；审计记录不在删除范围内；failed_items[] 保留在原批次供重跑，重跑结果经 CT-014 再次回流。
4. **读模型**：派生数据可秒级落后；重放重建必须经 P-重放守卫（过滤 ST-DELETION-BATCH 已完成批次中的 submission_id），保证「删除后教师端不可读」在重建后仍成立（AC-NFR-004-01 pass_rule）。
5. **幂等**：写 API 客户端幂等键（KD-005）；事件消费按 §3.3 业务键去重；批次确认/快照生成按各自幂等键；所有幂等记录与业务写入同事务。
6. **并发**：同一提交复核并发修改以后写为准，且全部写均产生调整记录（CT-008 父语义）；同一批次并发确认由 ST-IDEMPOTENCY-DELETION 收敛；事件乱序由「终态不改」规则（CT-005）与位点事务化推进吸收。

## 5. 父/兄弟所有权未转移确认

- Submission、Course、AssessmentResult 聚合仍分别归 MOD-02、MOD-03、MOD-04；本层仅以事件载荷复制值与 `material_refs[]` 引用方式持有派生数据，源数据可经事件重放重新派生。
- 实际材料清除由 MOD-02 执行（CT-012/CT-014）；MOD-05 不触碰材料文件。
- MOD-03 数据仅经 FLOW-011 读取课程结束时间一个字段用途，未扩展读取范围。
- 本层新增状态（ST-TEACHER-ACCESS-GRANT、ST-ACCESS-DENIED-LOG、ST-READ-MODEL、ST-PROJECTION-CHECKPOINT、三类幂等记录）均为 MOD-05 内部数据，不属于任何父层聚合，不向外提供读写。
