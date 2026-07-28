# Parent Boundary Rules

The parent architecture is a binding contract. The current level may refine internals inside one selected parent node, but may not redraw parent architecture, deployment, contracts, ownership, or sibling responsibilities.

## Selected-node extraction

Use `parent-package-adapter.md` first. Extract from the selected node and its direct boundaries only:

- stable node identity, responsibility, exclusions, and parent requirement traces;
- owned APIs, events, schemas, owners, side effects, dependencies, failures, and versioning;
- state and data ownership, lifecycle, retention, consistency, readers, and writers;
- direct upstream, downstream, sibling, and external dependencies;
- parent flows in which the node participates;
- accepted ADRs, rejected alternatives, technology constraints, deployment decisions, risks, and explicit delegation.

For an ID-less legacy package, record migration match evidence in the manifest. Do not make legacy name matching the normal path.

## Classification model

| Classification | Meaning | Child behavior |
|---|---|---|
| `inherited-fixed` | Binding parent decision. | Preserve exactly; return to parent if change is required. |
| `inherited-refinable` | External meaning is fixed; internal realization is open. | Preserve external behavior and refine only internals. |
| `delegated` | Parent explicitly assigned this decision to the child. | Decide locally and record it. |
| `unresolved` | Parent neither decided nor delegated it. | Decide only when impact remains inside the selected node; otherwise return to parent. |

## Non-negotiable rules

- Do not treat the selected node as a new independent system unless the parent delegates that status.
- Do not change parent architecture style, runtime identity, deployment mode, database platform, messaging platform, or technology stack locally.
- Do not create a service, container, deployable unit, or public runtime boundary when the parent defines an internal node.
- Do not rename, weaken, move, version-bump, or add required fields to a parent-owned public API or cross-node event.
- Do not transfer public contract or state ownership across parent nodes or siblings.
- Do not redesign sibling internals. Reference them only as collaborators or constraints.
- Decompose by responsibility, state, invariants, lifecycle, change reasons, and interaction; not generic layers alone.

## Return to parent

Write `parent-change-request.md` and stop before authoritative decomposition when the current PRD or human constraint changes parent responsibility, exclusions, public contract semantics, data ownership, dependency direction, ADR, technology, deployment boundary, or ancestor invariant.

If an internal tactic can satisfy the pressure without changing the parent, use that tactic and record the parent-level change as a rejected alternative. A child may improve internal caching, rate limiting, adapter isolation, worker isolation, or runtime replication only when the parent already permits the necessary platform and boundary.

## Recursive chain

Keep the chain visible at every depth:

```text
current child inside selected direct parent node inside ancestor architecture packages
```

If the direct parent conflicts with an ancestor invariant, name it as inherited inconsistency and do not amplify it into a new child decision.
