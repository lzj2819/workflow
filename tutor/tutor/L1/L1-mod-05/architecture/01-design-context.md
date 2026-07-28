# 01 Design Context — 设计上下文（L1 / MOD-05 teacher-web）

## 1. 已解析输入与预检证据

| 必需输入 | 解析值 | 状态 |
|---|---|---|
| `parent_architecture` | `architecture/L0/output` | 已读；顶层 DDD→系统包（根无 manifest、有 `output/01-system-overview.md`，适配器规则 2） |
| `target_node_id` | `MOD-05`（teacher-web） | 唯一匹配（见 `architecture-manifest.yaml` node_match_evidence 四条证据） |
| `current_prd` | `prd/L1/L1-mod-05/prd.md`（schema 2.0，status complete） | 已读 |
| `output_dir` | `architecture/L1/L1-mod-05` | 目录存在且为空，`new` 模式安全，不覆盖任何已有包 |
| `mode` | `new` | 默认 |
| `parent_prd`（可选） | `prd/L0/vibe-coding-course-prd.md` | 实际读取：补 REQ-009/010、NFR-001/004、AC 原文（父包已含主要追溯，读取为佐证） |

当前层 PRD 的「架构输入契约」继承 `../../L0-root/architecture/01-system-overview.md`、`03-data-and-consistency.md` 与 `04-interface-contracts.md`：本层不新造系统边界、外部依赖或跨模块约束，全部采用父层已有决策（见 §2）。

## 2. 父边界快照（Parent Boundary Snapshot）

> 仅提取 MOD-05 及其直接边界；兄弟节点（MOD-01/02/03/04）只作为协作约束引用，不重设计其内部。

### 2.1 身份、职责与排除项（inherited-fixed）

- **身份**：MOD-05 teacher-web，来源 BC-REVIEW + BC-RETENTION（父层将两 BC 合并为一个模块：同为教师驱动、读多写少、生命周期一致；数据清除仍由数据持有方 MOD-02 执行）。
- **职责**（逐字引自父包）：教师课程/小组/学生/提交查询（课程范围授权）；批注与最终等级调整（保留原始等级与调整记录）；展示视图生成；评分失败可见；删除确认与审计查看。
- **排除项**：见 `architecture-manifest.yaml` package.exclusions（不持有 Submission/Course/AssessmentResult 聚合、不做归属校验、不接触模型服务、不伪造等级、不创建独立部署单元）。

### 2.2 需求追溯（inherited-fixed）

| 父层追溯 | 内容 | 对 MOD-05 的绑定 |
|---|---|---|
| REQ-009（FR-009） | 教师查看课程/小组/学生/提交详情、材料、状态、依据、建议；批注与调整最终等级 | 本层 REQ-D001 的父需求 |
| REQ-010（FR-010） | 教师选择小组生成展示视图（项目结果、过程摘要、评分、批注） | 本层 REQ-D002 的父需求 |
| NFR-001（FR-013） | 约 100 名学生、20–50 个小组规模的提交与教师查询 | 教师查询侧读模型规模约束；查询类 API ≤10 秒（父 04 策略汇总） |
| NFR-004（FR-016） | 材料与评分记录保存至课程结束后 1 年，教师确认删除并可审计 | 保留治理、删除批次、审计记录全部由 MOD-05 承担（AC-NFR-004-01 = module_local，owning MOD-05） |
| SM-003 | 教师评分覆盖率 ≥95% | MOD-05 为 **contributing**（教师端可见性验证面），不单独承接指标（父 01 `modules_without_sm_allocation` 登记） |
| REQ-011（支撑性） | 材料缺失在教师端标记 | 缺失标记数据经 CT-006/CT-005 流入读模型；MOD-05 负责**展示**缺失标记（D-AC-REQ-010-01 boundaries），所有权仍在 MOD-02 |

### 2.3 契约边界（inherited-fixed；标识、字段、所有者、副作用、失败语义、版本均不可变）

| 契约 | 角色 | 要点 |
|---|---|---|
| CT-007 教师课程数据查询 | **Provider**（sync query，read-only） | 出参含课程/小组/学生/提交/材料引用/状态/原始等级/五维依据/建议/批注/最终等级/`deletion_batches[]`；条件出参 `failure_reason`、`retry_record`；错误 AUTH_INVALID / FORBIDDEN（记录 AccessDeniedLogged） |
| CT-008 批注与最终等级调整 | **Provider**（sync 写） | `request_id` 幂等键；annotation 与 final_grade 至少其一；NO_ORIGINAL_GRADE（不得伪造等级）；并发后写为准并完整留痕；AnnotationSaved/GradeAdjusted 为**模块内事件** |
| CT-009 展示视图生成 | **Provider**（sync 写） | 请求 `group_ids[]`；应答 `presentation_id` + `blocks[]`（含 missing_marks）；NO_AVAILABLE_SUBMISSION；幂等键=教师+小组集合+时间窗，重复生成返回最新快照；PresentationViewGenerated 为模块内快照事件 |
| CT-011 删除确认 | **Provider**（同步确认+异步执行） | 仅 `confirm=true` 触发；`exclusions[]` 教师排除标记；BATCH_NOT_EXPIRED；确认幂等；批次执行完成后经 Outbox publishes CT-012 |
| CT-005 SubmissionScored/ScoringFailed | **Consumer** | 副作用：创建复核记录、派生教师读模型、触发教师端内通知；按 `submission_id`+终态幂等去重 |
| CT-006 SubmissionReceived（读模型派生） | **Consumer** | 副作用：派生教师侧提交列表与处理状态读模型；按 `submission_id` 去重；可全量重建 |
| CT-012 RecordsDeleted | **Provider + 自消费** | 发布后 MOD-02 清除材料与提交记录；MOD-05 自消费部分为模块内清除读模型；审计记录不受影响 |
| CT-014 PurgeCompleted | **Consumer** | 更新批次执行状态；`failed_items[]` 保留在批次中供重跑；按 `batch_id`+`purged_at` 去重 |
| FLOW-011 课程结束时间 | **internal_read**（无网络契约） | 同 DU-2 进程内只读引用 MOD-03；`retention_due_at = 课程结束时间 + 1 年` 由 MOD-05 计算；不得扩展为读取 MOD-03 其他数据 |

### 2.4 状态与数据所有权（inherited-fixed）

| 数据 | Owner | 本地事务边界 / 不变量 |
|---|---|---|
| ReviewRecord（批注、最终等级、调整记录） | MOD-05 | 批注+最终等级+调整记录同事务；原始/最终等级、操作者、时间同时保留；scoring_failed 提交不得产生最终等级 |
| PresentationView（展示视图快照） | MOD-05 | 视图内容一次性写入；小组无可用提交时阻止生成；缺失材料显式标记；生成时快照不实时更新 |
| DeletionBatch（删除批次、确认记录、审计记录、排除标记） | MOD-05 | 确认+执行记录+审计记录同事务；未确认不删除；审计记录不在删除范围内且先于清除写入 |
| 教师读模型（派生） | MOD-05 | 来源 CT-005/CT-006 + 本地 ReviewRecord/DeletionBatch；秒级延迟可接受；事件重放可全量重建；派生不改变源数据所有权 |

### 2.5 相关父运行流（inherited-refinable：外部顺序与承诺固定，内部实现开放）

- DF-1 步骤 11–12（创建复核记录 → 教师查看/批注/调整）；DF-2 步骤 4–6（评分失败 → 教师端内通知 → 教师看到失败原因而非伪造等级）。
- DF-3 / F5-1~F5-3 / SCENARIO-016（保留期到期标记 → 教师 CT-007 查看到期批次 → CT-011 确认 → 审计先写 → CT-012 发布 → 清除 → CT-014 回流）。
- FLOW-007（CT-005 入）、FLOW-008（CT-006 入）、FLOW-009（教师浏览器边界入口，CT-007/008/009/011）、FLOW-010（CT-012 出）、FLOW-011（课程结束时间 internal_read）、FLOW-012（CT-014 入）。

### 2.6 继承决策、技术与部署约束

| 分类 | 项 | 内容 |
|---|---|---|
| inherited-fixed | KD-002 | 同组服务共部署（DU-2 内 MOD-02/03/05）+ 数据库 Outbox 表投递事件；不得引入消息中间件 |
| inherited-fixed | KD-003 | 单地域、HTTPS + 存储加密、每日备份 30 天、RPO 24h / RTO 48h、基础监控 |
| inherited-fixed | KD-005 | `/api/v1` 路径版本；写操作客户端幂等键；教师端使用教师账号会话（Bearer） |
| inherited-fixed | 部署 | MOD-05 为 DU-2 **内部节点**，读多写少负载低；保留治理到期标记与删除执行为 DU-2 内定时批处理 |
| inherited-fixed | 不采用方案 | 不引入缓存/搜索引擎（NFR-001 规模下事件派生读模型已满足查询）；不引入独立通知渠道（首版端内通知，A-005） |
| inherited-refinable | 读模型实现 | 派生方式、表形态、投影拓扑由本层决定（失效策略：事件重放可全量重建的承诺不变） |
| inherited-refinable | A-001 / A-003 | 教师账号由管理员/课程创建流程发放（教师身份不构成新领域边界）；过程摘要由 Agent 评估产出并随评估结果存储，展示视图直接引用 |
| delegated（父层显式暂缓，触发即本层） | 教师前端渲染技术 | 父 05「暂缓到详细设计」，触发条件 = MOD-05 详细设计（本层可继续下放到子节点） |
| delegated（同上） | 展示视图渲染与导出格式 | 同上 |
| unresolved（父层可选产品决策） | 调整等级是否强制填写理由 | PRD 列为可选补充决策；本层不得擅自强制（按可选处理，见 05-local-decisions） |

### 2.7 委托与未决项登记

- 数据库产品选型：父层 defer_to_detail_design（仅要求事务 + 备份），本层保持搁置（见 05）。
- 教师通知渠道扩展（邮件/IM）：父层暂缓至后续版本（A-005 首版端内通知）。
- 名单外部系统对接：父层暂缓（A-002 教师维护名单），与 MOD-05 无直接交互。

## 3. 当前 PRD 需求分配表

| 本层需求 | 分类 | 父层来源 | 分配到子节点（见 02） | 说明 |
|---|---|---|---|---|
| REQ-D001（教师查看课程/小组/学生/提交详情、材料、状态、依据、建议；批注与调整最终等级） | **allocated** | parent_req: REQ-009；AC: D-AC-REQ-009-01 ← AC-REQ-009-01 | CMP-TEACHER-UI、CMP-REVIEW-QUERY、CMP-REVIEW-COMMAND（ACCESS-GATE/RMP 为内部支撑） | 查看侧走读模型；写侧走 ReviewRecord；失败可见（failure_reason+retry_record）为查看的一部分 |
| REQ-D002（选择小组生成展示视图） | **allocated** | parent_req: REQ-010；AC: D-AC-REQ-010-01 ← AC-REQ-010-01 | CMP-TEACHER-UI、CMP-PRESENTATION（ACCESS-GATE/RMP 为内部支撑） | 缺失标记不隐藏缺口；无可用提交阻止生成 |
| （PRD 未重述）NFR-001 教师查询规模 | **inherited** | NFR-001 / FR-013 / AC-NFR-001-01（MOD-05 单模块契约） | CMP-REVIEW-QUERY、CMP-READMODEL-PROJECTOR | 事件派生读模型承接查询负载；≤10 秒查询时限 |
| （PRD 未重述）NFR-004 保留与删除 | **inherited / internal support** | NFR-004 / FR-016 / AC-NFR-004-01（module_local，owning MOD-05；MOD-02 execution_dependency） | CMP-RETENTION-GOVERNANCE、CMP-READMODEL-PROJECTOR（内部支撑）；CMP-REVIEW-QUERY 仅消费批次可读结果 | 当前 PRD 未列出 current NFR-D；保留治理继续实现但不作为 L2 直接 child，若需细化须先补 PRD 投影 |
| （PRD 未重述）REQ-011 教师端缺失标记 | **inherited（展示侧支撑）** | REQ-011 所有权在 MOD-02；展示义务经 CT-006 `missing_items[]`、CT-009 `missing_marks` 流入 | CMP-READMODEL-PROJECTOR、CMP-PRESENTATION、CMP-REVIEW-QUERY | 不改变 MOD-02 所有权 |
| 评分失败教师端内通知 | **inherited** | DF-2 步骤 4–6、F2-5、A-005、CT-005 副作用 | CMP-READMODEL-PROJECTOR（派生通知条目）、CMP-REVIEW-QUERY（列表/详情可见） | 首版端内通知，无外部渠道 |
| out-of-scope | — | — | — | 当前 PRD 无越界需求；未发现要求修改父边界的内容 |

**分配结论**：无需求被分给兄弟节点；无关键歧义。两条 allocated 需求均有父需求与 AC 对应；inherited 项均有父层 Requirement/NFR/契约/运行流可引。

## 4. 局部驱动（Local Drivers，仅作用于 MOD-05 内部）

1. **读多写少、秒级最终一致**（父 03/06）：查询全走派生读模型；写侧仅复核与删除确认两个低频频命令。
2. **失败透明、不伪造等级**（DF-2、CT-008 NO_ORIGINAL_GRADE）：失败原因与重试结果是一等展示数据。
3. **审计不变量**（FR-009、FR-016）：复核调整留痕、访问拒绝留痕、删除审计先于清除写入且永久留存。
4. **幂等与并发**（KD-005、CT-008/009/011）：写操作幂等键、事件消费按业务键去重、复核并发后写为准并完整留痕。
5. **生命周期治理**（DF-3）：保留期计算（课程结束 + 1 年）与定时批处理在 MOD-05 内；清除执行在 MOD-02，结果经 CT-014 回流。
6. **可重建性**（父 03）：读模型失效策略 = 事件重放全量重建 ⇒ 重建不得复活已删除数据（重放守卫，见 03/05）。

## 5. 可复用的父层/当前层能力

- 数据库 Outbox 投递器与持久化任务设施（KD-002，DU-2 附属基础设施）——本层仅实现消费/发布端口，不重造投递机制。
- 教师账号会话认证约定（KD-005 通用约定）与错误码目录（父 04 错误码汇总）。
- DU-2 共享数据库与定时批处理承载（06-deployment 保留治理批处理）。
- 父层暂缓项的下放通道：教师前端渲染技术、展示视图导出格式（delegated）。

## 6. 阻塞缺口

无。四项必需输入齐全；目标唯一匹配；关键父状态/契约/部署/决策均可获得；当前 PRD 不修改父边界；输出目录为空可安全写入。

## 7. 拟创建文件与上下游契约影响

- 拟创建（严格七个）：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。
- 上下游契约影响：**无**。本层不新增/修改/删除任何父契约字段、端点、事件或错误码；父契约由内部子节点组合实现（见 04 C4 映射）。
- 交接验证方法：C1–C6 映射完整性检查、子节点追踪列检查、父契约逐字段不可变比对、状态所有权越界检查、决策队列清零检查、ID 稳定排序检查（结果记录于 manifest validation 与 child-handoff）。

## 8. 假设、问题与冲突登记

| 编号 | 类型 | 内容 | 处置 |
|---|---|---|---|
| Q-01 | 问题（不阻塞） | 当前 PRD frontmatter `dependency_refs` 含 MOD-01，但父包中 MOD-05 与 MOD-01 无任何交互（无契约、无数据流） | 判定为 PRD 元数据噪音；本层不建立与 MOD-01 的任何依赖 |
| Q-02 | 问题（不阻塞，父层可见） | 教师读模型的课程/小组/学生列表按父 03 规定来源于 CT-005/CT-006（即有提交活动才出现）；若产品要求「无任何提交的课程也对教师可见」，需父层新增课程目录投影来源 | 本层严格按父边界实现；该诉求出现时走 `parent-change-request`，本层不擅自加读 MOD-03 数据（FLOW-011 仅限课程结束时间） |
| Q-03 | 假设（继承 A-003） | 展示视图的过程摘要引用 Agent 评估产出（经 CT-005 流入读模型），不由 MOD-05 自行生成 | 若 A-003 被证伪需返回父层 |
| Q-04 | 假设（继承 A-001） | 教师账号与课程授权关系由管理员/课程创建流程发放；MOD-05 本地持有授权数据用于课程范围鉴权 | 见 05 LCD-006（局部决定，影响不出本节点） |
| Q-05 | 冲突 | 无 | 父层各产物对 MOD-05 的描述一致，未发现继承不一致 |
