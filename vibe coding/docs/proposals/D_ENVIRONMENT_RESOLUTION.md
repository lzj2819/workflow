# D Environment Resolution (Day 2 — Pending A Approval)

Status: **PARTIALLY_VERIFIED**. The approved Git blob hash, local environment
installation, freeze evidence, and 27-test pytest baseline are verified. The full
Gate command remains blocked because the specified `tests/integration` path does not
exist in this checkout. See `docs/proposals/D_ENVIRONMENT_LOCK.md`.

## 1. A decision and canonical hash validation

A approved the following exact environment in `docs/DAY1_GATE_STATUS.md` and
`requirements-verilayer.txt`: CPython 3.12.10, `pytest==8.3.5`,
`fastapi==0.115.12`, `SQLAlchemy==2.0.41`, `pydantic==2.13.4`, and
`jsonschema==4.26.0`. A also accepted the D Code/TestResult/Evidence profile as
`ADDITIVE_ONLY` in `docs/contract-change-log.md`.

The approved-input SHA-256 recorded by A is
`f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472`. It matches
the raw LF bytes of the tracked Git blob
`origin/verilayer/a-contract-integration:vibe coding/requirements-verilayer.txt`.
This Windows checkout has `core.autocrlf=true`; its CRLF-transformed working file
hashes to `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03`.
The latter is an EOL-observation value, not a replacement approved input hash.

The relevant Artifact Contract rule is fail-closed: an unavailable or unverifiable
environment is an `ERROR`, not a `FAIL` or a successful Coding result. This proposal
therefore does not infer a final version from a minimum-version declaration.

## 2. Observed machine state

| Control | Observation |
|---|---|
| Platform | Windows 11, build 10.0.22631, 64-bit |
| Current interpreter | CPython 3.12.10 |
| Current pytest | absent (`python -m pytest --version` exits 1: no module named pytest) |
| Current FastAPI | absent |
| Current SQLAlchemy | absent |
| Current pydantic | 2.13.4 |
| Current jsonschema | 4.26.0 |
| Public pytest timeout | 120 seconds (frozen Day 1 protocol) |
| Repair limit | initial attempt plus at most two automatic repair rounds |

The current interpreter may be used only for read-only/static checks. It is not yet
the approved VeriLayer experiment environment.

## 3. Repository dependency evidence

| Source | Declared runtime | What it establishes | What it does not establish |
|---|---|---|---|
| `prd-generation/scripts/requirements.txt` | `fastapi>=0.115`, `SQLAlchemy>=2.0`, `pydantic>=2.7`, plus application dependencies | lower bounds used by an adjacent generator stack | an exact, compatible experiment lock |
| `mocktest/pyproject.toml` | Python `^3.10`, `pydantic ^2.0`, `jsonschema ^4.0`, dev `pytest ^7.0` | Mocktest's declared compatibility range | a verified strict-backend repair or Coding dependency set |
| `tutor/tutor-app/deploy/Dockerfile.server` | `python:3.12-slim` | Tutor's reference-container major/minor Python | permission to reuse Tutor code or its dependency environment |
| `tutor/tutor-app/server/requirements.txt` and `worker/requirements.txt` | `SQLAlchemy>=2.0`, `httpx>=0.27`, PostgreSQL-oriented packages | reference lower bounds only | fixed package versions for SQLite VeriLayer experiments |

No root `pyproject.toml`, lock file, or `vibe coding` requirements file currently
defines an exact experiment environment. Docker and Tutor manifests are reference
evidence only; they do not enter S1, model context, public tests, or C0--C5 data.

## 4. Proposed resolution record for A

| Field | Proposed value until approval |
|---|---|
| `environment_id` | `verilayer-py312-v1` |
| Python | CPython 3.12.10 (approved) |
| pytest | `8.3.5` (approved) |
| FastAPI | `0.115.12` (approved) |
| SQLAlchemy | `2.0.41` (approved) |
| pydantic/jsonschema | `2.13.4` / `4.26.0` (approved) |
| Installation source | approved package index/wheelhouse selected by D at installation time; credentials are not recorded |
| Virtual-environment location | `vibe coding/.venv/` only; local, ignored, never committed |
| Freeze artifact | `pip freeze --all` output plus SHA-256, recorded as a repository-relative evidence artifact after approval |
| Test invocation | `.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` |
| Timeout | 120 seconds per public pytest invocation |

## 5. Installation procedure and current result

1. Confirm the canonical Git blob hash and record the Windows EOL observation.
2. Use exactly `vibe coding/.venv/`; it is ignored by Git.
3. Install only the A-approved exact package list from the approved source.
4. Capture interpreter identity, platform, `pip freeze --all`, package-list hash, and
   install command provenance without credentials.
5. Run the required pytest baseline. Only exit `0` with all three root files
   collected permits the label “pytest 27-test baseline.”
6. Preserve command, exit code, stdout, stderr, and duration as environment
   evidence. A missing suite path, collection error, or nonzero exit remains `ERROR`.

## 6. Current gates and non-authorizations

- A accepted D's Code/TestResult/Evidence profile. The 27-test baseline is now
  PASS, but the specified full Gate command is still an `ENVIRONMENT_ERROR` until A
  supplies or corrects the missing `tests/integration` target.
- C's strict backend is currently `ERROR` because the public package omits
  `mock_framework.models`; this does not become a mock `PASS`, Leaf `STOP_LAYERING`,
  or Coding input.
- B has not supplied a legal S1 Architecture/Testcases bundle; C has not supplied a
  complete strict execution with an Architecture `PASS`; A has not issued a Coding
  release.
- No model call, repair loop execution, hidden-test creation/read/copy, Tutor input,
  or C0--C5 experiment is authorized by this proposal.

## 7. S1 Coding admission checklist

Real S1 Coding remains blocked until all six conditions are recorded:

1. A freezes the relevant Contract and approves D's artifact fields.
2. The approved local environment passes the real pytest 27-test baseline.
3. B provides valid S1 Architecture and Testcases artifacts.
4. C completes strict execution and records Architecture `PASS`.
5. C's Leaf result is `STOP_LAYERING` with complete evidence.
6. A explicitly releases this S1 leaf to D.
