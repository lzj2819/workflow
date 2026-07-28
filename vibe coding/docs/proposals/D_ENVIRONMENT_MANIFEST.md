# D Environment Manifest (Day 1 Proposal)

Status: proposal for A's Day 1 contract review. This records the machine observed on
2026-07-28; it is not an environment lock and is not a production configuration.

## Observed baseline environment

| Item | Observed value |
|---|---|
| Workspace root | `E:\workflow论文写作\vibe coding` (machine-local) |
| OS | Windows 11, build 10.0.22631 (64-bit) |
| Python executable | `C:\Users\Lenovo\AppData\Local\Programs\Python\Python312\python.exe` (machine-local) |
| Python | CPython 3.12.10 |
| pytest | not installed |
| FastAPI | not installed |
| SQLAlchemy | not installed |
| pydantic | 2.13.4 |
| jsonschema | 4.26.0 |

Machine-local paths above are diagnostic provenance only. Shared run manifests must
use a logical `environment_id`, repository-relative paths, dependency hashes, and
never this path.

## Baseline record

The requested pytest baseline command was attempted from the workflow root:

```text
python -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py
```

It exited `1` before collection because this Python has no `pytest` module. No test
failure is inferred from that result. A stdlib diagnostic was then run without
changing the environment:

```text
python -m unittest -v tests.test_contracts tests.test_module_runner tests.test_root_workflow
```

It exited `0`: **27 tests passed in 5.355 seconds**. This is diagnostic evidence,
not a replacement for the required frozen pytest baseline.

## Day 1 execution freeze proposal

| Control | Frozen proposal |
|---|---|
| Runtime profile | Python + FastAPI + pytest + SQLite, Modular Monolith |
| Public-test timeout | 120 seconds per pytest invocation |
| Automatic repair | initial attempt plus at most two repair rounds |
| C0--C5 executor | one executor identity, one code prompt hash, equal task budget and repair limit |
| Secret handling | only provider environment-variable *names* may be configured; values are never recorded, read, or committed |
| Allowed provider variable names | `VERILAYER_MODEL_PROVIDER`, `VERILAYER_MODEL_ID`, `VERILAYER_MODEL_BASE_URL`, `VERILAYER_MODEL_API_KEY` |
| Sensitive files excluded | `.env`, model caches, provider credential stores, private tests, and generated workspaces |
| Tutor status | read-only engineering oracle only; it is not a Coding input, C0--C5 task, test source, or automatic result |

`VERILAYER_MODEL_API_KEY` is a name only. This document intentionally contains no
key, endpoint credential, cached response, or provider value.

## Required environment lock before Day 2

1. Select one reproducible Python environment that has exact, recorded versions of
   `pytest`, `fastapi`, `sqlalchemy`, `pydantic`, and `jsonschema`.
2. Save a dependency lock or canonical package inventory and its SHA-256 in the
   environment preflight output; record absent packages as failures, never guesses.
3. Re-run the required pytest baseline with exit `0` and preserve command, stdout,
   stderr, duration, interpreter identity, and package inventory hash.
4. Keep the Tutor reference environment separate from the VeriLayer experiment
   environment. A reference-regression result cannot certify the experiment runtime.
5. A's frozen Artifact Contract and a B/C strict-PASS S1 leaf bundle are required
   before any real Coding Executor invocation.

