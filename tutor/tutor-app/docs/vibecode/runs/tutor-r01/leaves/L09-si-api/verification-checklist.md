# Verification Checklist — L09

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l09_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有测试不得回归）
- [ ] `ruff check server/course_app/submission_intake/api server/tests/test_l09_si_api.py server/migrations/versions/0006_auth_tokens.py`
- [ ] `python -m py_compile` 新增/改动 .py
- [ ] 迁移可导入、revision/down_revision 正确

## 语义断言（测试必须覆盖）

- [ ] auth/token：正确凭据 → 200 + access_token/Bearer/expires_in；错误凭据 → 401 AUTH_INVALID；签发审计落库（不含明文令牌）
- [ ] CT-001：有效提交 → 30 秒内 200 + submission_id/received_at/status=received/missing_items；缺字段 → 400 VALIDATION_FAILED；未知令牌 → 401
- [ ] 归属校验拒绝 → status=rejected + rejection_reason（业务终态，非 4xx/5xx）
- [ ] 同一 submission_uuid 重复提交 → 同一 submission_id（幂等，无重复记录）
- [ ] CT-002：已知 uuid → status/failure_reason?/missing_items；未知 uuid → 404 NOT_FOUND
- [ ] 应答字段与 contracts/ct-001.json、ct-002.json、auth-token.json 一致
