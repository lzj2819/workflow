# Contract Change Request — CCR-001

| 条目 | 值 |
|---|---|
| 状态 | **APPROVED（用户 2026-07-22 批准方案 A）→ 已实施（2026-07-23，验收见 SCENARIO-016）** |
| 提出方 | Integration Owner / Workflow Coordinator |
| 提出日期 | 2026-07-20 |
| 关联 | TD-08；设计包 MOD-04 child-handoff Q-001；NFR-004 / AC-NFR-004-01；findings GAP-01 |
| 冻结约束 | **批准前 CT-012 / CT-014 保持现状冻结，不得修改，不得实施本请求任何内容** |

## 1. 问题

NFR-004 / AC-NFR-004-01 要求「提交内容和评分记录」在课程结束后 1 年经教师确认删除且可审计。但现行冻结契约中：

- CT-012 RecordsDeleted 的消费者为 `[MOD-02, MOD-05]`，**不含 MOD-04**；
- AssessmentResult（原始等级、五维度依据、教师专用建议、重试记录）由 MOD-04 持有（03-data-and-consistency 数据所有权表）；
- 设计包 MOD-04 child-handoff Q-001 已登记：「父层未将 AssessmentResult 纳入删除接线——待 L0 修订处置，本层不自建接线」。

结果：删除链路执行后评分记录仍可存在于 MOD-04，AC-NFR-004-01 的 pass_rule（全部目标记录不可被教师端读取 + 删除审计）无法完整满足。Phase 5 前必须解决。

## 2. 提案（推荐方案 A）

### 2.1 接线变更

1. **CT-012 消费者集合扩展为 `[MOD-02, MOD-04, MOD-05]`**。事件 payload **不变**（`batch_id`、`submission_ids[]`、`scope`、`operator`、`executed_at`、`audit_record_id`、`v=1` 已足够 MOD-04 执行清除）；幂等语义不变（重复清除已删除记录为空操作）。
2. **新增 CT-015 AssessmentPurgeCompleted**（event，MOD-04 → MOD-05，Outbox，v=1），语义镜像 CT-014：
   - 必填：`batch_id`、`purged_submission_ids[]`、`failed_items[]`（元素 `submission_id`、`reason`）、`purged_at`、`v`；
   - 幂等：按 `batch_id` + `purged_at` 去重，重复事件不重复更新批次状态；
   - 无同步错误码；逐项失败以 `failed_items[]` 表达。
3. **回流语义**：MOD-05 删除批次执行状态 = 等待 CT-014（MOD-02 清除结果）**与** CT-015（MOD-04 清除结果）双到达；两者合并判定全部成功 / 部分失败。CT-014 本身不变。

### 2.2 MOD-04 清除行为

- 按 `submission_ids[]` 删除 AssessmentResult 业务内容（原始等级、维度依据、建议、重试记录）与对应 ScoringTask。
- **保留最小墓碑**（`submission_id`、`batch_id`、`purged_at`）：用于拒绝重放旧 CT-005 事件重建已删结果（重放守卫，对齐 MOD-05 LCD-005 语义），墓碑不含评分内容、不属于「评分记录」。
- 消费幂等：重复 CT-012（同 batch_id）对已删 submission 为空操作。

### 2.3 审计影响

- 删除审计记录仍由 MOD-05 DeletionBatch 持有、先于清除写入、永久留存、不在删除范围（不变）。
- 批次审计补充记录 MOD-04 清除结果（CT-015 到达后追加，审计只增不删）。
- MOD-04 侧不产生独立审计；其清除结果经 CT-015 汇入 MOD-05 批次审计。

### 2.4 失败与重跑

- MOD-04 清除部分失败 → CT-015 `failed_items[]` 回传；失败项保留在批次中，批次状态为部分失败。
- 重跑机制与现行一致：原批次重跑触发 CT-012 重发（或仅含失败项的重发），MOD-02/MOD-04 均按幂等语义处理；重跑结果再次经 CT-014/CT-015 回流。
- 审计记录在任何失败/重跑路径下不受影响。

### 2.5 文档修改点（批准后执行，tutor 设计包为只读输入，故修改落在 `contracts/` 与实现侧文档）

- `contracts/ct-012.json`：consumer 增加 MOD-04；side_effects 增补 MOD-04 清除 AssessmentResult。
- `contracts/ct-015.json`：新建（内容如 2.1.2）。
- `contracts/internal-contracts.json`：登记 MOD-04 清除执行与 CT-015 发布端口。
- contract-freeze.md：GAP-01 标记为已解决；CT-015 入冻结清单。
- execution-matrix.md：MOD-04 backfill（B-02）增加 CT-012 消费与 CT-015 发布；B-03 增加双回流批次聚合。
- 验收：AC-NFR-004-01 pass_rule 覆盖「评分记录不可读」的端到端验证（Phase 5/6）。

## 3. 备选方案（不推荐）

- **方案 B：评分记录不删除、仅匿名化**。违背 NFR-004「评分记录」删除口径；保留可推断的学生维度依据/建议文本不符合数据最小化；需产品重新决策保留口径。不推荐。
- **方案 C：MOD-02 同步调用 MOD-04 代理删除**。引入 DU-2→DU-3 同步依赖，DU-3 故障阻塞删除执行，违背故障隔离与事件驱动既定形态（KD-002）；且 CT-012 语义已具备承载能力，无需同步化。不推荐。

## 4. 影响面

| 对象 | 影响 |
|---|---|
| MOD-04 | 新增 CT-012 消费、清除执行（含墓碑）、CT-015 发布；均属 Phase 5 backfill 范围 |
| MOD-05 | 批次状态聚合改为双回流（CT-014 + CT-015）；重放守卫不变 |
| MOD-02 | 无影响（CT-012/CT-014 语义不变） |
| 契约冻结 | CT-012 consumer 扩展 + 新增 CT-015；无字段删除/改名/语义弱化；v=1 兼容 |
| 验收 | AC-NFR-004-01 可完整验证；SM 统计不受影响（终态统计在删除前已完成） |

## 5. 决策请求

请用户裁决：

1. 批准方案 A（推荐）/ 选择方案 B 或 C / 退回修订；
2. 若批准：上述文档修改点生效，Phase 5 按更新后的 backfill 范围实施。

**批准前：CT-012/CT-014 保持冻结，不得实施任何相关代码。**
