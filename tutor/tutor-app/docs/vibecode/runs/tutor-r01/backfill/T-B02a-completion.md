# T-B02a Completion — MODEL-SERVICE-ACL + RESULT-PUBLISHER

- task：T-B02a（Phase 5 / B-02，依赖 T-B01b SqlaOutboxStore）
- SHA：`3dbf9fa6796bd931f259e22378be458921fbf4a2`（分支 tutor-r01/B02a-model-acl，worktree `.worktrees/B02a-model-acl`；合并 main 为 fast-forward，无冲突）
- 日期：2026-07-21

## 改动（仅限允许路径，8 个新文件，+1044 行）

1. `worker/assessment_worker/model_acl/`（ICT-004）
   - `acl.py` `ModelServiceAcl`：包装任意 ModelProvider；evaluate 顺序 = 出站最小化校验（复用 `validate_request`，含 submission_id/student_name/group_name/invite_code/course_id 禁发，违例时供应商零调用）→ 可注入时钟计时调用（默认预算 `MODEL_CALL_TIMEOUT_SECONDS`=180s，超预算或 TimeoutError → MODEL_TIMEOUT）→ CT-010 应答 schema 校验（复用 L12 `validate_model_response`）→ 返回已校验应答。
   - `errors.py` `AclError`：稳定 code 三分类（MODEL_TIMEOUT / MODEL_ERROR / INVALID_RESPONSE_SCHEMA），直接复用 L12 常量保证与 L03 ERROR_TAXONOMY 一致；子类化 `ModelProviderError` 并暴露 `error_kind`，L12 engine 既有 `getattr(exc, "error_kind")` 映射无需改动。
   - `fake_adapter.py` `FakeVendorAdapter`：把 FakeModelProvider 包装为可替换适配器，`vendor="fake"`/`is_fake=True` 标注 fake 来源；无网络、无密钥、确定性假输出。
2. `worker/assessment_worker/result_publisher/`（ICT-007）
   - `publisher.py` `ResultPublisher`：session 注入构造 `SqlaOutboxStore`；`publish_scored` / `publish_scoring_failed` 产出与 L03 既有入队载荷逐字段一致的 CT-005 载荷（dedup_key = `{submission_id}:{outcome}`，领域校验复用 L03 `validate_assessment_result`）；内部不 commit/rollback（KD-002 同事务语义归调用方）；`claim_due`/`confirm`/`retry`/`delivery_status` 提供投递确认端口。
3. `worker/tests/test_b02a_model_acl.py`（18 例）、`worker/tests/test_b02a_result_publisher.py`（10 例）。

## 验证（worktree 根，全绿）

- `python -m unittest discover -s worker/tests -p "test_b02a_*.py" -v`：28 例 OK。
- `python -m unittest discover -s worker/tests`：73 例 OK（无回归）。
- `ruff check <改动路径>`：All checks passed；`py_compile` 全部通过。

## 契约影响

- 无契约变更：CT-010 仅复用既有 `validate_request` 与 L12 response 校验；CT-005 载荷形状/dedup 规则与 L03 orchestrator 逐字段相等（测试内同事件双路径比对断言）；Outbox 语义复用 T-B01b SqlaOutboxStore（pending → delivering → confirmed / retry_wait）。
- 未改 L03/L12 既有代码、未改其他目录、未引入新依赖；未接真实供应商/密钥/网络；fake 来源已标注。

## 风险

- 预算守卫为同步计时（调用返回后判定超时），不能抢占式中断真实慢调用；真实供应商接入（DD-009 后续）时需在线程/客户端层补强制超时。
- L03 orchestrator 当前以实例注入 OutboxStore；生产装配时须保证终态事务 session 与 ResultPublisher 注入 session 为同一事务（本任务提供端口，组合根接线归后续任务）。
