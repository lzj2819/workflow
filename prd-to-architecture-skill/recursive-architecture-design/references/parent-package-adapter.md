# Parent Package Adapter

Use this reference before reading a parent architecture in detail. Its purpose is to locate one selected parent node and extract only the constraints needed to refine that node.

## Required adapter inputs

| Input | Use |
|---|---|
| `parent_architecture` | Root directory of the parent package. Read-only. |
| `target_node_id` | Stable ID of the parent node to refine. |
| `mode` | `new`, `revise`, or `migrate`. |

## Detect the parent package

1. If `architecture-manifest.yaml` exists at the package root, classify it as a recursive child package.
2. Otherwise, if `output/01-system-overview.md` exists, classify it as a top-level DDD-to-system package.
3. Otherwise, if `mode` is `migrate`, inspect the declared legacy package index and allow only an evidence-recorded exact display-name match.
4. Otherwise stop: the package type is unsupported or unreadable.

Do not infer a package type by scanning unrelated repository directories.

## Locate the selected node

Match `target_node_id` in this order:

1. exact stable ID in the parent manifest, node registry, decomposition, or handoff;
2. only in `migrate` mode, one exact display-name match explicitly supplied by the user.

The migration fallback must record the source file, heading or table row, matched text, and reason a stable ID was unavailable. Stop on zero or multiple matches. Never silently choose the closest name.

## Selective extraction

After matching the node, extract only:

- node identity, responsibility, exclusions, and parent requirement traces;
- owned state, data, retention, lifecycle, readers, writers, and consistency rules;
- contracts where the node is Provider or Consumer, including identifiers, fields, side effects, dependencies, failure semantics, and versioning;
- parent flows in which the node participates;
- direct upstream, downstream, sibling, and external boundaries;
- applicable decisions, rejected alternatives, technology constraints, deployment boundary, and delegated decisions.

Use the parent package as a binding contract. Do not load or redesign sibling internals merely because they are mentioned in a flow or contract.

## Normalized parent-boundary snapshot

Record this in `architecture-manifest.yaml` and summarize it in `01-design-context.md`:

```text
parent_package_type
parent_node_id
target_node_id
node_match_evidence
responsibility_and_exclusions
state_and_data_ownership
provided_and_consumed_contracts
direct_boundaries
relevant_flows
inherited_decisions_and_constraints
delegated_and_unresolved_items
boundary_fingerprint
```

`boundary_fingerprint` is a stable list of parent artifact references and decision/contract IDs used by the child package. It is not a hash requirement.

## Parent PRD fallback

`parent_prd` is optional. Read it only when the selected node's parent requirement, FR, contract, flow, or decision trace cannot be found in the parent package. If the missing trace allows materially different child architectures, stop and request the parent PRD or a parent revision.
