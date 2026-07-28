# 05 Local Decisions — SI-CORE submission-core L2

> 本文件只记录 SI-CORE 内部结构选择。父层决策明确标记为 inherited；会改变父边界、公共契约、数据所有权、技术平台或部署边界的事项禁止在本层决定。

## 1. 局部决策队列结果（按稳定 ID 排序）

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Decision Status | Follow-up Target |
|---|---|---|---|---|---|---|---|
| LCD-SIC-001 | L1 02/04 | IC-SI-04、IC-SI-05、INV-5 | 02 decomposition；04 runtime | 父层规定“同事务写入”，但未决定由聚合、命令处理器还是事件溯源承载组合提交 | `decide_now` | decided | SI-CORE-TX 详细事务边界 |
| LCD-SIC-002 | L2 PRD acceptance | REQ-DD002、REQ-DD004、INV-3/5 | 02 local semantics；03 state | 父层要求清单/报告同提交，但未决定报告是否成为独立聚合或读模型 | `decide_now` | decided | SI-CORE-INTEGRITY 详细报告模型 |
| LCD-SIC-003 | L1 CT-002 | CT-002、ST-01 | 04 IC-SIC-03；03 read consistency | 父契约定义只读查询，但没有要求独立读模型；需选择一致读方式 | `decide_now` | decided | SI-CORE-AGG 详细查询端口 |
| LCD-SIC-004 | L1 state rules | INV-2、LCD-003 | 02 transition guards | 父层定义可观察状态序列，但本层需决定 ack、评分回写和清除回写是否都走同一聚合守卫 | `decide_now` | decided | SI-CORE-AGG 详细守卫表 |
| LCD-SIC-005 | L2 PRD / parent defer | ST-01、KD-002 | 03 storage intent | 数据库产品/索引/ORM 选择会影响实现，但不影响本层边界 | `defer_to_next_level` | deferred | SI-CORE-TX：详细持久化设计；父数据库产品决策仍需先就绪 |
| LCD-SIC-006 | L2 PRD | REQ-DD002、IntegrityReport | 02/04 | 类别排序、报告字段内部规范和 Integrity 错误码映射不改变系统级结构；TX 边界错误码与操作绑定必须可验证 | `defer_to_next_level` | deferred | SI-CORE-INTEGRITY：类别规范化、报告字段和错误映射；SI-CORE-TX：继续遵守 04 的操作级绑定 |
| LCD-SIC-007 | L2 runtime | IC-SIC-04 | 04/05 | 事务重试/锁定的具体框架配置属于实现细节，不应在架构包中固化 | `implementation_detail` | not_architecture_level | 实现阶段；遵守 INV-5 和父重试语义 |

无 `return_to_parent` 项。当前 PRD 的待补充架构输入不构成父边界变更请求，因为父 L1 包已经锁定本节点的边界、契约和所有权。

## 2. LCD-SIC-001：事务协调者的局部结构

### 问题来源

- Source Artifact: L1 `02-architecture-decomposition.md`、`04-contracts-and-runtime.md`
- Source ID: `IC-SI-04`、`IC-SI-05`、`INV-5`、`KD-002`
- Affected Output: `02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`

### 为什么普通映射不够

父层只固定了“状态 + 材料清单 + 完整性报告 + Outbox 同一事务”，没有规定组合提交的内部责任。若各命令自行提交，会产生部分状态或孤立 Outbox；若采用事件溯源，则会引入父层未授权的新持久化语义。

### 候选方案

| Candidate | Benefits | Costs / Risks | Best Fit |
|---|---|---|---|
| A. 聚合自行完成所有持久化和 Outbox | 代码路径短 | 聚合被基础设施污染，文件元数据和 Outbox 适配混入领域对象 | 不选 |
| B. `SI-CORE-TX` 作为本地事务协调者，调用聚合/完整性端口并写父 Outbox | 保持聚合纯度；显式保证单事务；不新增平台/部署边界 | 需要定义稳定内部端口 | **选定** |
| C. 事件溯源聚合 | 可追踪事件历史 | 改变父存储意图、查询/删除和保留语义，超出本层授权 | 不选 |

### 决策

选择 B。`SI-CORE-TX` 负责当前进程内事务组合，`SI-CORE-AGG` 负责状态语义，`SI-CORE-INTEGRITY` 负责清单/报告语义，父 Outbox 仍由 SI-RELAY 拥有。

## 3. LCD-SIC-002：完整性报告建模

### 候选与决策

| Candidate | 结果 |
|---|---|
| 独立 Integrity 聚合/独立读模型 | 拒绝；会引入额外一致性边界，且父层要求报告与 Submission 同事务 |
| Submission 内的 `IntegrityReport` 值对象，由 SI-CORE-INTEGRITY 构建 | **选定**；报告与材料清单同一事务生成，缺失项不阻塞 received |
| 在 SI-STORE 中生成报告 | 拒绝；SI-STORE 只提供元数据，不拥有完整性业务判断 |

## 4. LCD-SIC-003：CT-002 查询方式

选择 Submission 一致读端口，不新增读模型。原因：CT-002 是父层定义的只读查询，返回字段全部属于 ST-01；独立读模型会增加同步/保留/删除边界，不被当前需求或父决策授权。查询由 `SI-CORE-AGG` 语义拥有，经 `SI-CORE-TX` 使用已提交快照访问。

## 5. LCD-SIC-004：所有状态回写统一走聚合守卫

选择 `AdvanceToProcessing`、`ApplyScoringOutcome`、`PurgeSubmission` 全部进入 `SI-CORE-AGG` 的同一状态迁移守卫。这样可保证：

- CT-004 ack 只能把 `received` 推到 `processing`；
- CT-005 只能从 `processing` 写入两个评分终态；
- CT-012 的单项清除可以幂等地把存续状态推进到 `deleted`；
- 重复回写不会绕过 INV-2 或重复创建副作用。

## 6. 继承决策（本层不重开）

| Parent Decision | 继承内容 | 本层落点 |
|---|---|---|
| KD-002 | DU-2 同组/进程内部署、单库 Outbox、无限投递重试 | TX 只做同事务写入；SI-RELAY 投递 |
| KD-003 | HTTPS、存储加密、备份和基础监控 | 本层不新增安全/运维平台 |
| KD-004 | 500MB、类型白名单、200GB/课程配额 | 文件和配额由 SI-STORE/SI-XFER；本层只接受已验证元数据 |
| KD-005 | submission_uuid 幂等、分片续传、`/api/v1` | 本层落实 UUID/命令幂等；不处理端点 |
| LCD-002 | CT-006 在 received 或 upload_failed 发布，schema 不变 | TX 两条命令均按此写 Outbox |
| LCD-003 | CT-004 task_persisted 后推进 processing | AGG 状态守卫固定此前置条件 |

## 7. 父层决策禁止项

本层不决定或不修改：新服务/容器/部署单元、数据库产品、消息总线、缓存平台、公共 API、跨模块事件字段/版本、父状态值域、MOD-02 或兄弟模块数据所有权、保留期限计算、MOD-04/MOD-05 内部结构。若未来需求要求上述变化，必须建立 `parent-change-request.md` 并返回父层。
