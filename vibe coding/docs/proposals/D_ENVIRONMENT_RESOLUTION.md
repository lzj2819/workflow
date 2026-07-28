# D Environment Resolution (Day 2 — Pending A Approval)

Status: **PENDING_A_APPROVAL**. This is an environment-resolution proposal, not a
lock file and not authorization to install packages. No virtual environment has been
created, no dependency has been installed, and no system Python has been changed.

## 1. Decision requested from A

A must approve an exact, reproducible VeriLayer experiment environment before D
creates the project-local virtual environment. The approval must name exact versions
and installation source for Python, pytest, FastAPI, SQLAlchemy, pydantic, and
jsonschema; it must also approve the resulting package-inventory hash.

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
| `environment_id` | `verilayer-py312-pending` |
| Python candidate | CPython 3.12.10, because it matches the observed host and Tutor container major/minor; **pending A approval** |
| pytest | exact version **pending**; source constraint is Mocktest `^7.0` only |
| FastAPI | exact version **pending**; source constraint is `>=0.115` only |
| SQLAlchemy | exact version **pending**; source constraint is `>=2.0` only |
| pydantic/jsonschema | exact versions **pending**; current observed versions are not a lock decision |
| Installation source | approved package index/wheelhouse **pending A approval** |
| Virtual-environment location | `vibe coding/.venv/` only; local, ignored, never committed |
| Freeze artifact | `pip freeze --all` output plus SHA-256, recorded as a repository-relative evidence artifact after approval |
| Test invocation | `.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` |
| Timeout | 120 seconds per public pytest invocation |

## 5. Post-approval procedure (not yet executed)

1. Create exactly `vibe coding/.venv/`; confirm it is ignored before installation.
2. Install only the A-approved exact package list from the A-approved source.
3. Capture interpreter identity, platform, `pip freeze --all`, package-list hash, and
   install command provenance without credentials.
4. Run the required pytest baseline. Only exit `0` with all three files collected
   permits the label “pytest 27-test baseline.”
5. Preserve command, exit code, stdout, stderr, and duration as environment
   evidence. A missing package, collection error, or nonzero exit remains `ERROR`.

## 6. Current gates and non-authorizations

- A has not yet recorded approval of D's proposed `Code`, `TestResult`, and
  `Evidence` profiles; no executor skeleton may be written.
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

