---
name: validate-arch
description: Validate architecture documents or manifest packages against Gherkin `.feature` scenarios using strict component-by-component Codex simulation, contract checks, artifact audit, automatic minimal repair with reruns, caching, batch orchestration, and architecture change-card reports. Use when Codex is asked to run validate-arch, verify architecture against Gherkin scenarios, perform strict component-level simulation, auto-repair validation blockers, or report actionable architecture gaps.
---

# validate-arch

Validate architecture design documents against Gherkin scenarios using multi-agent simulation and validation.

## When to Use

- After completing an architecture design document (arch.md) at any layer
- After updating an architecture document and wanting to verify correctness
- Before proceeding to the next design layer (parent → children)
- When you need to verify cross-layer consistency

## When NOT to Use

- When no `.feature` file exists for the current layer
- When you just want to run unit tests on existing code

## Arguments

- `--feature`, `-f`: Path to the Gherkin .feature file (required)
- `--arch`, `-a`: Path to the architecture document or directory (required)
  - Single file: `arch/system.md`
  - Directory: `arch/system/` (aggregates the current-layer Markdown files into one validation input)
  - Manifest package: when `architecture-manifest.yaml` exists, its artifact inventory defines the current-layer inputs and is hash-recorded; handoff/README material is not treated as a simulated component definition
- `--mode`: `full` (simulate+validate+generate improvement suggestions) or `validate-only` (no suggestions)
- `--max-rounds`: Kept for backward compatibility, currently ignored
- `--show-reasoning`: Kept for backward compatibility, currently ignored

## Example Usage

```
$validate-arch --feature features/order.feature --arch arch/order-module.md
$validate-arch --feature features/system.feature --arch arch/system.md --mode validate-only
```

## Workflow

1. **Load**: Read arch.md and .feature file, parse Gherkin into `TestCase`s and architecture into `ArchDoc`
2. **Simulate**: Core `Simulator` builds an execution trace using the architecture's state model, latency model, and component mappings
3. **Validate**: Core `Validator` performs 5-dimension validation (structure, flow, state, contract, performance) on the **current layer only**
4. **Improve**: `ImprovementEngine` + `ArchDocModifier` generate structured suggestions for any FAIL/WARNING/MISSING result
5. **Report**: Generate structured validation report with per-test-case details and recommendations

> **Scope note**: `$validate-arch` validates only the architecture layer passed via `--arch`. It does not require child/next-layer documents (e.g., `modules/*.md`) to exist or be complete. Use the separate `layer-check` CLI when you explicitly want cross-layer consistency checking.

## Mandatory Auto-Repair Completion Rule

For every `validate-arch` run, treat any issue encountered during the requested validation scope as work to resolve, not as a stopping point. Continue until all selected scenarios have completed real component-by-component simulation and validator evaluation, the strict artifact audit has run, and the final architecture-design improvement report has been delivered.

1. Diagnose each failure from its preserved run evidence: entry/contract resolution, architecture content, parser or driver behavior, invalid subagent JSON, artifact hashes, report delivery, or other execution blockers.
2. Apply the smallest safe repair automatically, then continue from the exact failing scenario, component hop, validator, artifact, or report-delivery step. Preserve already successful evidence and do not re-run completed scenarios or hops unless the repair invalidates their input hash, contract dependency, or shared architecture evidence. Prefer correcting the passed architecture document when the evidence identifies an architecture gap; repair the project-local `validate-arch` workflow only when the root cause is in the workflow itself.
3. Never alter the supplied `.feature` scenarios to manufacture a pass, never fabricate component or validator responses, and never bypass the semantic gate, contract check, or strict audit.
4. Preserve the failed run evidence and resume the current run at the failure point whenever its retained artifacts remain valid. If a fresh workspace is required by changed inputs or artifact hashes, re-run only the affected scenario chain and its dependent validators; do not restart the full user-requested scope by default. Continue until every selected scenario has real component-hop evidence, one independent validator result, and a final strict audit.
5. Finish only after the selected scenarios reach their genuine final validation outcome and a final architecture-design improvement report is written to the requested report directory. If architecture findings remain after safe repairs, the report must state them as unresolved, actionable change cards; do not claim PASS.
6. Stop for user direction only when a safe repair requires a material product decision, authority outside the supplied workspace, or a change to the test scenario itself. State the exact blocker and preserve the latest evidence.

## Codex Execution

Resolve the project-local driver and a Python interpreter with PyYAML before running:

```powershell
$preflight = & python .agents\skills\validate-arch\scripts\preflight.py --root . | ConvertFrom-Json
if ($preflight.status -ne 'ok') { throw ($preflight.errors -join '; ') }
$py = $preflight.python
$driver = $preflight.driver
```

For normal strict Codex runs, prefer `main_session_strict_driver.py`. It writes prompt files and lets the current Codex session dispatch one independent subagent per component hop or validator. `run-strict` is the serial convenience path and invokes `codex exec` itself.

Initialize canonical runs with separate work and delivery paths:

```powershell
$run = ".work/validate-arch/runs/<feature-stem>-strict-<timestamp>"
python .agents/skills/validate-arch/main_session_strict_driver.py init `
  --feature <feature-path> --arch <arch-path> `
  --output-dir $run `
  --report-dir <requested-report-folder> `
  --artifact-retention report
```

Reuse the same `--output-dir` for every later driver command. `init` stores the report path
and retention policy in `driver_state.json`; `finalize` delivers the report, then performs
PASS-only cleanup. Never create the run directory inside the requested report folder.

### Subagent Mode Execution（组件级逐跳走链）

#### 递归架构包与子节点登记册

对于包含 `architecture-manifest.yaml` 和 `02-architecture-decomposition.md` 的 L1/L2 递归架构包：

- `子节点登记册（C1/C2）` 的 `child_id` 是可派发组件 subagent 的权威集合；Mermaid 中的外部调用方、外部 API 和协作者只作为边界证据，不会被创建为组件 subagent。
- 中文父契约、内部端口、状态/数据所有权、L1 NFR 分配、继承约束和简洁生命周期链会进入当前层 `ArchDoc` 与组件卡。
- Mermaid 简称会规范化到完整 `child_id`；场景标签、组件责任、Aggregate/Data Owner 语义和 provider-owned contract 共同决定入口。Scenario Outline 可使用精确 `@TC-*` 标签做受控组内共识；真正并列时仍保留 semantic gate，不按排序任选组件。
- 入口绑定区分两类证据：能唯一解析时使用真实 machine contract；组件已由高/中置信证据确定、但该模块内部行为没有唯一公开契约时，使用显式 `component_scope://<component>` 入口绑定。该绑定标记 `binding_kind=component_scope`、`architecture_declared=false`，只允许启动该组件，不会放宽后续跨组件 contract binding。
- `child-handoff.md` 是下一层交接材料，不进入当前层模拟上下文；manifest 自身作为独立 hash 输入写入 run manifest。
- `prepare` 会在 run-scoped `arch_current_layer.md` 中规范化等价的 L2 表头和组件短名（例如 `需求`、`内部契约 ID`、`输入窗口`），再交给通用解析器；源架构文档不会被修改。

这只扩展架构输入提取方式，不改变“一跳一个组件 subagent”、逐场景 validator、strict audit、报告聚合和缓存语义。

当 `$validate-arch` 在 subagent 模式运行时，当前 Codex 会话直接执行：

1. **准备**：
   ```bash
   python .agents/skills/validate-arch/run_subagent_skill.py prepare \
     --feature <feature_path> --arch <arch_path> \
     --slim-prompts \
     --output .work/validate-arch/manual/plan.json
   ```
   产出组件卡片、各场景的入口组件（`entry_component` / `entry_action` / `entry_confidence`）、入口绑定类型（`entry_binding_kind`）、触发消息、then 期望，并打印预估 subagent 次数。计划不再包含静态 hops。

   支持 `--output-dir`（默认写入 `<output-dir>/plan.json`）、`--start-scenario` / `--scenario-range`（按原始 scenario 顺序选择）、`--entry-overrides`（批量覆盖入口）和 `--scenario-ids`（显式 ID 过滤）。

   推荐使用 `--slim-prompts` 跑完整 `.feature`：`plan.json` 不嵌入所有组件 prompt 模板，`simulate-step-prompt` 会按当前 hop 的组件卡和架构数据流动态生成单组件 prompt。这样不改变逐 hop 真实 subagent 模拟，只减少重复静态文本。

2. **逐场景、逐跳组件 subagent 走链**（当前 Codex 会话执行，真正的 subagent 模式）：

   对 `plans` 里每个场景，当前 Codex 会话维护 `context={shared_state, last_output}`，并**严格串行**派发组件 subagent：
   - 构造首跳请求并调用 `simulate-step-prompt` 生成当前组件 prompt：
     ```bash
     python .agents/skills/validate-arch/run_subagent_skill.py simulate-step-prompt < hop_request.json
     ```
     `hop_request.json` 格式：
     ```json
     {
       "plan_path": ".work/validate-arch/manual/plan.json",
       "component": "Guidance Session",
       "action": "handle",
       "input_message": {"event": "call", "given": "...", "when": "..."},
       "shared_state": {},
       "phase": "when",
       "then_assertions": []   // 仅 then 阶段需要
     }
     ```
   - 将该命令输出的完整 prompt 派给**一个独立的 Codex subagent**。该 subagent 只扮演当前 `component`，必须返回符合 prompt schema 的 raw JSON HopResult。
   - 收回该跳的 HopResult；把 `output_message` 作为下一跳的 `input_message`；按 `state_change` 更新 `shared_state`。
   - 解析 `next_hop`：若非空且为合法组件，继续派下一跳 subagent；若为空或非法，则该场景模拟结束。
   - **约束**：每个组件 subagent 只扮演当前 `component`，不允许在一个 subagent 内模拟多个组件或整条链路。
   - 受 `--max-hops`（默认 20）约束，检测到 `(component, action)` 循环或越限时停止并记 WARNING。
   - 把全部场景的 hops 写成 `{test_case_id: [HopResult...]}` 到运行目录的 `hops.json`。不要把可变产物写入只读的 `.agents` skill 目录。

3. **确定性接口检查**：
   ```bash
   python .agents/skills/validate-arch/run_subagent_skill.py contract-check \
     --prompts .work/validate-arch/manual/plan.json --hops .work/validate-arch/manual/hops.json --output .work/validate-arch/manual/compat.json
   ```

4. **生成 validator prompts**：
   ```bash
   python .agents/skills/validate-arch/run_subagent_skill.py fill-validator-prompts \
     --prompts .work/validate-arch/manual/plan.json --hops .work/validate-arch/manual/hops.json \
     --compact-trace \
     --output .work/validate-arch/manual/plan_with_val.json
   ```
   对每个场景派一个 validator subagent，结果写到 `.work/validate-arch/manual/val_results.json`。

   推荐使用 `--compact-trace`：validator prompt 只携带五维判断所需的 compact trace、Gherkin 期望和触达组件摘要；完整 raw hops 仍保存在 `hops.json` 并由 strict audit/report 使用。

5. **生成报告**：
   ```bash
   python .agents/skills/validate-arch/run_subagent_skill.py report \
     --prompts .work/validate-arch/manual/plan_with_val.json --val-results .work/validate-arch/manual/val_results.json \
     --compat .work/validate-arch/manual/compat.json --hops .work/validate-arch/manual/hops.json \
     --output <feature-dir>/reports/<feature-stem>-validation-report.md
   ```

报告含 5+1 维（新增 interface_compat）、「数据流流转」段与「全局发现」段。

#### run-strict 一键命令

如果你希望把上述步骤（准备、逐跳组件 subagent、接口检查、validator subagent、strict audit、报告）交给脚本自动编排，可直接使用 `run-strict` 子命令。该命令在内部调用 `codex exec` 派发每个组件/validator subagent。运行证据默认进入 `.work/validate-arch/runs/<自动名称>`，最终报告单独交付到 `--report-dir`：

```bash
python .agents/skills/validate-arch/run_subagent_skill.py run-strict \
  --feature user/l1结果/L1-recommendation-orchestration/recommendation-orchestration.feature \
  --arch user/L1-recommendation-orchestration \
  --start-scenario 34 \
  --report-dir user/report/l1-report \
  --artifact-retention report \
  --slim-prompts \
  --compact-trace
```

常用选项：

- `--output-dir`：运行工作区；未指定时自动写入 `.work/validate-arch/runs/<feature-stem>-strict-<timestamp>`。不要把报告交付目录传给此参数。
- `--report-dir`：最终报告交付目录。报告自动命名为 `<run-name>-validation-report.md`。
- `--artifact-retention report|audit|full`：
  - `report`：strict audit PASS 后删除受管 `.work` 运行目录，只保留最终报告；使用 `--report-dir` 时为默认值。
  - `audit`：PASS 后保留核心审计 JSON、调用日志和输入哈希，删除逐调用 prompt/raw response。
  - `full`：保留全部运行产物；未使用 `--report-dir` 时为兼容默认值。
  - strict audit FAIL 时忽略清理请求并保留完整工作区，供诊断和复现。
- 新运行开始时会清理 `--report-dir` 下没有 `plan.json`/报告、且仅包含零字节启动日志的旧 `*-strict-*` 空壳目录；不会删除有效运行或无关用户目录。
- `--start-scenario N` / `--scenario-range M-N`：按原始 Gherkin scenario 顺序（1-based）选择场景，自动把 Scenario Outline 的所有展开行一起选中。
- `--scenario-ids`：显式指定 test_case_id（与范围参数可叠加过滤）。
- `--entry-overrides entry-map.json`：批量覆盖推断出的入口组件，避免手动修改 plan.json。
- `--slim-prompts`：推荐启用，按当前 hop 动态生成组件 prompt，减少 plan.json 体积。
- `--compact-trace`：推荐启用，生成更紧凑的 validator prompt。
- `--max-hops`：单场景最大组件跳数（默认 20）。
- `--subagent-timeout`：每个 subagent 超时秒数（默认 300）。
- `--diagnostics`：同时输出内部诊断报告。
- `--run-id` 与 `--project-id/--node-id/--parent-node-id/--branch-id`：可选的实验执行 ID 和分支身份。显式身份冲突必须产出 `ERROR`，不得继续给出架构 PASS。
- `--architecture-artifact-id/--testcase-artifact-id/--source-prd-id`：可选的上游制品追踪标识。
- `--random-seed/--simulator-model/--validator-model`：写入可复现实验日志，不改变严格模拟语义。

`prepare` 命令也支持 `--output-dir`、范围选择和 `--entry-overrides`，便于在手动编排与自动编排之间切换。

#### 多场景并行与复用选择

- 多场景 strict 运行优先使用 `main_session_strict_driver.py`：`next-components --limit N` 每次最多返回 N 个来自不同场景的待执行 hop；同一场景仍严格逐跳串行。`next-validators --limit N` 可并行派发独立 validator。
- `N` 取当前宿主可用 worker 数，不要超过客户端并发/速率限制。并行只减少 wall-clock 时间，不改变 prompt 内容或总 token。
- `multi-session-orchestrator-prompt.md` + `prepare_batches.py` 是更粗粒度的 Workflow 路径，适合大 Feature；batch 之间可并行，batch 内仍保持一跳一组件和一场景一 validator。
- Batch 运行只生成批次审计证据，不再生成每批 Markdown 报告；聚合阶段只交付一个自动命名的最终报告，并应用同一套 PASS-only retention。
- `run-strict` 是串行的一键便利路径，适合少量场景。它不应再额外维护一套线程池；大批量运行使用上面的 canonical driver/Workflow。
- `run-strict` 调用 Codex subagent 时通过 prompt 约束 raw JSON，并在本地做解析、结构校验和重试；不把当前工作流的宽松 schema 传给 `codex exec`，以兼容 Codex Responses API 对严格 JSON Schema 的要求。
- `--strict-equivalence` 保持 opt-in。只有 `plan.json.equivalence_summary.reusable_rows > 0` 才会减少调用；一键和 canonical driver 都只复制严格证明相同的代表行证据，并由 strict audit 重算 proof。
- 跨 run 缓存使用 canonical driver 的 `--reuse-from <strict-PASS-run>`。不要自动搜索或复用未显式指定的旧目录。
- 纯 NFR/P95/P99/可用性场景不得仅根据目标阈值生成 synthetic PASS。只有存在独立测量数据或明确可计算的逐边延迟/容量分配模型时，才可扩展确定性判定；聚合指标不能由单条 synthetic trace 证明。

### Current Strict Subagent Flow

For Codex skill execution, use this strict flow when the user asks for real per-component subagent validation:

1. Run `prepare`. Entry component inference is local-rule based by default; do not require or create an API-key LLM client.
   A resolved `component_scope` entry is valid only for a medium/high-confidence first component.
   It is not a substitute for an unresolved component and must never be propagated to a
   downstream inter-component hop.
2. For every scenario, call `simulate-step-prompt` for exactly one component hop, then spawn exactly one component subagent for that hop.
   Contract binding must match comma/Chinese-punctuation separated consumer lists by exact
   component token. A provider binding validates the contract request fields; a consumer
   binding records the response variants as `accepted_fields` and must not re-require the
   provider-only request fields. If binding is unresolved, keep the candidate interfaces in
   the prompt instead of erasing the evidence needed by the subagent.
   Internal component targets are listed in `legal_next_hop`; architecture edges to actors
   outside the current component registry are listed in `external_terminal_targets` and end
   with `next_hop=null`.
3. Append one component entry to `subagent_calls.jsonl` for every non-synthetic component subagent invocation.
4. Normalize each raw hop response with `normalize-hop-response`, or produce the same schema by hand if the tool is unavailable.
   Normalization recomputes `self_check.produced_fields` from the actual top-level
   `output_message` keys and fills a missing `next_hop.contract_id` only when the architecture
   determines exactly one contract for that internal edge.
   If the raw response cannot be parsed as JSON, treat it as an `invalid_json_response`
   artifact error and re-run/re-consume that component subagent before validation.
   Do not write invalid raw payloads into `hops.json` as normal business hops.
5. Write all scenario chains to `hops.json`, then run `contract-check`.
6. Run `fill-validator-prompts`.
   `--compact-trace` uses trace schema `validate-arch-trace-v2`: Gherkin
   Given/When/Then coverage is computed from source `.feature` steps, while
   component hops remain component execution evidence. Do not infer Gherkin
   phase coverage from the last component hop's `phase`.
7. Spawn exactly one validator subagent per scenario, append one validator entry to `subagent_calls.jsonl`, and write `val_results.json`.
8. Run `validate-run-artifacts --call-log <run-dir>/subagent_calls.jsonl --require-call-log`. The audit must pass before the final report can claim strict subagent execution.
   A failed audit is still a completed diagnostic outcome: preserve `strict_audit.json`,
   render a report with `--strict-audit` but without `--strict`, and return a non-zero status.
9. Generate the final report with:
   ```bash
   python .agents/skills/validate-arch/run_subagent_skill.py report \
     --prompts <run-dir>/plan_with_val.json \
     --val-results <run-dir>/val_results.json \
     --compat <run-dir>/compat.json \
     --hops <run-dir>/hops.json \
     --strict \
     --strict-audit <run-dir>/strict_audit.json \
     --audience architecture \
     --output <feature-dir>/reports/<feature-stem>-validation-report.md
   ```

`report --strict` must fail if `strict_audit.json` is missing or has `status != "PASS"`.
`report --strict-audit <failed-audit.json>` without `--strict` must render a diagnostic
report that clearly carries the failed audit status. `run-strict` follows this behavior
automatically, so a gate failure never suppresses the evidence report.
Strict audit also rejects stale validator prompts when the recorded artifact
hashes no longer match current `hops.json`, and rejects traces containing
`invalid_json_response` artifact errors.

`--audience architecture` is the default handoff format for architecture designers:
it hides raw component traces, full per-scenario validator details, strict-audit internals,
scenario fixture fixes, and validation-process defects from the final architecture report.
By default **only** the architecture delivery report is written. Pass `--diagnostics` to also
write those internal details next to the report as `*-diagnostics.md`.
Use `--audience full` only when debugging the validate-arch process itself.

Report-only delivery is self-contained and omits references to deleted sibling artifacts.
When audit/full retention is used, evidence references point to the preserved run workspace.

The architecture audience report must be directly actionable by architecture designers.
Each finding is rendered as an `Architecture Change Card` with:

- stable `ARCH-RISK-*` ID
- priority and confidence
- target files/sections
- current architecture gap
- required architecture change
- contract/state/event stub that can be copied into the architecture document
- affected scenarios
- acceptance criteria for re-running validate-arch
- evidence references to diagnostics and run artifacts

### Mode Selection

Use the canonical driver plus Codex subagents for large or parallel runs. Use `run-strict` for small serial runs. Do not use the Claude stdout-marker protocol from the source skill; Codex does not consume it.

### Formal experiment entry

Use `run-strict --input-manifest <mocktest-input/v1.json>` for formal experiments.
The architecture branch accepts a Markdown file/directory or `architecture/v1` JSON; the
testcase branch accepts one Gherkin file, a directory of `.feature` files, or `testcases/v1`
JSON. Normalized JSON must point back to its real Markdown/Gherkin source and never creates a
second simulation engine. Do not combine `--input-manifest` with `--feature` or `--arch`.

Formal mode rejects empty or conflicting `run_id`, `project_id`, `node_id`, `source_prd_id`,
artifact identity, or schema versions before simulation. `--ground-truth` is optional and is
used only for injection metrics. Unavailable token and cost values must remain JSON `null`.
Exit codes are `0=PASS`, `2=architecture FAIL`, `3=input/dependency/configuration ERROR`,
`4=execution/evidence ERROR`, and `5=schema/identity/downstream-contract ERROR`.

## Output

- Structured validation report with 5-dimension analysis
- Improvement recommendations mapped to failing dimensions
- Strict run evidence under `.work/validate-arch/runs/<auto-name>` unless an explicit work directory is required.
- **Final report** written to `--report-dir` with an automatic run-scoped name.
- On strict audit FAIL, the report is still delivered and the full work directory is preserved.
- Every finalized strict run also publishes a run-scoped formal delivery directory containing exactly:
  `mocktest_report.json`, `mocktest_report.md`, `leaf_gate_evidence.json`, and
  `execution_log.json`. Their versioned schemas are under `schemas/`.
- Formal status is `PASS` only when execution and every evaluated scenario pass; architecture
  defects are completed `FAIL` results; identity, input, model, tool, or evidence failures are
  `ERROR`. Leaf Gate consumes `leaf_gate_evidence.json`, not Markdown text.

> **Auto-repair note**: The mandatory auto-repair completion rule above supersedes the retired fixed-round `--mode=full` loop. Do not use a fixed retry count or stop after diagnosis: make the smallest safe repair, preserve the failed evidence, and resume at the exact failure point. Create a fresh workspace only when retained evidence is invalidated, and then re-run only the affected scenario chain and dependent checks until the requested scope reaches its genuine final outcome and the final report is delivered.

## Notes

- This skill requires the `mock_framework` package to be installed in the project
- The project-level skill is discovered from `.agents/skills/validate-arch` and executes its bundled local driver.
- The current strict subagent flow does not require an LLM API key; API-assisted entry inference is intentionally disabled by default.
- `run-strict` requires the local `codex` executable; canonical orchestration uses the current Codex session's subagent tools.
