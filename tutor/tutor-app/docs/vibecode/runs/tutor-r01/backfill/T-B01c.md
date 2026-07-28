# T-B01c — SI-PURGE：CT-012 清除执行与 CT-014 回传（Phase 5 / B-01）

- worktree：`tutor-app/.worktrees/B01c-purge`（分支 tutor-r01/B01c-purge，基线 main 917f8d1）
- 允许路径（仅这些）：
  - `server/course_app/submission_intake/purge/**`
  - `server/tests/test_b01c_purge.py`（及 `server/tests/b01c_*.py` 辅助）

## 目标

实现 CT-012 RecordsDeleted 消费（IC-SI-06）：按 submission_ids[] 清除材料（SI-STORE delete）与提交记录（L02 purge_submission → deleted），汇总结果经 CT-014 PurgeCompleted 回传（失败项保留供重跑；审计记录不受影响）。

## 交付物

1. `PurgeExecutor`：输入 CT-012 payload（batch_id、submission_ids[]、scope、operator、executed_at、audit_record_id）→ 逐项清除（材料删除经 MaterialStorePort.delete + MaterialFile 登记状态；提交记录经 L02 purge_submission 幂等）→ PurgeExecution 记录（ST-07：batch_id、逐项结果、失败原因）。
2. 幂等：重复 CT-012（同 batch_id）对已删项为空操作；失败项可在重跑中成功。
3. CT-014 载荷生成：batch_id、purged_submission_ids[]、failed_items[]（submission_id+reason）、purged_at、v=1，经 OutboxStore 抽象同事务入队（投递归 RELAY）。
4. 单元测试（SQLite + tmp_path 磁盘 + 内存 Outbox）：全部成功、部分失败（failed_items 含原因）、重跑幂等、CT-014 字段与 contracts/ct-014.json 一致、提交记录终态 deleted 且不可再读（经 L02 query 验证）。

## 禁止

- 实现/声称 AssessmentResult（MOD-04）删除接线（CCR-001 pending）；声称 SCENARIO-016 完成；改其他目录/契约。

## 验证

- `python -m unittest discover -s server/tests -p "test_b01c_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B01c-completion.md`。
