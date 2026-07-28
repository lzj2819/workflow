# T-B03c — RETENTION-GOVERNANCE：保留治理与 CT-011（Phase 5 / B-03）

- worktree：`tutor-app/.worktrees/B03c-retention`（分支 tutor-r01/B03c-retention，需先由协调者创建）
- 允许路径（仅这些）：
  - `server/course_app/teacher_web/retention/**`
  - `server/migrations/versions/0014_retention.py`（`down_revision="11a22f91f4b3"`）
  - `server/tests/test_b03c_*.py`

## 目标

实现保留治理（NFR-004/DF-3 除 SCENARIO-016 端到端声明外）：DeletionBatch 聚合、到期标记批处理、CT-011 删除确认端点接线、审计先行、CT-012 发布、CT-014 消费回写批次状态。**明确不声称 AssessmentResult 删除链路（CCR-001 pending）、不声称 SCENARIO-016 完成。**

## 交付物

1. 迁移 `0014_retention.py`：`deletion_batches`（batch_id、course_id、scope、retention_due_at、status(pending_mark/awaiting_confirm/executing/partially_failed/completed)、exclusions JSON、created_at、confirmed_at/operator）+ `deletion_audit_records`（追加：batch、动作、范围、操作者、时间；永久留存不在删除范围）。
2. 到期批处理 `mark_due_batches(now)`：retention_due_at = 课程结束时间 + 1 年（经 L01 CP-COURSE-ENDTIME 只读端口注入，FLOW-011 同进程），到期生成/更新待确认批次（幂等，可注入时钟）。
3. CT-011 端点（FastAPI APIRouter，不挂载）：`POST /api/v1/teacher/deletion-batches/{batch_id}/confirm`——confirm=true + exclusions[]；未到期 → BATCH_NOT_EXPIRED；同批次重复确认幂等；**审计记录先于任何清除动作写入**；确认后经 OutboxStore 抽象发布 CT-012（batch_id、submission_ids[]、scope、operator、executed_at、audit_record_id、v=1）。
4. CT-014 消费 handler：按 batch_id + purged_at 幂等更新批次状态（completed / partially_failed + failed_items 保留重跑）。
5. 与 L15 的 deletion_batches[] 视图和 L17 确认流的接线端口（M05-IC-06 读端口实现）。
6. 测试：到期标记（时钟注入）、未到期 409、审计先行顺序断言、CT-012 载荷与 contracts/ct-012.json 一致、CT-014 回写（含部分失败重跑）、批次视图端口。

## 禁止

- 实现/声称 MOD-04 AssessmentResult 删除接线（CCR-001 pending）；声称 SCENARIO-016 完成；改其他目录/契约；引入新依赖。

## 验证

- `python -m unittest discover -s server/tests -p "test_b03c_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`、迁移可导入

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B03c-completion.md`。
