# D Environment Evidence — A Baseline `d8041d0`

Status: **Day 1 NO-GO**. The full Gate is an
**ENVIRONMENT/ACCEPTANCE-SPEC ERROR**; this is neither a full-Gate PASS nor an
Architecture FAIL. This document is a review-only environment evidence record.
It does not authorize a Coding Executor, model call, repair loop, hidden-test
access, Tutor input, strict execution, Leaf evaluation, Coding, E2E, C0--C5, or
any other experiment.

## Provenance and scope

| Field | Value |
|---|---|
| Evidence branch | `verilayer/d-environment-evidence-rebased` |
| Requested A base | `verilayer/a-contract-integration` |
| Base commit | `d8041d022edec9a19a20654cf50c0c26baa5468b` |
| Workflow root | `vibe coding/` (repository-relative) |
| Local environment rule | `vibe coding/.venv/`, Git ignored |
| Scope | Environment evidence only; no business-code change |

## Requirements hash reconciliation — A decision required

Windows checkout conversion can change line endings in a working file. Therefore
the two byte-level observations below are both retained. They may differ because
the working file can use CRLF while the Git blob uses LF; neither observation is
silently replaced or declared stale by D.

| Observation | SHA-256 |
|---|---|
| Windows working-file raw bytes: `vibe coding/requirements-verilayer.txt` | `464c4c0f6b38397fdb33e130fc8d0fbb385a0de607b7192af40c9acf99e76e03` |
| Git blob LF raw bytes: `HEAD:vibe coding/requirements-verilayer.txt` | `f55ab0bdfdba077dce4951ff24396c31dc671f3b88ba22bfa7f05a39311ad472` |

**Required A decision:** identify which byte representation is the formal
installation input. D does not treat the other hash as expired, invalid, or an
installation failure merely because CRLF checkout conversion can produce a
different raw-byte digest.

## Environment identity

```text
python=3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]
pytest=8.3.5
platform=Windows-11-10.0.22631-SP0
```

No absolute path, credential, package-index token, or secret is recorded. The
project-local `.venv` is not committed.

## `pip freeze --all`

Raw `pip freeze --all` text SHA-256:

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

## Root 27-test baseline — raw command and log

The following was run from `vibe coding/` using the project-local frozen
environment:

```text
.\.venv\Scripts\python.exe -m pytest -q tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py
```

Exit code: `0`

Raw stdout:

```text
...........................                                              [100%]
27 passed in 5.25s
```

Raw stderr: empty.

This is a real, limited root baseline only. It must not be expanded into a
full-Gate PASS, strict-execution result, Leaf result, or Coding result.

## Full-Gate acceptance-spec check

Command evaluated from `vibe coding/`:

```text
Test-Path tests\integration
```

Raw result:

```text
False
```

`tests/integration` is absent. D did not create it, substitute another target,
or run hidden tests. Any acceptance command requiring that path cannot be
reported as a complete Gate PASS on this baseline. Required classification:
**ENVIRONMENT/ACCEPTANCE-SPEC ERROR**. This classification does not assert
Architecture FAIL.

## Review boundary

No Coding Executor, workspace, repair structure, root-workflow change, shared
contract/schema change, B/C-core change, hidden-test content, Tutor material,
model call, or C0--C5 data is included in this branch.
