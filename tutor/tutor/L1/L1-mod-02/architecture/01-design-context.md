# 01 Design Context — MOD-02 submission-intake 设计上下文

> 本文件是 L1 递归细化（recursive-architecture-design）阶段 1–2 的产物：父边界快照、边界分类、当前 PRD 需求分配与局部驱动。后续文件：`02-architecture-decomposition.md`（子节点分解）、`03-state-and-data.md`（状态与数据）、`04-contracts-and-runtime.md`（契约与运行时）、`05-local-decisions.md`（局部决策）。

## 输入绑定

| 项 | 解析结果 |
|---|---|
| `parent_architecture` | `architecture/L0/output`（顶层 DDD 到系统架构包：存在 `output/01-system-overview.md`，无 `architecture-manifest.yaml`） |
| `target_node_id` | `MOD-02`（submission-intake），在父包 `01-system-overview.md` 模块清单中**唯一匹配**（匹配行见下方快照） |
| `current_prd` | `prd/L1/L1-mod-02/prd.md`（doc_id `UNKNOWN-MOD-02-v1.0`，status: complete，schema 2.0） |
| `output_dir` | `architecture/L1/L1-mod-02`（目录已存在且为空，`new` 模式无覆盖风险） |
| `mode` | `new` |
| `parent_prd` | **未读取**：父包已提供充分的需求追溯（01 模块清单 REQ 追踪、04 契约、05 决策、acceptance-contract-projections.yaml 的 MOD-02 verification slices），无实质缺口 |
| `human_constraints` | 无 |

当前 PRD 的「架构输入契约」四节继承 `../../L0-root/architecture/01-system-overview.md`、`03-data-and-consistency.md` 与 `04-interface-contracts.md` 的既有边界和决策，本层不新造（继承明细见下表与 `05-local-decisions.md` 继承决策节）。PRD frontmatter 的 `implementation_surfaces: [domain_logic, worker_job, observability, integration_wiring]` 已映射到子节点（见 `02-architecture-decomposition.md` 子节点清单「实现面」列）。

## 父边界快照（Parent-Boundary Snapshot）

### 身份与匹配证据

- 来源：`architecture/L0/output/01-system-overview.md`「模块清单（按 module_id 排序）」
- 匹配行：`| MOD-02 | submission-intake | BC-SUBMISSION | REQ-003、REQ-004、REQ-007、REQ-011;NFR-002、NFR-003;SM-001 |`
- 匹配数：1（全包唯一）；同时与 `04-interface-contracts.md`「组件接口卡」MOD-02 条、`03-data-and-consistency.md` Submission 行交叉一致。

### 职责（继承自父包 01「模块职责」）

材料包接收（500MB 上限、类型白名单，KD-004）；提交生命周期状态机（upload_failed/rejected/received/processing/scored/scoring_failed）；完整性报告与缺失项标记；30 秒内返回接收确认；发布 SubmissionReceived 事件；执行保留期数据清除并回传清除结果（CT-014）。另按 04 通用约定提供 `POST /api/v1/auth/token` 令牌签发（KD-005，CT-001 契约族附属交互）。

### 排除项（由兄弟模块职责反推，本层不得越界）

- 不采集对话与材料（MOD-01 codex-plugin，学生侧 DU-1）。
- 不持有课程/邀请码/名单数据（MOD-03 course-roster）；每次提交必须经 CT-003 重新校验，不缓存通过结论（REQ-006）。
- 不执行 Agent 评分、不管理评分重试（MOD-04 assessment，DU-3）。
- 不提供教师端查询/批注/展示/删除确认（MOD-05 teacher-web）。
- 不计算保留到期时间、不持有删除批次与审计记录（MOD-05）；MOD-02 仅按 CT-012 `submission_ids[]` 执行清除并经 CT-014 回传结果，不接收、也不需要 `course_end_at` / `retention_due_at`（父包 02/03 保留期规则）。

### 需求追溯

| 追溯项 | 来源 | 说明 |
|---|---|---|
| REQ-003、REQ-004、REQ-007、REQ-011 | 父包 01 模块清单 | 本模块承接的功能需求（L1 PRD REQ-D001~D004 的 `parent_req`） |
| NFR-002（30 并发提交）、NFR-003（30 秒接收确认 / 10 分钟评分） | 父包 01 模块清单 | 本模块承接并发与 30 秒确认段 |
| SM-001（提交接收成功率 ≥95%） | 父包 01「Success Metric 分配」 | **Owning Module = MOD-02**，度量来源：CT-001 接收确认（received）/rejected/upload_failed 状态机统计 |
| AC-REQ-003-01（shared，owning=MOD-02） | acceptance-contract-projections.yaml | MOD-02 slice：材料持久化与完整性报告；提交详情可列出对话/代码/截图/结果及缺失项；空目录仍进入评分并标记缺失；维护 rejected/processing/upload_failed 状态并记录原因；校验通过时发布 SubmissionReceived |
| AC-REQ-007-01（shared，owning=MOD-02） | 同上 | MOD-02 slice：30 秒内返回含提交编号与 received_at 的接收确认；维护 received/processing/scored/scoring_failed 状态序列可观察；30 并发下独立编号与状态 |
| AC-REQ-008-01（shared，owning=MOD-04，participating=MOD-02） | 同上 | MOD-02 slice：向 MOD-04 提供材料清单与完整性报告（CT-004 载荷）；缺失标记经 CT-006 派生至教师端 |
| AC-NFR-003-01（shared，owning=MOD-02） | 同上 | MOD-02 slice：≥95% 有效提交 30 秒内返回接收确认 |
| AC-NFR-004-01（module_local MOD-05，MOD-02=execution_dependency） | 同上 | 按 CT-012 执行清除并经 CT-014 回传 |

### 状态/数据所有权（父包 03「数据所有权」Submission 行）

`Submission`：提交记录、状态机、材料清单、材料文件、完整性报告、上传失败原因。本地事务边界：状态迁移 + 材料清单 + 完整性报告。不变量：缺必填信息不创建可评分提交；状态机迁移顺序；缺失显式标记。

### 契约（父包 04「组件接口卡」MOD-02 条，逐字继承）

| 角色 | 契约 |
|---|---|
| provides | CT-001（材料包上传）、CT-002（提交状态查询）、`POST /api/v1/auth/token`（未编号附属端点，名单核对语义同 CT-003） |
| consumes_api | CT-003（课程归属校验，Provider=MOD-03） |
| consumes_events | CT-005（SubmissionScored/ScoringFailed，来自 MOD-04）、CT-012（RecordsDeleted，来自 MOD-05） |
| publishes_events | CT-004（SubmissionReceived→MOD-04）、CT-006（received 或 upload_failed→MOD-05）、CT-014（PurgeCompleted→MOD-05） |

### 直接边界与相关父运行流

- 直接上下游：MOD-01（CT-001/CT-002/auth-token）、MOD-03（CT-003）、MOD-04（CT-004 出 / CT-005 入）、MOD-05（CT-006/CT-014 出 / CT-012 入）。
- 相关流：FLOW-001、FLOW-002、FLOW-003、FLOW-004、FLOW-006、FLOW-008、FLOW-010、FLOW-012；SCENARIO-001（主链路）、SCENARIO-016（保留删除链路）；DF-1 步骤 2–6、DF-3 步骤 4–5。
- 部署：DU-2 course-app（与 MOD-03/MOD-05 同部署单元，KD-002）；MOD-02 需支撑 30 并发上传（NFR-002）；不新增部署单元。

### 继承决策与技术/部署约束

KD-002（同组共部署 + 数据库 Outbox）、KD-003（HTTPS + 存储加密 + 每日备份）、KD-004（500MB 单次上限 / 类型白名单 / 200GB 每课程配额）、KD-005（令牌 + 幂等键 submission UUID + 分片断点续传 + `/api/v1`）。存储形态：结构化元数据 → 单一关系型数据库；材料文件 → 服务器本地磁盘（加密）；异步任务与 Outbox 持久化于数据库。

### 委托与未决项

- 委托给本层：MOD-02 内部结构、内部状态拆分、内部契约、局部战术（本文件及后续产物）。
- 继承的全局暂缓项：数据库产品选型（defer_to_detail_design，父包 05；本层不重开）。

## 边界分类

| 项 | 分类 | 本层行为 |
|---|---|---|
| 父契约 CT-001~CT-006、CT-012、CT-014 的标识、所有者、路径/主题、字段、副作用、依赖、失败与版本语义 | `inherited-fixed` | 原样实现，不改名/不弱化/不增必需字段/不升版本；实现映射见 `04-contracts-and-runtime.md` |
| 状态机六态（外部可见值域）与终态语义 | `inherited-fixed` | 外部值域不变；仅允许内部子状态细化（见 `05-local-decisions.md` LCD-001） |
| Submission 数据所有权、材料磁盘为 DU-2/DU-3 共享设施、MOD-04 只读引用材料 | `inherited-fixed` | 所有权不转移；本层只拆分模块内部的读/写分工 |
| CT-006 的具体发布时机（父包已固化为 received 或终态 upload_failed） | `inherited-fixed` | 原样实现；schema/消费者/幂等不变，L1 只映射到 SI-CORE/SI-RELAY（LCD-002） |
| received→processing 的内部推进机制（父包只定义可观察状态序列） | `inherited-refinable` | 细化推进时机（LCD-003） |
| ROSTER_UNAVAILABLE 时「保持待校验并重试」的内部承载方式 | `inherited-refinable` | 细化内部子状态与重试策略（LCD-001），不向客户端暴露内部细节 |
| MOD-02 内部分解、内部契约、存储布局、可观测埋点 | `delegated` | 本层决定并记录 |
| 无 `return_to_parent` 项 | — | 本次设计不改变任何父职责、契约、所有权、依赖方向、ADR、技术或部署边界 |

## 需求分配（当前 PRD `prd/L1/L1-mod-02/prd.md`）

| 需求 | 分类 | 父层引用 | 分配到子节点 | 说明 |
|---|---|---|---|---|
| REQ-D001 每次提交采集完整 Codex 对话 | `allocated` | parent_req REQ-003；AC-REQ-003-01（D-AC-REQ-003-01）；CT-001 | SI-XFER（对话材料接收）、SI-CORE（对话入材料清单、提交详情可列出） | 采集行为本身在 MOD-01（out-of-scope）；本模块负责服务端接收、持久化与可列出 |
| REQ-D002 按插件配置收集代码/截图/结果并关联作业、姓名、小组 | `allocated` | parent_req REQ-004；CT-001；KD-004 | SI-XFER、SI-CORE（SI-STORE 为内部存储支撑） | 「按插件配置」的类别声明随 CT-001 材料分片类别标注到达，作为完整性比对基准 |
| REQ-D003 上传成功返回接收确认并异步执行 Agent 评分 | `allocated` | parent_req REQ-007；AC-REQ-007-01（D-AC-REQ-007-01）；CT-001/CT-004 | SI-API（30 秒同步确认）、SI-CORE（received 与状态机）；SI-RELAY 为内部事件支撑 | 评分执行在 MOD-04（out-of-scope）；本模块负责确认、事件发布与状态序列可观察 |
| REQ-D004 材料不完整时允许进入评分并在教师端标记缺失项 | `allocated` | parent_req REQ-011；AC-REQ-003-01 boundaries / AC-REQ-008-01；CT-004/CT-006 | SI-CORE（完整性报告与缺失项标记）；SI-RELAY 为内部传播支撑 | 缺失不阻塞 received 与评分；教师端展示在 MOD-05（out-of-scope） |
| NFR-002 30 并发提交 | `inherited` | 父包 01 模块清单；AC-REQ-007-01 boundaries | SI-API、SI-XFER（战术：无状态接入、会话持久化、幂等唯一约束） | 每个提交独立编号与状态 |
| NFR-003 30 秒接收确认 | `inherited` | 父包 01/04；AC-NFR-003-01 MOD-02 slice | SI-API（短同步路径）、SI-CORE（单事务持久化） | 10 分钟评分段归 MOD-04 |
| SM-001 提交接收成功率 ≥95% | `inherited`（Owning） | 父包 01 SM 分配 / AC-NFR-003-01 | SI-API 采集有效提交、30 秒内 received 应答和耗时；基础监控按课程周期聚合 | 分母排除学生主动取消、身份校验失败和材料不完整；查询走基础监控指标面板（LCD-009） |
| 采集完整对话（MOD-01）、评分与重试（MOD-04）、名单数据（MOD-03）、教师端功能与保留治理计算（MOD-05） | `out-of-scope` | 父包 01 模块职责 | — | 仅作为协作约束引用，不设计其内部 |

无 `local` 类需求（当前 PRD 全部需求均可追溯父层）；无疑似错配到兄弟模块的需求。

## 局部驱动（Local Drivers）

1. **30 秒同步确认 vs 500MB 分片上传**：确认路径必须短——认证、幂等检查、合并落盘、CT-003 校验、单事务持久化（含 Outbox）后即应答；完整性报告限定为**清单级比对**（类别/存在性/大小），不做内容级分析。
2. **30 并发与幂等**：接入层无状态；`submission_uuid` 唯一约束承载幂等去重；分片会话持久化支撑断点续传与并发互不干扰（每提交独立编号）。
3. **不丢事件（KD-002）**：业务数据与 Outbox 记录同一本地事务；投递器无限重试直至确认；入站消费按业务键幂等。
4. **存储边界（KD-004）**：500MB 单次上限、类型白名单、200GB/课程配额，在接收路径流式计数与校验。
5. **教师可见性**：upload_failed/rejected 记录原因；upload_failed 终态经 CT-006 派生（LCD-002），支撑父包「教师端可见失败原因」承诺与 SM-001 统计。
6. **保留清除闭环**：CT-012 触发、逐项清除、部分失败保留重跑、CT-014 回流，审计不受影响（审计在 MOD-05）。

## 可复用能力（Reusable Capability）

- 父包已固化的机制直接复用：数据库 Outbox 表 + 后台投递器（KD-002）、`/api/v1` 版本与错误码体系（04 通用约定与错误码汇总）、令牌认证与幂等键模式（KD-005）、共享材料磁盘与共享数据库（06 DU-2 附属设施）。
- 同 DU-2 内 MOD-03 为低延迟进程内/同机调用（FLOW-003 注释），CT-003 同步调用无新增网络边界。
- 本模块无既往 L1 包（`mode=new`），无本层已有资产可复用。

## 阻塞缺口

无。四项必需输入均已解析且经实际验证；父状态/契约/部署/决策全部可用；输出目录为空，无覆盖风险；未发现允许实质不同子架构的信息缺口。

## 拟写文件（本包全部输出）

`architecture-manifest.yaml`、`01-design-context.md`（本文件）、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。无 `parent-change-request.md`（无 return_to_parent 项）。

## 上下游契约影响

- 不改变任何父契约标识、Provider/Consumer、字段、错误与版本；L0 已将 CT-006 的触发条件明确为 `received` 或终态 `upload_failed`，L1 仅实现其内部映射。
- 对上游 MOD-01：无新约束（CT-001/CT-002/auth-token 语义不变）。
- 对下游 MOD-03/MOD-04/MOD-05：无新契约、无字段变更；CT-006 的 `received/upload_failed` 发布条件已由父包明确，schema 与消费者不变。
- 新增契约仅限模块内部（IC-SI-01~IC-SI-06），跨模块不可见。

## 验证方法（交接时采用）

1. 需求分配覆盖检查：REQ-D001~D004、NFR-002/003、SM-001 全部落入子节点且无越界。
  2. 子节点追踪检查：每个直接 child_id 至少拥有一条本层 `REQ-Dxxx`/`NFR-Dxxx`；CT/FLOW/状态/SM/FR/父层 Requirement 只作为补充追踪，内部支撑组件不进入 C1 清单。
3. 父契约不变性对照：逐条比对父包 04 的 contract_fields 与本包实现映射（字段、错误码、事件、幂等、版本）。
4. 状态机一致性：外部六态 + deleted 与父包 AC（D-AC-REQ-003-01、D-AC-REQ-007-01）及 FLOW 终态逐条对齐。
5. 稳定 ID 排序检查：子节点、内部契约、状态、决策注册表均按稳定 ID 排序。
6. 边界红线检查：未新增部署单元/平台/数据库/消息总线/公共运行时边界；未设计兄弟模块内部。

检查结果与实际输出清单记录于 `architecture-manifest.yaml` 与 `child-handoff.md`。

## 假设、问题与冲突

- 无新增假设（当前 PRD 与父包信息充分）。
- 说明 1：当前 PRD 的「架构输入契约」以父包为绑定来源，已在 PRD 中明确记录为继承，不视为缺口。
- 说明 2：LCD-002 的原有文字张力已通过同步修正 L0 CT-001、CT-006 与 FLOW-008 消除；L1 不再保留未解决的父层契约风险。
