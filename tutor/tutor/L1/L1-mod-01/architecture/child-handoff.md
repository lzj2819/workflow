# Child Handoff — MOD-01 codex-plugin（L1 → L2 交接）

> 本文件是下一层（L2 组件细化）的唯一入口。Human Gate 批准后，以 `[NEXT child_id]` 选择下表任一子节点继续递归细化。

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 节点 | `MOD-01 codex-plugin`（L1，DU-1 student-plugin，学生本机 Codex 环境） |
| 职责 | 识别自然语言提交意图；管理插件配置；采集完整对话与材料；分片上传；展示提交编号与失败原因；断网保留本地待上传任务 |
| 排除项 | 无服务端契约；不归属校验；不持有 Submission；不参与评分/教师端 |
| 父包 | `architecture/L0/output`（顶层 DDD 到系统架构包）；匹配证据与边界指纹见 `architecture-manifest.yaml` |
| 绑定决策 | KD-003（HTTPS）、KD-004（500MB/白名单）、KD-005（令牌+幂等键+分片续传+/api/v1）、A-007（队列机制 implementation_detail） |
| 验收绑定 | AC-REQ-001-01、AC-REQ-002-01（MOD-01 单模块）；AC-REQ-003-01 shared 的 MOD-01 slice；SM-001 contributing |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| CMP-CONFIG-STORE | 插件配置持久化与校验 | 配置 schema 演进与原子保存实现；目录可读性检查时机 | REQ-D002；D-AC-REQ-002-01 |
| CMP-DIALOGUE-COLLECTOR | 完整 Codex 对话导出（采集侧 ACL） | **宿主 Codex 环境对话导出机制确认**（父层未规定，见 §6 未解决项）；导出物格式与完整性校验 | REQ-D003；AC-REQ-003-01 MOD-01 slice |
| CMP-INTENT-PARSER | 指令解析与确定性缺项校验 | 提取机制实现（LCD-001 闸门语义固定，提取为 implementation_detail） | REQ-D001；F1-1 |
| CMP-MATERIAL-COLLECTOR | 三类目录材料收集与清单 | 遍历/过滤/预算统计实现；manifest schema | REQ-D004；KD-004 |
| CMP-PENDING-QUEUE | 本地任务队列与状态机 | **LCD-005 恢复调度触发机制**；持久化机制选型（LCD-004，A-007）；状态机迁移实现 | REQ-D001；KD-005 |
| CMP-STATUS-PRESENTER | 学生侧状态与错误展示 | 展示文案与交互形式（不改变展示数据源与「不伪造结论」规则） | REQ-D001/D002 展示面 |
| CMP-UPLOAD-CLIENT | CT-001/CT-002 consumer 实现 | 分片协议状态机与 checkpoint 对账细节；令牌缓存（LCD-006） | CT-001/CT-002；KD-003/005 |

无 `trace_exemption_reason`：全部子节点均有直接需求或父层追踪（追踪豁免数 = 0）。

## 3. 契约清单（继承 + 内部）

**继承契约（实现 consumer 侧，语义不可变）**：CT-001（含 auth/token 附属）、CT-002 —— 字段、失败、幂等、版本以 `architecture/L0/output/04-interface-contracts.md` 为准。

**内部契约（限定 MOD-01 内，按 ID 排序）**：

| 契约 ID | 名称 | Owner → Consumer |
|---|---|---|
| IC-M01-01 | 意图解析端口 | INTENT-PARSER → PENDING-QUEUE |
| IC-M01-02 | 配置端口 | CONFIG-STORE → 各读取方 |
| IC-M01-03 | 采集编排端口 | PENDING-QUEUE → DIALOGUE/MATERIAL-COLLECTOR |
| IC-M01-04 | 上传执行端口 | UPLOAD-CLIENT ↔ PENDING-QUEUE |
| IC-M01-05 | 状态展示端口 | PENDING-QUEUE / CONFIG-STORE → STATUS-PRESENTER |

字段、错误、幂等语义详见 `04-contracts-and-runtime.md` §3；L2 细化不得把内部契约提升为跨模块契约（任何跨模块需要 → return_to_parent）。

## 4. 状态所有权清单

| 状态 ID | 状态 | Owner |
|---|---|---|
| ST-01 | PluginConfig | CMP-CONFIG-STORE |
| ST-02 | 对话导出物（随任务） | CMP-DIALOGUE-COLLECTOR |
| ST-03 | MaterialManifest + 材料暂存引用 | CMP-MATERIAL-COLLECTOR |
| ST-04 | PendingTask 记录（含 submission_uuid、状态机、失败原因） | CMP-PENDING-QUEUE |
| ST-05 | UploadCheckpoint | CMP-UPLOAD-CLIENT |

关键不变量：INV-1 缺项不产生网络调用；INV-2 uuid 全程不变；INV-3 无效配置不覆盖；INV-4 采集快照重传不重采；INV-5 checkpoint 只记已确认分片（详见 `03-state-and-data.md` §4）。

## 5. 决策继承、本地决定与委托

- **继承（inherited-fixed）**：KD-003/004/005、A-007、DU-1 部署形态、CT-001/CT-002 全部语义。
- **本层已决定**：LCD-001（确定性缺项闸门）、LCD-002（创建即快照）、LCD-003（客户端预检+服务端权威）。
- **委托下一层**：LCD-005（恢复调度触发 → CMP-PENDING-QUEUE）。
- **implementation_detail**：LCD-004（持久化机制）、LCD-006（令牌缓存）、意图提取实现。

## 6. 未解决项与风险

| 事项 | 影响 | 建议 |
|---|---|---|
| 宿主 Codex 环境对话导出 API 父层未规定（仅「进程内集成+本机文件读取」） | 不影响本层结构；影响 CMP-DIALOGUE-COLLECTOR 的 L2 实现选型 | 下一层细化该节点时先确认宿主导出能力；若宿主无可用导出机制且需新外部依赖，回到本层乃至父层（return_to_parent）评估 |
| 指令与配置姓名/小组不一致的口径 | 已按「以当次指令为准」记录（LCD-001 后果）；服务端 CT-003 为最终权威，拒绝经 rejected 正常呈现 | 无需升级；如产品希望强制一致，属 PRD 变更而非架构问题 |

## 7. 推荐下一步

1. **首选 `CMP-PENDING-QUEUE`**：承载断网保留/恢复续传核心生命周期与 LCD-005 委托项，是 SM-001 contributing 链路的本地枢纽。
2. 次选 `CMP-UPLOAD-CLIENT`：分片协议与 checkpoint 对账是集成风险最高点（integration_wiring）。
3. `CMP-DIALOGUE-COLLECTOR`：需先落实 §6 的宿主导出机制确认。

所需祖先上下文：本包全部 7 个文件 + 父包 `04-interface-contracts.md`（CT-001/CT-002 全文）与 `02-runtime-architecture.md`（FLOW-001/002）；无需读取兄弟节点内部。

## 8. 实际输入/输出、验证证据与未完成项

**实际解析输入**：

| 输入 | 路径 | 状态 |
|---|---|---|
| parent_architecture | `architecture/L0/output`（8 个文件全读） | 顶层 DDD 到系统包，已识别 |
| target_node_id | `MOD-01` | 唯一匹配（证据见 manifest） |
| current_prd | `prd/L1/L1-mod-01/prd.md` | 已读（REQ-D001~D004 + 3 条 D-AC） |
| parent_prd（可选） | `prd/L0/vibe-coding-course-prd.md` | 已读（REQ-001~004、AC-REQ-001-01/002-01 原文） |
| output_dir | `architecture/L1/L1-mod-01` | 写入前确认为空目录 |

**实际生成输出**（7 个文件）：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`（本文件）。无 `parent-change-request.md`（无 return_to_parent）。

**实际执行的检查及结果**：

| 检查 | 结果 |
|---|---|
| 四必需输入解析 + 输出目录安全 | 通过（阶段 0 预检，目录为空无覆盖） |
| 父包类型识别与目标唯一匹配 | 通过（模块清单/接口卡/部署映射三处唯一命中 + PRD frontmatter 交叉确认） |
| 需求分配全覆盖（REQ-D001~D004 + 3 条 D-AC） | 通过（01 §3：全部 allocated/inherited，无 out-of-scope 误判） |
| 子节点清单追踪列（7 节点，含豁免列） | 通过（每节点有 REQ/父层追踪；豁免数 0） |
| 父契约语义不变（CT-001/CT-002/auth-token 字段、owner、失败、幂等、版本逐字核对） | 通过（04 §1/§6） |
| 父/兄弟数据所有权未转移 | 通过（03 §6 确认；ST-01~05 均为本机客户端状态） |
| 决策队列无遗留 decide_now / return_to_parent | 通过（05 §6） |
| 清单按稳定 ID 排序（CMP/IC/ST/LCD） | 通过 |
| 兄弟节点只引用未重设计 | 通过（02 §4 确认） |

**未完成项及影响**：

- LCD-005（恢复调度触发机制）已委托 CMP-PENDING-QUEUE 下一层，不阻塞本包交接。
- 宿主对话导出机制待确认（§6），不阻塞本层结构。
- 无阻塞项；本包内部一致，可进入一次 Human Gate。
