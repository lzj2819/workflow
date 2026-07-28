# Input Contract

Read this reference before designing anything. This skill refines one selected node from a parent architecture package; it does not redesign the full parent.

## Required inputs

| Field | Meaning | Required behavior |
|---|---|---|
| `parent_architecture` | Root directory of the parent architecture package. | Treat it as read-only. Detect its package shape through `parent-package-adapter.md`. |
| `target_node_id` | Stable ID of the one parent node to refine. | Match it uniquely before decomposition. In `migrate` mode only, permit one evidence-recorded exact display-name match. |
| `current_prd` | PRD for the current node. | Use it only for requirements inside the selected parent boundary. |
| `output_dir` | Destination of the current child package. | Resolve and display it before writing. Do not overwrite an existing package unless mode is `revise`. |

## Optional inputs

| Field | Meaning | Required behavior |
|---|---|---|
| `parent_prd` | Original PRD of the parent node or system. | Read only when parent requirements cannot be traced through the parent package. |
| `mode` | `new`, `revise`, or `migrate`; default is `new`. | `new` creates a new package, `revise` continues an explicitly selected package, and `migrate` enables legacy name matching. |
| `existing_architecture` | Existing current-node package. | Required for `revise`; never overwrite it silently. |
| `ancestor_architectures` | Ordered packages above the direct parent. | Supply only when a direct parent omits ancestor invariants needed for the current design. |
| `current_focus` | Narrower concern inside the current PRD. | Scope the child work without discarding inherited constraints. |
| `human_constraints` | Explicit preferences or constraints. | Apply only when compatible with the parent boundary; otherwise return to the parent. |

## Resolution order

1. Resolve paths against the declared repository root or current working directory.
2. Resolve `mode`, `parent_architecture`, `target_node_id`, `current_prd`, and `output_dir`.
3. Run the Parent Package Adapter before reading parent details.
4. Display the parent package type, target-node match evidence, and resolved output path before writing.
5. Read `parent_prd` only if required traceability is missing.

## Blocking gaps

Stop before child design when:

- the parent package is missing, unreadable, or unsupported;
- `target_node_id` has zero or multiple matches;
- migration name matching lacks one exact user-supplied match;
- binding parent state, contract, deployment, or decision information is unavailable;
- the current PRD changes a parent-owned boundary;
- output would overwrite a package without `revise`;
- missing information permits materially different child architectures.
