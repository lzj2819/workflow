# 05 Local Decisions — MOD-02 submission-intake 局部决策

> 本文件记录 L1 细化过程中发现的全部架构选择及其分类。分类规则：`decide_now`（本层完整性所需，比较局部方案后决定）、`defer_to_next_level`（交下一层子节点细化）、`implementation_detail`（编码/框架配置级）、`return_to_parent`（改变父边界——本次无）。决策按稳定 ID 排序。

## 局部决策队列

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-001 | 父包 04 CT-003 错误语义 / FLOW-003 | CT-003、FLOW-003 | 04-contracts-and-runtime.md RF-02 路径 B；02 SI-XFER/SI-VERIFY | 父契约只声明「保持待校验并重试、不向客户端暴露内部细节」，未规定待校验的内部承载方式与 CT-001 同步应答行为 | `decide_now` | 本文件 LCD-001 节 |
| LCD-002 | 父包 02 失败路径 / 04 CT-006 / AC-REQ-003-01 exceptions | CT-006、FLOW-001 | 04-contracts-and-runtime.md CT-006 实现映射、RF-02 路径 A | 父包同时承诺「upload_failed 教师端可见原因」与「CT-006 于提交接收后派生」，未显式规定 upload_failed 是否发布 CT-006 | `decide_now` | 本文件 LCD-002 节 |
| LCD-003 | 父包 AC-REQ-007-01 状态序列 / FLOW-004 | CT-004、D-AC-REQ-007-01 | 04-contracts-and-runtime.md RF-01；02 SI-RELAY | 父契约定义 received→processing 可观察序列，但未定义 MOD-02 侧推进 processing 的触发机制 | `decide_now` | 本文件 LCD-003 节 |
| LCD-009 | 父包 SM-001 / AC-NFR-003-01 | SM-001、NFR-003 | 04-contracts-and-runtime.md 可观测性说明；SI-API | 父包给出成功率目标，但 L1 未定义采集 owner、分子、分母、窗口、标签和查询方式 | `decide_now` | 本文件 LCD-009 节 |
| LCD-004 | KD-005 / 04 通用约定 | auth-token 端点 | 02 SI-API；03 ST-06 | 令牌具体形态（签名令牌 vs 不透明令牌 + 服务端存储）不影响本层结构 | `implementation_detail` | 实现阶段：短 TTL 签名令牌 + ST-06 签发审计 |
| LCD-005 | AC-REQ-003-01 rejected 语义 | CT-001 | 04 RF-01 分支；03 ST-02 | rejected 提交的暂存材料清理时机（立即 vs 定期）不影响架构 | `implementation_detail` | 实现阶段：会话 failed 后按 TTL 清理暂存 |
| LCD-006 | 03 ST-02 生命周期 | UploadSession | 03-state-and-data.md | 会话记录保留 TTL、Outbox 归档清理周期、投递器轮询间隔 | `implementation_detail` | 实现阶段随运维参数确定 |
| LCD-007 | 03 ST-03 存储意图 | MaterialFile | 03-state-and-data.md | 磁盘目录布局、文件名规范、加密算法参数（在 KD-003 存储加密约束内） | `defer_to_next_level` | SI-STORE 详细设计（`[NEXT SI-STORE]`） |
| LCD-008 | 04 IC-SI-05 投递循环 | OutboxRecord | 04-contracts-and-runtime.md | 投递器并发度、批量大小、退避曲线 | `defer_to_next_level` | SI-RELAY 详细设计（`[NEXT SI-RELAY]`） |

无 `return_to_parent` 项：CT-006 的触发条件曾存在父包歧义，现已在 L0 `04-interface-contracts.md` 与 `02-runtime-architecture.md` 同步固化；本 L1 包不再保留未解决的父层契约扩展。

## decide_now 决策详情

### LCD-001 ROSTER_UNAVAILABLE 的待校验承载方式

**问题**：CT-003 超时/不可用时，父契约要求「提交保持待校验状态并重试；不向客户端暴露内部错误细节」。父状态机没有「待校验」外部状态，CT-001 同步应答语义（received/rejected）无法覆盖此情形。

| 方案 | 内容 | 评估 |
|---|---|---|
| A. 同步长重试直至应答 | 在 30 秒预算内持续重试 CT-003，成功则正常应答 | 名单服务故障时必然超预算，且阻塞 30 并发下宝贵的连接资源；超时后仍无承载状态 |
| B. 新增外部状态值（如 verifying） | CT-002 可见第七态 | **改变父契约状态机值域**（inherited-fixed），可能破坏 MOD-01/MOD-05 对未知值的处理——实质为 return_to_parent，拒绝 |
| **C. 会话层承载待校验（选定）** | 提交记录在校验通过前不创建；上传会话转 `pending_verification`（材料保留），30 秒预算内有限快速重试后返回暂态失败；SI-XFER 后台有限重试 CT-003，恢复后继续 RF-01；客户端按 CT-001 既有约定「30 秒超时未确认 → CT-002 查询/同幂等键重发」驱动 | 外部语义零变化：客户端只看到延迟与既有暂态失败；「保持待校验并重试」由 ST-02 会话与后台重试承载；幂等键保证重发不产生重复提交 |

**决定**：采用方案 C。**后果**：提交未成立期间 CT-002 返回 NOT_FOUND（语义=提交未成立，与父契约「未知 UUID → 404」兼容；客户端行为已由父契约 CT-001 错误语义规定）；后台重试次数/间隔为 implementation_detail；若重试最终耗尽，会话转 `failed_terminal`，再由 SI-CORE 写入 `upload_failed` 并发布 CT-006 可见性事件。

### LCD-002 upload_failed 终态的 CT-006 发布

**问题**：父包 02 失败路径与 AC-REQ-003-01 exceptions 均要求「upload_failed，教师端可见原因」；教师端可见性的唯一机制是 MOD-05 读模型 ← CT-006，因此父包必须显式声明终态 upload_failed 也触发 CT-006。

| 方案 | 内容 | 评估 |
|---|---|---|
| A. 不发布 | 严格按 Trigger 字面，仅 received 发布 | 教师端不可见 upload_failed，**直接违反父包 02 与 AC 的可见性承诺**；SM-001 统计也缺失败侧数据 |
| **B. received + upload_failed 终态均发布（选定）** | CT-006 载荷 `status` 字段承载 `upload_failed`；schema、字段、消费者、幂等（按 `submission_id` 去重）、`v=1` 全部不变 | 实现父包既有承诺；`status` 值域沿用父状态机六态（upload_failed 本在其中），无值域扩展；MOD-05 幂等去重不受额外事件影响 |
| C. 新建专用事件契约 | 如 SubmissionUploadFailed | 新增跨模块契约 = return_to_parent；为一个状态值新建契约明显过度，拒绝 |

**决定**：采用方案 B。**后果**：CT-006 发布时机 = received 与 upload_failed 终态；rejected 仍**不发布**。L0 CT-001、CT-006、FLOW-008 已同步记录该条件，因此本决策不再依赖父层默许。

### LCD-003 received→processing 的推进时机

**问题**：AC-REQ-007-01 要求状态序列 received、processing、scored/scoring_failed 依次可观察；父包未定义 MOD-02 侧何时把 received 推进为 processing。

| 方案 | 内容 | 评估 |
|---|---|---|
| A. 接收即推进 | ConfirmReceived 事务内直接写 processing | received 状态瞬逝，**违反 AC「依次可观察」**；CT-001 应答 status=received 与库内状态立即不一致 |
| **B. CT-004 任务持久化确认后推进（选定）** | SI-RELAY 收到 MOD-04 `consumer_ack=task_persisted` → `AdvanceToProcessing` | processing 语义 = 评分任务已持久化；MOD-04 宕机时提交停留 received（真实、可观察、可恢复）；重复 ack 只执行幂等状态推进，不重复创建任务 |
| C. 定时批推 | 周期性扫描 received 推进 | 引入无业务语义的延迟；MOD-04 不可用时状态虚假推进，拒绝 |

**决定**：采用方案 B。**后果**：SI-RELAY 增加「任务持久化确认 → 状态推进」回调职责（IC-SI-05 → IC-SI-04）；状态机迁移表不变（INV-2）。

### LCD-009 SM-001 接收成功率统计口径

**决定**：SI-API 负责采集有效 CT-001 请求、`received` 应答和确认耗时；基础监控负责按课程周期聚合。分母为有效提交总数，排除学生主动取消、身份校验失败和材料不完整；分子为 30 秒内返回 `status=received` 的提交数；阈值为 `>=95%`。查询通过基础监控指标面板，不新增业务 API。

## 继承决策（明确标记，本层不重开）

| 父决策 | 内容 | 本层落实 |
|---|---|---|
| KD-002 | 同组服务共部署 + 数据库 Outbox | 全部子节点为 DU-2 进程内组件；ST-04 Outbox 与业务数据同事务；不引入消息中间件 |
| KD-003 | 基础级运维（HTTPS、存储加密、每日备份、基础监控） | 材料磁盘加密（ST-03）；SM-001 埋点接入基础级监控；不新增运维设施 |
| KD-004 | 500MB 单次上限、类型白名单、200GB/课程配额 | SI-XFER 流式校验上限/白名单；SI-STORE 配额预检+终检；413/415 错误映射 |
| KD-005 | 令牌 + 幂等键 + 分片续传 + `/api/v1` | SI-API 令牌认证与签发审计（ST-06）；`submission_uuid` 幂等；SI-XFER 断点续传；端点沿用 `/api/v1` |

继承暂缓项：数据库产品选型（父包 defer_to_detail_design）本层不重开，仅要求事务 + 备份。

## 父层专属禁止项确认

- 未创建新服务/容器/部署单元/公共运行时边界（子节点均为 DU-2 内部组件）。
- 未改名/弱化/移动/升级任何父契约，未为父 API/事件增加必需字段。
- 未跨父节点或兄弟节点转移状态、公共契约或数据所有权。
- 未重选父架构风格、数据库、消息平台或技术栈；未设计兄弟模块内部。
