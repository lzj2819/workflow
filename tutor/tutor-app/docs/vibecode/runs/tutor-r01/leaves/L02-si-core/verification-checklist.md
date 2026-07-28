# Verification Checklist — L02

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l02_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有测试不得回归）
- [ ] `ruff check server/submission_intake/core server/tests/test_l02_si_core.py server/migrations/versions/0003_submission_core.py`
- [ ] `python -m py_compile` 新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] 六态迁移守卫：合法路径（received→processing→scored；received→processing→scoring_failed；→upload_failed；→rejected；→deleted）通过，非法迁移拒绝
- [ ] 终态不可逆；重复 CT-005 终态事件不改状态（幂等）
- [ ] 同一 submission_uuid 重复创建 → 同一 submission_id，无重复记录
- [ ] 完整性报告：空材料目录类别进入 missing_items；缺失不显式隐藏
- [ ] 状态推进（received/upload_failed）时 Outbox 行与业务写入同事务（以内存 OutboxStore 断言入队载荷含 CT-004/CT-006 必填字段与 dedup_key）
- [ ] 迁移文件可导入、revision/down_revision 正确
