# Completion Report — L14 CMP-REVIEW-COMMAND（tutor-r01 / W3）

- leaf：L14；分支：`tutor-r01/L14-review-command`（worktree `.worktrees/L14-review-command`，基线 main 59ca070）
- 提交 SHA：`58b6ee918e8393f54a02e31091c5d60cb40eea8d`
- 状态：done

## 改动清单

| 文件 | 说明 |
|---|---|
| `server/course_app/teacher_web/review_command/__init__.py` | 公开面导出（服务/路由/端口/错误/模型） |
| `server/course_app/teacher_web/review_command/errors.py` | CT-008 冻结错误码映射：VALIDATION_FAILED→400、AUTH_INVALID→401、FORBIDDEN→403、NOT_FOUND→404、NO_ORIGINAL_GRADE→409 |
| `server/course_app/teacher_web/review_command/models.py` | ST-REVIEW-RECORD（ReviewRecord + GradeAdjustmentRecord）与 ST-IDEMPOTENCY-REVIEW SQLAlchemy 模型 |
| `server/course_app/teacher_web/review_command/ports.py` | ACCESS-GATE（实现归 backfill，仅调用）、L02 状态查询、M05-IC-05 事件端口抽象 + 进程内事件收集器 |
| `server/course_app/teacher_web/review_command/service.py` | GUARD（request_id / submission_id 双键幂等，LCD-003）+ POLICY（至少一项写字段、NO_ORIGINAL_GRADE 禁伪造、adjustment_reason 可选 TD-09/DD-007）+ WRITER（单事务写聚合+调整留痕+幂等记录，原始等级复制值不可变，后写为准）；含 M05-IC-01 创建端口实现（供 PROJECTOR 幂等调用） |
| `server/course_app/teacher_web/review_command/router.py` | CT-008 `PUT /api/v1/teacher/submissions/{submission_id}/review` APIRouter（不挂载）；请求/应答严格对齐 contracts/ct-008.json；M05-IC-05 事件提交后发布（LCD-004） |
| `server/migrations/versions/0007_review_records.py` | review_records / review_grade_adjustments / review_idempotency_keys 三表；`revision="0007_review_records"`、`down_revision="b9c6e3d6276a"` |
| `server/tests/test_l14_review_command.py` | 17 项测试，覆盖 checklist 全部语义断言 |

## 验证命令与结果（worktree 根）

- `python -m unittest discover -s server/tests -p "test_l14_*.py" -v` → **Ran 17 tests … OK**
- `python -m unittest discover -s server/tests` → **Ran 136 tests … OK**（既有 119 项无回归，新增 17 项）
- `ruff check server/course_app/teacher_web/review_command server/tests/test_l14_review_command.py server/migrations/versions/0007_review_records.py` → **All checks passed!**
- `python -m py_compile`（全部 8 个新增/改动 .py）→ **OK**
- 迁移可导入、revision/down_revision 正确 → 由 `TestMigration` 断言通过

## 语义断言覆盖对照

- 仅 annotation / 仅 final_grade 均可；两者皆缺 → 400 VALIDATION_FAILED ✔
- 同一 request_id 重复 → 同一复核记录（响应一致、无重复写入/调整记录）✔
- scoring_failed 且无原始等级 → final_grade 被拒（409 NO_ORIGINAL_GRADE，无部分写入），批注仍可保存 ✔
- original_grade/final_grade/operator/updated_at 同时保留；原始等级复制值不被后续调整改写 ✔
- 连续两次调整 → 后写为准；两条调整记录（唯一 adjustment_id + 前后值 + 操作者 + 时间）可追溯 ✔
- adjustment_reason 缺失正常保存（可选不强制，TD-09/DD-007/LCD-001）✔
- 应答字段与 contracts/ct-008.json 一致；未授权 → 403 且 ACCESS-GATE stub 断言被调用 ✔
- M05-IC-01 按 submission_id 幂等创建；重复 scored 不覆盖原始等级、不追加调整记录 ✔

## 契约影响

无。未修改 `contracts/`、`shared/`、既有迁移、W1/W2 实现或任何兄弟目录；CT-008/M05-IC-01/M05-IC-05 字段、错误码、幂等键与版本语义按冻结面实现。HTTP 状态码映射（409 for NO_ORIGINAL_GRADE）属实现细节，契约只冻结错误码。

## 风险 / 阻塞

- 无阻塞；未触发 contract-change-request（adjustment_reason 保持可选）。
- 轻微：ACCESS-GATE 真实实现、路由器挂载、M05-IC-05 与 RMP 的真实接线均归 backfill（任务边界内预期）。
- NO_ORIGINAL_GRADE → HTTP 409 为本叶子选用的映射（契约未冻结 HTTP 状态）；如集成层另有约定可在 backfill 统一调整。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD` 输出仅含 allowed-context 内的 8 个路径（review_command/**、0007_review_records.py、test_l14_review_command.py），无越界改动。
