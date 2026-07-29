# Day 1 Environment Evidence — A Baseline `8766793`

Status: **Day 1 GO evidence only**. This record does not assert a strict run,
semantic PASS/FAIL, Leaf decision, Coding/repair result, end-to-end execution,
or experiment result.

## Immutable inputs

| Field | Value |
|---|---|
| A baseline | `8766793e9723c56cfbfbeed5ca4fbeaab9b7f85b` |
| Python | CPython 3.12.10 |
| Installation input | Git blob `8766793:vibe coding/requirements-verilayer.txt` |
| Canonical blob SHA-256 | `370d4e7bd1ae9df0ede903ac4741c5f1fd4c02a53b13eb0e732c380a10ba0bc6` |
| Windows checkout SHA-256 | `de4f9477b138a00a3c959d33766ef92bff6c03048d06710c59caf4ebb3ca49fb` |
| Freeze SHA-256 | `f7477b69477c9b29ee43f8434d26ad6fa533ab46f3e652cd131b620749d8a288` |

The blob digest is the canonical installation rule. The checkout digest is a
separate CRLF working-file observation and is neither silently replaced nor
classified as stale.

## Frozen environment result

`pip freeze --all` exited 0. The environment includes the frozen requirements
and transitive packages; `pip==26.1.2` is an environment tool used to produce
the required freeze record.

The host's default user temporary directory is inaccessible to pytest. `TMP`
and `TEMP` were set to the repository-local, uncommitted `.pytest-tmp`
directory before execution. The accepted command itself was unchanged:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py tests/test_artifact_contract.py
```

Result: exit 0, `28 passed in 27.60s`.

## B fixture review

B fixture source: `verilayer/b-generation@6272d30fc08ea9ce361b82836bdbcc44cf51255e`.

Using this A baseline's frozen interpreter and v0.2 schema:

| Check | Result |
|---|---|
| Architecture fixture schema validation | exit 0 |
| Testcases fixture schema validation | exit 0 |
| Architecture fixture canonical content hash | exit 0 |
| Testcases fixture canonical content hash | exit 0 |
| `tests/test_artifact_contract.py` on B fixture branch | exit 0; `1 passed` |

These are contract-fixture results only. They are not fresh Architecture or
Testcases generation evidence.

## C smoke

With `PYTHONPATH=mocktest/src` in the frozen A environment:

| Command | Result |
|---|---|
| `python -c "import mock_framework.models"` | exit 0 |
| `python -c "import mock_framework.models.validator"` | exit 0 |
| `main_session_strict_driver.py --help` | exit 0 |

The help command proves only that the strict driver imports and parses CLI
arguments. It is not a strict execution-completeness result and does not carry
a semantic status.
