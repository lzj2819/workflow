# VibeCode Task — L03 CMP-SCORING-ORCHESTRATOR（W1）

- run：tutor-r01；leaf：L03；波次：W1；分支：`tutor-r01/L03-scoring-orchestrator`
- 模块：MOD-04 assessment / CMP-SCORING-ORCHESTRATOR 评分任务编排（DU-3，一致性核心）。

## 目标

实现评分任务的持久化、状态机、认领/租约、幂等消费 CT-004、重试一次策略与终态事务。

## 交付物

1. ScoringTask 持久化（与 DU-2 同一 PostgreSQL；单测 SQLite）：submission_id（唯一，幂等键）、状态、attempts、retry_record、claim 租约字段（lease_owner/lease_expires_at/reclaim_count）、时间戳。
2. 任务状态机：pending → claimed/running →（completed | failed_retryable → claimed（仅一次重试）| failed_terminal）；reclaim_count>3 终态化（MOD-04 LCD-002）。
3. CT-004 消费处理器：按 submission_id 幂等创建任务（重复事件不建重复任务）；任务持久化后才确认事件（LCD-003）。
4. ICT-001 ClaimScoringTask：经 `tutor_shared.lease.LeaseStore` 抽象认领（原子、租约到期可重认领）。
5. ICT-005/ICT-006 完成/失败端口：终态写入（结果引用、重试记录）与 CT-005 载荷同事务经 `tutor_shared.outbox.OutboxStore` 入队（dedup_key=submission_id+终态；发布由 backfill 的 RESULT-PUBLISHER 负责）。
6. 迁移：`server/migrations/versions/0004_scoring_tasks.py`（共享 DB，`down_revision="0001_baseline"`）。
7. 测试：`worker/tests/test_l03_scoring_orchestrator.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-04/L2-mod-04-cmp-scoring-orchestrator/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-04/architecture/`（03-state-and-data.md 的 ST-001/INV/CON/IDM、04-contracts-and-runtime.md、05-local-decisions.md 的 LCD-001~004）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-004/CT-005）、`03-data-and-consistency.md`（AssessmentResult 行）
- 验收：根 PRD AC-REQ-007-01（MOD-04 slice）、REQ-012（重试一次）
- 仓库：`contracts/ct-004.json`、`ct-005.json`、`shared/tutor_shared/lease.py`、`outbox.py`

## 关键语义

- 评分失败自动重试一次（仅一次，REQ-012）：attempts 上限 2；重试成功回主链路，再失败终态 scoring_failed。
- CT-005 scored 四件套 / scoring_failed 两件套（contracts/ct-005.json 条件字段）。
- 不实现：模型调用（ACL，backfill）、五维评估（L12）、提示编排（RUBRIC-PROMPT-COMPOSER，backfill）、结果发布（RESULT-PUBLISHER，backfill）。
- CCR-001 pending：不得实现任何 CT-012 消费/删除逻辑。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
