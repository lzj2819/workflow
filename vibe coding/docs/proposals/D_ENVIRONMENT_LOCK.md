# D Environment Lock Evidence (Day 1, post-freeze re-verification)

Status: **VERIFIED for the root baseline subset** on 2026-07-28, after A froze the
raw working-file requirements hash in commit `4c54853`. This supersedes the
pre-freeze claims in the previous revision of this document. No credentials,
index URLs, tokens, or private-test details are recorded here.

## 1. Frozen input verification (performed after the freeze, before install)

| Field | Value |
|---|---|
| Branch state | `verilayer/d-coding-experiments` rebased onto `4c54853712a7f0cdfe4a6a1a6da2325ae089a874` |
| Canonical input | `vibe coding/requirements-verilayer.txt` raw checked-out working-file bytes |
| Frozen SHA-256 (A) | `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03` |
| Recomputed SHA-256 (D) | `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03` |
| Command | `sha256sum "vibe coding/requirements-verilayer.txt"` on the working file, exit 0 |
| Result | **MATCH** — installation proceeded only after this match |

The LF-normalized Git-blob value `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472`
is not used as installation evidence.

## 2. Environment identity

| Field | Value |
|---|---|
| Environment ID | `verilayer-py312-v2` |
| Python | CPython 3.12.10 (`python -VV`: `3.12.10 (tags/v3.12.10:0cc8128, Apr 8 2025) [MSC v.1943 64 bit (AMD64)]`) |
| Environment location | `vibe coding/.venv/` (Git-ignored, never committed) |
| Platform | Windows 11, build 10.0.22631, 64-bit |
| Public pytest timeout | 120 seconds |

## 3. Installation provenance

```text
.venv/Scripts/python.exe -m pip install --disable-pip-version-check --no-input -r requirements-verilayer.txt
```

Exit code: `0`. All five approved direct dependencies installed at the frozen
versions. The package index was used without recording its URL, token, or
credentials.

## 4. `pip freeze --all` evidence

Full output committed at `vibe coding/docs/proposals/D_PIP_FREEZE.txt`.

- SHA-256 of the captured stdout bytes (LF): `79e4c5de123d0db2fc070e1cf9d6518258a92466f6b2d91b9218fba826593e90`
- The committed file may be EOL-normalized by `core.autocrlf` on checkout; the
  hash above covers the exact command stdout bytes. Package identities and
  versions are unaffected by EOL normalization.

Direct-dependency check against the frozen input: `pytest==8.3.5`,
`fastapi==0.115.12`, `SQLAlchemy==2.0.41`, `pydantic==2.13.4`,
`jsonschema==4.26.0` — all present at exact versions.

## 5. Test evidence (real runs, this environment, after the freeze)

| # | Command | Exit | Result | Classification |
|---|---|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` | 0 | `27 passed in 5.25s` | **PASS: pytest 27-test baseline** |
| 2 | `.venv/Scripts/python.exe -m pytest -q tests/test_artifact_contract.py` | 0 | `1 passed in 0.02s` | PASS |
| 3 | `.venv/Scripts/python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py tests/integration` | 4 | `ERROR: file or directory not found: tests/integration` | **ENVIRONMENT_ERROR — missing target** |

Notes:

- Run 2 was executed with `TEMP`/`TMP` redirected to the workspace-local
  directory `vibe coding/.work/tmp` (Git-ignored). The unmodified attempt hits
  `PermissionError [WinError 5]` on the machine-local
  `%TEMP%\pytest-of-Lenovo` directory, which is owned by another security
  principal and cannot be removed without elevation. This is a machine-local
  tool error, not a test failure; it affects only pytest's default `basetemp`.
- Run 3 is A's specified full Gate command. It fails at collection because
  `tests/integration` does not exist in this checkout (or at `4c54853`). Per
  the fail-closed rule this is an `ERROR`, never a `FAIL` or inferred `PASS`.
  **A must supply or correct the `tests/integration` target.**

## 6. Pre-existing failure in A-owned files (reported, not modified)

`.venv/Scripts/python.exe -m pytest -q tests/test_vibecode.py` reports:

```text
FAILED tests/test_vibecode.py::SchemaTests::test_baseline_schemas_are_valid_json_and_share_public_statuses
AssertionError: Items in the first set but not the second: 'verilayer-artifact.schema.json'
```

This failure reproduces identically at clean commit `4c54853` (verified in a
temporary worktree with no D changes): `tests/test_vibecode.py` enumerates an
expected baseline schema set that does not include
`vibecode/schemas/verilayer-artifact.schema.json`. Both files are A-owned
(`docs/FILE_OWNERSHIP.md`); D has not modified them and reports this as a Gate
item for A.

## 7. Non-authorizations

This lock does not authorize Executor implementation, a model call, repair
execution, hidden-test access, Tutor input, or S1/C0–C5 execution. S1 Coding
admission still requires items 3–6 of the checklist in
`docs/proposals/D_ENVIRONMENT_RESOLUTION.md` §7.
