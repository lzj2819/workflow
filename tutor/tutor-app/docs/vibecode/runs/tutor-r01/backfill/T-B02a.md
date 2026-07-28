# T-B02a — MODEL-SERVICE-ACL + RESULT-PUBLISHER（Phase 5 / B-02）

- worktree：`tutor-app/.worktrees/B02a-model-acl`（分支 tutor-r01/B02a-model-acl，需先由协调者创建）
- 允许路径（仅这些）：
  - `worker/assessment_worker/model_acl/**`
  - `worker/assessment_worker/result_publisher/**`
  - `worker/tests/test_b02a_*.py`

## 目标

1. MODEL-SERVICE-ACL（ICT-004）：可替换的模型调用防腐层——出站数据最小化校验（复用 model_provider.validate_request，禁业务标识）+ 单次 ≤3 分钟预算守卫 + 应答 CT-010 schema 校验 + 错误三分类（MODEL_TIMEOUT/MODEL_ERROR/INVALID_RESPONSE_SCHEMA）；接口可替换（供应商适配为后续实现细节，**本任务只提供 fake 适配，不接真实供应商、不配置密钥、不发网络请求**）。
2. RESULT-PUBLISHER（ICT-007）：CT-005 事件经 SQL Outbox（T-B01b SqlaOutboxStore）的发布端口——为 L03 终态事务提供与 PG 绑定的 OutboxStore 装配（session 注入），并验证 CT-005 scored/scoring_failed 载荷的发布与投递确认语义（消费方确认前不推进 outbox 状态；消费确认语义同 T-B01b）。

## 交付物

1. `ModelServiceAcl`：包装任意 ModelProvider；evaluate(request) → 校验请求（最小化）→ 计时调用 → 校验应答（grade/五维/suggestions 形状；非法应答 → INVALID_RESPONSE_SCHEMA）→ 返回或分类异常（AclError 携带三分类 code）。
2. `FakeVendorAdapter`：把 FakeModelProvider 包装为 ACL 的可替换适配器（标注 fake 来源）。
3. `ResultPublisher`：以 session 注入的 SqlaOutboxStore 实现 CT-005 发布端口（enqueue 于 L03 终态事务内）；投递状态查询（pending/confirmed）供断言。
4. 测试：最小化拒绝（含 submission_id 的请求）、schema 非法应答分类、超时分类（注入慢 fake）、fake 适配器端到端（L12 engine → ACL → fake）、CT-005 经 SQL outbox 发布+确认流转（SQLite）。

## 禁止

- 接真实供应商/网络/密钥；外发材料或业务标识；改 L03/L12 既有代码（只提供装配端口）；改其他目录。

## 验证

- `python -m unittest discover -s worker/tests -p "test_b02a_*.py" -v` 全绿
- `python -m unittest discover -s worker/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B02a-completion.md`。
