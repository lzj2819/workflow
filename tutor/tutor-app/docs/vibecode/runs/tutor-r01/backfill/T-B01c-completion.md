# T-B01c 完成记录 — SI-PURGE：CT-012 清除执行与 CT-014 回传

- 日期：2026-07-21
- 分支：tutor-r01/B01c-purge（worktree tutor-app/.worktrees/B01c-purge）
- 提交 SHA：fd44fd6（基线：merge main ddddb482，fast-forward 无冲突）

## 改动

新增（均在允许路径内）：

- `server/course_app/submission_intake/purge/__init__.py` — 公共入口导出。
- `server/course_app/submission_intake/purge/errors.py` — `PurgeValidationError`（CT-012 载荷不合冻结契约）。
- `server/course_app/submission_intake/purge/models.py` — ST-07 持久化：`PurgeExecutionRow`（batch_id 主键、scope/operator/audit_record_id 快照、status partial/completed、run_count、first/last_executed_at）+ `PurgeExecutionItemRow`（batch_id+submission_id 唯一、result purged/failed、reason）；独立 `Base`。
- `server/course_app/submission_intake/purge/executor.py` — `PurgeExecutor`：
  - `validate_ct012` 按 contracts/ct-012.json 校验（必填/多余字段/v=1/非空字符串），批次内重复 submission_id 去重；
  - 逐项独立小事务：清单 material_refs（SubmissionMaterial）→ `MaterialStorePort.delete`（幂等，MaterialFile 登记转 deleted、配额扣减）→ L02 `purge_submission`（→ deleted，已删 duplicate_ignored 空操作）；单项失败（NotFound/StorageIoError/暂态）记 failed 不阻塞其他项；
  - ST-07 登记 upsert：重跑更新既有行（run_count 递增、failed→purged、reason 清空、批次转 completed），不新增行；
  - CT-014 载荷 `{batch_id, purged_submission_ids[], failed_items[{submission_id, reason}], purged_at, v=1}`，dedup_key=`batch_id:purged_at`（冻结幂等键），经 `OutboxStore` 抽象与登记行同事务入队（支持实例或 `Callable[[Session], OutboxStore]` 工厂，SQL 接线直接传 `SqlaOutboxStore`）；投递归 SI-RELAY。
- `server/tests/test_b01c_purge.py` — 8 个单测（SQLite StaticPool 内存库 + tmp 磁盘 DATA_DIR + 内存 Outbox；真实 FilesystemMaterialStore + SubmissionCoreService）。

## 验证

- `python -m unittest discover -s server/tests -p "test_b01c_*.py" -v`：8/8 通过。
- `python -m unittest discover -s server/tests`（全量无回归）：224/224 通过。
- `ruff check server/course_app/submission_intake/purge server/tests/test_b01c_purge.py`：All checks passed。
- `py_compile` 全部新增文件：通过。

测试覆盖：全部成功（磁盘删除/登记 deleted/配额扣减/提交终态 deleted 经 L02 query_by_uuid 验证/ST-07 completed）；CT-014 载荷 jsonschema 校验 contracts/ct-014.json + 字段全集 + dedup_key；部分失败（未知 submission_id 含原因、批次 partial、失败项保留）；重跑（模拟 StorageIoError 暂态后成功、登记更新、新发 CT-014）；重复 CT-012 幂等（Submission.version 不变、材料保持 deleted、仍计 purged 回传）；契约拒绝无副作用；SQL Outbox 工厂同事务入队；批次内重复 id 去重。

## 契约影响

- 无契约变更：CT-012 仅消费（校验对齐 contracts/ct-012.json），CT-014 载荷与 contracts/ct-014.json 逐字段一致（jsonschema 验证），不改任何冻结文件。
- 未触碰 AssessmentResult（MOD-04）删除链路（CCR-001 pending）；未声称 SCENARIO-016。

## 风险 / 集成跟进

1. **ST-07 表无 alembic 迁移**（迁移不在 T-B01c 允许路径）：`purge_executions` / `purge_execution_items` 需集成阶段补迁移（down_revision=11a22f91f4b3 多头之一，merge heads 时一并处理）；单测经 `metadata.create_all` 建表。
2. 每次执行（含幂等重跑）各发一条 CT-014（purged_at 不同）；消费侧按 batch_id+purged_at 去重为冻结语义，重复回传内容一致，无副作用；CT-012 入站去重归 SI-RELAY ST-05。
3. 审计记录不在本模块范围（归 MOD-05），仅登记 audit_record_id 引用；未验证 MOD-05 侧消费（属 T-B03c）。
