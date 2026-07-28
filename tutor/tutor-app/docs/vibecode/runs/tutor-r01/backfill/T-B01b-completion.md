# T-B01b 完成记录 — SI-RELAY：PG Outbox 绑定 + 投递器 + 入站去重

- 日期：2026-07-21
- 分支/SHA：`tutor-r01/B01b-relay` @ `4ea8b68838167d9b158e751cae40cd6f03153c6d`（基线 main 917f8d1）
- worktree：`tutor-app/.worktrees/B01b-relay`

## 改动

| 路径 | 内容 |
|---|---|
| `server/migrations/versions/0010_outbox.py` | 新增。`outbox_records`（id/contract_id/payload JSON/dedup_key/status(pending/delivering/retry_wait/confirmed)/attempts/next_attempt_at/created_at + ix(status,next_attempt_at)）与 `inbound_event_dedup`（event_key 唯一主键/contract_id/status(received/processing/applied/retry_wait/quarantined)/attempts/last_error/updated_at）。`down_revision="11a22f91f4b3"`（并行多头，待集成 merge）。 |
| `shared/tutor_shared/outbox.py` | 仅追加：`OUTBOX_METADATA`/`OUTBOX_RECORDS_TABLE`（Core Table）+ `SqlaOutboxStore`（构造接收既有 Session，内部不 commit/rollback；enqueue 与业务同事务；fetch_due 在 PG 用 `FOR UPDATE SKIP LOCKED`、SQLite 退化为同事务内条件更新认领；mark_confirmed/mark_retry 实现 ABC 语义，退避沿用 `default_backoff`）。sqlalchemy 导入带 ImportError 守卫，缺失环境既有 ABC/内存实现语义与可导入性不变。 |
| `server/course_app/submission_intake/relay/models.py` | 新增。ST-05 `InboundDedupRecord` ORM 模型（与迁移 DDL 一致）。 |
| `server/course_app/submission_intake/relay/dedup.py` | 新增。`InboundDedup`（同 Session 去重检查+业务处理，不 commit）：首次 received→processing→applied；重复（applied/quarantined）→ DUPLICATE 不再应用、记录不推进；可重试异常 → retry_wait 交还重投；`QuarantineError` → quarantined，不阻塞后续合法事件。`DedupOutcome` 枚举。 |
| `server/course_app/submission_intake/relay/relayer.py` | 新增。`OutboxRelayer`：poll_once 认领（一个事务提交）→ 逐条投递（contract_id→handler）→ 成功 mark_confirmed / 异常 mark_retry（各一个事务），无限重试直至确认；`run`/`stop` 轮询（DD-006 基线 1s/50）。结构化日志仅含 outbox_id/contract_id/attempts/error_type，不记 payload。 |
| `server/tests/test_b01b_relay.py` | 新增。15 个测试（SQLite 文件库 + 内存 handler spy）。 |

## 验证（worktree 根，全绿）

- `python -m unittest discover -s server/tests -p "test_b01b_*.py"`：15 通过。
- `python -m unittest discover -s server/tests`：198 通过（无回归）。
- `python -m unittest discover -s worker/tests`：45 通过（shared/outbox.py 追加未影响 worker）。
- `ruff check`（全部改动路径）：All checks passed。
- `py_compile`：全部改动文件通过。
- 迁移可导入：`revision="0010_outbox"`、`down_revision="11a22f91f4b3"` 断言通过。

覆盖语义：同事务可见性/回滚全消；fetch_due 认领互斥与 limit；退避推进（到期前不可见/到期后重投、显式 next_attempt_at）；确认后不再投递；失败重试直至确认；未知 contract 进 retry；日志不含 payload；入站重复不重复应用且不推进去重记录；retry_wait→applied；quarantine 路径与不阻塞后续事件；去重与业务同事务回滚全消。

## 契约影响

- 无契约语义变更，未触发 CCR。ST-04/ST-05 按 L1-mod-02 `03-state-and-data.md` 状态机落地；事件键派生（CT-005：submission_id+终态；CT-012：batch_id+载荷哈希）由消费方负责，本任务仅提供机制。
- 为 T-B02a（MOD-04 RESULT-PUBLISHER 经 SQL Outbox 发布）与 T-B03b/c 提供 `SqlaOutboxStore` 与 `InboundDedup` 复用点。

## 风险

- `fetch_due` 的 `FOR UPDATE SKIP LOCKED` 分支仅经 SQLite 退化路径单测验证，PG 并发认领语义需集成环境（T-B05 E2E 或 PG 冒烟）复核；其余无已知风险。
