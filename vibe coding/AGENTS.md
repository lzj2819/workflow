# Agent Instructions

## Layered Vibe Coding

When the user asks to implement, continue, backfill, integrate, run vibe coding, work on a leaf, or proceed with layered development, use the `layered-vibecode` skill before editing code.

The source playbook is `layered-vibecoding-flow.md`. Root runs use run-scoped manifests/checkpoints under the selected output directory; the legacy post-Leaf-Gate compatibility workflow uses `vibecode/state.json`.

For an ongoing workflow-maintenance build, recover the objective from `task_plan.md`, `progress.md`, and `findings.md`. Resume only the phase marked `in_progress`; maintenance must not advance the sample runtime state unless that phase explicitly requires an isolated migration test.

Required workflow:

1. Read `vibecode/state.json`; if `vibecode/execution-log.jsonl` exists, run `python vibecode/scripts/vibecode.py audit-state`; then run `next-step` before workflow execution.
2. Only execute the current stage.
3. Do not skip human gates: matrix approval, contract changes, high-risk failures, and final release decision.
4. Leaf Owner work may only modify files allowed by `vibecode/leaves/<node-path>/allowed-context.md`.
5. Integration Owner work may only modify integration-layer files named by the current backfill plan.
6. Run `python vibecode/scripts/vibecode.py verify-stage` before advancing.
7. Advance only with `python vibecode/scripts/vibecode.py advance-state`.

For a new root-to-integration run, use `python vibecode/scripts/vibecode.py run-workflow --help`. Never use `advance-state` for that command. Resume only with the same `run_id`, input, config, model settings, seed, modes, and version hashes. Recursive backfill requires a real recorded Integration Owner approval; Fixture approvals are test-only.

Never let a leaf implementation modify parent wiring, sibling internals, root-level DTO/event schema, or shared contracts without a contract change request.
