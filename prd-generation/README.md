# PRD Generation

`prd-generation` converts product evidence into one canonical PRD model. The
machine authority is `prd.json` (`artifact_schema_version: prd/v3`); `prd.md`
is a deterministic twelve-section view of the same model.

## Quick start

```powershell
python scripts/run_prd_flow.py --help
python scripts/validate_prd.py --help
```

Dependencies are listed in `scripts/requirements.txt`. Do not set
`PYTHONPATH`; both launchers are portable and force UTF-8 output on Windows.

## Root

```powershell
python scripts/run_prd_flow.py --input root.json --output-dir artifacts/run-1/root `
  --run-id run-1 --project-id demo --node-id root `
  --created-at 2026-08-02T00:00:00Z --review-artifact review.json
```

Without a valid semantic-hash-bound independent review, Root writes
`prd.draft.md` and exits `2`. `--validate-only` never calls `input()` and always
keeps the result blocked.

## Derive

```powershell
python scripts/run_prd_flow.py --parent-prd parent/prd.md `
  --architecture-package architecture --target-module ReservationProcessor `
  --output child/prd.md

python scripts/run_prd_flow.py --derive-all --parent-prd parent/prd.md `
  --architecture-package architecture --output-dir artifacts/run-1
```

Derive inherits explicit parent obligations only. It never creates product
behavior from architecture prose or similarity. A split parent contract needs
an explicit projection. Full-layer output is all-or-nothing and every child
contains the complete five-file bundle.

## Canonical bundle

Every successful Root or child output directory contains:

- `prd.json` — single machine-authoritative model;
- `prd.md` — fixed twelve-section human view;
- `prd_manifest.json` — both JSON and Markdown SHA-256 values;
- `validation_report.json` — semantic/schema gate evidence;
- `execution_log.json` — run identity and execution evidence.

Blocked Root additionally contains `blocking_questions.json` and uses
`prd.draft.md`. It is never handoff-ready.

The shared envelope uses `schema_version: "1.0"`; PRD content uses
`artifact_schema_version: "prd/v3"`. Envelope `status` (`PASS|FAIL|ERROR`) is
separate from `prd_status` (`draft|approved|complete`).

## Validation

```powershell
python scripts/validate_prd.py path/to/prd.json --consumer canonical
python scripts/validate_prd.py path/to/prd.json --consumer architecture
python scripts/validate_prd.py path/to/prd.json --consumer gherkin
python scripts/validate_prd.py path/to/prd.json --consumer leaf

python -m compileall -q scripts
python -m unittest discover -s tests -v
```

The Architecture and Gherkin profiles validate PRD readiness/evidence semantics.
The Leaf profile validates the PRD fields needed for a later full Leaf bundle;
it does not bypass Architecture, Testcases, Mocktest, hashes, or repair lineage.
`module-result.json` remains the responsibility of the root workflow's command
adapter, not the standalone PRD domain CLI.
