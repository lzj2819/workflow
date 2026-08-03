# Verification Checklist — L17

## 命令

- [ ] `python -m unittest discover -s server/tests -p "test_l17_*.py" -v` 全绿
- [ ] `python -m unittest discover -s server/tests` 全绿（既有 119 项不得回归）
- [ ] `ruff check server/course_app/teacher_web/ui server/tests/test_l17_teacher_ui.py`
- [ ] `python -m py_compile` 新增/改动 .py

## 语义断言（测试必须覆盖）

- [ ] 课程/小组/学生/提交详情页渲染包含：材料清单、状态、原始等级、五维依据、教师建议、批注、最终等级编辑入口（stub API 数据驱动）
- [ ] 展示视图页渲染 blocks 与 missing_marks（缺失可见不隐藏）
- [ ] 删除批次页渲染批次状态/到期/范围/排除标记 + 确认入口（仅发起 CT-011 API 调用，spy 断言，不实现端点）
- [ ] scoring_failed 页面展示失败原因与重试结果，无等级显示
- [ ] 最终等级编辑表单提交走 CT-008 客户端（spy 断言 request_id 幂等键携带）
- [ ] 登录页仅对接会话 API；页面不含 secret/令牌明文
