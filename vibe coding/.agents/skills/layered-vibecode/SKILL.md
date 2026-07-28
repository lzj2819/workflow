---
name: layered-vibecode
description: Use for running or maintaining root-to-integration layered vibe coding or its legacy post-Leaf-Gate workflow, including recursive nodes, recovery, leaf coding, contract/backfill gates, reports, and persistent planning files.
---

# Layered Vibe Coding

Use this skill for the root-to-integration workflow and its preserved post-Leaf-Gate compatibility commands from `layered-vibecoding-flow.md`.

## Start

1. For maintenance, read `task_plan.md`, `progress.md`, and `findings.md`; resume only the phase marked `in_progress`.
2. Read `vibecode/state.json` if it exists. If `vibecode/execution-log.jsonl` exists, run `python vibecode/scripts/vibecode.py audit-state`.
3. If state does not exist, run:

```bash
python vibecode/scripts/vibecode.py init --leaf-root workspace/nodes --target-repo .
```

4. Run:

```bash
python vibecode/scripts/vibecode.py next-step
```

5. Execute only the step returned by the script. Workflow maintenance follows the active plan phase and must not advance sample runtime state unless that phase explicitly requires an isolated migration test.

For a new root run, do not initialize or advance the legacy state. Inspect `run-workflow --help`, prepare a structured project config, and choose a unique output root/run ID. Resume only with `--resume` and an identity-matching manifest/checkpoint.

## Stage Commands

| Need | Command |
| --- | --- |
| Check inputs | `python vibecode/scripts/vibecode.py doctor` |
| Generate matrix | `python vibecode/scripts/vibecode.py generate-matrix` |
| Approve a gate | `python vibecode/scripts/vibecode.py approve --gate matrix --note "approved by user"` |
| Generate leaf task packs | `python vibecode/scripts/vibecode.py generate-leaf-tasks` |
| Check active stage | `python vibecode/scripts/vibecode.py verify-stage` |
| Audit state/event consistency | `python vibecode/scripts/vibecode.py audit-state` |
| Explicitly repair from the last valid checkpoint | `python vibecode/scripts/vibecode.py audit-state --repair` |
| Advance after verification | `python vibecode/scripts/vibecode.py advance-state` |
| Check changed file paths | `python vibecode/scripts/vibecode.py guard-paths <changed-file> ...` |
| Compare contracts | `python vibecode/scripts/vibecode.py contract-diff --parent <file> --child <file> --output <file>` |
| Build final summary | `python vibecode/scripts/vibecode.py collect-reports` |
| Validate/start root workflow | `python vibecode/scripts/vibecode.py run-workflow --help` |

## Hard Rules

- Treat the append-only event log plus hashed artifacts as evidence; `state.json` is an atomic projection. Never repair it silently.
- Do not work ahead of the active stage.
- Do not auto-approve human gates.
- Leaf Owner: read only the active leaf task pack and allowed parent contract context.
- Leaf Owner: do not edit parent wiring, sibling internals, shared contracts, or root-level DTO/event schema.
- Integration Owner: only backfill through parent integration-layer files.
- Always run `verify-stage` before `advance-state`.
- If `contract-diff` returns `CONTRACT_CHANGE_REQUIRED`, stop and produce a contract change request for the user.
- Root workflow truth is its manifest, hashed checkpoint, execution log, and run-scoped artifacts together.
- `dry-run` invokes no module and is never completion evidence.
- Ablations remain labelled `is_ablation=true` and `full_run=false`.
- Recursive backfill requires real recorded Integration Owner approval; never reuse a Fixture approval.

## Expected Artifacts

- `vibecode/execution-matrix.md`
- `vibecode/integration-map.md`
- `vibecode/global-contract-index.md`
- `vibecode/leaves/<node-path>/vibecode-task.md`
- `vibecode/leaves/<node-path>/allowed-context.md`
- `vibecode/leaves/<node-path>/forbidden-changes.md`
- `vibecode/leaves/<node-path>/verification-checklist.md`
- `vibecode/backfill/<parent-node-path>/backfill-report.md`
- `vibecode/final-report.md`
- `<output>/<run_id>/run_manifest.json`
- `<output>/<run_id>/run_report.json` and `run_report.md`
- `<output>/<run_id>/node_tree.json`
- `<output>/<run_id>/contract_diff_report.json`
- `<output>/<run_id>/experiment_metrics.json`
- `<output>/<run_id>/execution_log.json`
