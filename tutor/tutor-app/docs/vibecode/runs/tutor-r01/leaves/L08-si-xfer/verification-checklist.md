# Verification Checklist — L08

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l08_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 76 项不得回归）
- [ ] `ruff check server/course_app/submission_intake/xfer server/tests/test_l08_si_xfer.py server/migrations/versions/0005_upload_sessions.py`
- [ ] `python -m py_compile` 新增/改动 .py
- [ ] 迁移可导入、revision/down_revision 正确（down_revision="9c99fa53f9f8"）

## 语义断言（测试必须覆盖）

- [ ] 建会话 → 追分片（乱序）→ 合并：checkpoint 只含已确认分片；重复分片幂等
- [ ] 中断后会话可恢复续传（interrupted_retryable），失败终态（failed_terminal）不可再写
- [ ] 合并时总大小 >500MB 拒绝；白名单外类别拒绝
- [ ] 合并前不产生正式材料引用（SI-STORE 未接入时以抽象断言调用形状）
- [ ] 会话 TTL 过期处理（可注入时钟）
