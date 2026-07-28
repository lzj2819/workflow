# C Mocktest → Leaf mapping — Day 1 proposal

Status: proposal for A review. It does not alter the Artifact Contract or either tool.

## Boundary rule

Mocktest and Leaf retain their native formats inside their tools. The C Adapter is the only normalization boundary. All cross-module artifacts use A's canonical `node_id`; `child_node_id` is read only as a legacy Leaf input field and is never emitted in Adapter output.

| Source evidence | Native field / state | Canonical Adapter output | Gate |
|---|---|---|---|
| Mocktest input manifest | `run_id`, `project_id`, `node_id`, `parent_node_id`, source PRD/artifact IDs | same identity, no generated replacement | identity mismatch → `ERROR` |
| Strict trace | component hops and validator results | evidence references and hashes | retained for audit, not silently summarized away |
| Strict audit | `strict_audit.json.status` | `execution.strict_audit_status` and `execution.completeness` | anything other than `PASS` blocks Leaf |
| Mocktest semantic outcome | report `status`, `execution_status`, `validation_status` | `semantic_status` and envelope `status` | only completed semantic `PASS` may enter Leaf |
| Architecture finding | `finding.defect_type`, severity, requirement/scenario/component references | `defects[]` classified by C taxonomy | `FAIL` blocks Leaf and Coding |
| Process failure | `status=ERROR`, artifact errors, import/config/process exit evidence | error artifact with category/code/redacted message | tool error, not architecture FAIL |
| Leaf formal input | `prd.json`, `architecture.json`, `testcases.json`, `mocktest_report.json`/`leaf_gate_evidence.json` | matching canonical identity + content hashes | missing/mismatched/incomplete evidence → Leaf `ERROR` |
| Leaf decision | `STOP_LAYERING`, `CONTINUE_LAYERING`, `ERROR` | same decision/status plus `node_id` identities | `ERROR` blocks; `CONTINUE` returns to Derive; only verified `STOP` reaches Coding |
| Leaf child proposal | native `proposed_children[].child_node_id` | `proposed_children[].node_id`, with `parent_node_id` equal to the decision node | reject duplicate or mismatched child identity |

## Required gate predicate

The Adapter may invoke Leaf only when all predicates hold:

```text
strict_audit_status == PASS
AND execution_status == COMPLETED
AND validation_status == PASS
AND mocktest_report.status == PASS
AND all four formal artifacts have equal schema_version/run_id/project_id/node_id
AND all required hashes verify
```

This deliberately strengthens the native Leaf check (which accepts a passing Mocktest) with strict-completeness evidence. A strict audit `PASS` with semantic `FAIL`, including CMP-CONFIG-STORE, does not meet the predicate.

## `child_node_id` compatibility

1. Read `child_node_id` only from a native Leaf `proposed_children[]` item.
2. Validate it is nonempty and derive `node_id = child_node_id` exactly once.
3. Emit only `node_id` in every Adapter/module-result/cross-module artifact.
4. Set the child `parent_node_id` to the current decision `node_id`.
5. If both names are ever supplied and differ, emit `ERROR` with `ARTIFACT_IDENTITY_MISMATCH`; do not choose one.

## Contract changes proposed to A

These are versioned change requests, not C edits to the shared contract:

- Add `execution.completeness` (`COMPLETE|INCOMPLETE|NOT_RUN`) and `execution.strict_audit_status` (`PASS|FAIL|MISSING`) to the Mocktest artifact profile.
- Add `semantic_status` (`PASS|FAIL|NOT_RUN`) separate from envelope `status`, plus `tool_error` (`category`, `code`, redacted `message`, `exit_code`).
- Define profile-specific `input_artifacts`: Mocktest currently emits artifact records, whereas the A envelope currently specifies string paths. The profile must prescribe either normalized references or a typed object form.
- Make `content_path` and `content_sha256` explicit requirements for Mocktest and Leaf delivery profiles, and define the hash bytes/canonicalization rule.
- Define `proposed_children[].node_id` for the canonical Leaf profile; retain native `child_node_id` solely in the Adapter input compatibility profile.
- Define a downstream gate field such as `downstream_gate: ALLOW|BLOCK|ERROR`, so an audit-complete architecture `FAIL` is mechanically non-routable.
