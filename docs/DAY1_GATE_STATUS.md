# Day 1 Gate Status

Status: **GO** as of 2026-07-29. Active evidence baseline: `verilayer/a-contract-integration@8766793e9723c56cfbfbeed5ca4fbeaab9b7f85b`; the earlier NO-GO audits remain historical records below.

## Historical pre-closure environment audit (superseded)

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
- Historical input statement, superseded below: the canonical installation digest is the Git-blob SHA-256 `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472`. D's `464c4c…e76e03` is a Windows checkout observation, not stale input.

This is an exact install specification, not a completed lock. D must install from this exact current-A input, provide `pip freeze --all` and its SHA-256, then rerun commands on the current A baseline before any test result becomes a baseline.

## Required Gate closures

> **Historical record only — not the active Day 1 checklist.** The following table predates the 2026-07-29 scope correction. In particular, fresh B output, complete strict execution, semantic PASS, Leaf, Coding, and `tests/integration` are Day 3-or-later concerns and are not Day 1 acceptance conditions.

| Blocker | Owner | Acceptance command/evidence | Next step |
|---|---|---|---|
| Environment | A + D | `.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py tests/integration` exits 0; the root subset reports 27 passed | install only the approved project-local environment, capture `pip freeze --all` and its SHA-256; never commit `.venv` |
| Contract review | A + B + C + D | accepted B/C/D samples validate with `tests/test_artifact_contract.py`; signed review record | B/C/D rebase to A, open PRs to A, and resolve review comments without changing shared contract directly |
| C strict ready | C + A | import `mock_framework.models`; import `mock_framework.models.validator`; `main_session_strict_driver.py --help` all exit 0 in A-frozen environment | C rebase, redact evidence paths, open `fix/mocktest-models-package` → A, then A verifies hashes; `--help` is not strict PASS |
| B fresh output | B + C + A | fresh B Architecture/Testcases identity-valid bundle; then C records strict audit PASS and semantic PASS | B must provide fresh output after its PR review; neither fixture nor `--help` releases S1 Coding |

## Current branch evidence

- A: evidence baseline `c12c4f5`; PR #5 is already merged at that SHA. Subsequent A governance commits only record the audit and do not alter the baseline evidence.
- B: PR #3 is open and unmerged; head `3cca4a8`, base `c12c4f5`. Its seven files are proposals/fixtures, not fresh output.
- C: PR #5 is closed and merged at `c12c4f5`; restored models are present, but the current smoke record remains `ENVIRONMENT_ERROR`.
- D: PR #4 is closed and unmerged; head `1407c5e`. Its raw input hash `464c4c…e76e03` differs from current-A `f55ab0…ad472`, so it is rejected as current-A environment evidence.

All B/C/D PR targets are `verilayer/a-contract-integration`; no team branch may merge directly to `main`.

## 2026-07-29 reconciliation audit

| Evidence / command | Recorded exit | Current-A audit conclusion |
|---|---:|---|
| `Get-FileHash vibe coding/requirements-verilayer.txt` on current A | 0 | raw-bytes SHA-256 `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` |
| D PR #4 `sha256sum requirements-verilayer.txt` | 0 | reports Windows checkout observation `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03`; not a canonical blob digest, not stale input |
| D PR #4 `pip freeze --all | sha256sum` | 0 | reports `79e4c5de123d0db2fc070e1cf9d6518258a92466f6b2d91b9218fba826593e90`; historical/unmerged review evidence, not a current-A lock |
| D PR #4 root pytest baseline | 0 | reports 27 passed; historical/unmerged review evidence, not a current-A baseline |
| D PR #4 full Gate command including `tests/integration` | 4 | `ENVIRONMENT_ERROR`: target absent; no PASS inferred |

| Subject | Strict execution completeness | Semantic PASS/FAIL | Environment |
|---|---|---|---|
| C models restoration (PR #5, merged) | `NOT_RUN` | `NOT_RUN` | `ERROR`: smoke commands exit 1 because `pyyaml` is missing |
| D environment evidence (PR #4, closed/unmerged) | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `ERROR`: current-A environment evidence pending; missing integration target |
| B fixture/validator evidence (PR #3, open) | `NOT_RUN` | `NOT_RUN` | validator fixtures are not current-A pytest/E2E evidence |

PR #3 is open and unmerged with seven proposal/fixture files; it is acceptable as a Day 1 proposal only. PR #4 is closed and unmerged. PR #5 is closed and merged at `c12c4f5`; restored models do not establish strict PASS. `main_session_strict_driver.py --help` is never strict PASS.

## 2026-07-29 prior acceptance-language resolution (historical environment input)

The only active artifact envelope is **v0.2**. The v0.3 entry in `docs/contract-change-log.md` is a profile-field decision record; it is not a second envelope, schema version, or Gate approval.

### Canonical installation input at the prior baseline

The reproducible installation input is the Git blob byte stream at `c12c4f508ba7247c40ee84e40c256f2878600e18:vibe coding/requirements-verilayer.txt`, SHA-256 `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472`.

```powershell
$p = [Diagnostics.Process]::new(); $p.StartInfo.FileName = 'git'; $p.StartInfo.Arguments = 'cat-file blob "c12c4f508ba7247c40ee84e40c256f2878600e18:vibe coding/requirements-verilayer.txt"'; $p.StartInfo.UseShellExecute = $false; $p.StartInfo.RedirectStandardOutput = $true; [void]$p.Start(); $m = [IO.MemoryStream]::new(); $p.StandardOutput.BaseStream.CopyTo($m); $p.WaitForExit(); $h = [Security.Cryptography.SHA256]::Create(); ([BitConverter]::ToString($h.ComputeHash($m.ToArray())) -replace '-', '').ToLower(); $p.ExitCode
Get-FileHash "vibe coding/requirements-verilayer.txt" -Algorithm SHA256
git check-attr -a -- "vibe coding/requirements-verilayer.txt"
```

All three commands exited `0` in A's current checkout. Blob bytes and current checkout bytes both hash to `f55ab0...ad472`; `core.autocrlf=true` is observed and no explicit attribute is returned for the path. D's reported Windows working-file bytes `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03` remain a separate observation. Without D's exact checkout bytes and a frozen EOL policy, A does **not** classify that hash as wrong or stale. It is noncanonical solely because Git blob bytes are the frozen install rule.

### Full-Gate target

`vibe coding/tests/integration` is absent. It is excluded from the executable Day 1 Gate; a command containing it must record pytest exit `4` as an acceptance-spec `ERROR`, never as PASS. The current valid target, still unrun on current A, is:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py
```

### Closure and result matrix

| Owner | Required acceptance |
|---|---|
| B | PR #3 stays proposal/fixture-only until fresh Architecture/Testcases samples pass contract tests in the frozen current-A environment. |
| C | PR #5 models recovery is merged, but imports, `main_session_strict_driver.py --help`, and a real strict run must complete in that environment. `--help` alone is not strict PASS. |
| D | install from the canonical blob input, record `pip freeze --all` plus SHA-256, and rerun the valid target on current A. The `8cb3582` 27-test log is review evidence only. |
| A+B+C+D | accept samples and complete four-owner Gate sign-off. |

| Subject | environment ERROR | strict execution completeness | semantic PASS/FAIL | real pytest |
|---|---|---|---|---|
| Current A | `ERROR`: no project-local `.venv` | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| B PR #3 | not environment evidence | `NOT_RUN` | `NOT_RUN` | fixture/proposal only |
| C models PR #5 | smoke/strict unrun in frozen A environment | `NOT_RUN` | `NOT_RUN` | `NOT_RUN` |
| D `verilayer/d-environment-evidence@8cb3582` | current-A rerun missing | `NOT_APPLICABLE` | `NOT_APPLICABLE` | reports 27 passed; not current-A baseline |

**Gate decision at this historical audit checkpoint: NO-GO. Superseded by the closure record below.**

## Active Day 1 Gate checklist (closed)

All four narrowed Day 1 items below have reviewable evidence on the active baseline. Nothing else in this document is a Day 1 acceptance condition.

| # | Owner | Required Day 1 evidence |
|---:|---|---|
| 1 | A | Complete: Contract v0.2 remains the active envelope; v0.3 is only a profile-field decision record. |
| 2 | D | Complete: `8766793` environment evidence uses Git blob digest `370d4e7bd1ae9df0ede903ac4741c5f1fd4c02a53b13eb0e732c380a10ba0bc6`; freeze/hash and valid pytest evidence are recorded below. The CRLF checkout observation `de4f9477b138a00a3c959d33766ef92bff6c03048d06710c59caf4ebb3ca49fb` is retained, not stale input. |
| 3 | B | Complete: PR #3 head `6272d30` fixtures pass live Contract v0.2 schema and canonical content-hash validation in D's frozen A environment. Fresh generated Architecture/Testcases output is not a Day 1 result. |
| 4 | C | Complete: the three frozen-environment smoke commands exit 0. They remain smoke only, not strict or semantic PASS. |

The following are explicitly deferred to **Day 3 or later**: fresh B output, a complete strict audit/run, semantic PASS/FAIL, Leaf, Coding, and any `tests/integration` suite. If `tests/integration` is named before that suite exists, pytest exit `4` remains an acceptance-spec `ERROR`, never PASS.

## 2026-07-29 Day 1 closure record (active)

The active environment input was corrected only to include the three runtime
dependencies proven necessary for the declared Day 1 C smoke commands:
`PyYAML==6.0.2`, `rich==13.9.4`, and `gherkin-official==24.1.0`. This is an
environment-input correction, not an Artifact Contract version change.

| Evidence | Result |
|---|---|
| A baseline | `8766793e9723c56cfbfbeed5ca4fbeaab9b7f85b` |
| Python | CPython 3.12.10 |
| Canonical installation input | Git blob SHA-256 `370d4e7bd1ae9df0ede903ac4741c5f1fd4c02a53b13eb0e732c380a10ba0bc6` |
| Windows checkout observation | SHA-256 `de4f9477b138a00a3c959d33766ef92bff6c03048d06710c59caf4ebb3ca49fb` |
| `pip freeze --all` | exit 0; UTF-8/LF SHA-256 `f7477b69477c9b29ee43f8434d26ad6fa533ab46f3e652cd131b620749d8a288` |
| Valid Day 1 pytest target | exit 0; `28 passed in 27.60s` |
| B fixture validation | PR #3 head `6272d30`; v0.2 schema exit 0, content-hash exit 0, contract unit test exit 0 (`1 passed`) |
| C smoke | models import exit 0; validator import exit 0; strict-driver `--help` exit 0 |

The pytest command was executed from `vibe coding/` with `TMP` and `TEMP`
set to repository-local `.pytest-tmp` because the user-level default temp
directory is not accessible on this host. The test target itself is unchanged:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py
```

The coordinator performed the A/B/C/D owner review in the user's authorized
takeover scope. **Day 1 Gate decision: GO.** This decision authorizes only Day
2 production skeleton work. It does not claim a strict run, semantic result,
Leaf decision, Coding Executor, repair result, E2E flow, C0--C5 run, or
experiment result.
