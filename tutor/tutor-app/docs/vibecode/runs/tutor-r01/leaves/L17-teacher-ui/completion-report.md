# Completion Report — L17 CMP-TEACHER-UI（tutor-r01，W3）

- 状态：done
- 提交 SHA：`70119ae6b07c877938c55a263e56f1ca6985f436`（分支 `tutor-r01/L17-teacher-ui`，基线 main `59ca070`）

## 改动清单

全部位于允许路径内（16 文件，+1688/-1）：

- `server/course_app/teacher_web/ui/client.py`：注入式 API 客户端层。`TeacherApiClient` Protocol（CT-007 query_view / CT-008 save_review / CT-009 generate_presentation / CT-011 confirm_deletion_batch / 会话 create_session）+ `HttpTeacherApiClient`（httpx，仅向冻结端点发调用，不实现端点）；冻结错误码与等级/状态枚举。
- `server/course_app/teacher_web/ui/view_models.py`：PageViewModel 装配；缺失字段显式 missing，不填默认等级；scoring_failed 透传 failure_reason/retry_record；missing_marks 原样可见。
- `server/course_app/teacher_web/ui/views.py`：SSR 路由工厂 `create_router(api_client=...)`（不挂载）。登录、课程/小组/学生列表、提交详情+复核表单（CT-008，request_id 在交互边界生成 uuid4）、展示视图选择与渲染（CT-009）、删除批次确认页（CT-011 仅调用）。AUTH_INVALID→登录重定向；FORBIDDEN→403 访问拒绝页；NO_ORIGINAL_GRADE/NO_AVAILABLE_SUBMISSION/BATCH_NOT_EXPIRED 冻结语义呈现。
- `server/course_app/teacher_web/ui/templates/`（11 个 Jinja2 模板）：base（内联 CSS + 原生 JS 提交锁定/删除二次确认，无前端框架/构建链）、login、courses、groups、students、submission_detail、presentation_select、presentation、deletion_batch、deletion_batch_result、error。
- `server/course_app/teacher_web/ui/__init__.py`：导出面。
- `server/tests/test_l17_teacher_ui.py`：19 项测试（spy 注入 stub；TestClient）。

## 验证命令与结果（worktree 根执行）

- `python -m unittest discover -s server/tests -p "test_l17_*.py" -v` → Ran 19 tests，OK
- `python -m unittest discover -s server/tests` → Ran 138 tests，OK（既有 119 项无回归，新增 19 项）
- `ruff check server/course_app/teacher_web/ui server/tests/test_l17_teacher_ui.py` → All checks passed!
- `python -m py_compile`（ui 全部 .py + 测试文件）→ OK

语义断言覆盖：详情页材料/状态/原始等级/五维依据/建议/批注/编辑入口；展示页 blocks+missing_marks 可见；删除批次页状态/到期/范围/排除标记+确认（spy 断言 confirm=True、exclusions、batch_id）；scoring_failed 展示真实原因与重试结果且无等级显示（无 grade-value、无 final_grade 编辑入口）；CT-008 提交 spy 断言 request_id 幂等键携带；登录页无令牌明文、会话 Cookie HttpOnly、页面不回显 token。

## 契约影响

无。未修改 `contracts/`、`shared/`、迁移、兄弟叶子；未新增/改变 CT-007/008/009/011 字段、错误码或幂等语义；CT-011 只调用不实现（端点归 backfill）；教师会话端点（`/api/v1/teacher/session`）仅客户端对接，校验归平台/backfill。

## 风险/阻塞

- 低风险：SSR 页面路由（/teacher/...）挂载归平台装配（main.py 未动）；`HttpTeacherApiClient` 未做真实 HTTP 联调（L14/L15/L16 未集成，按任务要求注入 stub）。
- 无阻塞。

## 范围自检

`git diff --name-only main...HEAD` 输出 16 个文件，全部在
`server/course_app/teacher_web/ui/**` 与 `server/tests/test_l17_teacher_ui.py`
允许路径内，无越界改动。
