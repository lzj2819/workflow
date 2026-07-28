# Tutor Migration Manifest

Status: Day 1 inventory baseline. `tutor/` is read-only source material; this manifest does not copy, repack, execute, or modify it.

## Asset accounting

| Asset class | Count | Source location | Allowed Day 1 use |
|---|---:|---|---|
| Layered design node packages | 22 | `tutor/tutor/` | field mapping and migration fixture provenance |
| L2 prepared structured five-packs | 16 | `tutor/tutor/**/` | PRD/Architecture/Testcases/Mocktest/Leaf mapping only |
| Implemented leaves | 17 | `tutor/tutor-app/docs/vibecode/runs/tutor-r01/` | read-only code/test/integration oracle |
| Backfill task/completion packages | 12 | `tutor/tutor-app/docs/vibecode/runs/tutor-r01/` | read-only integration/backfill evidence |

The 16 L2 five-packs are not 16 complete automated runs. The 17 leaves include the 16 L2 STOP nodes and the separately terminal `MOD-03` L1 node.

## Five-pack mapping

| Legacy file | Canonical artifact type | Migration rule |
|---|---|---|
| `prd.json` | `prd` | retain source fact; Adapter supplies canonical envelope |
| `architecture.json` | `architecture` | retain source fact; not evidence of a current Architecture executor |
| `testcases.json` | `testcases` | retain source fact; not evidence of current Gherkin generation |
| `mocktest_report.json` | `mocktest` | mark as `prepared`; never infer strict completion from `PASS` |
| `leaf_gate_decision.json` | `leaf` | preserve owner-terminal provenance; not independent Leaf ground truth |

## Exclusions and non-claims

- Never read, copy, display, hash, or include `tutor/tutor-app/.env` or any other `.env` file.
- Do not treat `tutor-r01` as a production `run-workflow`, a C0-C5 run, or a current E2E result.
- Exclude `.git/`, `.worktrees/`, `data/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `.superdesign/`, machine-local drafts, secrets, and caches from any future shared package.
- Day 1 creates only the manifest and contract. Creating a clean package, per-file hashes, and relocation loaders remains a separately gated Day 2 activity.
