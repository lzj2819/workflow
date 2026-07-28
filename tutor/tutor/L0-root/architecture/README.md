# Architecture Package — Vibe Coding 课程评估系统顶层架构

## 架构包范围

基于已批准 PRD(`prd/L0/vibe-coding-course-prd.md`,schema 2.0）生成的顶层（L0）系统架构：5 个 Module、14 个接口/事件契约、3 个部署单元、5 项已确认关键架构取舍。本包可作为 L1 模块细化（recursive-architecture-design）的父包。

## 交付输入/输出清单

**实际使用的输入：**

| 输入 | 路径 | 状态 |
|---|---|---|
| PRD | `prd/L0/vibe-coding-course-prd.md` | approved,agent_review_passed |
| DDD 产物 | `architecture/FR.md`、`ubiquitous-language.md`、`domain-events-catalog.md`、`bounded-contexts.md`、`aggregates.md`、`context-map.md`、`domain-flow.md` | 本次生成 |
| 假设登记 | `architecture/assumptions.md`(A-001~A-007) | 本次生成 |
| 授权决策 | KD-001~KD-005，用户 Human Gate 确认（2026-07-17) | 已确认 |
| 映射工作文件 | `architecture/architecture-workbench.md` | 本次生成（过程文件，非交付阅读入口） |

**实际生成的输出：**

- `output/README.md`（本文件）
- `output/01-system-overview.md`
- `output/02-runtime-architecture.md`
- `output/03-data-and-consistency.md`
- `output/04-interface-contracts.md`
- `output/05-decisions-and-technology.md`
- `output/06-deployment.md`
- `output/acceptance-contract-projections.yaml`（跨模块验收契约处置声明，2026-07-18 补交：解除 derive 生成 L1 子 PRD 的完整性门禁阻塞；AC-REQ-003-01、AC-REQ-007-01、AC-REQ-008-01、AC-NFR-003-01 声明为 shared,AC-NFR-004-01 登记为 module_local + 执行依赖）

## 本包状态

- 架构范围：PRD 全部 12 条 REQ 与 4 条 NFR 均已映射至 Module 与契约（见 01 模块清单追踪）;3 条 Success Metric(SM-001~003）已显式分配 Owning Module（见 01「Success Metric 分配」)。
- 系统级关键取舍 KD-001~KD-005 全部经用户确认并沉淀于 `output/05-decisions-and-technology.md`,Key Decision Queue 无遗留 `decide_now` 项。
- 当前可进入的下一阶段：L1 模块详细设计（以 `target_node_id` = MOD-01~MOD-05 之一 + 该模块范围 PRD 调用 recursive-architecture-design)；或直接进入实施规划。

## 建议阅读路径

- 业务/产品负责人：`01-system-overview.md`（目标、范围、模块职责）→ 本 README 的「暂缓与跟踪事项」。
- 架构/技术负责人：`05-decisions-and-technology.md` → `02-runtime-architecture.md` → `03-data-and-consistency.md` → `06-deployment.md`。
- 模块详细设计人员：目标 Module 在 `01` 中的职责与追踪 → `04-interface-contracts.md` 中该 Module 提供/消费的契约 → `03` 中其数据边界。

## 关键架构结论

1. 五 Module:codex-plugin（学生侧）、submission-intake、course-roster、assessment、teacher-web(01)。
2. 同步上传确认（30 秒）+ 异步评分（10 分钟，Outbox 事件驱动）+ 教师端读模型（02、03)。
3. 服务端仅 2 个部署单元：course-app(MOD-02/03/05)+ assessment-worker(MOD-04)，同组共部署存储与任务设施（06,KD-002)。
4. Agent 评估经 ACL 调用外部模型 API(KD-001)；失败自动重试一次，再失败标记并通知教师，不伪造等级（02,DF-2)。
5. 数据保留 1 年，教师确认删除，审计记录独立留存（03、06,DF-3)。

## 已确认关键取舍摘要

| Decision ID | 结论 | 详见 |
|---|---|---|
| KD-001 | 外部模型 API + ACL | 05 |
| KD-002 | 同组服务共部署 + Outbox 事件 | 05、06 |
| KD-003 | 基础级运维（单地域/加密/每日备份/RPO 24h) | 06 |
| KD-004 | 500MB 单次上限、类型白名单、200GB/课程 | 04、06 |
| KD-005 | 令牌 + 幂等键 + 分片续传 + /api/v1 | 04、05 |

## 暂缓事项摘要

| 事项 | 原因 | 后续负责阶段 | 触发条件 |
|---|---|---|---|
| 数据库产品选型 | 不影响系统级结构（defer_to_detail_design) | 详细设计 | DU-2 实施启动 |
| 教师前端渲染技术、展示视图导出格式 | 局部实现选择（defer_to_detail_design) | 详细设计 | MOD-05 详细设计 |
| 教师通知渠道扩展（邮件/IM) | 首版端内通知（A-005) | 后续版本 | 教师提出渠道需求 |
| 调整等级是否强制填写理由 | PRD 列为可选产品决策 | 独立 review / 实现阶段 | 产品决策补充 |
| 名单外部系统对接 | 首版教师维护（A-002) | 后续版本 | 学校名单服务可用 |

## 后续工作的输入

- **L1 模块详细设计**：以本包 `01` 的模块职责、`04` 的契约、`03` 的数据边界为父级约束；不得无来源推翻已确认边界与 KD 决策，确需调整时回溯至对应 DDD 产物、`architecture-workbench.md` 映射记录或 `05` 的决策记录。
- **实施规划**：以 `06` 的部署单元与 `04` 的契约为输入。
- **部署规划**：以 `06` 与 KD-003 运维等级为输入。

## 跨模块接口请求与兼容性影响

本次为新建架构包，未发现需要改变既有上游输入、下游消费格式或外部契约语义的变更；无未确认的跨模块接口请求。14 个契约（CT-001~CT-014）均为本次新定义，状态为已生效设计。2026-07-18 依据 validate-arch 报告（tutor-vibe-coding-course-failed-fixed-20260717-002）修订：CT-007 增加删除批次可读出参、新增 CT-014 PurgeCompleted 清除结果回流、CT-010 增加 request_id 与数据最小化约定、补齐 SCENARIO-012/016 机器可读场景链路。

## 实际验证证据与未完成项

**实际执行的检查及结果：**

| 检查 | 结果 |
|---|---|
| DDD 产物完整性（7 个文件 + assumptions) | 通过，全部生成且 FR 可追溯 PRD 编号 |
| DDD 一致性回检（事件有发布/消费方、聚合归属 BC、术语一致、无孤立 BC) | 通过，见 `domain-flow.md` 回检表 |
| workbench 六类映射（M1~M6）完整 | 通过 |
| Key Decision Queue 无未完成 decide_now | 通过,KD-001~005 全部 decided（用户确认） |
| 最终输出仅 `output/` 下 7 个文件，未生成 ADD 过程包 | 通过（2026-07-18 补交 `acceptance-contract-projections.yaml` 后为 8 个文件） |
| 接口契约硬性字段（contract_id/contract_type/side_effects/dependencies 等 13 项） | 通过，CT-001~CT-014 逐条齐备；查询契约 side_effects 均为 `None; read-only` |
| Module 稳定 module_id(MOD-01~05）与 Requirement/FR 追踪 | 通过，无 trace_exemption 缺省（所有 Module 均有需求来源） |
| 带 ID 清单按稳定 ID 排序 | 通过（MOD、CT、KD、FR 均按编号排序） |
| 图中元素可追溯（DDD 产物/映射/已确认决策） | 通过，图注标注 KD 编号与契约编号 |

**未完成项及影响：**

- 无阻塞项。暂缓事项均为 defer_to_detail_design 或 PRD 声明的可选补充决策，已在「暂缓事项摘要」显式登记，不影响本包进入 L1 详细设计。
