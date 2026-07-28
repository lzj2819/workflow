# Multi-Session True Subagent Orchestrator

You are the **orchestrator** for a multi-session `validate-arch` run. Your job is to split a large `.feature` file into batches, dispatch one **batch subagent** per batch, wait for all of them, aggregate their outputs into a single final report, and return only a concise summary to the parent session.

Work from the repository root that contains `.agents/skills/validate-arch` and `src/mock_framework`.

## Inputs you receive

You will be given by the parent session:
- `--feature`: path to the `.feature` file.
- `--arch`: path to the architecture doc or directory.
- `--report-dir`: delivery directory for the final report.
- `--run-dir` (optional): managed work root. Default to
  `.work/validate-arch/runs/<feature-stem>-strict-<timestamp>`.
- `--batch-size` (optional): number of scenarios per batch. If omitted, partition by `@REQ-XXX` tag.

## Outputs you must produce

1. One subdirectory per batch under `--run-dir`, e.g. `--run-dir\batch-001\`.
2. Each batch subdirectory must contain:
   - `plan.json`
   - `hops.json`
   - `compat.json`
   - `plan_with_val.json`
   - `val_results.json`
   - `subagent_calls.jsonl`
   - `strict_audit.json`
3. One auto-named final aggregated report under `--report-dir`.
4. A concise return summary to the parent session:
   - total scenarios
   - number of batches
   - PASS / FAIL / WARNING counts
   - final report path

## Step-by-step algorithm

### 1. Prepare full plan

Run:

```bash
python .agents/skills/validate-arch/run_subagent_skill.py prepare \
  --feature <FEATURE> \
  --arch <ARCH> \
  --slim-prompts \
  --output <RUN_DIR>\plan.json
```

Use `--slim-prompts` for the full plan so `batches.json` and parent-session
context do not carry all static component prompt templates.

### 2. Partition into batches

Run:

```bash
python .agents/skills/validate-arch/prepare_batches.py \
  --plan <RUN_DIR>\plan.json \
  --output <RUN_DIR>\batches.json \
  --write-plans-to <RUN_DIR> \
  [--batch-size N | --by-tag]
```

Read `batches.json`. It has:

```json
{
  "feature_path": "...",
  "arch_path": "...",
  "batches": [
    {
      "name": "batch-001",
      "scenario_ids": ["SCENARIO-001", "SCENARIO-002"],
      "plan_path": "<RUN_DIR>\\batch-001\\plan.json"
    },
    ...
  ]
}
```

`prepare_batches.py --write-plans-to` writes each batch's sliced `plan.json`
up front. Batch subagents must use that file when present and only run
`prepare --scenario-ids` as a fallback.

### 3. Dispatch batch subagents

For each batch in `batches.json`:

1. Create the batch output directory, e.g. `<RUN_DIR>\batch-001\`.
2. Confirm the pre-sliced `<RUN_DIR>\batch-001\plan.json` exists when
   `plan_path` is present in `batches.json`.
3. Read `.agents/skills/validate-arch/batch-subagent-instructions.md`.
4. Spawn a Codex subagent with `spawn_agent`. Give it:
   - The full content of `batch-subagent-instructions.md` as system instructions.
   - The concrete parameters for this batch:
     - `--feature`: from `batches.json["feature_path"]`
     - `--arch`: from `batches.json["arch_path"]`
     - `--scenario-ids`: comma-separated list from the batch
     - `--output-dir`: `<RUN_DIR>\batch-XXX\`
5. Tell the batch subagent to return only a short summary when done.

You may dispatch multiple batch subagents **in parallel** up to the available collaboration concurrency limit. Use `wait_agent` until all have returned.

If a batch subagent fails, retry once. If it still fails, record the batch as failed and continue.

### 4. Aggregate results

After all batch subagents complete, run:

```bash
python .agents/skills/validate-arch/aggregate_batch_results.py \
  <RUN_DIR>\batch-001 \
  <RUN_DIR>\batch-002 \
  ... \
  --output <REPORT_DIR>\<RUN_NAME>-validation-report.md \
  --run-dir <RUN_DIR> \
  --artifact-retention report
```

Pass every batch directory as a positional argument.

### 5. Return summary to parent

Return ONLY:

```markdown
多会话 true subagent 验证完成
- 总场景数: X
- 批次数: Y
- 通过: A
- 失败: B
- 警告: C
- 缺失: D
- 最终报告: <REPORT_DIR>\<RUN_NAME>-validation-report.md
```

Do not paste the full report or detailed traces into your final response.

## Important rules

- **Do not run the simulation yourself.** Each batch must be handled by an independent batch subagent.
- **Do not keep detailed traces in your context.** Only keep batch summaries and the final aggregated summary.
- **All intermediate file I/O goes under `--run-dir`.** Only the final report goes to `--report-dir`.
- **Cleanup only after merged strict audit PASS.** A failed batch/audit keeps the complete run directory.
- **If a batch fails twice**, continue without it and note it in the summary.
