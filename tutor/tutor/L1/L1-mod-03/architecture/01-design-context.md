# 01 Design Context — MOD-03 course-roster（L1 设计上下文）

## 1. 本次设计范围

- **目标节点**：`MOD-03 course-roster`（父包 L0 唯一匹配，匹配证据见 `architecture-manifest.yaml`）。
- **当前 PRD**：`prd/L1/L1-mod-03/prd.md`（REQ-D001 / REQ-D002 + D-AC-REQ-003-01 / D-AC-REQ-006-01）。
- **模式**：`new`；输出目录 `architecture/L1/L1-mod-03`（写入前已确认不存在，不覆盖既有包）。
- 指令原文提及「生成 L1-mod-01 的架构」，与 PRD（`module_name: MOD-03`）、输出目录（`L1-mod-03`）、父包需求追踪（REQ-005/REQ-006）三方证据不一致，经交叉确认按 MOD-03 执行；`architecture/L1/L1-mod-01` 为已存在的独立包，本运行未触碰。
- 本层只设计 MOD-03 内部结构；兄弟节点（MOD-01/02/04/05）仅作为协作约束引用，不重设计其内部。

## 2. 父边界快照（Boundary Snapshot）

以下条目逐条摘自父包，构成本层不可逾越的「墙、门和水电」。

### 2.1 身份与职责

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `MOD-03 course-roster`，来源 BC-COURSE（一一对应） | 01 §模块清单、§BC 到 Module 映射 | inherited-fixed |
| 职责 | 课程、邀请码、名单（姓名+小组）维护；每次提交的归属校验（不缓存通过结论）；提供课程结束时间供保留治理引用 | 01 §模块职责 | inherited-refinable（内部拆分开放） |
| 排除项 | 不消费任何 API/事件、不发布任何事件；不持有 Submission 等兄弟聚合；不参与评分与教师端展示；不执行保留期数据清除；不承接成功指标 | 04 §组件接口卡、03 §数据所有权、01 §SM 分配 | inherited-fixed |
| 部署形态 | DU-2 course-app（与 MOD-02/05 共部署，共享数据库与本地磁盘）；不得创建独立服务/部署单元 | 06 §部署单元、§Module 到部署单元映射 | inherited-fixed |

### 2.2 需求与验收契约追溯

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 父需求 | REQ-005（归属校验）、REQ-006（每次提交重新校验），对应 FR-005、FR-006 | 01 §模块清单；04 §CT-003 Source FR | inherited-fixed |
| 共享 AC | AC-REQ-003-01 = shared，MOD-03 为 participating module；verification_slice：每次提交经 CT-003 执行邀请码+姓名+小组归属校验，不缓存通过结论（REQ-006）；校验失败返回具体拒绝原因，支撑 rejected 状态及原因记录 | acceptance-contract-projections.yaml §AC-REQ-003-01 | inherited-fixed |
| 单模块 AC | AC-REQ-006-01 不在 shared 清单（全量盘点仅 4 条跨模块契约）；REQ-006 归属 MOD-03，为单模块契约，由 derive 直接投影为 D-AC-REQ-006-01 | acceptance-contract-projections.yaml §全量盘点结论 | inherited-fixed |
| 成功指标 | MOD-03 无 SM 分配（支撑能力，已含于 SM-001 链路 REJECTED_MEMBERSHIP 统计） | 01 §modules_without_sm_allocation | inherited-fixed |

### 2.3 契约与外部边界

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 提供契约 | CT-003 课程归属校验（Consumer MOD-02，同步）；CT-013 名单导入（Consumer 教师浏览器/名单文件，同步） | 04 §CT-003/CT-013、§组件接口卡 | inherited-fixed |
| 消费/发布 | `consumes_api: []`、`consumes_events: []`、`publishes_events: []` | 04 §组件接口卡 | inherited-fixed |
| 内部只读边界 | MOD-05 经 FLOW-011 只读引用课程结束时间（`internal_read`，无网络契约） | 02 §FLOW-011、04 §组件接口卡 `internal_read_by` | inherited-fixed（机制 inherited-refinable） |
| 外部系统 | 课程名单来源：文件导入/手工录入，Adapter 归 MOD-03；首版教师手工维护（A-002），外部系统对接暂缓 | 01 §外部系统边界、README §暂缓事项 | inherited-refinable（C5：未来接入落在本节点 Adapter 内部） |
| 相关父运行流 | FLOW-003（CT-003，同 DU-2 进程内低延迟调用）；SCENARIO-001 seq 2；DF-1 步骤 4–5（F1-4）；DF-3 步骤 1（课程结束时间只读引用） | 02 §合法数据流/场景链路/Domain Flow 追溯表 | inherited-fixed |
| 认证与通用约定 | `/api/v1` 前缀；CT-013 使用教师账号会话；AUTH_INVALID 适用全部 API 契约；写操作幂等；认证端点 `POST /api/v1/auth/token` 由 MOD-02 提供，名单核对语义同 CT-003 | 04 §通用约定 | inherited-fixed |

### 2.4 继承决策、技术与约束

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| KD-002 | 同组服务共部署；结构化元数据存于单一关系型数据库；异步任务与 Outbox 持久化于数据库 | 05、03 §存储形态 | inherited-fixed |
| KD-003 | 基础级运维：单地域、HTTPS + 存储加密、每日备份保留 30 天、基础监控告警 | 05、06 | inherited-fixed |
| KD-005 | 令牌认证 + 客户端幂等键 + `/api/v1` 版本前缀 | 05、04 §通用约定 | inherited-fixed |
| A-002 | 名单首版教师维护；名单外部系统对接暂缓至后续版本（触发条件：学校名单服务可用） | 01 §外部系统边界、README §暂缓事项 | inherited-fixed（触发后经 C5 在管理子节点内落地） |
| 数据库产品选型 | defer_to_detail_design，仅要求支持事务与备份 | 05 §暂缓到详细设计 | delegated（继承至下一层/详细设计） |

### 2.5 状态与数据所有权

- **Course 聚合归 MOD-03**：课程、邀请码、名单（姓名+小组）、课程结束时间（03 §数据所有权）。
- 本地事务边界：名单/小组变更与课程一致性；不变量：**邀请码唯一映射课程；姓名+小组命中名单才通过校验**（03 §Aggregate 到数据边界映射）。
- 跨边界：Course → 保留治理为只读引用（课程结束时间变更频率极低，批处理时读取最新值；03 §跨边界一致性策略）。
- 父层未列出「校验记录」状态；CT-003 `side_effects` 要求「记录校验结果（通过/拒绝原因）」，其状态模型属本层 inherited-refinable 内部细化，所有权仍在 MOD-03 内（03-state-and-data §1），不触碰任何兄弟聚合。

### 2.6 委托与未解决项

| 条目 | 处置 | 说明 |
|---|---|---|
| 数据库产品选型 | delegated → 详细设计（继承父层暂缓） | 仅要求事务 + 备份 |
| 名单外部系统对接 | delegated → 后续版本（A-002 触发条件） | 触发后经 C5 在 CMP-COURSE-ROSTER-ADMIN 内新增 Adapter，不改变本层结构 |
| 拒绝原因编码枚举、名单文件格式与冲突判定细则、邀请码生成规则 | delegated → 下一层组件设计 | 父契约只规定字段存在性与语义，未规定取值细节 |
| **阻塞缺口** | **无** | 关键父状态/契约/部署/决策全部可得；当前 PRD 不要求改变父边界 |

## 3. 当前 PRD 需求分配

分类口径：`inherited`（父层已定，本层原样遵守）/ `allocated`（父层分配给本节点，需本层结构设计承接）/ `local`（本层内部细节）/ `out-of-scope`（不属于本节点）。

| 当前需求 | 分类 | 父层追踪 | 本子层承接（子节点见 02） |
|---|---|---|---|
| REQ-D001 用邀请码+名单+提交中的姓名和小组校验课程归属 | allocated | REQ-005 / FR-005；CT-003；F1-4；DF-1 步骤 4–5 | CMP-MEMBERSHIP-VERIFIER（CMP-COURSE-ROSTER-ADMIN 仅为内部名单提供方） |
| REQ-D002 学生修改姓名或小组后每次提交重新校验 | allocated | REQ-006 / FR-006；CT-003 幂等条款（每次必须重新调用，不得缓存通过结论）；F1-4 | CMP-MEMBERSHIP-VERIFIER（每次调用直读当前名单、写入独立校验记录） |
| D-AC-REQ-003-01（shared 的 MOD-03 slice） | allocated | contract_projection: MOD-03:shared；acceptance-contract-projections.yaml §AC-REQ-003-01 | 运行流 R1/R2（04）；CMP-MEMBERSHIP-VERIFIER |
| D-AC-REQ-006-01 | allocated | parent_acceptance_contract: AC-REQ-006-01（MOD-03 单模块契约投影） | 运行流 R1/R2/R3（04）；CMP-MEMBERSHIP-VERIFIER（ADMIN 仅提供当前名单） |
| 30 秒接收确认路径 / 30 并发 | inherited | NFR-003、NFR-002；CT-003 位于 CT-001 同步路径（FLOW-003 注释：同 DU-2 进程内低延迟调用） | CMP-MEMBERSHIP-VERIFIER 校验战术（LCD-002：毫秒级本地直读，无远程调用） |
| 单一关系型数据库 / HTTPS / 存储加密 / 教师会话 | inherited | KD-002、KD-003、KD-005 | 两子节点共用 DU-2 平台能力（03 §2） |
| 成功指标（无分配） | inherited | 01 §modules_without_sm_allocation | 本层无统计义务；校验结论统计口径支撑 SM-001 链路 REJECTED_MEMBERSHIP（04 §5 可观测注记） |
| out-of-scope | — | 无 | 当前 PRD 全部需求均在 MOD-03 边界内；无错分给兄弟节点的条目 |

说明：① 当前 PRD「架构输入契约」继承 `../../L0-root/architecture/01-system-overview.md`、`03-data-and-consistency.md` 与 `04-interface-contracts.md`；本层不新增系统边界、外部依赖或跨模块约束。② PRD `implementation_surfaces` 含 `frontend`，该面落在兄弟节点（MOD-01 插件设置页修改姓名/小组、MOD-05 教师端名单维护界面）；本节点无自有前端组件，仅承接 `domain_logic` 与 `integration_wiring`。

## 4. 局部驱动（Local Drivers）

1. **同步热路径低延迟**：CT-003 位于 CT-001 接收确认（30 秒，NFR-003）与认证签发的同步路径上，30 并发提交（NFR-002）下须为毫秒级本地判定，不得在校验路径引入远程调用。
2. **不缓存通过结论 + 每次独立记录**（REQ-006、CT-003 幂等条款、D-AC-REQ-006-01 oracle「本次提交存在独立的校验时间/校验记录」）：每次调用直读当前名单并产生新校验记录，服务方与调用方均不得复用旧结论。
3. **名单数据当前性**：学生修改姓名/小组后、教师修改名单后，下一次校验立即按当前已提交状态判定（D-AC-REQ-006-01 response/boundaries：仅改姓名、仅改小组、两者同改均触发重新校验）。
4. **失败可重试且不泄露内部**：名单存储故障映射为 ROSTER_UNAVAILABLE，不向客户端暴露内部细节；消费方保持待校验并重试（CT-003 Error/Timeout 语义；D-AC-REQ-006-01 exceptions「记录可重试原因」）。
5. **审计与授权留痕**：校验结论逐条记录（CT-003 side_effects）；CT-013 课程范围授权失败返回 FORBIDDEN 并记录 AccessDeniedLogged（04 §错误码汇总）。
6. **实现面**：`domain_logic`（校验策略、名单管理）+ `integration_wiring`（CT-003/CT-013 HTTP 端点）；无前端（见 §3 说明②）。

## 5. 可复用能力

- 父包已固化的契约语义（CT-003/CT-013 字段、错误码、幂等、版本），本层直接做 provider 侧实现映射，不重新设计协议。
- 验收契约投影（AC-REQ-003-01 MOD-03 slice）已给出本节点判据，可直接映射到子节点与运行流。
- DU-2 平台能力：共享单一关系型数据库、教师账号会话鉴权、HTTPS 与存储加密、基础监控（KD-002/003/005），本层直接使用，不另建基础设施。

## 6. 拟创建/更新文件

`architecture-manifest.yaml`（draft→ready_for_human_gate）、`01-design-context.md`（本文件）、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。无 `parent-change-request.md`（无 return_to_parent 项）。

## 7. 上下游契约影响

**无变更。** 本层不新增、改名、弱化或升级任何父契约；CT-003/CT-013 仅做 provider 侧实现映射；FLOW-011 保持无网络契约的 internal_read；不向兄弟节点提出新契约；不引入新外部系统与事件。PRD frontmatter `dependency_refs: [MOD-02, MOD-05, MOD-01]` 与父包数据流核对后确认：MOD-02 = CT-003 既有消费方（FLOW-003）；MOD-05 = FLOW-011 既有只读引用方（CT-013 的教师界面宿主在 MOD-05，但契约 Consumer 为教师浏览器，本节点不与 MOD-05 新建网络契约）；MOD-01 = 无直接跨边界流（学生修改姓名/小组的设置在 MOD-01，端到端链路间接相关）。均不产生本节点的新跨边界依赖，本层不为它们创建任何接口。

## 8. 交接验证方法

阶段 6 以实际证据验证：① 四必需输入解析与唯一匹配证据（已记入 manifest）；② REQ-D001/D002 与 2 条 D-AC 全部分配且有子节点承接；③ 子节点清单含追踪列且无豁免缺省；④ CT-003/CT-013 字段、owner、失败/幂等/版本语义逐字未改；⑤ Course 聚合与兄弟状态所有权未转移；⑥ 决策队列无遗留 `decide_now`、无 `return_to_parent`；⑦ 全部清单按稳定 ID 排序；⑧ 未引入新部署单元/事件/消息总线/公共运行时边界。

## 9. 假设、问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | CT-003 的消费场景含 CT-001 处理（FLOW-003）与认证端点签发（名单核对语义同 CT-003，04 §通用约定），均由 MOD-02 发起，同一契约语义 | 运行流 R1 注记（04） |
| 假设 | 「当前名单」= 调用时刻已提交（read-committed）的名单状态；名单导入与校验并发时，校验看到调用前已提交状态，两种结果均为有效「当前」 | 03 §4 并发规则 |
| 问题（非阻塞） | D-AC-REQ-006-01 exceptions 的提交状态名 `identity_validation_failed` 属 MOD-02 提交状态机的细化命名；父包 FLOW-003 表述为「保持待校验并重试」。对 MOD-03 契约语义无影响（ROSTER_UNAVAILABLE + 可重试语义不变） | 观察项 1，留 MOD-02 L1 设计核对；记入 `child-handoff.md` 未完成项 |
| 问题（非阻塞） | 课程创建/邀请码签发无父级公共契约，当前 PRD 亦无对应需求 | LCD-004（v1 运维预置）；未来教师自助建课需 return_to_parent |
| 问题（非阻塞） | 课程级数据（名单/校验记录）的保留清除无父级契约（DF-3 仅覆盖提交数据） | LCD-005 本地对齐「课程结束+1 年」；观察项 3 |
| 显式不发明 | 「课程已结束的提交是否应拒绝」父包未定义该策略，本层不增设课程状态判定 | 登记为开放问题；如需该策略应由父层决策 |
| 冲突 | 无 | dependency_refs 差异已在 §7 解释 |
