# Completion Report — L16 CMP-PRESENTATION（tutor-r01, W3）

- leaf：L16 CMP-PRESENTATION（MOD-05 展示视图生成与快照，CT-009 / REQ-010）
- 分支：`tutor-r01/L16-presentation`（worktree `.worktrees/L16-presentation`，基线 main 59ca070）
- 提交 SHA：**34bb13bd66da8869ad1477036d2fcdef12fa1986**
- 状态：done

## 改动清单

新增/改动（全部在 allowed-context 内）：

- `server/course_app/teacher_web/presentation/__init__.py`（公共出口）
- `.../presentation/errors.py`（冻结错误码 AUTH_INVALID/FORBIDDEN/VALIDATION_FAILED/NO_AVAILABLE_SUBMISSION → 401/403/400/409）
- `.../presentation/ports.py`（M05-IC-02 读模型查询端口 Protocol + 冻结 DTO；ACCESS-GATE 端口 Protocol；缺失枚举 对话/代码/截图/结果）
- `.../presentation/models.py`（ST-PRESENTATION-VIEW `presentation_views`、ST-IDEMPOTENCY-PRESENTATION `presentation_idempotency`）
- `.../presentation/missing_marks.py`（CMP-PRES-MISSING-MARKS：资格判定 + 显式缺失标记，纯函数）
- `.../presentation/assembler.py`（CMP-PRES-BLOCK-ASSEMBLER：CT-009 blocks[] 装配）
- `.../presentation/store.py`（CMP-PRES-SNAPSHOT-STORE：单写方；幂等命中、同事务写入、跨时间窗 supersede）
- `.../presentation/coordinator.py`（CMP-PRES-GENERATION-COORDINATOR：唯一编排入口）
- `.../presentation/output.py`（CMP-PRES-OUTPUT-ADAPTER：CT-009 稳定响应 + 静态 HTML 导出，v1 无 PDF）
- `.../presentation/router.py`（CT-009 APIRouter，`POST /api/v1/teacher/presentations`，不挂载）
- `server/migrations/versions/0008_presentation_views.py`（`down_revision="b9c6e3d6276a"`，alembic 单 head 验证通过，upgrade/downgrade 实测通过）
- `server/tests/test_l16_presentation.py`（13 项）

## 验证命令与结果（worktree 根，尾部输出）

- `python -m unittest discover -s server/tests -p "test_l16_*.py" -v` → `Ran 13 tests ... OK`
- `python -m unittest discover -s server/tests` → `Ran 132 tests in 0.924s / OK`（既有 119 项无回归，119+13=132）
- `ruff check server/course_app/teacher_web/presentation server/tests/test_l16_presentation.py server/migrations/versions/0008_presentation_views.py` → `All checks passed!`
- `python -m py_compile <全部新增/改动 .py>` → COMPILE_OK
- 迁移：`python -m alembic heads` → `0008_presentation_views (head)`（链 b9c6e3d6276a → 0008）；对临时 SQLite 实测 `upgrade head` / `downgrade -1` 均成功

语义断言覆盖：blocks 与所选小组一一对应（6 字段）；任一组无可用提交 → 409 NO_AVAILABLE_SUBMISSION + 原因且零视图落库；同参数同窗重复生成 → 同一 presentation_id、仅 1 条视图记录、命中不重读读模型；缺材料 → missing_marks 按冻结枚举序显式列出、project_result 为 None 不伪造；读模型后续变更后同窗再请求 → 快照内容不变（一次性快照）；新时间窗 → 新快照 + 旧快照 superseded + 幂等记录指向最新；应答顶层字段与 missing_marks 枚举和 contracts/ct-009.json 一致；AUTH_INVALID/FORBIDDEN/VALIDATION_FAILED 映射；静态 HTML 导出含小组/批注/缺失标记且无脚本。

## 契约影响

无。CT-009 路径/字段/错误码/幂等语义未变；未改 contracts/、shared/、其他模块、既有迁移。M05-IC-02 与 ACCESS-GATE 仅以注入端口消费（与 L15 同一冻结端口形状，集成时由 PROJECTOR/backfill 提供实现）。

## 风险/阻塞

- 幂等键时间窗粒度取 UTC 自然日（父 05 §4 列为 implementation_detail，可注入替换）；同窗内读模型滞后由再生成（新窗口/新部署窗口）吸收，符合 F4-1 语义。
- M05-IC-02 端口形状按 L1 冻结字段定义；若 L15 落地时端口签名有出入，需在集成对齐（不属本叶范围）。

## 范围自检

`git diff --name-only main...HEAD` 仅含：

```
server/course_app/teacher_web/presentation/__init__.py
server/course_app/teacher_web/presentation/assembler.py
server/course_app/teacher_web/presentation/coordinator.py
server/course_app/teacher_web/presentation/errors.py
server/course_app/teacher_web/presentation/missing_marks.py
server/course_app/teacher_web/presentation/models.py
server/course_app/teacher_web/presentation/output.py
server/course_app/teacher_web/presentation/ports.py
server/course_app/teacher_web/presentation/router.py
server/course_app/teacher_web/presentation/store.py
server/migrations/versions/0008_presentation_views.py
server/tests/test_l16_presentation.py
```

全部在 allowed-context.md 可写路径内；无 forbidden-changes 触碰。
