# Verification Checklist — L03

## 命令

- [ ] `python -m unittest discover -s worker/tests -p "test_l03_*.py" -v` 全绿
- [ ] `python -m unittest discover -s worker/tests` 全绿（既有 8 项不得回归）
- [ ] `ruff check worker/scoring_orchestrator worker/tests/test_l03_scoring_orchestrator.py server/migrations/versions/0004_scoring_tasks.py`
- [ ] `python -m py_compile` 新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] CT-004 消费幂等：同一 submission_id 重复事件只建一个任务；任务持久化后才确认
- [ ] 状态机守卫：pending→claimed→completed；failed_retryable 仅允许一次重试（attempts 上限 2），第二次失败 → failed_terminal
- [ ] 认领互斥：一 worker 持有租约时另一不可认领；租约到期可重认领；reclaim_count>3 → 终态
- [ ] ICT-005：完成写入 + CT-005 scored 载荷同事务入队（含 original_grade/dimension_rationales/teacher_suggestions/scored_at/v，dedup_key 幂等）
- [ ] ICT-006：失败写入 + CT-005 scoring_failed 载荷同事务入队（含 failure_reason/retry_record/v）
- [ ] 迁移文件可导入、revision/down_revision 正确
