# Day 1 Gate Status

Status: **NO-GO** as of 2026-07-29. Current A baseline: `verilayer/a-contract-integration@c12c4f508ba7247c40ee84e40c256f2878600e18`.

## Current-A environment evidence audit

Current A has no `vibe coding/.venv/Scripts/python.exe`; `vibe coding/tests/integration` does not exist. D PR #4 is closed and unmerged, so its environment records cannot be promoted into current-A evidence.

The baseline is therefore recorded as:

```text
status: ENVIRONMENT_ERROR
command: .\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py tests/integration
result: not started on current A — project-local .venv and tests/integration are absent
```

No static check, log, historical report, fixture, xfail, Tutor artifact, or unrun test is a substitute for a current-A `27 passed` run.

## Approved environment specification (installation still pending)

- Python: CPython 3.12.10.
- `pytest==8.3.5`
- `fastapi==0.115.12`
- `SQLAlchemy==2.0.41`
- `pydantic==2.13.4`
- `jsonschema==4.26.0`
- Install source: the approved package index/wheelhouse selected by D at installation time; credentials and index tokens are not recorded.
- Project-local environment path: `vibe coding/.venv/` only, ignored by Git.
- Approved input file: `vibe coding/requirements-verilayer.txt` with current-A raw-bytes SHA-256 `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` (recomputed by A on 2026-07-29). D PR #4 reports `464c4c…e76e03` for a different checked-out input; it is stale and not current-A installation evidence.

This is an exact install specification, not a completed lock. D must install from this exact current-A input, provide `pip freeze --all` and its SHA-256, then rerun commands on the current A baseline before any test result becomes a baseline.

## Required Gate closures

| Blocker | Owner | Acceptance command/evidence | Next step |
|---|---|---|---|
| Environment | A + D | `.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py tests/integration` exits 0; the root subset reports 27 passed | install only the approved project-local environment, capture `pip freeze --all` and its SHA-256; never commit `.venv` |
| Contract review | A + B + C + D | accepted B/C/D samples validate with `tests/test_artifact_contract.py`; signed review record | B/C/D rebase to A, open PRs to A, and resolve review comments without changing shared contract directly |
| C strict ready | C + A | import `mock_framework.models`; import `mock_framework.models.validator`; `main_session_strict_driver.py --help` all exit 0 in A-frozen environment | C rebase, redact evidence paths, open `fix/mocktest-models-package` → A, then A verifies hashes; `--help` is not strict PASS |
| B fresh output | B + C + A | fresh B Architecture/Testcases identity-valid bundle; then C records strict audit PASS and semantic PASS | B must provide fresh output after its PR review; neither fixture nor `--help` releases S1 Coding |

## Current branch evidence

- A: `verilayer/a-contract-integration`, commit `4c54853`, pushed to `origin`; it freezes the approved raw requirements hash.
- B: `origin/verilayer/b-generation`, latest `0f8fc8f`; PR #3 is open but B must rebase to A, emit canonical child `node_id`, and provide validator evidence before review.
- C: `origin/verilayer/c-validation`, latest `3117416`; the independent models candidate is `origin/fix/mocktest-models-package@36956b4` and is not eligible for merge until it is rebased to A and its evidence is UTF-8, path-redacted, and hash-consistent.
- D: `origin/verilayer/d-coding-experiments`, latest `7884c69`; its pre-freeze environment record is rejected as a baseline. D must rebase to A and create the approved project-local environment before opening `D → A` PR.

All B/C/D PR targets are `verilayer/a-contract-integration`; no team branch may merge directly to `main`.

## 2026-07-29 reconciliation audit

| Evidence / command | Recorded exit | Current-A audit conclusion |
|---|---:|---|
| `Get-FileHash vibe coding/requirements-verilayer.txt` on current A | 0 | raw-bytes SHA-256 `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` |
| D PR #4 `sha256sum requirements-verilayer.txt` | 0 | reports `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03`; `ENVIRONMENT_ERROR/STALE_INPUT_HASH` |
| D PR #4 `pip freeze --all | sha256sum` | 0 | reports `79e4c5de123d0db2fc070e1cf9d6518258a92466f6b2d91b9218fba826593e90`; unmerged and stale-input-bound, not an accepted current-A lock |
| D PR #4 root pytest baseline | 0 | reports 27 passed; unmerged and stale-input-bound, not an accepted current-A baseline |
| D PR #4 full Gate command including `tests/integration` | 4 | `ENVIRONMENT_ERROR`: target absent; no PASS inferred |

| Subject | Strict execution completeness | Semantic PASS/FAIL | Environment |
|---|---|---|---|
| C models restoration (PR #5, merged) | `NOT_RUN` | `NOT_RUN` | `ERROR`: smoke commands exit 1 because `pyyaml` is missing |
| D environment evidence (PR #4, closed/unmerged) | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `ERROR`: stale input hash; missing integration target |
| B fixture/validator evidence (PR #3, open) | `NOT_RUN` | `NOT_RUN` | validator fixtures are not current-A pytest/E2E evidence |

PR #3 is open and unmerged with seven proposal/fixture files; it is acceptable as a Day 1 proposal only. PR #4 is closed and unmerged. PR #5 is closed and merged at `c12c4f5`; restored models do not establish strict PASS. `main_session_strict_driver.py --help` is never strict PASS.
