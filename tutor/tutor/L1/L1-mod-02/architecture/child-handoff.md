# Child Handoff — MOD-02 submission-intake L1 架构包交接

> 本文件是 L1 包的交接入口：为下一层（L2 组件细化，`[NEXT child_id]`）与 Human Gate 评审提供精确锚点。

## 节点身份与父层绑定

- **target_node_id**：`MOD-02`（submission-intake），层级 L1，部署于 DU-2 course-app（进程内组件，不独立部署）。
- **职责**：材料包接收（500MB/白名单，KD-004）；提交状态机（upload_failed/rejected/received/processing/scored/scoring_failed →deleted）；完整性报告与缺失项标记；30 秒接收确认；发布 SubmissionReceived；保留期清除执行与 CT-014 回传；auth-token 签发。
- **排除项**：不采集（MOD-01）、不持有名单（MOD-03）、不评分（MOD-04）、不做教师端与保留治理计算（MOD-05）。
- **父层绑定 / 边界指纹**：父包 `architecture/L0/output`（顶层 DDD 到系统包）；匹配证据 `01-system-overview.md` 模块清单 MOD-02 行（唯一匹配）；绑定契约 CT-001/CT-002/auth-token（provides）、CT-003（consumes_api）、CT-005/CT-012（consumes_events）、CT-004/CT-006/CT-014（publishes_events）；数据所有权 `03-data-and-consistency.md` Submission 行；决策 KD-002/003/004/005；部署 DU-2；验收切片 AC-REQ-003-01/AC-REQ-007-01/AC-NFR-003-01（owning）、AC-REQ-008-01（participating）、AC-NFR-004-01（execution_dependency）。

## 下一层 target_node_id 清单（直接 child_id；按稳定 ID 排序）

| child_id | 名称 | 一句话职责 | 建议细化焦点 | 所需祖先上下文 |
|---|---|---|---|---|
| SI-API | intake-api 接入层 | CT-001/CT-002/auth-token 端点、认证、幂等接入、30 秒编排 | 端点路由与中间件、错误码映射表、30 秒预算分解 | 父包 04 CT-001/CT-002 与错误码汇总；KD-005 |
| SI-CORE | submission-core 提交聚合核心 | Submission 聚合、状态机、完整性报告、单事务持久化 | 状态机守卫实现、事务脚本、清单/报告模型 | 父包 03 Submission 行；本包 INV-1~5、ST-01 |
| SI-XFER | upload-transfer 分片上传会话 | 会话/分片/断点续传/合并、500MB 与白名单校验 | 分片清单存储、中断检测、会话 TTL（LCD-006） | 父包 CT-001 分片协议、KD-005；本包 ST-02 |

> `SI-PURGE`、`SI-RELAY`、`SI-STORE`、`SI-VERIFY` 为内部实现支撑组件，保留在本包契约/状态台账中，但不作为下一层 target，也不得使用 `[NEXT ...]` 派发。

## 契约清单

**继承父契约（语义不变，实现映射见 `04-contracts-and-runtime.md` 第 1 节）**：CT-001、CT-002、`POST /api/v1/auth/token`（未编号附属端点）、CT-003、CT-004、CT-005、CT-006、CT-012、CT-014。

**内部契约（仅 MOD-02 内，按 ID 排序）**：

| contract_id | owner → consumer | 用途 |
|---|---|---|
| IC-SI-01 | SI-XFER → SI-API | 上传会话命令/查询（建会话/追分片/合并/中止）；字段绑定见 `04-contracts-and-runtime.md` 2.1 |
| IC-SI-02 | SI-STORE → SI-XFER/SI-CORE/SI-PURGE | 材料写入/转正式/元数据/删除/配额查询；字段绑定见 `04-contracts-and-runtime.md` 2.1 |
| IC-SI-03 | SI-VERIFY → SI-API | 归属校验（CT-003 客户端封装）；字段绑定见 `04-contracts-and-runtime.md` 2.1 |
| IC-SI-04 | SI-CORE → SI-API/SI-RELAY/SI-PURGE | 提交聚合命令与查询（含状态机守卫）；字段绑定见 `04-contracts-and-runtime.md` 2.1 |
| IC-SI-05 | SI-RELAY → SI-CORE/SI-PURGE；外部入站 | Outbox 事务写入、投递循环、入站消费路由；字段绑定见 `04-contracts-and-runtime.md` 2.1 |
| IC-SI-06 | SI-PURGE → SI-RELAY | 清除执行与结果汇总；字段绑定见 `04-contracts-and-runtime.md` 2.1 |

## 状态所有权清单（按 ID 排序）

| state_id | 状态 | owner |
|---|---|---|
| ST-01 | Submission（记录/状态机/清单/报告/失败原因） | SI-CORE |
| ST-02 | UploadSession（会话/分片清单/续传进度；含 interrupted_retryable/failed_terminal） | SI-XFER |
| ST-03 | MaterialFile（加密磁盘）+ CourseQuotaUsage | SI-STORE |
| ST-04 | OutboxRecord（pending/delivering/retry_wait/confirmed） | SI-RELAY |
| ST-05 | InboundEventDedup（received/processing/applied/retry_wait/quarantined） | SI-RELAY |
| ST-06 | AuthTokenGrant（令牌签发审计） | SI-API |
| ST-07 | PurgeExecution（清除执行记录） | SI-PURGE |

## 决策清单

- **继承（不重开）**：KD-002、KD-003、KD-004、KD-005；数据库产品选型暂缓（父包 defer_to_detail_design）。
- **本地已决定（decide_now）**：LCD-001（会话层承载待校验，外部状态机不变）；LCD-002（CT-006 在 received 与 upload_failed 终态发布，schema 不变）；LCD-003（CT-004 投递确认后推进 processing）；LCD-009（SM-001 的采集、聚合、分母排除与标签口径）。
- **委托下一层（defer_to_next_level）**：LCD-007（SI-STORE 目录布局/加密参数）、LCD-008（SI-RELAY 投递器并发/退避）。
- **实现细节（implementation_detail）**：LCD-004（令牌形态）、LCD-005（rejected 暂存清理时机）、LCD-006（会话 TTL/归档周期/轮询间隔）。
- **已解决风险**：LCD-002 的 CT-006 发布时机已在 L0 CT-001、CT-006 与 FLOW-008 中统一登记为 `received` 或终态 `upload_failed`；LCD-003 的确认语义已明确为 MOD-04 评分任务持久化确认。

## 推荐下一步

1. **Human Gate 评审本包**（重点：LCD-001/002/003/009 与 CT-006 时机说明）。
2. 批准后按 `[NEXT SI-CORE]` 优先细化聚合核心（状态机与事务是全模块锚点），随后 `[NEXT SI-XFER]`、`[NEXT SI-API]`；SI-RELAY/SI-STORE/SI-VERIFY/SI-PURGE 仅作为内部支撑随直接子节点细化。
3. 每层细化以本文件 child_id 为 `target_node_id`，祖先上下文 = 本包 + 父包 `architecture/L0/output`。

## 追踪豁免与实际输入/输出

- **直接 child_id 需求所有权**：3 个直接子节点均拥有 current `REQ-Dxxx`；4 个内部支撑组件仅保留父契约/流程/状态追踪，不作为 L2 target。
- **实际输入**：`prd/L1/L1-mod-02/prd.md`、`architecture/L0/output`（01~06 + acceptance-contract-projections.yaml）；未读取 parent_prd（父包追溯充分）。
- **实际输出**：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`（共 7 个，无 parent-change-request.md）。

## 验证检查与结果

| 检查 | 结果 |
|---|---|
| 父包识别（顶层 DDD 到系统包）与 MOD-02 唯一匹配 | 通过（01 模块清单唯一行，04 组件接口卡交叉一致） |
| 需求分配覆盖 REQ-D001~D004、NFR-002/003、SM-001，无越界、无错配兄弟 | 通过（01 需求分配表） |
| 每个直接 child_id 拥有 current REQ-D/NFR-D；内部支撑不进入 direct children | 待复验（02 直接清单与内部实现台账） |
| 父契约语义与 L0 CT-001/CT-004/CT-006/FLOW-008 一致 | 待复验（已同步 L0/L1；需重新执行 strict audit） |
| 状态机外部值域与父 AC/FLOW 终态一致（六态 + deleted） | 待复验（已补充 UploadSession、Submission、Outbox、InboundEventDedup 迁移） |
| 子节点/内部契约/状态/决策注册表按稳定 ID 排序 | 通过（SI-*、IC-SI-0x、ST-0x、LCD-00x 均有序） |
| 未新增部署单元/平台/数据库/消息总线/公共边界；未设计兄弟内部 | 通过（05 禁止项确认） |

**未完成项及影响**：文档修复已落盘，但当前工作区尚未重新执行 strict audit；在复验完成前不宣称验证通过。LCD-007/LCD-008 继续委托下一层，LCD-004~006 为实现细节。
