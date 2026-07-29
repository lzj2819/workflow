# Day 2 Production Skeleton Evidence

Baseline: `730bb3064603b7dcb69ed0ca53a9321f1ae4dd9e`.

This record covers the Day 2 command/configuration skeleton only. It contains no strict execution, semantic validation, Leaf, Coding, repair, end-to-end, or experiment outcome.

## Verified commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe experiments\run_matrix.py --config config\verilayer.production.json --validate-only
.\.venv\Scripts\python.exe vibecode\scripts\vibecode.py run-workflow --requirement examples\day2_s1_requirement.json --config config\verilayer.production.json --output-dir <empty-output-dir> --run-id day2-dry-run-rerun --project-id verilayer-day2 --root-node-id s1 --dry-run
```

Results: full suite exit 0 (`59 passed in 28.45s`); config validation exit 0; root dry-run exit 0.

The dry-run output is a plan only. It invokes no configured module command and must not be cited as a workflow completion result.

## Controlled unavailable-module behavior

For each production module (`prd`, `architecture`, `gherkin`, `mocktest`, `leaf_gate`, `coding`, `backfill`, and `integration`), the Day 2 adapter writes `module-result.json` with:

- `status: ERROR`;
- `error_type: MODULE_NOT_IMPLEMENTED`;
- a v0.2 envelope with lowercase `error.category: system`;
- repository-relative input reference; and
- no invented output artifact.

The Day 2 test validates all eight results against `vibecode/schemas/verilayer-artifact.schema.json`. This is controlled transport evidence, not a PASS from any real module.
