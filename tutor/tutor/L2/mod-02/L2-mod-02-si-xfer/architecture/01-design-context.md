# 01 Design Context — SI-XFER upload-transfer L2 设计上下文

本文件记录 SI-XFER 的输入绑定、父边界快照、当前 PRD 分配和局部架构驱动。当前层只细化 L1 `SI-XFER` 内部，不重设计 MOD-02、SI-STORE 或其他兄弟节点。

## 输入绑定

| 项 | 解析结果 |
|---|---|
| `parent_architecture` | `architecture/L1/L1-mod-02`，递归子层包，存在 `architecture-manifest.yaml` |
| `target_node_id` | `SI-XFER`，在 L1 `child-handoff.md` 的下一层清单中唯一匹配 |
| `current_prd` | `prd/L2-PRD/mod-02/L2-mod-02-si-xfer/prd.md`，status=complete，release_scope_frozen=true |
| `output_dir` | `architecture/L2/mod-02/L2-mod-02-si-xfer`，new 模式，写入前为空 |
| `mode` | `new` |
| `parent_prd` | 未读取：L1 已提供当前目标的职责、状态、契约、运行流和决策追溯 |
| `human_constraints` | 用户确认按前置设计生成；无额外边界变更授权 |

## 父边界快照

### 身份、职责和排除项

- 节点身份：`SI-XFER` / `upload-transfer`，L1 `MOD-02 submission-intake` 的直接子节点，部署于既有 DU-2 `course-app` 内。
- 职责：上传会话、分片、断点续传、合并、500MB 单次上限、类型白名单校验，并以 `IC-SI-01` 向 `SI-API` 提供会话命令和查询。
- 消费边界：通过 `IC-SI-02` 使用 `SI-STORE` 的暂存写入、正式提升、元数据和删除能力。
- 排除项：不拥有 Submission 聚合和外部提交状态机；不拥有 MaterialFile/CourseQuotaUsage；不执行名单校验；不负责 HTTP/API 编排；不负责 Outbox 或外部事件投递；不新增部署单元。

### 父层状态与所有权

| 父状态 | 绑定内容 | L2 处理 |
|---|---|---|
| ST-02 UploadSession | `receiving/interrupted_retryable/merged/pending_verification/failed_terminal`；SI-XFER 唯一拥有 | 细化为内部状态和子节点所有权；外部状态值不扩展 |
| ST-03 MaterialFile/CourseQuotaUsage | SI-STORE 拥有 | 仅通过 IC-SI-02 调用，不转移所有权 |
| ST-01 Submission | SI-CORE 拥有 | 合并成功后返回 material_refs，不在本层创建 Submission |

### 契约与运行流

| 契约/流 | 父层语义 | L2 绑定 |
|---|---|---|
| IC-SI-01 | `create_session`、`append_chunk`、`finalize`、`abort`、`get_session`；按 submission_uuid/seq/finalize 幂等 | 由 XFER-SESSION/XFER-CHUNK/XFER-FINALIZE 实现映射 |
| IC-SI-02 | `write_stage`、`promote_to_final`、`read_metadata`、`delete`、配额查询 | 由 XFER-CHUNK/XFER-FINALIZE 消费；字段和错误语义不变 |
| CT-001 | `/api/v1/submissions` 分片上传，30 秒同步确认 | SI-XFER 只实现上传会话子流程，不改变 CT-001 外部字段、错误码和副作用 |
| RF-01 | 成功：建会话→分片→合并→归属校验→SI-CORE 持久化 | 本层覆盖建会话到 merged |
| RF-02 | 中断：保留断点→恢复；耗尽后 failed_terminal→MarkUploadFailed | 本层承载中断、恢复和终止 |

## 当前 PRD 需求分配

当前 PRD 的架构输入契约四节未提供具体值，但 frontmatter 已声明继承完成，且需求通过父层映射可追溯。因此本包不凭空补造父契约，采用 L1 已确认边界。

| 当前需求 | 分类 | 父层追踪 | L2 分配 | 说明 |
|---|---|---|---|---|
| REQ-DD001：接收完整 Codex 对话材料 | allocated | REQ-D001 → REQ-003；CT-001；AC-REQ-003-01 | XFER-SESSION、XFER-CHUNK、XFER-FINALIZE | MOD-01 负责采集；本层负责分片接收、保存和最终化 |
| REQ-DD002：按插件配置接收代码/截图/结果并关联作业/姓名/小组 | allocated | REQ-D002 → REQ-004；CT-001；KD-004 | XFER-SESSION、XFER-CHUNK、XFER-FINALIZE | 类别声明和业务关联上下文由 SI-API 传入；本层保存并校验上传材料，不拥有名单数据 |
| 500MB/白名单/配额 | inherited | KD-004；IC-SI-02 | XFER-CHUNK、XFER-FINALIZE | 不改变限制值和错误映射 |
| 断点续传与幂等 | inherited | KD-005；IC-SI-01 | XFER-SESSION、XFER-CHUNK | `submission_uuid`、`seq` 和 finalize 语义不变 |
| 30 秒确认 | inherited | NFR-003；CT-001 | 本层不得阻塞恢复等待；通过短路径返回结果 | 时间预算由 SI-API 统筹，本层提供可恢复的有限工作单元 |
| 观测 | local | PRD implementation_surface=observability；SM-001 | XFER-SESSION/XFER-FINALIZE 埋点 | 仅记录上传过程指标，不改变 SM-001 owner=SI-API |
| 名单校验、提交状态机、评分、教师展示、保留期治理 | out-of-scope | L1 exclusions | — | 仅提供边界结果，不设计兄弟内部 |

## 局部驱动

1. **大文件与短同步响应**：分片必须流式处理，合并和存储操作可恢复；不把评分、名单服务恢复或长时间重试放进上传会话同步路径。
2. **并发和幂等**：同一 `session_id` 采用单写者语义；重复分片不重复写入，冲突分片显式失败；不同 submission_uuid 之间互不阻塞。
3. **文件和元数据边界**：SI-XFER 只拥有会话及分片清单；文件内容、正式引用和配额由 SI-STORE 统一管理。
4. **故障可恢复**：暂存写入失败、中断和服务重启必须保留可识别的会话进度；最终化必须可以安全重试。
5. **父契约稳定**：所有内部细化都必须投影回 IC-SI-01 的命令、状态和错误集合，不能新增外部状态值或必需字段。

## 可复用能力、缺口、拟写文件和上下游影响

### 可复用父层能力

- SI-API 的认证、幂等入口、CT-001 编排和 30 秒预算。
- SI-STORE 的加密材料存储、配额检查、暂存/正式区转换和删除接口。
- SI-CORE 的 Submission 状态机和 `MarkUploadFailed` / `ConfirmReceived` 命令。
- L1 的 KD-002 Outbox、KD-003 加密/备份、KD-004 限制、KD-005 续传约束。

### 本层缺口与处理

- 目录布局、文件名和加密算法参数：留给 `SI-STORE`，记录为 `L2D-005`，不在本层决定。
- 会话 TTL、归档周期、轮询间隔：L1 LCD-006 已分类为实现细节，本层记录实现约束，不给出平台级参数。
- L1 manifest 仍记录 strict audit 待复验：本包不冒充完成该父包审计；本包只验证自身结构和边界。

### 拟创建文件

严格创建本包七个文件：manifest、设计上下文、分解、状态数据、契约运行时、局部决策、child handoff；不创建代码、测试、部署清单或 `parent-change-request.md`。

### 上下游影响

- 对 SI-API：保持 IC-SI-01 命令/查询语义；返回会话进度、material_refs 或既有错误。
- 对 SI-STORE：调用既有 IC-SI-02；不改变其状态所有权、目录、加密和配额契约。
- 对 SI-CORE：只在最终化成功或上传终止时交付既有边界结果；不直接写 ST-01。
- 对 SI-VERIFY/SI-RELAY：无直接新契约；归属校验和事件投递仍由 L1 编排。

## 验证方法、假设和冲突

- 验证方法：检查七文件存在；manifest 输入和输出清单一致；子节点有需求/父层追踪；内部状态、契约、决策按稳定 ID 排序；grep 检查未引入新部署单元/公共契约值域；交叉确认 ST-02、IC-SI-01、IC-SI-02 所有权不变。
- 假设：当前 PRD 的 `inheritance_complete=true` 允许使用 L1 的需求和契约追踪补足空白架构输入契约；不把空白内容解释为新增授权。
- 冲突检查：未发现当前 PRD 要求修改父职责、公共契约字段、状态所有权、依赖方向、技术选择或部署方式；因此不返回父层。
