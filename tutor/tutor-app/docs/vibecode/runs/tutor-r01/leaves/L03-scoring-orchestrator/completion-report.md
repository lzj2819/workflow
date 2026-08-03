# Completion Report — L03 CMP-SCORING-ORCHESTRATOR（W1）

- leaf：L03；run：tutor-r01；分支：`tutor-r01/L03-scoring-orchestrator`
- 提交 SHA：`066e516`（feat(l03): scoring orchestrator — task persistence, state machine, lease, one-retry, terminal tx）
- 基线：已合并 main（含 outbox 平台测试时钟修复 2ad9dc6；合并无冲突）

## 改动清单

| 文件 | 说明 |
|---|---|
| `worker/assessment_worker/scoring_orchestrator/__init__.py` | 包导出（替换 Phase 1 占位 docstring，唯一被修改的既有文件） |
| `worker/assessment_worker/scoring_orchestrator/models.py` | ST-001 ScoringTask / ST-002 ScoringResult ORM 模型（sa.JSON，SQLite 可测；naive UTC） |
| `worker/assessment_worker/scoring_orchestrator/errors.py` | 本地诊断错误（STALE/DUPLICATE_TERMINAL_CALLBACK、INVALID_RESPONSE_SCHEMA 映射） |
| `worker/assessment_worker/scoring_orchestrator/lease_store.py` | `SqlaTaskLeaseStore(LeaseStore)`：原子条件 UPDATE 认领；到期重认领保留 attempts、reclaim_count+1；上限返回 None |
| `worker/assessment_worker/scoring_orchestrator/orchestrator.py` | CT-004 幂等消费（submission_id 唯一，持久化后才返回供确认）；ICT-001 认领；ICT-005/006 终态事务（业务写入 + CT-005 载荷经 `OutboxStore` 抽象同事务入队，dedup_key=submission_id+终态）；REQ-012 重试一次（attempts≤2）；reclaim_count>3 → REPEATED_WORKER_CRASH 终态化 |
| `server/migrations/versions/0004_scoring_tasks.py` | scoring_tasks + scoring_results 两表；`down_revision="0001_baseline"`；不含 Outbox 表（0001 约定由 Integration Owner 统一建立） |
| `worker/tests/test_l03_scoring_orchestrator.py` | 24 项测试（21 编排语义 + 3 迁移） |

## 验证命令与结果（worktree 根，尾部）

```
$ python -m unittest discover -s worker/tests -p "test_l03_*.py" -v
Ran 24 tests in 0.274s
OK

$ python -m unittest discover -s worker/tests
Ran 32 tests in 0.259s      # 24 L03 + 既有 8 项，无回归
OK

$ ruff check worker/assessment_worker/scoring_orchestrator worker/tests/test_l03_scoring_orchestrator.py server/migrations/versions/0004_scoring_tasks.py
All checks passed!

$ python -m py_compile <全部 7 个新增/改动 .py>
PY_COMPILE_OK

$ python -m unittest discover -s server/tests   # 附加自检（非清单要求）
Ran 36 tests in 0.078s
OK
```

语义断言覆盖：CT-004 幂等（重复事件不建重复任务、持久化后才确认）；状态机守卫（pending→in_progress→scored；第一次失败进唯一重试、第二次失败 scoring_failed、第三次回调拒绝）；认领互斥/到期重认领保留 attempt/reclaim_count>3 终态且终态不可再认领；ICT-005 scored 四件套+scored_at+v 与 dedup_key；ICT-006 scoring_failed failure_reason+retry_record+v；Outbox 失败时终态事务整体回滚（INV-3）；迁移可导入、revision/down_revision 正确、SQLite upgrade/downgrade 与 ORM 列一致。

## 契约影响

无。未修改 `contracts/`、`shared/`、`server/`（除新迁移）、`worker/assessment_worker/` 其他文件、`plugin/`、`deploy/`；CT-004/CT-005 标识、字段、版本语义原样实现；无 CT-012 消费/删除接线（CCR-001 pending）。

## 风险/阻塞

- 无阻塞。
- 低风险：终态事务的「Outbox 同事务」在单测中以「enqueue 在 `session.begin()` 块内、失败即整体回滚」证明；生产 PG 侧 Outbox 表与会话绑定的 SQL OutboxStore 由 Integration Owner / backfill（RESULT-PUBLISHER、SI-RELAY）落地，本叶仅依赖冻结抽象。
- 低风险：claim 候选 SELECT 为建议性读取，并发互斥由条件 UPDATE 守卫；PG 行锁（with_for_update）已用于终态守卫读取，SQLite 下自动忽略。

## 范围自检

```
$ git diff --name-only main...HEAD
server/migrations/versions/0004_scoring_tasks.py
worker/assessment_worker/scoring_orchestrator/__init__.py
worker/assessment_worker/scoring_orchestrator/errors.py
worker/assessment_worker/scoring_orchestrator/lease_store.py
worker/assessment_worker/scoring_orchestrator/models.py
worker/assessment_worker/scoring_orchestrator/orchestrator.py
worker/tests/test_l03_scoring_orchestrator.py
```

全部位于 allowed-context.md 允许路径内。
