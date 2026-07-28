# Coding Executor Protocol (Day 1 Proposal)

Status: Day 1 protocol proposal. It specifies the future D-owned executor boundary;
it does not implement, invoke, or claim the existence of a real executor.

## 1. Scope and admission

The executor may accept one leaf only after `execution.admit_coding`-equivalent
admission has verified same-run/project/node identity, a `STOP_LAYERING` decision,
PASS Mocktest, complete Leaf evidence, and a non-blocking interface contract. A
`FAIL`, `ERROR`, prepared-only Mocktest, `CONTINUE_LAYERING`, or incomplete bundle
blocks coding.

Tutor is a read-only engineering oracle. Its source, tests, task packages, expected
behavior, or completion reports are never executor input and do not constitute a
Coding result or a C0--C5 task.

## 2. Input: `CodingRequest` proposal

The Adapter will produce one JSON request. It carries A's canonical envelope and
the following D-proposed profile fields:

| Field | Required | Rule |
|---|---:|---|
| `schema_version`, `run_id`, `project_id`, `node_id`, `parent_node_id`, `task_id` | yes | identity must match the admitted leaf; `parent_node_id` is `null` only for a root leaf |
| `artifact_id`, `artifact_type=code_request`, `created_at`, `generator` | yes | canonical provenance |
| `requirement_ids`, `input_artifacts`, `input_hashes` | yes | repository-relative refs and SHA-256 values only |
| `admission_evidence` | yes | PRD, architecture, testcases, strict Mocktest, Leaf decision, and interface-contract IDs/hashes |
| `workspace` | yes | repository-relative run path, empty at admission, and one leaf identity |
| `allowed_paths` | yes | normalized relative paths writable by this leaf only |
| `public_test_paths` | yes | public-test references only; never private-test paths |
| `technology_profile` | yes | frozen Python/FastAPI/pytest/SQLite profile and scaffold version/hash |
| `executor` | yes | executor ID, code-prompt template hash, model identity/settings version |
| `budget` | yes | task token ceiling, coding/repair ceiling, `pytest_timeout_seconds=120`, `max_repair_rounds=2` |
| `private_acceptance` | yes | opaque contract ID and hash only; no file path, content, test name, failure detail, or answer |

The model context is derived only from the admitted public fields and public
artifacts. It excludes private tests, hidden-test output, Tutor assets, credentials,
model caches, sibling workspaces, parent wiring, and unrelated repository files.

## 3. Workspace isolation

For each `<run_id>/<node_id>`, the executor creates exactly one empty leaf workspace
under the run evidence root. Every candidate write resolves against that workspace
and must remain inside it after normalization. Absolute paths, `..` traversal,
symlinks resolving outside the workspace, writes to a sibling or parent, and writes
outside `allowed_paths` are a `SYSTEM_ERROR` that stops the leaf.

Only the leaf completion package may leave that workspace for A's later integration.
The executor does not edit the root workflow, B/C modules, shared contracts, parent
wiring, or Tutor. Private acceptance runs in a separate private root after public
repair is terminal; no private files or failure details are copied into the workspace
or a repair prompt.

## 4. Attempts, tests, and repair

`attempt=0` is initial generation followed by public pytest. Attempts `1` and `2`
are the only permitted automatic repairs. Each repair can receive the previous
public-test command, exit status, redacted stdout/stderr, public failure summary,
and the prior code manifest; it cannot receive private-acceptance information.

Each public pytest invocation is limited to **120 seconds**. Its command, resolved
working directory, start/end timestamps, duration, exit code, stdout, stderr, and
optional JUnit/JSON summary are immutable evidence. `PASS` requires public pytest
exit `0`; timeout, process failure, evidence loss, or path escape is `ERROR`.
After attempt 2, a remaining public-test failure is terminal `FAIL`. Human edits are
recorded separately and can never turn an automatic `FAIL` into automatic `PASS`.

For every attempt, preserve:

```text
request/input-hashes.json
model-call.json                 # metadata; secret values excluded
raw-model-output.txt
generated-files.json
patch.diff
hashes-before-after.json
tests/command.json
tests/stdout.txt
tests/stderr.txt
tests/result.json
```

## 5. Output profiles proposed to A

### `Code` artifact

Required canonical envelope fields plus:

```text
task_id
attempt_index
workspace_path                 # repository-relative evidence path
allowed_paths
generated_files                # repository-relative path, SHA-256, byte count
changed_paths
patch_path / patch_sha256
before_hashes / after_hashes
requirement_code_map           # requirement_id -> generated path(s)
executor_id / prompt_template_sha256 / model_config_hash
token_usage                    # integer or null, with unavailable_reason when null
model_call_count / duration_ms
```

### `TestResult` artifact

Required canonical envelope fields plus:

```text
task_id
attempt_index
test_scope                     # PUBLIC or PRIVATE_ACCEPTANCE
command                        # structured argv, never a shell string with secrets
working_directory              # repository-relative
timeout_seconds
started_at / ended_at / duration_ms
exit_code
timed_out
stdout_path / stdout_sha256
stderr_path / stderr_sha256
junit_path / junit_sha256      # nullable when no JUnit is produced
summary                        # pass/fail/skip/error counts when available
tested_requirement_ids
code_artifact_id / code_content_sha256
```

Private acceptance emits only this result profile and an opaque contract ID/hash; it
must not emit private source paths, test names, test text, assertions, or detailed
failures into shared evidence or any repair input.

### `Evidence` record

Required canonical envelope fields plus:

```text
evidence_kind                  # request, model_call, file_manifest, patch, test_log, repair, leak_audit
attempt_index
relative_path / sha256 / size_bytes
redaction_status               # PASS, REDACTED, or BLOCKED
producer
retention_policy
related_artifact_ids
```

An evidence validator must reject an absolute shared path, missing hash, overwritten
attempt, secret pattern, or private-test leakage. Unknown status values fail closed.

## 6. Contract proposal to A

This document is not a change to `ARTIFACT_CONTRACT.md`. D proposes that A adopt the
`Code`, `TestResult`, and `Evidence` fields above as additive profiles after:

1. A records a versioned contract review and compatibility outcome;
2. D supplies a synthetic, non-secret sample of each profile;
3. the samples validate against the authoritative envelope and profile schema; and
4. A confirms downstream Adapter and integration impact.

Until then, no D code writes shared-contract fields that are not already approved.

## 7. C0--C5 equality checks

For one task/seed, the configuration validator must require identical executor ID,
prompt template hash, model/settings hash, technology profile hash, task-budget
hash, public-test hash, timeout, and repair limit. Permitted differences are only
the frozen workflow-stage inputs and C2's explicit `ABLATION_NOT_RUN` evidence.
Any mismatch invalidates the run rather than granting a configuration an advantage.
