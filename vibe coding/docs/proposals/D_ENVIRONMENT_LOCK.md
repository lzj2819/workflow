# D Environment Lock Evidence (Day 2)

Status: **PARTIALLY_VERIFIED** on 2026-07-28. This document records the approved
environment and observed commands without credentials, absolute paths, or local
index configuration.

## Approved dependency input

| Field | Value |
|---|---|
| Environment ID | `verilayer-py312-v1` |
| Canonical input | `vibe coding/requirements-verilayer.txt` Git blob bytes |
| Approved SHA-256 | `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` |
| Python | CPython 3.12.10 |
| Direct packages | `pytest==8.3.5`, `fastapi==0.115.12`, `SQLAlchemy==2.0.41`, `pydantic==2.13.4`, `jsonschema==4.26.0` |
| Local environment | `vibe coding/.venv/` (Git ignored) |
| Platform | Windows-11-10.0.22631-SP0 |
| Public pytest timeout | 120 seconds |

The approved hash matches the raw LF bytes of the tracked Git blob. This Windows
working tree uses CRLF conversion; its working-file byte hash is
`464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03`, retained
only as an EOL observation.

## Installation provenance

```text
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input -r requirements-verilayer.txt
```

The approved package index/wheelhouse was used without recording its URL, token, or
credentials. The command completed with exit code 0.

## `pip freeze --all`

Raw freeze-output SHA-256:

```text
79e4c5de123d0db2fc070e1cf9d6518258a92466f6b2d91b9218fba826593e90
```

```text
annotated-types==0.8.0
anyio==4.14.2
attrs==26.1.0
colorama==0.4.6
fastapi==0.115.12
greenlet==3.5.4
idna==3.18
iniconfig==2.3.0
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
packaging==26.2
pip==25.0.1
pluggy==1.6.0
pydantic==2.13.4
pydantic_core==2.46.4
pytest==8.3.5
referencing==0.37.0
rpds-py==2026.6.3
SQLAlchemy==2.0.41
starlette==0.46.2
typing-inspection==0.4.2
typing_extensions==4.16.0
```

## Test evidence

| Command | Result | Gate classification |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py` | `27 passed in 5.53s` | **PASS: pytest 27-test baseline** |
| `.\.venv\Scripts\python.exe -m pytest -q tests/test_artifact_contract.py` | `1 passed in 0.04s` | PASS |
| `.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py tests/integration` | exit 1: `ERROR: file or directory not found: tests/integration` | **ENVIRONMENT_ERROR** |

The full Gate is not complete. This lock therefore does not authorize Executor
implementation, a model call, repair execution, hidden-test access, Tutor input, or
S1/C0--C5 execution.
