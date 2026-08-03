---
name: leaf-gate
description: Validate canonical PRD, Architecture, Testcases, and Mocktest v2 evidence, enforce the repair-and-revalidation loop, and deterministically decide whether to decompose or enter coding.
---

# Leaf Gate v2

Leaf Gate is a read-only consumer and routing gate. It never repairs Architecture, rewrites Testcases, manufactures child boundaries, or edits upstream evidence.

## Required inputs

Start from one node directory containing `leaf_gate_input.json` (`leaf-gate-input/v2`). The manifest MUST reference exactly these current artifacts by relative path and file SHA-256:

1. `prd/v3`
2. `architecture/v2`
3. `testcases/v2`
4. `mocktest-report/v2`
5. `mocktest-leaf-evidence/v2`

Use `schemas/leaf-gate-run.schema.json` as the sole v2 contract registry. The PRD, Architecture and Testcases must share `project_id`, `node_id`, `parent_node_id`, and PRD lineage. Mocktest may have its own run ID; its report and evidence must agree with each other and hash the current Architecture and Testcases bytes.

When authoring a manifest, read `references/leaf_gate_input.example.json`. The policy is embedded in that manifest; do not introduce a second config file.

## Mandatory upstream loop

Mocktest does not automatically hand off to Leaf Gate.

- `overall=PASS`, `validation_verdict=PASS`, `audit_state=PASS`, `publication_state=COMPLETE`, and `gate_recommendation=ALLOW`: eligible for Leaf admission.
- `WARNING|FAIL|BLOCKED`: return `next_action.type=RETURN_TO_ARCHITECTURE`; apply the Mocktest findings to Architecture, keep Testcases frozen, revalidate every affected testcase, then publish a new complete Mocktest report.
- execution, audit, publication, or evidence failure: return `RETURN_TO_VALIDATION`; repair validation evidence and rerun Mocktest.

For `repair_history.mode=REPAIRED`, every cycle must prove failed report → changed Architecture → affected testcase set → revalidated testcase superset → final report. The last cycle must end at the current Architecture and current Mocktest report. A first-pass full-suite PASS uses `FIRST_PASS` with an empty cycle list.

## Execution

```powershell
python leaf-gate/scripts/run_leaf_gate.py <node-dir> --output-dir <output-dir>
```

To use a non-default manifest:

```powershell
python leaf-gate/scripts/run_leaf_gate.py <node-dir> --input-manifest <leaf_gate_input.json> --output-dir <output-dir>
```

Exit codes: `0` is a valid layering decision, `2` is an upstream return route, `3` is a missing node directory, `4` is an internal failure, and `5` is a contract/hash/lineage failure.

## Decision rules

Only `admission.state=ADMITTED` may produce a layering decision.

- `CONTINUE_LAYERING`: at least one deterministic or accepted semantic decomposition signal exists, depth allows another level, and Architecture already declares at least two valid direct child nodes. `proposed_children` is a lossless projection of those Architecture nodes.
- `STOP_LAYERING`: no decomposition signal remains. `proposed_children` is empty and the next action is `VIBECODE`.
- Any non-admitted or invalid input has `decision.value=null` and cannot enter coding.

Optional semantic judgement is schema-constrained by five criteria in `references/leaf_gate_rubric.md`. It may add a decomposition signal but can never override admission, hashes, lineage, coverage, depth, or missing explicit Architecture child nodes.

When changing the runner or contract, execute the cases in `references/pressure_scenarios.md` and the standard-library regression suite.

## Fixed output bundle

Every invocation writes exactly these five names and fixed structures:

- `leaf_gate_report.json` — canonical machine result (`leaf-gate-report/v2`)
- `leaf_gate_report.md` — deterministic seven-section view
- `next_action.json` — orchestrator route (`leaf-gate-next-action/v2`)
- `execution_log.json` — deterministic ordered events (`leaf-gate-execution-log/v2`)
- `bundle_manifest.json` — file hashes and bundle hash (`leaf-gate-bundle/v2`)

Never add generated timestamps, free-form production annotations, or alternative decision files. Identical input bytes and policy must produce identical output bytes.

## Human gates

Pause only when policy explicitly requires semantic judgement and none is supplied, a valid judgement cannot be obtained, or a triggered decomposition lacks explicit Architecture child boundaries. Do not guess. Return the structured route and preserve the upstream artifacts.
