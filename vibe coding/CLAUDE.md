# Claude Project Instructions

## Layered Vibe Coding

For implementation, continuation, backfill, integration, leaf work, or vibe coding requests, use `/layered-vibecode` before editing files.

Follow `layered-vibecoding-flow.md`. New root runs use `run-workflow` and run-scoped manifests/checkpoints; legacy post-Leaf-Gate compatibility commands use `vibecode/state.json`.

For workflow-maintenance work, first restore the active objective from `task_plan.md`, `progress.md`, and `findings.md`, and resume only the phase marked `in_progress` without advancing the sample runtime state.

Rules:

- Read `vibecode/state.json`; if `vibecode/execution-log.jsonl` exists, run `audit-state`; then run `next-step` before workflow execution.
- Work only on the active stage.
- Do not bypass human gates: matrix approval, contract changes, high-risk failures, and final release decision.
- Leaf Owner edits must stay inside the active leaf `allowed-context.md`.
- Integration Owner edits must stay inside the current backfill plan.
- Run `python vibecode/scripts/vibecode.py verify-stage` before advancing.
- Advance only with `python vibecode/scripts/vibecode.py advance-state`.
- Do not call `advance-state` for `run-workflow`. Resume a root run only when its identity and checkpoint hashes validate, and never reuse Fixture approvals in production.

Stop and produce `contract-change-request.md` if a shared contract must change.
