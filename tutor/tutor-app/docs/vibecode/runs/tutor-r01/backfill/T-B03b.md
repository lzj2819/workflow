# T-B03b — READMODEL-PROJECTOR：教师读模型投影（Phase 5 / B-03）

- worktree：`tutor-app/.worktrees/B03b-projector`（分支 tutor-r01/B03b-projector，需先由协调者创建）
- 允许路径（仅这些）：
  - `server/course_app/teacher_web/projector/**`
  - `server/migrations/versions/0013_read_model.py`（`down_revision="11a22f91f4b3"`）
  - `server/tests/test_b03b_*.py`

## 目标

实现教师端读模型（03-data-and-consistency：派生、秒级滞后、可重放重建）：消费 CT-005/CT-006/CT-014（+M05-IC-05 复核模块内事件 + CT-012 自消费清除），维护读模型表，实现 M05-IC-02 双侧面（L15 query() / L16 group_view()，兼容性已在 Wave 3 集成验证）。

## 交付物

1. 迁移 `0013_read_model.py`：`rm_courses`、`rm_groups`、`rm_students`、`rm_submissions`（含状态/缺失项/材料引用/原始等级/五维/建议/批注/最终等级/失败原因/重试记录快照）、`projection_checkpoints`（consumer、position，与投影同事务，ST-PROJECTION-CHECKPOINT）。
2. `ReadModelProjector`：handler 注册形状（供 RELAY consumer 调用）；幂等消费（submission_id/终态去重，重复事件不改投影）；CT-005 scored → 同时经 M05-IC-01（L14 create_review_record，注入）幂等建复核记录；scoring_failed → 投影失败原因+重试记录；CT-006 → 列表/状态投影；CT-014 → 清除投影（重放守卫：后续重放旧事件不重建已清除数据）；CT-012 自消费 → 清除读模型目标行。
3. `ProjectorReadModel`：实现 M05-IC-02 两侧面（query()、group_view()），输出形状与 L15/L16 端口 dataclass 完全一致（Wave 3 已验证兼容口径）。
4. 重放支持：从事件序列重建（projection replay 工具方法，位点重置）。
5. 测试：三事件投影、幂等重放、M05-IC-01 调用、失败投影、CT-014 清除+重放守卫、双侧面输出形状对照 L15/L16 端口、位点同事务。

## 禁止

- 改 L14/L15/L16/L17 代码；跨模块同步读；改其他目录/契约；引入新依赖。

## 验证

- `python -m unittest discover -s server/tests -p "test_b03b_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`、迁移可导入

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B03b-completion.md`。
