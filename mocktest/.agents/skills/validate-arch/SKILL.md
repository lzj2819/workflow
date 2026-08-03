---
name: validate-arch
description: Strictly validate canonical Architecture v2 against Testcases/Feature v2 and publish a deterministic Mocktest v2 evidence bundle.
---

# Validate Architecture — Mocktest v2

## Purpose

Validate whether the current architecture layer supports the frozen canonical testcases. Preserve
evidence, keep execution completeness separate from architecture verdict, and publish exactly one
versioned result contract.

## Non-negotiable rules

1. Architecture and Testcases/Feature are read-only. Never repair either input during Mocktest.
2. Prefer `architecture/v2` + `testcases/v2`; `feature/v2` is a deterministic testcase view.
3. Never mix one canonical v2 branch with one legacy branch.
4. Never guess a component, contract, event, field, state owner, or next hop.
5. A binding is executable only when its status is `BOUND`. `AMBIGUOUS`, `UNBOUND`, and
   `INVALID` are blocked regardless of confidence.
6. One component subagent performs one hop. One validator subagent judges one testcase.
7. Same-scenario hops are serial. Different scenarios may run in parallel.
8. A validator may judge retained evidence only; it may not invent missing execution.
9. `execution_state`, `validation_verdict`, `audit_state`, and `publication_state` are independent.
10. strict audit PASS is not architecture PASS. Architecture FAIL is not a tool ERROR.
11. All terminal paths, including zero-hop BLOCKED and ERROR, materialize the fixed artifact set.
12. JSON is authoritative. Markdown is a pure view and must never be parsed downstream.

## Authoritative contracts

Read before execution:

- `schemas/mocktest-run.schema.json`
- `schemas/mocktest_input.schema.json`
- `README.md`, sections 1–8

Canonical inputs:

- Architecture: `artifact_schema_version=architecture/v2`, `status=PASS`,
  `ready_for_downstream=true`.
- Testcases: `artifact_schema_version=testcases/v2`, `status=PASS`.
- Identity: `project_id`, `node_id`, and source PRD lineage must agree.
- Architecture semantic `content_sha256` must verify.

Both Architecture modes are valid:

- `architecture_mode=top_level`
- `architecture_mode=decompose`

They use the same importer and result contract. Never branch the output schema by architecture mode.

## Canonical extraction and binding

For each testcase, join evidence only through explicit fields:

1. `testcases[].requirement_ids`
2. `architecture.payload.runtime_flows[].requirement_ids`
3. the matching flow's ordered first step
4. that step's `contract_id`
5. the same ID in `architecture.payload.contracts[]`

Emit every candidate with:

- component ID
- contract ID
- flow ID
- action
- exact JSON field-path provenance

Mapping truth table:

| Candidate count / validity | Binding status | Runner action |
|---|---|---|
| exactly one valid tuple | `BOUND` | execute |
| more than one valid tuple | `AMBIGUOUS` | block |
| zero tuples | `UNBOUND` | block |
| invalid identity/hash/schema | `INVALID` | error/block before runner |

Confidence is diagnostic metadata only. It cannot convert a non-BOUND mapping into BOUND.

## Canonical execution path

### Small serial run

```powershell
python .agents\skills\validate-arch\run_subagent_skill.py run-strict `
  --arch <architecture.json> `
  --feature <testcases.json> `
  --output-dir <unique-run-dir> `
  --slim-prompts --compact-trace
```

### Main-session run

Initialize once:

```powershell
python .agents\skills\validate-arch\main_session_strict_driver.py init `
  --arch <architecture.json> `
  --feature <testcases.json> `
  --output-dir <unique-run-dir>
```

Then repeat exactly:

1. `next-components`
2. spawn one component subagent for each returned pending item
3. write each raw response only to its declared response path
4. `consume-component` for each pending item
5. repeat until no component remains
6. `prepare-validators`
7. `next-validators`
8. spawn one validator subagent per returned testcase
9. `consume-validator`
10. repeat until no validator remains
11. `finalize`

Never resume past a failed semantic or evidence gate. Resume the exact failed hop/testcase only when
its inputs and earlier evidence remain valid. If a shared input, normalized binding, plan, prompt
schema, or component card changed, create a new run or invalidate all dependent work.

## Mandatory workspace artifacts

Every canonical run contains:

1. `run_manifest.json`
2. `normalized_input.json`
3. `extraction_report.json`
4. `execution_plan.json`
5. `scenario_events.json`
6. `contract_check.json`
7. `validator_results.json`
8. `strict_audit.json`
9. `execution_log.json`

Create schema-valid empty arrays/objects before any dispatch. A zero-hop run is diagnosable and may
be BLOCKED; it is never silently absent or complete.

Private migration evidence such as `plan.json`, `hops.json`, `compat.json`, `val_results.json`,
`driver_state.json`, and `subagent_calls.jsonl` may exist temporarily. They are not public contracts.

## Validation and audit gates

Before validator dispatch, fail closed when any of these is true:

- testcase binding is not `BOUND`
- component ID is not in canonical Architecture nodes
- contract ID is absent or does not match the selected runtime-flow step
- required contract/schema evidence is absent
- next hop is not an explicitly legal architecture edge
- state mutation has no explicit state owner
- a Gherkin `When` was dropped, reordered, or merged
- input identity/hash no longer matches the frozen plan

Before publication, strict audit checks:

- every READY testcase has the required component and validator calls
- every call has retained raw and normalized evidence
- every `When` interaction is represented in order
- hop phase, contract binding, component identity and event ordering are valid
- cached evidence comes only from an equivalent audited source
- result counts and coverage reconcile with the execution plan
- no unresolved artifact error remains

## State algebra

Use exactly:

- execution: `NOT_STARTED | BLOCKED | PARTIAL | COMPLETED | ERROR`
- validation: `NOT_EVALUATED | PASS | WARNING | FAIL`
- audit: `NOT_RUN | PASS | FAIL`
- publication: `NOT_STARTED | COMPLETE | ERROR`
- overall: `PASS | WARNING | FAIL | BLOCKED | ERROR`

Derive overall in this order:

1. execution ERROR or audit FAIL → ERROR
2. execution NOT_STARTED/BLOCKED/PARTIAL → BLOCKED
3. validation FAIL → FAIL
4. validation WARNING → WARNING
5. execution COMPLETED + validation PASS + audit PASS → PASS
6. otherwise → BLOCKED

Empty or unevaluated testcase sets cannot PASS.

## Fixed delivery bundle

Publish exactly:

1. `mocktest_report.json`
2. `mocktest_report.md`
3. `leaf_gate_evidence.json`
4. `execution_log.json`
5. `bundle_manifest.json`

Use `scripts/canonicalize_run.py` or the canonical publisher invoked by `finalize`/`run-strict`.

Serialization requirements:

- UTF-8
- LF
- terminal newline
- sorted JSON keys
- stable arrays by stable ID or explicit semantic order
- stable empty arrays/objects
- semantic hashes exclude their own hash field and execution timestamps
- bundle hash covers the four content-file records and their hashes

The Markdown report always has seven sections in this order:

1. Identity
2. State Summary
3. Coverage
4. Findings
5. Extraction Diagnostics
6. Evidence
7. Errors

Do not add audience-specific sections or recompute findings in Markdown.

## Exit codes

- `0`: overall PASS
- `2`: valid FAIL, WARNING, or BLOCKED result
- `3`: input path, dependency, or configuration error
- `4`: execution, evidence, or publication error
- `5`: schema, identity, or downstream-contract error

## Legacy compatibility

Markdown Architecture and `.feature` input use the explicit `legacy-markdown/v1` adapter only.
Legacy parsing may emit candidates/provenance/diagnostics but may not write public status directly.
Aliases must be versioned and exact after normalization; multiple matches remain AMBIGUOUS.

Do not physically delete the legacy driver, StepMapper, GapDetector, or renderer until a shadow
corpus proves field-, state-, and artifact-level equivalence for:

- top-level and decompose Architecture
- multi-When Feature
- BOUND, AMBIGUOUS, UNBOUND
- zero-hop and partial execution
- PASS, WARNING, FAIL, ERROR
- reordered input arrays

Project-specific repair scripts and domain-specific report rules are forbidden.

## Human gate and modification boundary

Mocktest never applies Architecture changes automatically. Report findings and remediation hints,
then stop for human review. If the user authorizes an Architecture repair later, make the smallest
safe change in the Architecture workflow, preserve Feature, and rerun only the affected strict
evidence when dependency analysis proves earlier evidence remains valid.
