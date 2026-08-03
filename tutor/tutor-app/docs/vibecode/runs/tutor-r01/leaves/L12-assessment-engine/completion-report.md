# Completion Report — L12 CMP-ASSESSMENT-ENGINE（tutor-r01, W2）

- leaf：L12；分支：`tutor-r01/L12-assessment-engine`；worktree：`tutor-app/.worktrees/L12-assessment-engine`
- 状态：done

## 提交

- SHA：`3e560c08baeafc64c736e4d2cb4645bfc20b1fdc`（基线 main `a4d373f`）

## 改动清单

- `worker/assessment_worker/assessment_engine/__init__.py` — 包导出
- `worker/assessment_worker/assessment_engine/engine.py` — AssessmentEngine/AssessmentOutcome：
  ICT-002 提示组装（端口注入）→ ICT-003 材料只读加载（端口注入）→ CT-010 请求组装
  （数据最小化 + `validate_request` 守卫）→ ModelProvider.evaluate（ICT-004，仅 FakeModelProvider）
  → 应答 schema 校验 → ICT-005 成功载荷装配（原始等级/五维依据/教师建议/scored_at/
  missing_materials_impact/prompt_version/rubric_version/model_meta）；
  失败分类装配 ICT-006 载荷（error_kind/attempt_no/at）
- `worker/assessment_worker/assessment_engine/ports.py` — PromptComposerPort（ICT-002）、
  MaterialReadPort（ICT-003）协议；实现归 backfill/MOD-02
- `worker/assessment_worker/assessment_engine/errors.py` — 失败分类常量（与 L03
  ERROR_TAXONOMY 一致）与端口/校验异常
- `worker/assessment_worker/assessment_engine/validator.py` — CT-010 response schema 与
  五维领域校验（等级 A–E、五维各一次、依据非空、建议非空、拒绝额外字段）
- `worker/assessment_worker/assessment_engine/impact.py` — missing_items →
  missing_materials_impact 说明（D-AC-REQ-008-01 boundaries）
- `worker/tests/test_l12_assessment_engine.py` — 13 项测试（fake provider + stub 端口 +
  L03 SQLite 内存库真实回调兼容）

## 验证命令与结果（worktree 根）

- `python -m unittest discover -s worker/tests -p "test_l12_*.py" -v` → `Ran 13 tests ... OK`
- `python -m unittest discover -s worker/tests` → `Ran 45 tests ... OK`（既有 32 项无回归，13 项新增）
- `ruff check worker/assessment_worker/assessment_engine worker/tests/test_l12_assessment_engine.py` → `All checks passed!`
- `python -m py_compile`（全部 7 个新增/改动 .py）→ 通过

## 语义断言覆盖

- 完整链路（组装→加载→fake evaluate→装配）：`test_full_pipeline_success`
- CT-010 请求数据最小化（不含 submission_id/student_name/group_name/course_id，
  request_id 为 uuid，不携带业务标识）：`test_ct010_request_data_minimization`
- 非法应答 → INVALID_RESPONSE_SCHEMA：`test_invalid_response_schema_classification`
- MODEL_TIMEOUT / MODEL_ERROR / PROMPT_ASSEMBLY_FAILED / MATERIAL_UNREADABLE 分类：各专项测试
- missing_items 非空 → 影响说明；空 → None：`test_missing_items_impact_present/empty`
- 成功/失败输出与 L03 complete_assessment / fail_assessment 真实调用兼容
  （SQLite 内存库， scored 终态 + RetryEntered 重试推进）：`L03CompatibilityTests`
- fake 可追溯：model_meta `provider/is_fake_provider/provider_trace` + 日志 `fake=True`，
  明确 "not a real assessment"：`test_fake_traceability_in_result_and_logs`

## 契约影响

无。未修改 contracts/、shared/、L03 编排器或其他叶子资产；ICT-002/003/004 以端口注入
消费，ICT-005/006 仅装配与 L03 签名兼容的载荷；CT-010 请求/应答形状按 contracts/ct-010.json 守卫。

## 风险 / 阻塞

- 无阻塞。
- 材料类别 → CT-010 三桶（dialogue_summary/code/result_description）的映射为本叶子
  临时实现（含未识别类别折叠进 result_description）；精确映射/截断策略属 LCD-005，
  归 CMP-RUBRIC-PROMPT-COMPOSER / CMP-MODEL-SERVICE-ACL backfill 细化。
- 真实供应商适配、rubric composer、材料端口实现均不在本叶子范围（backfill）。

## 范围自检

`git -C <worktree> diff --name-only main...HEAD`：

```
worker/assessment_worker/assessment_engine/__init__.py
worker/assessment_worker/assessment_engine/engine.py
worker/assessment_worker/assessment_engine/errors.py
worker/assessment_worker/assessment_engine/impact.py
worker/assessment_worker/assessment_engine/ports.py
worker/assessment_worker/assessment_engine/validator.py
worker/tests/test_l12_assessment_engine.py
```

全部位于 allowed-context.md 允许路径内；无 forbidden-changes 触碰；无网络调用、
无真实供应商、无外发材料或业务标识。
