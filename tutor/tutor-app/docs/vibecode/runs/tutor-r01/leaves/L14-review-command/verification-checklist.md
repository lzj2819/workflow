# Verification Checklist — L14

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l14_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 119 项不得回归）
- [ ] `ruff check server/course_app/teacher_web/review_command server/tests/test_l14_review_command.py server/migrations/versions/0007_review_records.py`
- [ ] `python -m py_compile` 新增/改动 .py
- [ ] 迁移可导入、revision/down_revision 正确

## 语义断言（测试必须覆盖）

- [ ] 保存批注（仅 annotation）与调整等级（仅 final_grade）均可；两者皆缺 → 400 VALIDATION_FAILED
- [ ] 同一 request_id 重复请求 → 同一复核记录（幂等，无重复写入）
- [ ] scoring_failed 且无原始等级 → 设置 final_grade 被拒（NO_ORIGINAL_GRADE），批注仍可保存
- [ ] 复核记录同时保留 original_grade/final_grade/operator/updated_at；原始等级复制值不被后续调整改写
- [ ] 连续两次调整 → 后写为准且两次调整记录均可追溯
- [ ] adjustment_reason 缺失时正常保存（可选不强制）
- [ ] 应答字段与 contracts/ct-008.json 一致；未授权 → 403（ACCESS-GATE 注入断言被调用）
