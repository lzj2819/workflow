# Leaf Gate Override ? CMP-REVIEW-QUERY

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — 子层交接（L2 / CMP-REVIEW-QUERY）

## 1. 当前节点身份

- **target_node_id**：`CMP-REVIEW-QUERY`
- **父包**：`architecture/L1/L1-mod-05`
- **职责**：只读装配 CT-007 教师课程/小组/学生/提交详情查询，含评分结果、失败信息和 `deletion_batches[]`。
- **排除项**：不授权、不写状态、不消费事件、不生成展示快照、不执行评分/删除、不新增公共运行时边界。
- **状态**：`ready_for_human_gate`

## 2. 下一层可选 target_node_id（按稳定 ID 排序）

| child_id | 一句话职责 | 优先级 | 继承上下文 |
|---|---|---|---|
| CMP-RQ-OUTCOME-ADAPTER | scored/scoring_failed 结果视图和禁伪造等级规则 | 高 | REQ-DD001；D-AC-REQ-009-01；CT-007；M05-IC-02；LCD-RQ-002 |
| CMP-RQ-QUERY-FACADE | CT-007 查询编排、完整响应和端口失败收敛 | 高 | REQ-DD001；CT-007；M05-FLOW-002；LCD-RQ-001/004/005 |
| CMP-RQ-RETENTION-VIEW-ADAPTER | M05-IC-06 删除批次只读视图适配 | 中 | CT-007 `deletion_batches[]`；M05-IC-06；LCD-RQ-003/004 |
| CMP-RQ-SCOPE-ASSEMBLER | 课程/小组/学生/提交层级查询装配 | 高 | REQ-DD001；CT-007；M05-IC-02；NFR-001；LCD-RQ-006 |
| CMP-RQ-SUBMISSION-DETAIL-ASSEMBLER | 提交详情字段装配并委托结果分支 | 高 | REQ-DD001；D-AC-REQ-009-01；CT-007；M05-IC-02；LCD-RQ-002/006 |

以上 child_id 是本层内部稳定入口，不是新的父层模块或部署单元。下一层不得直接读取 ST-READ-MODEL/ST-DELETION-BATCH 的底层存储，必须继续使用本层继承的端口边界。

## 3. 继承契约清单

| 契约 | 角色 | L2 约束 |
|---|---|---|
| CT-007 | 本节点通过 Facade 参与 Provider | path、字段、错误码、只读、≤10 秒、`deletion_batches[]` 和版本不可变 |
| M05-IC-02 | CMP-READMODEL-PROJECTOR → 本节点 | 只读；字段集和 Owner 不变；失败不可降级为缺字段成功 |
| M05-IC-06 | CMP-RETENTION-GOVERNANCE → 本节点 | 只读；只装配批次视图；不拥有/修改 DeletionBatch |
| CT-005/006/012/014 | 本节点不消费 | 事件消费继续归父层 CMP-READMODEL-PROJECTOR/CMP-RETENTION-GOVERNANCE |

## 4. 本层内部契约

- `RQ-IC-001`：Facade → Scope Assembler，层级查询视图。
- `RQ-IC-002`：Facade → Submission Detail Assembler，提交详情视图。
- `RQ-IC-003`：Submission Detail → Outcome Adapter，评分成功/失败结果视图。
- `RQ-IC-004`：Facade → Retention View Adapter，`deletion_batches[]`。
- `RQ-IC-005`：四类局部视图 → Facade，完整 CT-007 响应组合。

完整字段、错误/重试、幂等和合法流定义见 `04-contracts-and-runtime.md`。

## 5. 状态所有权清单

| 状态/数据 | owner | 本层行为 |
|---|---|---|
| ST-READ-MODEL | CMP-READMODEL-PROJECTOR | 通过 M05-IC-02 只读 |
| ST-DELETION-BATCH | CMP-RETENTION-GOVERNANCE | 通过 M05-IC-06 只读 |
| ReviewRecord | CMP-REVIEW-COMMAND | 不读取其底层状态；只消费读模型中已投影的批注/最终等级 |
| PresentationView | CMP-PRESENTATION | 不装配、不写入 |
| Submission/Material | MOD-02 | 只读取材料引用，不持有材料文件 |

## 6. 已决、委托与未决风险

- **已决**：LCD-RQ-001 单一 Facade；LCD-RQ-002 显式失败结果；LCD-RQ-003 批次数组稳定返回；LCD-RQ-004 端口失败整体重试；LCD-RQ-005 复用授权上下文。
- **委托**：LCD-RQ-006 查询计划/索引/分页实现；LCD-RQ-007 DTO 序列化与具体框架映射。
- **开放风险**：读模型秒级最终一致意味着教师刚看到评分结果后可能短暂读不到最新投影；L2 只能返回父允许的最终一致结果，不得引入跨模块同步读。
- **阻塞风险**：无；若产品新增分页、导出、查询字段或授权维度，必须重新进行父层契约/边界审查。

## 7. 实际输入、输出与验证证据

### 实际输入

- `prd/L2-PRD/mod-05/L2-mod-05-cmp-review-query/prd.md`
- `architecture/L1/L1-mod-05`
- `target_node_id=CMP-REVIEW-QUERY`
- `mode=new`

### 实际输出

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

### 已执行检查

| 检查 | 结果 |
|---|---|
| 四项输入解析、父包可读、目标目录写入前为空 | 通过 |
| 目标节点唯一匹配 | 通过 |
| REQ-DD001 → REQ-D001 → D-AC-REQ-009-01/CT-007 追踪 | 通过 |
| 五个 child_id 在 manifest/decomposition/handoff 中一致且排序稳定 | 通过 |
| C1-C6 映射与父/兄弟所有权不转移 | 通过 |
| CT-007/M05-IC-02/M05-IC-06 父语义不可变 | 通过 |
| 失败结果、缺字段和重试分支明确 | 通过 |
| 决策队列清零、无 return_to_parent | 通过 |

## 8. Human Gate

当前包已生成至 `ready_for_human_gate`。后续只能在 Human Gate 批准后，使用 `[NEXT child_id]` 进入某个内部 child 的更深层细化；本包不自动进入实现或测试阶段。

## 9. 验证责任与覆盖前提

| 场景/检查 | 权威组件 | 本包允许验证的内容 | 不得据此修改的内容 |
|---|---|---|---|
| SCENARIO-002 保存批注/调整等级 | `CMP-REVIEW-COMMAND` / CT-008 | 通过 M05-IC-05 投影后，CT-007 能读到批注和最终等级 | 不给 Query 增加写状态或 CT-008 next_hop |
| SCENARIO-003 原始/最终等级及操作者时间留痕 | ReviewRecord / `CMP-REVIEW-COMMAND`；RMP 投影 | 读取已经存在的读模型事实 | 不给 Scope Assembler 增加审计、留痕或持久化能力 |
| `deletion_batches[]` | `CMP-RQ-RETENTION-VIEW-ADAPTER` / M05-IC-06 | 有批次返回批次视图，无批次返回空数组，读取失败整体 retryable | 不删除 Adapter，不转移 DeletionBatch owner |
| CT-007 入口 | `CMP-RQ-QUERY-FACADE` 经 ACCESS-GATE | 验证 Facade→局部 child→完整响应的合法流 | 不把未被某一通用场景触达判为组件孤儿 |

严格验证的测试输入应提供已授权选择范围和可查询读模型 fixture，并至少覆盖一次 `deletion_batches[]` 分支；这些是验证前提，不是本层新增业务状态。
