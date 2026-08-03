# Verification Checklist — L16

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l16_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 119 项不得回归）
- [ ] `ruff check server/course_app/teacher_web/presentation server/tests/test_l16_presentation.py server/migrations/versions/0008_presentation_views.py`
- [ ] `python -m py_compile` 新增/改动 .py
- [ ] 迁移可导入、revision/down_revision 正确

## 语义断言（测试必须覆盖）

- [ ] 选定小组生成视图：presentation_id + blocks[] 与所选小组一一对应（含 project_result/process_summary/grades/annotations/missing_marks）
- [ ] 任一小组无可用提交 → NO_AVAILABLE_SUBMISSION + 原因说明，不产生视图
- [ ] 相同参数重复生成 → 返回最新快照，不产生重复视图记录（幂等）
- [ ] 小组缺某类材料 → blocks 中 missing_marks 显式列出（不隐藏）
- [ ] 快照写入后不随读模型后续变化而改变（一次性快照）；应答字段与 contracts/ct-009.json 一致
