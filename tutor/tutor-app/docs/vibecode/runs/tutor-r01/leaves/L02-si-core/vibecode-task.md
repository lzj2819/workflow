# VibeCode Task — L02 SI-CORE（W1）

- run：tutor-r01；leaf：L02；波次：W1；分支：`tutor-r01/L02-si-core`
- 模块：MOD-02 submission-intake / SI-CORE 提交聚合核心（DU-2）。

## 目标

实现 Submission 聚合、提交生命周期状态机、完整性报告与单事务持久化（MOD-02 的一致性强心）。

## 交付物

1. Submission 聚合持久化（PostgreSQL 目标、单测 SQLite）：提交记录、状态机、材料清单、完整性报告、上传失败原因（ST-01）。
2. 状态机（六态 + deleted）：upload_failed / rejected / received / processing / scored / scoring_failed → deleted；守卫非法迁移；终态不可逆。
3. 幂等创建：以 submission_uuid 为幂等键，重复创建返回同一 submission_id，不产生重复提交。
4. IC-SI-04 提交聚合命令与查询端口实现（供 SI-API/RELAY/PURGE 消费；含状态机守卫）。
5. 终态回写处理器：CT-005（scored/scoring_failed）与清除终态（deleted）的幂等应用（重复事件不改终态）。
6. 同事务 Outbox 写入：状态推进（received / upload_failed）时经 `tutor_shared.outbox.OutboxStore` 抽象在同一事务入队 CT-004/CT-006 待发布载荷（投递由 backfill 的 SI-RELAY 负责，本叶子只保证同事务入队语义与去重键）。
7. 迁移：`server/migrations/versions/0003_submission_core.py`（`down_revision="0001_baseline"`）。
8. 测试：`server/tests/test_l02_si_core.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-02/L2-mod-02-si-core/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-02/architecture/`（03-state-and-data.md 的 INV-1~5/ST-01、04-contracts-and-runtime.md 的 IC-SI-04、05-local-decisions.md 的 LCD-001/002/003/009）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-001/002/004/005/006）、`03-data-and-consistency.md`（Submission 行）
- 验收：根 PRD AC-REQ-003-01、AC-REQ-007-01（owning）
- 仓库：`contracts/ct-001.json`~`ct-006.json`、`internal-contracts.json`、`shared/tutor_shared/outbox.py`、`server/course_app/db.py`

## 关键语义

- 缺必填信息不创建可评分提交；缺失材料显式标记 missing_items；材料不完整仍允许进入评分。
- 业务写入与 Outbox 行同一本地事务；重复事件不改终态；不得伪造等级或状态。
- SI-STORE/RELAY/VERIFY/PURGE 不是本叶子：它们的端口以抽象注入，实现归 Phase 5 backfill。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
