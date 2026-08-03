# Leaf Gate Override ? CMP-PRESENTATION

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — L2 / CMP-PRESENTATION

> 当前包是 `MOD-05 / CMP-PRESENTATION` 的 L2 细化结果；Human Gate 通过后，下一层可使用下表 exact `child_id` 继续递归。

## 1. 当前节点与父绑定

- **节点**：`CMP-PRESENTATION`（L2），父节点 `MOD-05 / teacher-web`，部署于 `DU-2 course-app`。
- **职责**：生成 CT-009 展示视图、显式装配 missing_marks、写入 PresentationView 快照、支持父幂等再生成。
- **排除项**：不改变 CT-009/M05-IC-02；不读取兄弟源数据；不负责授权、教师 UI、读模型写入、ReviewRecord、DeletionBatch、材料清除或独立部署。
- **边界指纹**：父 `architecture-manifest.yaml` 的 CMP-PRESENTATION 行；父 02 §3A；父 03 的 ST-PRESENTATION-VIEW/ST-IDEMPOTENCY-PRESENTATION；父 04 的 CT-009/M05-IC-02/M05-FLOW-004/015；父 LCD-004/005/008；父 DU-2/KD-002/003/005。

## 2. 下一层 target_node_id（稳定排序）

| child_id | 一句话职责 | 需求/父追踪 | 关键状态 | 推荐优先级 |
|---|---|---|---|---|
| CMP-PRES-BLOCK-ASSEMBLER | 将合格小组读模型片段装配为 GroupSection[]/ProcessSummary/评分/批注/missing_marks | REQ-DD002；D-AC-REQ-010-01；CT-009；PRES-IC-02 | ST-PRES-MISSING-MARKS（只读输入）；瞬时 GroupSectionBuild | 高 |
| CMP-PRES-GENERATION-COORDINATOR | 编排 CT-009 的读、判定、装配、快照与响应闭环 | REQ-DD002；D-AC-REQ-010-01；CT-009；M05-FLOW-004 | ST-PRES-GENERATION-CONTEXT | 高 |
| CMP-PRES-MISSING-MARKS | 判定任一小组无可用提交、生成显式缺失标记，并按 `group_id` 透传 `group_view` 上下文 | REQ-DD002；D-AC-REQ-010-01 exception/boundary；CT-009；PRES-IC-01/02 | ST-PRES-MISSING-MARKS | 高 |
| CMP-PRES-OUTPUT-ADAPTER | 保持 CT-009 blocks 响应兼容，并细化网页/导出格式 | REQ-DD002；CT-009；LCD-008 | ST-PRES-RESPONSE | 中；承接 LCD-008 |
| CMP-PRES-SNAPSHOT-STORE | 拥有 PresentationView/幂等记录，闭合写入、再生成、supersede 与 purge | REQ-DD002；CT-009；LCD-005；ST-PRESENTATION-VIEW | ST-PRESENTATION-VIEW；ST-IDEMPOTENCY-PRESENTATION | 高 |

所有 child 均有需求或父契约/流程/决策追踪，无 trace exemption。

## 3. 契约交接

### 继承契约（不可变）

| contract_id | 角色 | 关键字段/语义 | 下一层注意 |
|---|---|---|---|
| CT-009 | 本节点 Provider，教师浏览器 Consumer | `POST /api/v1/teacher/presentations`；`group_ids[]` → `presentation_id + blocks[]`；`missing_marks`；`NO_AVAILABLE_SUBMISSION`；父幂等键 | 不能新增 GET/端点、字段要求、错误码或版本 |
| M05-IC-02 | `CMP-READMODEL-PROJECTOR` Provider，本节点 Consumer | 只读读模型输入；输出评分/批注/状态/材料引用/缺失字段 | 不改 owner，不直连 MOD-02/MOD-04 |

### 当前层内部契约

| contract_id | owner → consumer | 用途 |
|---|---|---|
| PRES-IC-01 | GENERATION-COORDINATOR → MISSING-MARKS | 资格判定、缺失标记与组视图上下文 |
| PRES-IC-02 | MISSING-MARKS → BLOCK-ASSEMBLER | 按 `group_id` 将 `group_view`、`eligibility`、`missing_marks` 交给区块装配 |
| PRES-IC-03 | BLOCK-ASSEMBLER → SNAPSHOT-STORE | 写入快照和幂等记录 |
| PRES-IC-04 | SNAPSHOT-STORE → OUTPUT-ADAPTER | 将快照映射为 CT-009 response |
| PRES-IC-05 | READMODEL-PROJECTOR → SNAPSHOT-STORE | CT-012 自消费后的展示内容擦除 |

## 4. 状态交接

| state_id | owner | 下一层约束 |
|---|---|---|
| ST-IDEMPOTENCY-PRESENTATION | CMP-PRES-SNAPSHOT-STORE | 与 PresentationView 同事务；相同父生成键返回最新快照 |
| ST-PRES-GENERATION-CONTEXT | CMP-PRES-GENERATION-COORDINATOR | 请求内瞬时，不持久化为公共状态 |
| ST-PRES-MISSING-MARKS | CMP-PRES-MISSING-MARKS | 只复制/派生读模型事实，不修改源数据 |
| ST-PRES-RESPONSE | CMP-PRES-OUTPUT-ADAPTER | 只在调用内存在，不缓存学生内容 |
| ST-PRESENTATION-VIEW | CMP-PRES-SNAPSHOT-STORE | `snapshot_created → superseded → purged`；删除后不得重放复活 |

## 5. 决策、风险与下一步

- **继承决策**：KD-002、KD-003、KD-005、LCD-004、LCD-005；不得在下一层改为跨模块实时读取或新建平台/部署边界。
- **本层已决**：生成编排、资格与缺失分离、快照状态单写方、blocks 与渲染解耦、PRES-IC-05 purge 入口。
- **委托决策**：LCD-PRES-006 / 父 LCD-008 → `CMP-PRES-OUTPUT-ADAPTER`，启动条件为该 child 下一层细化；需要在不改变 CT-009 的前提下选择具体网页/导出格式。
- **风险**：父读模型秒级最终一致可能让刚更新的批注暂时未进入快照；继续使用 CT-009 幂等再生成吸收，不引入跨模块同步读。
- **开放问题**：本层没有需要返回父层的开放问题；若未来要求新增 CT-009 字段、实时读取兄弟源数据、跨节点转移 PresentationView 所有权或新增独立部署单元，必须创建 parent-change-request 并停止递归。

## 6. 实际输入/输出与验证

### 实际输入

- `current_prd`: `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-05/L2-mod-05-cmp-presentation/prd.md`
- `parent_architecture`: `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-05`
- `target_node_id`: `CMP-PRESENTATION`
- `output_dir`: `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L2/mod-05/L2-mod-05-cmp-presentation`
- `mode`: `new`

### 实际输出

1. `architecture-manifest.yaml`
2. `01-design-context.md`
3. `02-architecture-decomposition.md`
4. `03-state-and-data.md`
5. `04-contracts-and-runtime.md`
6. `05-local-decisions.md`
7. `child-handoff.md`

### 交接检查

| 检查 | 初始结果 |
|---|---|
| 七文件存在且无 `parent-change-request.md` | 通过 |
| manifest YAML 可解析，状态与生成清单一致 | 通过 |
| child_id/contract_id/state_id/decision_id 稳定且排序一致 | 通过 |
| 所有 child 有需求或父追踪，无伪造 trace exemption | 通过 |
| CT-009、M05-IC-02 父字段/owner/错误/幂等/版本未改变 | 通过 |
| 三类本地流覆盖成功、失败/恢复、生命周期 | 通过 |
| 无新增公共 API、跨模块事件、存储、部署单元或兄弟重设计 | 通过 |

**当前 Human Gate 状态**：`ready_for_human_gate`。只有 Human Gate 通过后，才可使用 `[NEXT child_id]`。
