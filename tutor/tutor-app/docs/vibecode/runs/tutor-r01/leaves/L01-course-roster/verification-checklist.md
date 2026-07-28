# Verification Checklist — L01

运行目录：worktree 根。全部通过才算完成。

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l01_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 35 项不得回归）
- [ ] `ruff check server/course_roster server/tests/test_l01_course_roster.py server/migrations/versions/0002_course_roster.py`
- [ ] `python -m py_compile` 所有新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] CT-003：邀请码+姓名+小组命中名单 → verified=true + course_id；未命中 → verified=false + reason（区分邀请码无效/名单未命中）
- [ ] 每次调用重新直读：修改名单后下一次调用即生效（无缓存）
- [ ] 每次调用产生独立 VerificationRecord（含 invite_code/student_name/group_name/verified/reason?/verified_at）
- [ ] 名单查询异常 → ROSTER_UNAVAILABLE 语义（不向调用方暴露内部细节）
- [ ] CT-013：导入去重（姓名+小组）、格式错误逐项报告、conflicts[]、部分成功可见、重复导入幂等
- [ ] CT-003/CT-013 router 应答必填字段与 contracts/ct-003.json、ct-013.json 一致
- [ ] CP-COURSE-ENDTIME 只读端口返回 course_end_time
- [ ] 运维预置工具可创建课程+邀请码（CLI 可运行、幂等）
- [ ] 迁移文件可导入、revision/down_revision 正确
