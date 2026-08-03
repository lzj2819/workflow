# T-B03b 完成记录 — READMODEL-PROJECTOR（教师读模型投影）

- 分支：`tutor-r01/B03b-projector`（worktree `tutor-app/.worktrees/B03b-projector`）
- 提交 SHA：`d3929561dd49d1948361cca78b8d504bf55e45d6`
- 前置：`git merge main --no-edit` 无冲突。

## 改动

- `server/course_app/teacher_web/projector/`（新增包）
  - `models.py`：`rm_courses` / `rm_groups` / `rm_students` / `rm_submissions`
    （状态/缺失项/材料引用/原始等级/五维依据/教师建议/批注/最终等级/失败原因/
    重试记录 + `applied_adjustment_ids` 幂等键）、`rm_purge_tombstones`
    （重放守卫墓碑）、`projection_checkpoints`（consumer、position）。
  - `projector.py`：`ReadModelProjector`。`handlers()` 返回
    `{CT-005/CT-006/CT-012/CT-014: handler}`（RELAY `Callable[[OutboxRecord], None]`
    形状，record_id 即位点）；投影与位点推进同一本地事务（失败整体回滚）。
    - CT-006：submission_id upsert + 目录派生；状态单调秩前进，旧状态重放不
      回退终态；逐字段比对，重复事件不改投影。
    - CT-005 scored：投影五维/建议/等级，并经注入的 M05-IC-01（L14
      `create_review_record`，组合根绑定）幂等建复核记录；scoring_failed：
      投影 failure_reason + retry_record，不写等级（INV-1）；终态去重
      （冻结契约：重复事件不改变终态）。
    - M05-IC-05（`publish(events)`，ReviewEventPublisher 形状）：按
      adjustment_id 去重；AnnotationSaved 追加批注、GradeAdjusted 写最终等级。
    - CT-012 自消费 / CT-014：删除读模型目标行并登记墓碑；重放守卫——命中
      墓碑的旧事件跳过，不重建已清除数据。
    - `replay(records, reset=True)`：从事件序列重建读模型并重置位点。
  - `read_model.py`：`ProjectorReadModel` 实现 M05-IC-02 双侧面——L15
    `query()` 返回 `review_query.ports.ReadModelView`、L16 `group_view()` 返回
    `presentation.ports.GroupReadView`（SubmissionView/MaterialRef/
    AnnotationView 均直接复用两侧冻结 dataclass）；小组无记录返回 None；
    已清除提交不出现；读取失败抛对应侧面的 ReadModelUnavailableError。
- `server/migrations/versions/0013_read_model.py`：`down_revision="11a22f91f4b3"`
  （并行多头，`python -m alembic heads` 已见 `0013_read_model (head)`）。
- `server/tests/test_b03b_readmodel_projector.py`：25 个测试。

## 验证（worktree 根，全绿）

- `python -m unittest discover -s server/tests -p "test_b03b_*.py" -v`：25 通过。
- `python -m unittest discover -s server/tests`：294 通过（无回归）。
- `python -m unittest discover -s worker/tests`：104 通过。
- `python scripts/smoke_wave3.py`：SMOKE_OK（M05-IC-02 兼容口径未受影响）。
- `ruff check <改动路径>`：All checks passed；`py_compile` 全部通过；
  迁移经 importlib 加载 + SQLite upgrade/downgrade 执行（测试内含）。

## 契约影响

- 无契约变更。消费 CT-005/CT-006/CT-012/CT-014 与 M05-IC-01/M05-IC-02/
  M05-IC-05 均按冻结形状；不改 L14/L15/L16/L17 代码、不做跨模块同步读、
  不引入新依赖。SCENARIO-016 / AssessmentResult 删除链路未触碰（CCR-001 不动）。

## 风险 / 说明

- 新增 `rm_purge_tombstones` 表（任务书交付物枚举的 5 表之外）：重放守卫必须
  在删除投影行后仍持久化"已清除"事实，墓碑是唯一不污染读模型表设计的载体。
- material_refs 列保留但按空投影：消费契约集内无材料引用明细来源（CT-006 仅
  携带 missing_items；CT-004 归 MOD-03 不在本任务消费集合），missing_marks 由
  CT-006 missing_items 如实供给；若后续要求材料引用展示需契约/范围变更（CCR）。
- M05-IC-01 与投影分属两个本地事务（L14 自有 session）：L14 先提交、投影
  回滚的极端序列为安全方向（重试后 M05-IC-01 幂等命中，不会双建）。
- read_model_version 以最大位点 `pos:<n>` 表示，仅供 L16 观测，无契约语义。
