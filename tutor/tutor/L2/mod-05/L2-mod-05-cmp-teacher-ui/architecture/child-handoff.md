# Leaf Gate Override ? CMP-TEACHER-UI

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — L2 / CMP-TEACHER-UI

> 本文件是下一层（L3）细化与 Human Gate 的入口。只有当前包通过 Human Gate 后，才使用 `[NEXT child_id]`。

## 1. 当前节点身份与父绑定

- **当前节点**：`CMP-TEACHER-UI`（L2），父节点为 L1/MOD-05 的同名直接 child。
- **职责**：教师网页的查询、提交详情、批注/最终等级编辑、展示视图、删除确认和失败/通知可观察面。
- **排除项**：不拥有服务端业务聚合；不做授权、评分、投影、删除执行；不直连存储或兄弟节点；不新增部署边界。
- **部署**：DU-2 course-app 内的教师网页表面；不创建服务、容器或公共运行时。
- **边界指纹**：父 CT-007/008/009/011、M05-BIND-FLOW-009-BROWSER-UI、M05-BIND-CT-007/008/009/011-UI-GATE、REQ-DD001/REQ-DD002、LCD-007、A-005。

## 2. 下一层可选 target_node_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议优先级 | L3 所需上下文 |
|---|---|---|---|
| `CMP-TUI-COURSE-SUBMISSION-BROWSER` | 课程/组/学生/提交导航与详情查询可观察面 | 高 | REQ-DD001；D-AC-REQ-009-01；CT-007；ST-TUI-CURRENT-COURSE-SCOPE/ST-TUI-QUERY-STATUS |
| `CMP-TUI-NOTIFICATION-STATUS` | 失败原因、重试结果和端内通知展示 | 中 | A-005；LCD-TUI-004；TUI-IC-02/06；ST-TUI-NOTIFICATION-QUEUE |
| `CMP-TUI-PRESENTATION-WORKSPACE` | 小组选择、展示视图打开和 missing_marks 呈现 | 高 | REQ-DD002；D-AC-REQ-010-01；CT-009；LCD-004 |
| `CMP-TUI-RETENTION-CONFIRMATION` | 删除批次查看、排除项和二次确认 | 中 | CT-007 `deletion_batches[]`；CT-011；DF-3；ST-TUI-RETENTION-* |
| `CMP-TUI-REVIEW-WORKBENCH` | 批注、最终等级编辑和保存反馈 | 高 | REQ-DD001；D-AC-REQ-009-01；CT-008；NO_ORIGINAL_GRADE；ST-TUI-REVIEW-* |

L3 不得将上述 child 变成独立服务，也不得共享或转移父层服务端状态所有权。

## 3. 继承契约清单

- 提供给浏览器并经 GATE 路由：CT-007、CT-008、CT-009、CT-011。
- UI 入口绑定：M05-BIND-FLOW-009-BROWSER-UI、M05-BIND-CT-007-UI-GATE、M05-BIND-CT-008-UI-GATE、M05-BIND-CT-009-UI-GATE、M05-BIND-CT-011-UI-GATE。
- L2 内部契约：TUI-IC-01 至 TUI-IC-06；这些契约只描述浏览器 child 间的局部协作，不能外溢为新父契约。
- 失败/幂等/版本原样继承父层；UI 只增加 action status、draft 和 scope_key 等瞬时状态。

## 4. 状态所有权清单

| 状态范围 | owner | 关键约束 |
|---|---|---|
| ST-TUI-CURRENT-COURSE-SCOPE / DETAIL-SELECTION / QUERY-STATUS | COURSE-SUBMISSION-BROWSER | 旧 scope 响应不得覆盖新 scope；不缓存授权真相 |
| ST-TUI-NOTIFICATION-QUEUE | NOTIFICATION-STATUS | 只读映射父投影结果；不生成 CT-005 事实 |
| ST-TUI-PRESENTATION-SELECTION / PRESENTATION-STATUS | PRESENTATION-WORKSPACE | blocks 是 CT-009 快照；不本地生成展示视图 |
| ST-TUI-RETENTION-CONFIRMATION-DRAFT / RETENTION-STATUS | RETENTION-CONFIRMATION | confirm=true 只由明确用户动作触发；不把 accepted 当完成 |
| ST-TUI-REVIEW-DRAFT / REVIEW-STATUS | REVIEW-WORKBENCH | 原始等级只读；NO_ORIGINAL_GRADE 不可绕过；草稿不被刷新覆盖 |
| ST-TUI-ACTION-STATUS | 各 action owner | 浏览器瞬时、非持久化；服务端响应为权威 |

服务端 `ST-READ-MODEL`、`ST-REVIEW-RECORD`、`ST-PRESENTATION-VIEW`、`ST-DELETION-BATCH`、`ST-TEACHER-ACCESS-GRANT` 和 `ST-ACCESS-DENIED-LOG` 的 owner 均保持 L1 定义。

## 5. 继承、局部与未决决策

- **继承**：KD-002、KD-003、KD-005、A-005、LCD-001、LCD-004、LCD-006；父契约和 DU-2 部署边界。
- **本层局部决定**：LCD-TUI-001 混合渲染策略、LCD-TUI-002 局部状态 owner、LCD-TUI-003 幂等键交互策略、LCD-TUI-004 失败优先可见策略。
- **下一层委托**：LCD-TUI-005 页面布局、LCD-TUI-006 可访问性细则、LCD-TUI-007 具体框架/组件库/兼容矩阵。
- **未解决风险**：视觉设计与浏览器兼容标准尚未输入；不影响当前架构契约和状态设计。若未来要求自助授权、跨模块实时同步或新的持久化客户端状态，必须回父层评估。

## 6. 实际输入、输出与验证证据

**实际解析输入**：

- `parent_architecture=architecture/L1/L1-mod-05`
- `target_node_id=CMP-TEACHER-UI`
- `current_prd=prd/L2-PRD/mod-05/L2-mod-05-cmp-teacher-ui/prd.md`
- `output_dir=architecture/L2/mod-05/L2-mod-05-cmp-teacher-ui`
- `mode=new`

**实际生成输出（7 个文件）**：manifest、01-design-context、02-architecture-decomposition、03-state-and-data、04-contracts-and-runtime、05-local-decisions、child-handoff。

**已执行检查**：

| 检查 | 结果 |
|---|---|
| 四项输入和输出安全 | 通过 |
| 父包类型识别与 CMP-TEACHER-UI 唯一匹配 | 通过 |
| 当前 PRD 需求和验收契约追踪 | 通过 |
| 五个 child 的稳定 ID、职责、排除项、状态、依赖和追踪列 | 通过 |
| CT-007/008/009/011 父契约不可变 | 通过 |
| 服务端状态所有权未转移 | 通过 |
| C1-C6 映射与五条 local_legal_flows | 通过 |
| 决策队列无未处理 decide_now、无 parent-change-request | 通过 |

## 7. Human Gate

当前包状态：`ready_for_human_gate`。

下一步命令：

```text
[APPROVE]
[REVISE phase-N]
[EXPLAIN decision-id]
[NEXT child_id]
```
