# Verification Checklist — L12

## 命令

- [ ] `python -m unittest discover -s worker/tests -p "test_l12_*.py" -v` 全绿
- [ ] `python -m unittest discover -s worker/tests` 全绿（既有 32 项不得回归）
- [ ] `ruff check worker/assessment_worker/assessment_engine worker/tests/test_l12_assessment_engine.py`
- [ ] `python -m py_compile` 新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] 完整链路：ClaimedTask 上下文 → prompt 组装 → 材料加载 → fake evaluate → 结果装配（原始等级/五维/建议）
- [ ] CT-010 请求校验：不含 submission_id/student_name/group_name/course_id（数据最小化断言）
- [ ] 应答 schema 校验：非法应答 → INVALID_RESPONSE_SCHEMA 分类（映射 ICT-006）
- [ ] missing_items 非空 → 结果含缺失材料影响说明
- [ ] 成功输出形状与 L03 complete_assessment 参数兼容；失败输出与 fail_assessment 兼容
- [ ] fake 来源在结果/日志中可追溯（不假扮真实评估）
