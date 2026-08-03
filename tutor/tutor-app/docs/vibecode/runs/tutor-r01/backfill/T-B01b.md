# T-B01b — SI-RELAY：PG Outbox 绑定 + 投递器 + 入站去重（Phase 5 / B-01）

- worktree：`tutor-app/.worktrees/B01b-relay`（分支 tutor-r01/B01b-relay，基线 main 917f8d1）
- 允许路径（仅这些）：
  - `server/course_app/submission_intake/relay/**`
  - `shared/tutor_shared/outbox.py`（**仅追加** SQL 实现类，不得改既有抽象/内存实现语义）
  - `server/migrations/versions/0010_outbox.py`（`down_revision="11a22f91f4b3"`）
  - `server/tests/test_b01b_relay.py`（及 `server/tests/b01b_*.py` 辅助）

## 目标

KD-002 落地：业务写入与 Outbox 行同一本地事务；投递器无限重试直至消费方确认；消费方按业务键幂等（ST-04 OutboxRecord / ST-05 InboundEventDedup）。

## 交付物

1. 迁移 `0010_outbox.py`：`outbox_records`（id、contract_id、payload JSON、dedup_key、status(pending/delivering/retry_wait/confirmed)、attempts、next_attempt_at、created_at）+ `inbound_event_dedup`（event_key 唯一、contract_id、status(received/processing/applied/retry_wait/quarantined)、attempts、last_error、updated_at）。
2. `SqlaOutboxStore`（shared/tutor_shared/outbox.py 追加）：构造接收既有 SQLAlchemy Session（**不自建事务**），enqueue 用同一 session 写行（业务+事件同事务，由调用方提交）；实现 OutboxStore ABC（enqueue/fetch_due/mark_confirmed/mark_retry；fetch_due 用 `FOR UPDATE SKIP LOCKED`（PG）/ SQLite 退化为普通更新）。
3. 投递器 `OutboxRelayer`：轮询（间隔/批量可配，DD-006 基线 1s/50）→ 取 due → 调注册的 consumer（contract_id → handler）→ 成功 mark_confirmed / 异常 mark_retry（default_backoff）；结构化日志（不含 payload 内容，只含 id/contract/attempts）。
4. 入站去重 `InboundDedup`：handler 包装器——按 event_key 首次 applied 后跳过重复投递（重复事件不改变终态）；失败进 retry_wait 交还投递器；不可解析进 quarantined。
5. 测试（SQLite + 内存 handler spy）：同事务语义（enqueue 后 session 未提交不可见、提交后可见、回滚全消）、fetch_due 认领互斥、retry 退避推进、确认后不再投递、入站重复事件不重复应用、quarantine 路径。

## 禁止

- 改既有 OutboxStore ABC / InMemoryOutboxStore 语义；改 relay 以外目录（除 shared/outbox.py 追加与迁移/测试）；引入消息中间件/新依赖。
- 在 SqlaOutboxStore 内部 commit/rollback（事务边界归调用方）。

## 验证

- `python -m unittest discover -s server/tests -p "test_b01b_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（既有测试不得回归）
- `ruff check <改动路径>`、`py_compile`、迁移可导入且 down_revision 正确

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B01b-completion.md`。
