# Leaf Gate Override ? CMP-DIALOGUE-COLLECTOR

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-DIALOGUE-COLLECTOR（L2 → L3）

## 1. 当前节点身份与父绑定

| 条目 | 值 |
|---|---|
| 节点 | `CMP-DIALOGUE-COLLECTOR`（L2，位于 MOD-01 / DU-1） |
| 职责 | 将当前作业项目相关的完整 Codex 对话导出为 dialogue 类、可验证、不可变的本地提交材料 |
| 排除项 | 不采集其他材料；不上传；不决定提交；不做服务端校验/状态机；不新增部署边界 |
| 直接父包 | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L1\L1-mod-01` |
| 目标 PRD | `C:\Users\Lenovo\Desktop\codex_plugin\prd\L2-PRD\mod-01\L2-mod-01-cmp-dialogue-collector\prd.md` |
| 绑定状态 | L1 ST-02；本层 ST-DLG-01 / ST-DLG-02 |
| 绑定契约 | IC-M01-02、IC-M01-03、CT-001 dialogue material slice |
| 绑定决策 | KD-003、KD-004、KD-005、A-007、LCD-002、LCD-003 |
| 部署绑定 | DU-1 student-plugin；进程内组件、本机暂存 |
| boundary_fingerprint | 见 `architecture-manifest.yaml` |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| CMP-DLG-ARTIFACT-STORE | 保存、读取、终态清理不可变 DialogueArtifact | 序列化 envelope、原子写入、checksum、清理重试 | REQ-DD003；L1 ST-02；IC-DLG-004 |
| CMP-DLG-CAPTURE-COORDINATOR | 编排任务锚点、宿主读取、校验和产物保存 | 同 UUID 幂等、错误归因、阶段迁移、IC-DLG-001 | REQ-DD003；D-AC-REQ-003-01；IC-M01-03 |
| CMP-DLG-HOST-ADAPTER | 访问宿主 Codex 对话导出能力的 ACL | **确认宿主 API/能力版本、分页、截断和历史 anchor 能力** | REQ-DD003；L1 C5 委托；IC-DLG-002 |
| CMP-DLG-SNAPSHOT-VALIDATOR | 验证完整性、顺序、来源和 dialogue 类别 | completeness 证据、规范化、不可修补缺失内容 | REQ-DD003；D-AC-REQ-003-01；IC-DLG-003 |

无 `trace_exemption_reason`：4 个子节点均具有直接需求或父层追踪。

## 3. 契约清单

### 3.1 继承契约

| 契约 | 本层处理 |
|---|---|
| CT-001 | 只提供 `material_chunks[]` 的 `category=dialogue` 内容来源；字段、路径、owner、失败/幂等/版本不变 |
| CT-002 | 不参与，由 UPLOAD-CLIENT 实现 |
| auth/token | 不参与，由 UPLOAD-CLIENT 实现 |
| IC-M01-02 | 只读引用父层配置/上下文 |
| IC-M01-03 | 接收 task_ref，返回 dialogue_artifact 或 CollectionFailed |

### 3.2 L2 子契约

| contract_id | Owner → Consumer | 用途 |
|---|---|---|
| IC-DLG-001 | Capture Coordinator → PENDING-QUEUE | 采集命令与结果 |
| IC-DLG-002 | Host Adapter → Capture Coordinator | 宿主快照 ACL |
| IC-DLG-003 | Snapshot Validator → Capture Coordinator | 完整性验证 |
| IC-DLG-004 | Artifact Store → Capture Coordinator | 本地产物持久化 |

## 4. 状态与关键不变量

| 状态 | Owner | 关键约束 |
|---|---|---|
| ST-DLG-01 DialogueCaptureSession | CMP-DLG-CAPTURE-COORDINATOR | 同 UUID 至多一个 active session；记录 task_created_at anchor |
| ST-DLG-02 DialogueArtifact | CMP-DLG-ARTIFACT-STORE | 不可变、category=dialogue、同 UUID 至多一个有效 artifact、终态清理 |

关键不变量：任务创建时刻快照；完整性不足 fail closed；重试复用同 UUID；本层无网络；父/兄弟状态所有权不变。

## 5. 决策与未解决风险

- **已决定**：Host Adapter 隔离（LCD-DLG-001）；task_created_at 锚点（LCD-DLG-002）；完整性不足不放行（LCD-DLG-003）；artifact 单一写方与不可变（LCD-DLG-004）。
- **已委托**：宿主具体 API/能力版本（LCD-DLG-005）给 `CMP-DLG-HOST-ADAPTER`；具体序列化与文件布局（LCD-DLG-006）给 `CMP-DLG-ARTIFACT-STORE`。
- **实现细节**：API 调用封装、checksum 算法、临时文件布局等不提升为父层决策。
- **风险**：如果宿主不能提供任务锚定的快照或完整性证据，不能降级上传当前最新对话；需要回到父层申请能力/边界修订。

## 6. 推荐下一步

1. **首选 `CMP-DLG-HOST-ADAPTER`**：确认宿主可用能力、历史/锚定快照、分页和截断元数据。
2. 次选 `CMP-DLG-SNAPSHOT-VALIDATOR`：定义完整性证明与规范化规则，不改变 CT-001。
3. 随后细化 `CMP-DLG-ARTIFACT-STORE` 和 Coordinator 的原子持久化/幂等实现。

所需祖先上下文：本包七个文件；L1 `04-contracts-and-runtime.md` 中 IC-M01-03 与 CT-001/CT-002 摘要；无需读取兄弟节点内部。

## 7. 实际输入/输出、验证证据与未完成项

### 7.1 实际输入

| 输入 | 路径 | 结果 |
|---|---|---|
| parent_architecture | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L1\L1-mod-01` | 递归父包，7 个文件可读 |
| target_node_id | `CMP-DIALOGUE-COLLECTOR` | 通过父包子节点注册表和 handoff 唯一匹配 |
| current_prd | `C:\Users\Lenovo\Desktop\codex_plugin\prd\L2-PRD\mod-01\L2-mod-01-cmp-dialogue-collector\prd.md` | 已读；REQ-DD003、D-AC-REQ-003-01 |
| parent_prd | 未读取 | 父包已有完整需求/契约追踪，不需要回退读取 |
| output_dir | `C:\Users\Lenovo\Desktop\codex_plugin\architecture\L2\mod-01\L2-mod-01-cmp-dialogue-collector` | 写入前为空目录 |

### 7.2 实际生成输出

本次生成七个文件：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。未生成 `parent-change-request.md`，因为本轮没有实际提出父边界变更。

### 7.3 已执行验证

| 检查 | 结果 |
|---|---|
| 四项必需输入和输出安全 | 通过 |
| 父包类型与目标唯一匹配 | 通过 |
| 需求分配与父追踪 | 通过 |
| 子节点稳定 ID、追踪列、依赖、排除项和存在理由 | 通过 |
| ST-02 单一所有权、快照、隐私和终态清理 | 通过 |
| CT-001/CT-002/auth-token 外部语义不变 | 通过 |
| 成功、失败/恢复、生命周期三条本地流 | 通过 |
| 决策队列无遗留 decide_now / return_to_parent | 通过 |
| 输出文件清单和排序 | 通过；七个文件均已实际写入，清单按规范列出 |

未完成项仅为宿主具体导出能力确认，已明确下一层目标与阻塞条件，不阻塞本层结构交接。
