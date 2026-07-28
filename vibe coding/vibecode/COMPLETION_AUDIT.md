# 完整代码开发工作流完成审计

审计日期：2026-07-17  
审计依据：`01-所有流程公共修改提示词.md`、`07-完整代码开发工作流修改提示词.md`  
审计结论：模块内 P0/P1 和禁止项均有实现及当前验证证据；生产实验仍须在项目配置中接入真实上游模块命令、真实模型凭证环境和真实 Integration Owner 审批，这些是运行输入，不是本仓库可伪造的默认值。

## 实际入口、输入和输出

- 根级入口：`python vibecode/scripts/vibecode.py run-workflow --help`。
- 兼容入口：原有 `init`、`next-step`、`verify-stage`、`advance-state`、`contract-diff` 等命令保留。
- 根级输入：原始需求或根 PRD、项目 JSON 配置、输出目录、运行/项目/根节点 ID、模型参数、种子、最大深度、重试限制、实验和分支模式、`resume`、`dry-run`。
- 模块适配器：PRD、Architecture、Gherkin、Mocktest、Leaf Gate、coding、backfill、integration 均以结构化 `module-result.json` 连接。
- 正式输出：`run_manifest.json`、`run_report.json`、`run_report.md`、`node_tree.json`、`contract_diff_report.json`、`experiment_metrics.json`、`execution_log.json`，以及节点/阶段/尝试目录。

## P0 完成对照

| P0 | 结论 | 实现证据 | 验证证据 |
| --- | --- | --- | --- |
| 统一 Leaf Gate 状态 | 完成 | 公共状态与旧别名归一化；新产物只写公共状态 | `test_public_and_legacy_decisions_normalize`、`test_scanner_admits_only_stop_layering` |
| 顶层编排入口 | 完成 | `run-workflow` 支持全部要求参数和配置化命令适配器 | `test_public_cli_runs_external_process_fixture`、CLI `--help` |
| 真实并行分支 | 完成 | 两工作线程读取同一 PRD；当前尝试隔离；双 PASS 后才进入 Mocktest | `test_parallel_join_is_concurrent_and_sequential_is_labelled` 峰值并发为 2；Phase D barrier 测试 |
| 递归节点调度 | 完成 | 显式 DAG、父子/深度/循环/重复校验、`proposed_children` 递归 | `test_two_layer_recursive_backfill_reaches_root`、RunGraph 全组测试 |
| STOP 后代码开发 | 完成 | 根流程直接调用 `admit_coding`，校验 PRD/架构/测试/Mock/Leaf/契约 ID 和 Hash | CodingAdmission 全组测试、单层/双层 E2E |
| 可靠状态机 | 完成 | 公共 `status` 加显式 `lifecycle_stage`，覆盖 INIT 到 FAILED 的要求阶段 | `run-report.schema.json` 枚举、干净 CLI 报告 `COMPLETED/COMPLETED` |
| 状态/历史一致 | 完成 | 原子 JSON、append-only 旧账本；根 checkpoint 包含 state、日志和成功结果/实际输出 Hash | ledger 测试、`test_resume_rejects_tampered_log_or_declared_output` |
| 失败关闭/恢复 | 完成 | FAIL/ERROR/契约/运行错误分别退出 2/3/5/4；新 attempt；身份和 Hash 恢复 | branch、Mock FAIL/ERROR、interrupt/resume、identity/tamper 测试 |
| 逐层回填 | 完成 | 叶交付、冻结批次、六项检查、语义 diff、人工审批、apply、父交付逐层提升 | Backfill 全组测试、双层 E2E、契约冲突 E2E |

## P1 完成对照

| P1 | 结论 | 实现/证据 |
| --- | --- | --- |
| 结构化语义契约 | 完成 | `contracts.py` 按稳定接口/字段比较；根回填只接受完整 semantic diff |
| 十类差异 | 完成 | `test_all_required_breaking_difference_classes` 覆盖全部指定类型 |
| 实验遥测 | 完成 | 总/模块/并行/顺序时间、Token、成本、调用/重试/人工、节点/深度/决策、Mock、编码、契约、失败阶段和终态均进入报告 |
| 实验模式 | 完成 | `full_recursive`、三种消融及 sequential/parallel；消融强制 `is_ablation=true/full_run=false` |
| 可复现性 | 完成 | manifest 固定输入/配置/模型/种子/模块版本/code/git 字段和身份 Hash；checkpoint 审计；敏感模型参数脱敏 |
| 六个 E2E Fixture | 完成 | `tests/fixtures/root_workflow/scenarios.json` 为目录；`tests/test_root_workflow.py` 执行单层、双层、Mock 缺陷、中断恢复、分支失败和契约冲突 |
| 七个正式产物 | 完成 | 干净 CLI 检查七项全部存在且解析内容；对应 Schema 共 18 个可解析 |

## 禁止行为审计

- 并行任一分支 ERROR 时，Mocktest 未被调用；根报告不是 COMPLETED。
- 每次运行/节点/阶段使用新 `attempt-N`；恢复检查当前 manifest、checkpoint、日志及实际输出 Hash，不读旧结果补缺。
- 根流程真相由 manifest、checkpoint、执行日志和内容寻址产物共同构成；旧 `state.json` 不是根流程真相源。
- 默认 `contract-diff` 为结构化语义比较；旧文本行模式只能显式 `--legacy-text` 使用并标注非权威。
- 父节点必须经过冻结 batch、完整检查集和人工审批，叶完成不能跳过回填。
- 消融永不标记为 full run。
- 模块 ERROR、未处理异常或契约冲突均不能生成 COMPLETED 根报告。

## 必须测试的 18 项

1. 单层完整运行：`test_single_layer_emits_authoritative_reports`。
2. 两层递归：`test_two_layer_recursive_backfill_reaches_root`。
3. Architecture/Gherkin 并行同步：root 并发峰值测试及 Phase D barrier 测试。
4. 一侧分支失败：`test_branch_error_and_mock_fail_close_downstream`。
5. Mocktest FAIL：同上。
6. Mocktest ERROR：同上，退出 3。
7. CONTINUE_LAYERING：双层 E2E 和 DAG 测试。
8. STOP_LAYERING：单层 E2E 和兼容扫描测试。
9. 旧状态兼容：LeafDecision 测试。
10. 最大递归深度：`test_maximum_depth_and_error_failure_closure`。
11. 中断恢复：`test_interrupted_run_resumes_without_rerunning_successes`。
12. 状态/事件一致：StateLedger 测试和根日志/输出篡改恢复拒绝测试。
13. 结构化契约差异：SemanticContractTests 全组。
14. 子节点回填：双层 root E2E。
15. 父节点集成测试：Phase F `parent_integration` 必填检查及最终 integration 阶段。
16. 实验指标：单层报告字段与 execution-log Schema 字段测试。
17. sequential/parallel：root 分支模式测试及 Phase D 顺序测试。
18. 消融标识：`test_ablation_label_and_dry_run_do_not_invoke_modules`。

## 当前最终验证

```powershell
python -m unittest discover -s tests -p "test_*.py" -q
python -m compileall -q vibecode tests
python vibecode/scripts/vibecode.py self-test
python vibecode/scripts/vibecode.py verify-stage
```

- 55 tests passed。
- 18 个 JSON Schema 全部可解析。
- 干净 `dry-run`：退出 0，只生成 `dry_run_plan.json`。
- 干净 full CLI：退出 0，七个正式产物齐全；`status=COMPLETED`、`lifecycle_stage=COMPLETED`、`full_run=true`、`is_ablation=false`。
- 退出规则测试：0 成功、2 业务 FAIL、3 模块/配置 ERROR、4 未处理运行异常、5 Schema/契约不兼容。
- 旧兼容状态仍为 `INIT`；SHA-256 为 `B2F47F817BE08085EF09351D6DB9D52866D551371D7913E03E5A419CBD8553A5`；未创建 live `vibecode/execution-log.jsonl`。

## 样例、接口和风险

- 正常样例：`tests/fixtures/root_workflow/requirement.json` + `project-config.single.json`，输出完整七报告。
- 异常样例：Fixture 目录中的 Mock 缺陷、分支 ERROR、契约冲突和中断恢复场景；分别验证退出 2/3/5/恢复。
- 上游要求：每个真实模块必须在给定 attempt 目录写结构化 `module-result.json`，声明本尝试内存在的输出，并使用公共状态/字段；Architecture 必须提供清晰接口，Leaf Gate 必须提供完整证据和 children/decision，backfill 必须提供完整六检查和 semantic diff。
- 下游保证：成功产物均带 run/project/node/provenance、输入输出 Hash；失败不进入下游；报告和节点树可由 Schema 约束消费。
- 跨模块接口请求：真实 PRD/Architecture/Gherkin/Mocktest/Leaf Gate/编码/集成模块应提供其生产命令和版本；凭证通过进程环境管理，不写项目配置或日志。
- 已知风险：外部模型即使固定种子也可能不保证确定性，manifest 已明确记录该条件；真实生产审批不能自动化或复用 Fixture 值；外部模块自身质量仍由各模块负责。
- 正式实验条件：本模块的编排、恢复、测量和审计条件已满足；开始真实实验前必须提供上述生产适配器、固定版本/模型和真实人工审批证据。
