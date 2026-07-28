# VeriLayer File Ownership — Day 1

| Area | Owner | Change rule |
|---|---|---|
| Canonical Artifact Contract, contract log, root migration/current-state/path policy | A | A merges versioned contract changes after review |
| `vibe coding/vibecode/schemas/verilayer-artifact.schema.json` | A | B/C/D submit proposals; do not edit directly |
| PRD/root wiring, common adapters, integration/backfill wiring | A | Day 2+ only after the Day 1 Gate |
| Architecture/Gherkin payloads and validators | B | must conform at Adapter boundary; no shared-schema edits |
| Mocktest/Leaf payloads, strict evidence, defect taxonomy | C | must conform at Adapter boundary; no shared-schema edits |
| Code/TestResult/Evidence payloads and future executor | D | must conform at Adapter boundary; no shared-schema edits |
| Tutor archive | no implementation owner | read-only; never modify, repackage, or use as formal experiment output |

## Day 1 boundary

This ownership table authorizes only contract documents and the canonical JSON Schema. It does not authorize changes to B/C/D module implementations, a Coding Executor, production Adapter commands, `root_workflow.py`, `module_runner.py`, `contracts.py`, legacy `state.json`, or `advance-state`.
