# 01 Design Context — MOD-04 assessment 设计上下文

本文件记录父边界快照、当前 PRD 需求分配与局部驱动。设计范围严格限定在 MOD-04 内部；
父层职责、契约、数据所有权、部署与技术决策为绑定边界，本层不做任何修改。

## 1. 父边界快照

### 1.1 节点身份

| 项 | 值 | 父层出处 |
|---|---|---|
| target_node_id | MOD-04 | 01-system-overview「模块清单」 |
| Module | assessment | 同上 |
| 来源 BC | BC-ASSESSMENT（一一对应） | 01「BC 到 Module 映射」 |
| 部署单元 | DU-3 assessment-worker（仅含 MOD-04，独立扩缩） | 06-deployment |
| 父层追踪 | REQ-008、REQ-012；NFR-003；SM-002、SM-003 | 01 模块清单、Success Metric 分配 |

### 1.2 职责与排除项（继承，原文见 manifest.boundary_fingerprint）

- 消费 SubmissionReceived 创建评分任务；
- 经 ACL 调用外部模型 API（KD-001）执行五维度独立评估（需求理解、Codex 迭代过程、代码质量、最终功能、文档/展示完整性 —— ubiquitous-language「维度依据」）；
- 产出原始等级、依据、教师专用建议；
- 失败自动重试一次，再失败标记 scoring_failed 并触发教师通知。

排除项：不提供任何网络契约；不承担教师端展示/通知呈现（MOD-05）；不持有提交状态机、材料文件、完整性报告（MOD-02）；不执行保留期删除（父层未接线，见 §6 Q-001）。

### 1.3 状态与数据所有权（继承）

| 聚合 | 内容 | 关键不变量（父层 aggregates.md / 03） |
|---|---|---|
| AssessmentResult | 评分任务、原始等级、五维度依据、教师专用建议、重试记录、失败原因 | 原始等级一经产出不可变；最多自动重试一次；失败必须记录原因与重试结果，不得伪造等级；等级落在 A–E 及默认区间（A=90–100 … E=0–59，FR-008）；建议标记为教师专用；单次评估结果及其重试记录在同一事务内 |

### 1.4 契约边界（继承）

| 契约 | 角色 | 对端 | 关键语义（本层不得改变） |
|---|---|---|---|
| CT-004 SubmissionReceived（事件） | Consumer | MOD-02 → MOD-04 | 载荷含 submission_id、course_id、assignment、student_name、group_name、material_refs[]、missing_items[]、received_at、v=1；按 submission_id 幂等消费，重复事件不创建重复任务 |
| CT-005 SubmissionScored/ScoringFailed（事件） | Provider | MOD-04 → MOD-02、MOD-05 | outcome ∈ {scored, scoring_failed}；scored 时携带 original_grade、dimension_rationales[5]、teacher_suggestions[]、scored_at；scoring_failed 时携带 failure_reason、retry_record；v=1 向后兼容追加；消费幂等 |
| CT-010 模型评估推理（external_api） | Consumer（经 ACL） | 模型服务（外部） | 单次调用 ≤3 分钟；请求 = evaluation_prompt + materials（ACL 内最小化编排）+ 可选 request_id；应答 = grade、dimension_rationales[5]、suggestions[]；错误 MODEL_TIMEOUT/MODEL_ERROR/INVALID_RESPONSE_SCHEMA 均计入评分失败策略；不向供应商发送业务标识（KD-001 数据最小化） |

### 1.5 直接边界与相关父运行流

- 直接上游：MOD-02（CT-004；材料内容只读来源，见 LCD-001）。
- 直接下游：MOD-02、MOD-05（CT-005）；模型服务（外部，CT-010）。
- 兄弟节点 MOD-01、MOD-03：仅作协作约束引用，不读取、不重设计其内部。
- 父运行流：FLOW-004（CT-004 进入条件：归属校验通过且材料持久化完成）、FLOW-005（CT-010，单次 ≤3 分钟）、FLOW-006/007（CT-005，终态 scored/scoring_failed）、SCENARIO-012、DF-2（仅自动重试一次；失败展示原因与重试结果；不得伪造等级）。

### 1.6 继承决策与约束

KD-001（外部模型 API + ACL 隔离、材料最小化、供应商可替换）；KD-002（同组共部署、数据库任务表 + Outbox 事件、单一关系库 + 本地材料磁盘）；KD-003（基础级运维与监控告警）；时限约束（CT-010 单次 ≤3 分钟；任务创建至 scored ≤10 分钟，NFR-003/SM-002 ≥95%）；父层「不采用方案」（消息中间件、工作流引擎、缓存/搜索引擎、分布式事务、自托管模型）同样约束本层内部选型。

## 2. 当前 PRD 需求分配

| 本层需求 | 分类 | 父层追踪 | 分配到子节点 | 说明 |
|---|---|---|---|---|
| REQ-D001 五维度评估输出（A–E 等级、分维度依据、改进建议） | allocated | parent_req REQ-008；FR-008；AC-REQ-008-01（本层投影 D-AC-REQ-008-01） | CMP-ASSESSMENT-ENGINE（直接 owner）；Rubric/ACL 为内部支撑 | 评估结果、五维依据和教师建议由引擎直接负责；准则与模型调用不构成独立 L1 产品义务 |
| REQ-D002 失败自动重试一次；仍失败标记“评分失败”并通知教师 | allocated | parent_req REQ-012；FR-012；DF-2；AC-REQ-007-01（MOD-04 slice） | CMP-SCORING-ORCHESTRATOR（直接 owner）；RESULT-PUBLISHER/ACL 为内部支撑 | “通知教师”经 CT-005 outcome=scoring_failed 触发 MOD-05 端内通知（A-005），本层只负责产出该事件 |
| NFR-003 时限（评分 10 分钟内） | inherited-refinable | NFR-003；FR-015；AC-NFR-003-01（MOD-04 slice）；04 错误/超时策略 | CMP-SCORING-ORCHESTRATOR（期限跟踪）、CMP-SCORING-METRICS（口径统计） | 外部语义固定：CT-010 单次 ≤3 分钟、任务 ≤10 分钟；内部调度策略开放 |
| SM-002 评分按时完成率 ≥95% | inherited | 01 Success Metric 分配（Owning=MOD-04） | CMP-SCORING-METRICS | 口径：CT-004 任务创建至 CT-005 outcome=scored 时长 |
| SM-003 教师评分覆盖率 ≥95% | inherited | 01 Success Metric 分配（Owning=MOD-04） | CMP-SCORING-METRICS | 口径：任务创建至终态（scored/scoring_failed）比例 |
| D-AC-REQ-008-01 边界：材料不完整仍生成结果并说明缺失影响 | allocated | parent_acceptance_contract AC-REQ-008-01 boundaries；REQ-011（MOD-02 提供缺失标记输入） | CMP-ASSESSMENT-ENGINE、CMP-RUBRIC-PROMPT-COMPOSER | 输入来自 CT-004 载荷 missing_items[]；缺失不阻断评分 |
| D-AC-REQ-008-01：建议默认不暴露给学生 | inherited | AC-REQ-008-01 observable_oracles；聚合不变量“建议标记为教师专用” | CMP-ASSESSMENT-ENGINE（产出教师专用标记）；暴露控制属 MOD-05 | 本层仅保证标记与 CT-005 字段携带，展示控制不在边界内 |
| 前端展示实现面 | out-of-scope（展示面） | REQ-D001 的教师可见结果由 MOD-05 经 CT-005/CT-007 承担 | — | 按父边界解释为“结果数据经 CT-005 供 MOD-05 展示”；本层不新建前端或公共运行时边界（见 §6 A-002） |

无需求被分配给兄弟节点；无关键歧义。

## 3. 局部驱动

1. **时限预算**：任务创建至 scored ≤10 分钟（SM-002），单次模型调用 ≤3 分钟，最多两次尝试 + 有界退避（LCD-002、LCD-004）。
2. **五维度准则**：等级、维度依据、建议的产出结构固定（CT-005/CT-010 载荷），准则与提示词是高频调优点，需版本化（LCD-003）。
3. **数据最小化合规**：材料内容出境受 KD-001 约束，最小化编排必须在 ACL 内完成。
4. **幂等与可恢复**：事件至少一次投递 + worker 可崩溃恢复（06 故障隔离），任务表持久化 + 幂等键是本层一致性的根基。
5. **指标承接**：SM-002/SM-003 为 MOD-04 自有指标，需从任务状态直接可算。
6. **材料降级**：missing_items[] 不为空时仍须产出结果并说明影响（D-AC-REQ-008-01 boundaries）。

## 4. 可复用能力（父层/当前层）

| 能力 | 来源 | 本层用法 |
|---|---|---|
| 数据库持久化任务表 + Outbox 表 + 后台投递器 | KD-002；05 技术组件 | 评分任务持久化与 CT-005 投递，不引入消息中间件 |
| 同组共享数据库 + 本地材料磁盘（存储加密） | KD-002/KD-003；06 部署图（DU-3---DB） | 材料内容只读访问通道（LCD-001） |
| 基础级监控告警 | KD-003；06 监控列表（评分任务积压、模型调用失败率） | CMP-SCORING-METRICS 暴露观测钩子 |
| DU-3 独立扩缩（2–3 worker 副本） | 06 扩缩容策略 | 多副本经任务表认领协调，无需新基础设施 |

## 5. 计划输出与验证方法

- 拟写文件（本包严格七个）：`architecture-manifest.yaml`、`01-design-context.md`（本文件）、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。
- 上下游契约影响：无。CT-004/CT-005/CT-010 的标识、所有者、字段、副作用、失败与版本语义本层原样实现，不改名、不弱化、不升级。
- 验证方法：C1-C6 逐条检查（02/04 内附检查表）；子节点清单追踪列完整（无需求/父层追踪者填非空 trace_exemption_reason）；父契约逐字段实现映射；稳定 ID 排序（CMP/ICT/LCD/ST）。

## 6. 假设、问题与冲突

- **A-001（假设）**：CT-004 到达即视为父层前置条件“提交状态 processing 且材料已持久化”成立（FLOW-004 入口条件）；材料文件在评分时不可读（IO 错误）按基础设施失败处理，进入 REQ-D002 重试一次 → scoring_failed 路径，而非“材料不完整”降级路径。
- **A-002（假设）**：REQ-D001 元数据中的 frontend surface 指“结果最终对教师可见”，其实现由 MOD-05 经 CT-005/CT-007 承担；本层不产生任何前端或面向教师的契约。
- **A-003（假设）**：教师通知的呈现完全由 MOD-05 消费 CT-005 outcome=scoring_failed 完成（父层 04 CT-005 side_effects、DF-2 步骤 4）；本层不新增通知渠道。
- **Q-001（父层未决问题，非阻塞）**：父层删除流程（DF-3、CT-012）未将 AssessmentResult 纳入清除范围（CT-012 消费者仅 MOD-02/MOD-05）。本层 PRD（REQ-D001/D002）不依赖删除行为，故不触发 return_to_parent；按父层专属事项登记于 05-local-decisions，建议 L0 修订时明确接线方式（如扩展 CT-012 消费者或新增清除契约）。
- **冲突**：无。当前 PRD 未要求改变父职责、排除项、公共契约、数据所有权、依赖方向、ADR、技术或部署。
