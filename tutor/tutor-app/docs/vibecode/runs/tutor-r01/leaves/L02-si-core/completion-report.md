# Completion Report — L02 SI-CORE（tutor-r01, W1）

- leaf：L02 SI-CORE（MOD-02 submission-intake 提交聚合核心）
- 分支：`tutor-r01/L02-si-core`
- 提交 SHA：`2970b01`（feat(l02): SI-CORE submission aggregate, state machine, integrity report, single-tx outbox）
- 状态：**done**

## 改动清单

| 文件 | 内容 |
|---|---|
| `server/course_app/submission_intake/core/__init__.py` | 包公共导出（SubmissionCoreService 等） |
| `server/course_app/submission_intake/core/errors.py` | 错误码：ILLEGAL_TRANSITION / NOT_FOUND / MATERIAL_METADATA_UNAVAILABLE / VALIDATION_FAILED |
| `server/course_app/submission_intake/core/status.py` | 六态+deleted 状态机与迁移守卫（INV-2，终态不可逆） |
| `server/course_app/submission_intake/core/models.py` | ST-01 三表模型（submissions / submission_materials / submission_integrity_reports，sa.JSON，SQLite/PG 可移植） |
| `server/course_app/submission_intake/core/integrity.py` | SI-CORE-INTEGRITY：清单+完整性报告、missing_items 显式标记（INV-3/4）；SI-STORE 元数据端口 Protocol（抽象注入） |
| `server/course_app/submission_intake/core/aggregate.py` | SI-CORE-AGG：创建/推进/终态回写/清除命令与守卫；幂等（uuid、submission_id+outcome、重复 ack/已删） |
| `server/course_app/submission_intake/core/service.py` | SI-CORE-TX / IC-SI-04 端口：ConfirmReceived/MarkRejected/MarkUploadFailed/AdvanceToProcessing/ApplyScoringOutcome/PurgeSubmission/query_by_uuid；业务写入+CT-004/CT-006 Outbox 同事务入队（dedup_key=submission_id） |
| `server/migrations/versions/0003_submission_core.py` | 新建三表；`revision=0003_submission_core`，`down_revision="0001_baseline"` |
| `server/tests/test_l02_si_core.py` | 22 个单测（SQLite :memory: + InMemoryOutboxStore） |

## 验证命令与结果（worktree 根）

- `python -m unittest discover -s server/tests -p "test_l02_*.py" -v` → `Ran 22 tests ... OK`（全绿）
- `python -m unittest discover -s server/tests` → `Ran 57 tests ... OK`（既有 35 个无回归）
- `ruff check server/course_app/submission_intake/core server/tests/test_l02_si_core.py server/migrations/versions/0003_submission_core.py` → `All checks passed!`
- `python -m py_compile`（9 个新增/改动 .py）→ 通过

语义断言覆盖：合法路径 received→processing→scored / scoring_failed、∅→rejected / upload_failed、→deleted；非法迁移与终态不可逆（ILLEGAL_TRANSITION 且无副作用）；重复 CT-005 终态事件 duplicate_ignored 不改终态/版本；同 uuid 重复创建返回同一 submission_id、单行、无重复事件；空材料目录 missing_items 全量标记仍 received 且 CT-004 照发；received/upload_failed 时 Outbox 同事务（CT-004/CT-006 必填字段+v=1+dedup_key=submission_id；元数据失败整体回滚无孤立 Outbox）；rejected 不发事件；迁移文件 revision/down_revision 正确。

## 契约影响

无。CT-001~CT-014 与 internal-contracts.json 零变更；Outbox 载荷按冻结 schema（CT-004/CT-006 v=1）组装；未新增跨模块契约。

## 范围自检

`git diff --name-only main...HEAD` 输出仅上述 9 个文件，全部在允许路径内（`server/course_app/submission_intake/core/**`、`server/migrations/versions/0003_submission_core.py`、`server/tests/test_l02_si_core.py`；路径前缀以协调者更正后的 `course_app` 布局为准）。未触碰 contracts/、shared/、course_app 其他部分、兄弟目录与既有迁移。SI-XFER/API/STORE/VERIFY/RELAY/PURGE 均未实现，依赖全部抽象注入。

## 实现说明（implementation_detail，供登记 findings）

- `received_at` 在三条创建命令落库时即写入（intake 记录定型时间），保证 upload_failed 终态的 CT-006 载荷仍满足 schema 的 `received_at` 必填 date-time。
- Outbox 表（ST-04）不在本迁移：归 SI-RELAY，按 0001_baseline 注释由 Integration Owner 在投递器 backfill 迁移建立；本叶子只保证经 `OutboxStore` 抽象在事务内入队与去重键。
- rejected/upload_failed 的身份字段可空（归属校验未通过时 course_id 未知）；received 路径强制四字段非空；事件载荷以 `or ""` 兜底仅用于可选身份缺失的极端路径。

## 风险/阻塞

无阻塞。残余风险（低）：Outbox 同事务语义当前以内存 OutboxStore 断言，真实 SQL 实现（SI-RELAY backfill）需绑定同一 Session 才能继承同事务回滚；已在 service 层把 enqueue 置于事务内、commit 前，backfill 只需提供 Session 绑定实现。
