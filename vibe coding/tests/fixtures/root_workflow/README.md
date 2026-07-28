# Root workflow fixtures

`scenarios.json` is the authoritative catalog for the six required E2E conditions. `command_adapter.py` is a deterministic external process adapter that writes the same structured `module-result.json` contract required from real modules. `project-config.single.json` is a directly runnable CLI example; scenario-specific fault injection is covered by `tests/test_root_workflow.py` through the same adapter boundary.

Example dry run from the repository root:

```powershell
python vibecode/scripts/vibecode.py run-workflow --requirement tests/fixtures/root_workflow/requirement.json --config tests/fixtures/root_workflow/project-config.single.json --output-dir .tmp/vibecode-fixtures --run-id dry-run-1 --project-id fixture --dry-run
```

Dry-run emits only `dry_run_plan.json`. A normal run emits the seven named authoritative reports and run-scoped node artifacts. Fixture approvals are test evidence only and must never be reused as production Integration Owner approval.
