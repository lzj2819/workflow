# Child Handoff — MOD-04 assessment L1 包交接

本文件为 L2 继续细化的唯一入口。下一层以本文件中的 `child_id` 作为 `target_node_id`，
以本包为 `parent_architecture`（包类型：递归子层包，根含 architecture-manifest.yaml）。

## 1. 当前节点身份与父层绑定

- 节点：MOD-04 assessment（BC-ASSESSMENT，DU-3 assessment-worker）。
- 职责/排除项：见 `architecture-manifest.yaml` package 节。
- 父层绑定：CT-004（消费）、CT-005（发布）、CT-010（经 ACL 消费）；KD-001/KD-002/KD-003；
  时限（单次 ≤3min、任务 ≤10min）；父层「不采用方案」。boundary_fingerprint 全文见 manifest。
- 验收投影：D-AC-REQ-008-01（继承 AC-REQ-008-01，owning=MOD-04）；AC-REQ-007-01、AC-NFR-003-01 的 MOD-04 slice。

## 2. 可继续细化的直接子节点（下一层 target_node_id 候选）

| child_id | 下一层焦点 | 进入触发条件 | 所需祖先上下文 |
|---|---|---|---|
| CMP-ASSESSMENT-ENGINE | 领域校验规则集、结果装配、缺失材料影响说明生成策略 | 编排器细化后 | 本包 03/04；L0 FR-008、AC-REQ-008-01 |
| CMP-SCORING-ORCHESTRATOR | 任务表结构与状态机细化、认领/租约参数、终态事务实现、重试决策表落地 | **推荐首先进入**（一致性核心） | 本包 03/04；L0 03-data-and-consistency、KD-002 |

> `CMP-MODEL-SERVICE-ACL`、`CMP-RESULT-PUBLISHER`、`CMP-RUBRIC-PROMPT-COMPOSER`、`CMP-SCORING-METRICS` 为内部实现/观测支撑组件，不作为 L2 target；其契约和状态继续由本包台账维护。

## 3. 契约清单

**继承契约（语义不变，禁止改名/弱化/新增必需字段/升级版本）：**

| 契约 | 本层角色 | 实现子节点 |
|---|---|---|
| CT-004 SubmissionReceived | 消费（submission_id 幂等，任务持久化后确认） | CMP-SCORING-ORCHESTRATOR |
| CT-005 SubmissionScored/ScoringFailed | 发布（scored 四件套 / scoring_failed 两件套，v=1） | CMP-RESULT-PUBLISHER |
| CT-010 模型评估推理 | 经 ACL 消费（≤3min、最小化、三分类错误） | CMP-MODEL-SERVICE-ACL |

**内部契约（限定 MOD-04 内，随本包演进）**：ICT-001 ClaimScoringTask、ICT-002 ComposeEvaluationPrompt、
ICT-003 LoadMaterialContents（MOD-02 所有权只读端口）、ICT-004 InvokeModelAssessment、
ICT-005 CompleteAssessment、ICT-006 FailAssessment、ICT-007 PublishScoringOutcome、ICT-008 QueryScoringMetrics。
字段与语义见 `04-contracts-and-runtime.md` 第 3 节。

## 4. 状态所有权、决策与未解决风险

**状态所有权**：ST-001 ScoringTask（含 retry_record、claim_lease/reclaim_count）→ CMP-SCORING-ORCHESTRATOR；
ST-002 AssessmentResult 结果内容（写后不可变）→ CMP-SCORING-ORCHESTRATOR 持久化 / CMP-ASSESSMENT-ENGINE 装配；
ST-003 Outbox 行 → CMP-RESULT-PUBLISHER；ST-004 RubricPolicy → CMP-RUBRIC-PROMPT-COMPOSER。
不变量 INV-1~5、并发 CON-1/2、幂等 IDM-1/2 见 `03-state-and-data.md` 第 3 节。

**决策**：
- 继承（绑定）：KD-001/002/003、REQ-012 重试一次语义、NFR-003 时限、DU-3 部署、父层不采用清单。
- 本地（decide_now）：LCD-001 材料只读通道；LCD-002 有界退避重试与崩溃恢复（reclaim_count>3 终态化）；LCD-003 准则/提示版本化存证；LCD-004 期限跟踪不强杀。
- 委托下一层：LCD-005（提示模板与摘要策略）；implementation_detail：LCD-006（schema/参数/配置）。
- **未解决风险**：
  1. Q-001 父层未将 AssessmentResult 纳入删除接线（CT-012 消费者无 MOD-04）——待 L0 修订处置，本层不自建接线；
  2. 模型输出质量与五维度稳定性依赖提示调优（LCD-005），上线前需样例回归；
  3. 供应商不可用窗口长于一次退避时 scoring_failed 率上升——属 REQ-D002 既定行为，经 SM-003 终态覆盖与教师通知兜底。

## 5. 追踪豁免与实际验证

- 直接 child_id 需求所有权：2 个直接子节点分别拥有 REQ-D001/REQ-D002；4 个内部支撑组件保留实现追踪但不作为 L2 target。
- 实际输入：见 `architecture-manifest.yaml` resolved_inputs（父包 8 文件 + 父层 DDD 追踪 4 文件 + 本层 PRD）。
- 实际输出（本包严格七文件）：
  `architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、
  `03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`（本文件）。
  未生成 `parent-change-request.md`（无 return_to_parent）。

**验证检查及结果：**

| 检查 | 结果 |
|---|---|
| 四项必需输入解析 + 输出目录安全（空目录、mode=new） | 通过 |
| 父包类型识别 + target_node_id=MOD-04 唯一匹配（3 处证据） | 通过（manifest node_match_evidence） |
| 需求分配四类齐备，无错分兄弟节点、无关键歧义 | 通过（01 §2） |
| 子节点清单含追踪列与 trace_exemption_reason 列；全部有直接追踪 | 通过（02 §2） |
| C1–C6 | 通过（02 §5） |
| 父契约逐字段实现映射；无改名/弱化/新增必需字段/版本变更 | 通过（04 §1–2） |
| 内部契约按 ICT-001~008 稳定排序，含所有者/消费者/触发/schema/副作用/错误/幂等/兼容 | 通过（04 §3） |
| 运行流覆盖成功、失败/恢复、生命周期三类 | 通过（04 §4） |
| 决策队列无未处理 decide_now；无 return_to_parent | 通过（05 §2–3） |
| 稳定 ID 排序（CMP/ST/ICT/LCD） | 通过 |

**未完成项及阻塞影响：** 无阻塞项。Q-001 为父层登记事项，不影响本包进入 Human Gate；
LCD-005/006 为显式委托与实现细节，不影响本层结构完整性。

**Human Gate：** 请确认本包。确认后可以 `[NEXT CMP-SCORING-ORCHESTRATOR]`（推荐）或上表任一 child_id 进入 L2 细化。
