# Leaf Gate Override ? CMP-REVIEW-COMMAND

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — 子层交接（L2 / CMP-REVIEW-COMMAND）

> 本包是 L3 细化入口；`[NEXT child_id]` 仅在本包 Human Gate 批准后使用。

## 1. 当前节点身份与父绑定

- **当前节点**：`CMP-REVIEW-COMMAND`（L2），父节点同名 L1 child，隶属 MOD-05 / DU-2。
- **职责**：CT-008 复核写侧、M05-IC-01 ReviewRecord 创建、批注/最终等级调整、禁伪造等级和调整留痕。
- **排除项**：不实现查询、展示、UI、授权、评分、材料、读模型投影、保留治理或跨模块清除。
- **父边界指纹**：见 `architecture-manifest.yaml`，固定依据为 CT-008、M05-IC-01、M05-IC-05、ST-REVIEW-RECORD、KD-002/KD-003/KD-005、LCD-003/LCD-009。

## 2. 下一层可选 target_node_id（按稳定 ID 排序）

| child_id | 一句话职责 | 主要追踪 | 建议优先级 |
|---|---|---|---|
| CMP-RC-REVIEW-IDEMPOTENCY-GUARD | request_id/submission_id 幂等、首次响应回放和同事务幂等边界 | REQ-DD001、CT-008、M05-IC-01、KD-005 | 高 |
| CMP-RC-REVIEW-INTEGRITY-POLICY | 批注/等级输入规则、原始等级存在性、NO_ORIGINAL_GRADE | REQ-DD001、D-AC-REQ-009-01、CT-008、LCD-009 | 高 |
| CMP-RC-REVIEW-RECORD-WRITER | ReviewRecord 创建/更新、调整留痕和 M05-IC-05 提交后事件 | REQ-DD001、D-AC-REQ-009-01、M05-IC-01、M05-IC-05、LCD-003 | 高 |

## 3. 继承契约注册表

| contract_id | 方向 | 本层规则 |
|---|---|---|
| CT-008 | ACCESS-GATE → CMP-REVIEW-COMMAND | `request_id`、至少一项写字段、NO_ORIGINAL_GRADE、后写为准、返回 review_record；`/api/v1` 不变 |
| M05-IC-01 | CMP-READMODEL-PROJECTOR → CMP-REVIEW-COMMAND | scored 结果创建 ReviewRecord；submission_id 幂等；原始等级复制值不可变 |
| M05-IC-05 | CMP-REVIEW-COMMAND → CMP-READMODEL-PROJECTOR | AnnotationSaved/GradeAdjusted；adjustment_id 去重；仅模块内事件 |
| M05-IC-07 | CMP-RETENTION-GOVERNANCE → CMP-REVIEW-COMMAND | ReviewRecord 内容清除；batch_id+submission_id 去重；失败项可重试；不改变 CT-012 |

## 4. 状态所有权注册表

| state_id | owner child | 关键约束 |
|---|---|---|
| ST-IDEMPOTENCY-REVIEW | CMP-RC-REVIEW-IDEMPOTENCY-GUARD | request_id/submission_id 去重；与业务写入同事务 |
| ST-REVIEW-RECORD | CMP-RC-REVIEW-RECORD-WRITER | 原始等级不可变；最终等级、操作者、时间和调整记录完整留痕 |

## 5. C1-C6 与运行流摘要

- **C1**：父复核写侧细化为 GUARD、POLICY、WRITER。
- **C2**：幂等状态归 GUARD，ReviewRecord 聚合归 WRITER，POLICY 无持久状态。
- **C3**：CT-008/M05-IC-01 均按 GUARD → POLICY → WRITER；M05-IC-05 在提交后到 RMP；M05-IC-07 从 Retention-Governance 到 Writer 清除内容。
- **C4**：父契约字段由三个 child 组合实现，外部语义不变；M05-IC-07 通过 RC-IC-004 落到 Writer。
- **C5**：不新增 Adapter/ACL；ACCESS-GATE、RMP、Outbox 均沿用父边界；Retention-Governance 只通过 M05-IC-07 触发本节点自身内容清除。
- **C6**：幂等、禁伪造、单写方、留痕和可重放驱动内部策略。

## 6. 决策、风险与未决项

- **本层已决**：LCD-001（调整理由可选）、LCD-002（单一 writer）、LCD-003（双幂等键共享事务）、LCD-004（提交后事件）。
- **已委托**：LCD-005 → POLICY；LCD-006 → GUARD；LCD-007 → WRITER。
- **继承不可改**：KD-002/KD-003/KD-005、CT-008/M05-IC-01/M05-IC-05、ReviewRecord 所有权、DU-2 部署；M05-IC-07 不改变上述契约语义。
- **回父层触发器**：若要求调整理由成为 CT-008 必填字段、增加新错误码、改变并发/幂等语义、转移状态所有权或新增公共服务，必须创建 `parent-change-request.md` 并停止当前递归链。

## 7. 实际输入、输出与验证证据

**实际输入**：

- `current_prd=prd/L2-PRD/mod-05/L2-mod-05-cmp-review-command/prd.md`
- `parent_architecture=architecture/L1/L1-mod-05`
- `target_node_id=CMP-REVIEW-COMMAND`
- `output_dir=architecture/L2/mod-05/L2-mod-05-cmp-review-command`
- `mode=new`

**实际生成输出（7 个文件）**：

`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。

**交接检查**：

| 检查 | 结果 |
|---|---|
| 输入、父包类型、目标唯一匹配、输出安全 | 通过 |
| 三个 child 均有稳定 ID、职责、排除项、状态/需求或父追踪、依赖和理由 | 通过 |
| C1-C6、成功/失败恢复/生命周期流齐备 | 通过 |
| 父契约 CT-008/M05-IC-01/M05-IC-05 字段和语义不变 | 通过 |
| 状态所有权、事务、幂等和兄弟边界未越界 | 通过 |
| child/state/contract/decision 注册表按稳定 ID 排序 | 通过 |
| 决策队列无未处理 decide_now 或 return_to_parent | 通过 |
| 未生成代码、测试、脚手架、部署清单或 parent-change-request.md | 通过 |

未完成项只有三个已登记的下一层细化项（LCD-005~007）和父级数据库产品 deferred，不阻塞本包 Human Gate。

## 8. Human Gate

本包状态：`ready_for_human_gate`。可用命令：`[APPROVE]`、`[REVISE phase-N]`、`[EXPLAIN decision-id]`、`[PARENT_CHANGE]`、`[NEXT child_id]`。
