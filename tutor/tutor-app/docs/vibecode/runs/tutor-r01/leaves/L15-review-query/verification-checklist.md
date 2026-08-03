# Verification Checklist — L15

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l15_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 119 项不得回归）
- [ ] `ruff check server/course_app/teacher_web/review_query server/tests/test_l15_review_query.py`
- [ ] `python -m py_compile` 新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] 课程/小组/学生/提交详情各视图返回 CT-007 出参字段（含 material_refs/status/original_grade/dimension_rationales/teacher_suggestions/annotations/final_grade）
- [ ] 提交详情含 deletion_batches[]（batch_id/retention_due_at/scope/batch_status/exclusions）
- [ ] scoring_failed → 返回 failure_reason + retry_record，无任何等级字段填充
- [ ] 无权课程 → 403 且 ACCESS-GATE 端口被调用（AccessDeniedLogged 由其实现）
- [ ] 应答字段与 contracts/ct-007.json 一致；读模型经 M05-IC-02 端口注入（未自建表）
