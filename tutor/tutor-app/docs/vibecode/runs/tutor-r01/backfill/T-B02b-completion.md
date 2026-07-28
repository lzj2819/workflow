# T-B02b 完成记录 — RUBRIC-PROMPT-COMPOSER + SCORING-METRICS

- 日期：2026-07-21
- 分支：`tutor-r01/B02b-rubric-metrics`（worktree `tutor-app/.worktrees/B02b-rubric-metrics`，先 merge main：fast-forward 无冲突）
- 提交 SHA：`458121c1c8706b6d308b1f213a0049e69a7f58d6`

## 改动清单（均在允许路径内）

1. `server/migrations/versions/0011_rubric_policies.py`（`down_revision="11a22f91f4b3"`，并行多头）：
   - `rubric_policies` 表（ST-004：rubric_version、prompt_version、template_body、dimensions、grade_bands、status active/superseded、created_at；可移植类型 sa.JSON）；
   - 版本对唯一约束 `uq_rubric_policies_version` + 同库 active 唯一部分索引 `uq_rubric_policies_active`（sqlite_where/postgresql_where）；
   - 种子 v1（rubric-v1/prompt-v1，active）：五维与 contracts/ct-010.json 枚举一致（需求理解、Codex 迭代过程、代码质量、最终功能、文档/展示完整性），A–E 默认区间（FR-008），模板含缺失材料影响提示与输出格式要求。
2. `worker/assessment_worker/rubric/`：
   - `models.py`：RubricBase + RubricPolicy ORM（SQLite 可测，与迁移列一致）；
   - `composer.py`：`RubricPromptComposer` 实现 ICT-002 端口形状（compose → evaluation_prompt/prompt_version/rubric_version）；只读 active 策略，占位符按固定顺序纯替换，同版本同输入同输出；缺失声明口径对齐 L12 `build_missing_materials_impact`；失败抛 L12 `PromptAssemblyFailedError`（无 active/多 active/模板缺占位符/空 assignment/坏 material_ref）；材料清单仅类别标注（KD-001，不带 filename/ref）；
   - `budgets.py`：CT-010 三桶预算编排——类别→桶映射与 L12 `_minimize_materials` 完全一致（未识别类别折叠进 result_description 带 [类别] 标签），每桶确定性截断预算（dialogue_summary 4000 / code 8000 / result_description 2000 字符，超预算追加固定截断标记），missing_items 缺失类别标签化（截断后追加，不被预算吞掉）。
3. `worker/assessment_worker/scoring_metrics/`：
   - `metrics.py`：`ScoringMetrics`（record_task_created / record_terminal(submission_id, outcome, at)，均幂等）；SM-002（创建→scored ≤10min 达标率，分母为创建时间已知的 scored 任务）、SM-003（(scored+scoring_failed)/已创建覆盖率）、积压表盘（创建−终态）；计数/表盘落 `tutor_shared.metrics.registry`（可注入独立 registry）；`snapshot()` 为 ICT-008 只读查询端口；分母为零时比率为 None（不伪造 0/0）；aware 时间戳归一化 naive UTC。
4. 测试：`worker/tests/test_b02b_rubric_composer.py`（19 项）、`worker/tests/test_b02b_scoring_metrics.py`（12 项）。

## 验证（worktree 根，全绿）

- `python -m unittest discover -s worker/tests -p "test_b02b_*.py" -v`：31 项 OK。
- `python -m unittest discover -s worker/tests`：104 项 OK（无回归）。
- `ruff check`（全部改动路径）：All checks passed。
- `py_compile` 全部新文件 OK；迁移可导入（revision/down_revision 断言）。
- `python -m alembic heads`（server/）：`0011_rubric_policies` 作为并行 head 正确登记。

## 契约影响

- 无契约语义变更。ICT-002 按 L12 端口形状实现；ICT-008 提供只读快照端口；CT-010 五维枚举原样引用，未新增/未改名/未弱化任何字段；prompt_version/rubric_version 仅内部存证（LCD-003），不经 CT-005 外发。

## 风险 / 边界

- ScoringMetrics 为进程内统计（重启由事件流重建），与 KD-003 基础监控口径一致；未接线到 L03 编排器（组合根归后续任务）。
- 三桶预算数值（4000/8000/2000 字符）为 LCD-005 委托到本层的实现细节，上线前需样例回归确认体量。
- 迁移为并行多头之一，集成时需 `alembic merge heads`。
- 未接真实供应商、未改 L03/L12 既有代码、未改任何其他目录/契约。
