# T-B02b — RUBRIC-PROMPT-COMPOSER + SCORING-METRICS（Phase 5 / B-02）

- worktree：`tutor-app/.worktrees/B02b-rubric-metrics`（分支 tutor-r01/B02b-rubric-metrics，需先由协调者创建）
- 允许路径（仅这些）：
  - `worker/assessment_worker/rubric/**`
  `worker/assessment_worker/scoring_metrics/**`
  - `server/migrations/versions/0011_rubric_policies.py`（`down_revision="11a22f91f4b3"`）
  - `worker/tests/test_b02b_*.py`

## 目标

1. RUBRIC-PROMPT-COMPOSER（ICT-002）：RubricPolicy 版本化存证（ST-004：rubric_version、prompt_version、模板正文、状态 active/superseded）；compose() 实现 L12 端口形状（evaluation_prompt/prompt_version/rubric_version），同版本同输入同输出（纯组装）；CT-010 三桶预算编排（dialogue_summary/code/result_description 各自的确定性截断预算与缺失类别标签化处理，对齐 L12 既有折叠口径）。
2. SCORING-METRICS（ICT-008）：SM-002（评分任务创建→scored 时长，10 分钟目标达成率）与 SM-003（终态覆盖率 scored+scoring_failed/总任务）度量；计数/表盘接入 tutor_shared.metrics；查询端口返回当前指标快照。

## 交付物

1. 迁移 `0011_rubric_policies.py`（rubric_policies 表）+ 种子 v1 五维模板（与 contracts/ct-010.json 五维枚举一致）。
2. `RubricPromptComposer`：从 PG 读 active policy → compose()；缺失材料影响提示注入（missing_items 标签）；确定性（同输入同输出）。
3. `ScoringMetrics`：record_task_created / record_terminal(submission_id, outcome, at) 接口 + snapshot()（SM-002 达标率、SM-003 覆盖率、当前积压）；落 tutor_shared.metrics.registry 供 /metrics 暴露。
4. 测试：composer 确定性与版本读取、三桶预算截断、缺失标签化；metrics 计数/比率/积压计算；迁移可导入。

## 禁止

- 改 L03/L12 既有代码；引入新依赖；改其他目录/契约。

## 验证

- `python -m unittest discover -s worker/tests -p "test_b02b_*.py" -v` 全绿
- `python -m unittest discover -s worker/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`、迁移可导入

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B02b-completion.md`。
