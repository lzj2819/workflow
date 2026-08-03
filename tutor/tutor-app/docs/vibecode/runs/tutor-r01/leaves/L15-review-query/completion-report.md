# Completion Report — L15 CMP-REVIEW-QUERY（tutor-r01 / W3）

- leaf：L15；分支：`tutor-r01/L15-review-query`（worktree `.worktrees/L15-review-query`，基线 main 59ca070）
- 状态：**done**
- 提交 SHA：`c846a362db07bac3ba946e308a7ff8dc641bd155`

## 改动清单

全部在允许路径内，共 7 文件（+1152 行）：

- `server/course_app/teacher_web/review_query/__init__.py` — 包导出
- `server/course_app/teacher_web/review_query/errors.py` — 消费方错误冻结面（AUTH_INVALID/FORBIDDEN/NOT_FOUND/VALIDATION_FAILED + 端口失败与 RetryableQueryError）
- `server/course_app/teacher_web/review_query/ports.py` — ACCESS-GATE / M05-IC-02 / M05-IC-06 端口 Protocol 与视图 dataclass（ReadModelView、RetentionBatchView、AuthorizedQueryContext）
- `server/course_app/teacher_web/review_query/assemblers.py` — CMP-RQ-SCOPE-ASSEMBLER / SUBMISSION-DETAIL-ASSEMBLER / OUTCOME-ADAPTER / RETENTION-VIEW-ADAPTER
- `server/course_app/teacher_web/review_query/facade.py` — CMP-RQ-QUERY-FACADE + GATE 编排入口（端口失败 → RetryableQueryError，禁止 partial success）
- `server/course_app/teacher_web/review_query/router.py` — CT-007 视图族 APIRouter（不挂载）：课程列表 / 小组列表（可选 group_id 过滤）/ 学生详情 / 提交详情
- `server/tests/test_l15_review_query.py` — 15 项测试

## 关键语义落实

- 读模型经 M05-IC-02 端口注入消费；**未建读模型表/迁移、无投影逻辑**；无跨模块同步读。
- scoring_failed → failure_reason + retry_record，original_grade/final_grade/dimension_rationales/teacher_suggestions 一律不输出（不伪造等级，LCD-RQ-002）。
- deletion_batches[] 恒在响应中（无批次返回空数组，LCD-RQ-003）；仅暴露 CT-007 契约字段（batch_id/retention_due_at/scope/batch_status/exclusions）。
- ACCESS-GATE 端口注入调用；403 + AccessDeniedLogged 由其实现（stub 登记断言）；授权在 GATE 终止时读模型端口不被调用。
- M05-IC-02 / M05-IC-06 端口失败 → 503 可重试失败，无业务字段、不新增公共错误码（LCD-RQ-004）。

## 验证命令与结果（worktree 根）

- `python -m unittest discover -s server/tests -p "test_l15_*.py" -v` → **Ran 15 tests … OK**
- `python -m unittest discover -s server/tests` → **Ran 134 tests in 1.038s … OK**（既有 119 项无回归 + 新增 15 项）
- `ruff check server/course_app/teacher_web/review_query server/tests/test_l15_review_query.py` → **All checks passed!**
- `python -m py_compile`（6 个包文件 + 测试文件）→ **COMPILE_OK**

## 契约影响

无。未修改 `contracts/`、`shared/`、迁移目录或任何 W1/W2 实现；CT-007/M05-IC-02/M05-IC-06 字段、错误码、owner、只读语义未变。应答字段断言为 `contracts/ct-007.json` 出参子集（仅额外透出 M05-IC-02 既有输出字段 `missing_marks`，契约 additionalProperties=true 允许）。

## 风险/阻塞

- 风险（低）：读模型/批次/授权端口的真实实现归 backfill（PROJECTOR / RETENTION-GOVERNANCE / ACCESS-GATE），本叶子以注入 stub 验证装配语义；集成接线需在 backfill 阶段完成并挂载路由（本叶子按约定不挂载）。
- 无阻塞；无 contract-change-request。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD` 输出仅：

```
server/course_app/teacher_web/review_query/__init__.py
server/course_app/teacher_web/review_query/assemblers.py
server/course_app/teacher_web/review_query/errors.py
server/course_app/teacher_web/review_query/facade.py
server/course_app/teacher_web/review_query/ports.py
server/course_app/teacher_web/review_query/router.py
server/tests/test_l15_review_query.py
```

全部在 allowed-context.md 可写路径内；未触碰 forbidden-changes.md 任何条目。
