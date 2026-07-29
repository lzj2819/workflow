# D Environment Evidence — A Baseline `c12c4f5`

Status: **ENVIRONMENT/ACCEPTANCE-SPEC ERROR for the full Gate**; the root
27-test baseline below is independently **PASS**. This is a narrow environment
evidence record only. It does not authorize Executor implementation, model calls,
repair, hidden-test access, Tutor input, or C0--C5 execution.

## Provenance

| Field | Value |
|---|---|
| Head branch | `verilayer/d-environment-evidence` |
| Base branch | `verilayer/a-contract-integration` |
| Base commit | `c12c4f508ba7247c40ee84e40c256f2878600e18` |
| Workflow root | `vibe coding/` (repository-relative) |
| Local environment | `vibe coding/.venv/` (Git ignored) |

## Requirements digest

The working file is subject to Windows CRLF checkout conversion. Both observations
are retained so the content-addressed Git input and local raw file are distinguishable.

| Input | SHA-256 |
|---|---|
| Current working-file raw bytes: `vibe coding/requirements-verilayer.txt` | `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03` |
| Tracked Git blob raw LF bytes at `HEAD:vibe coding/requirements-verilayer.txt` | `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` |

## Environment identity

```text
python=3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]
pytest=8.3.5
platform=Windows-11-10.0.22631-SP0
```

`.venv` is ignored by the repository's `.gitignore`; no virtual-environment path,
credential, package-index token, or secret is recorded here.

## `pip freeze --all`

Raw `pip freeze --all` output SHA-256:

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

## Root baseline command and raw log

Command run from `vibe coding/`:

```text
.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py
```

Exit code: `0`

Raw combined stdout/stderr:

```text
...........................                                              [100%]
27 passed in 5.75s
```

## Full-Gate precondition

Command evaluated before attempting the full Gate from `vibe coding/`:

```text
Test-Path tests\integration
```

Result: `False`.

The acceptance command that names `tests/integration` cannot be a complete PASS on
this baseline because the path is absent. D did not create the directory and did not
run a substituted test target. Report to A: **ENVIRONMENT/ACCEPTANCE-SPEC ERROR**.

