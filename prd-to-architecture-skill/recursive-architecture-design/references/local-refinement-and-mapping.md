# Local Refinement and Parent-to-Child Mapping

Use this reference after the parent-boundary snapshot is complete. Refine only inside the selected parent node; do not repeat top-level strategic DDD or system architecture selection.

## Local semantic refinement

Refine local aggregates, entities, value objects, invariants, commands, internal events, policies, lifecycle states, and collaboration only when they belong inside the selected node.

Do not:

- redraw parent bounded contexts or module boundaries;
- transfer parent or sibling state ownership;
- alter parent public contract meaning;
- choose a new parent architecture style, database, message bus, cache platform, deployment unit, or public runtime boundary.

Choose child nodes by responsibility, owned state, invariants, lifecycle, change reason, and interaction. Controller/Service/Repository is not a sufficient decomposition rule.

## C1-C6 mappings

| Mapping | Source | Child-level result | Boundary rule |
|---|---|---|---|
| C1 | Selected parent node | Child elements with stable `child_id` | Child elements remain inside the selected node. |
| C2 | Local aggregate or state | State owner and local consistency boundary | Parent and sibling ownership remains unchanged. |
| C3 | Parent flow and local lifecycle | Internal runtime collaboration | Preserve parent business order and external promises. |
| C4 | Parent contract | Internal realization map and child-only contracts | Parent identifiers, fields, owners, side effects, dependencies, failure semantics, and versioning remain unchanged. |
| C5 | Parent external dependency | Owned Adapter/ACL internals, only when delegated | Do not redesign a dependency owned by another parent node. |
| C6 | Local driver | Internal tactic | Do not introduce a parent-level platform, datastore, message bus, deployable unit, or public boundary. |

## Requirement allocation

Classify every current-level requirement as:

- `inherited`: a fixed parent requirement or decision;
- `allocated`: a parent requirement implemented wholly or partly inside this node;
- `local`: remains fully inside this node;
- `out-of-scope`: belongs to a sibling or needs parent revision.

For `inherited` and `allocated`, cite a parent requirement ID, FR, flow, contract, or decision whenever one exists.

## Runtime and contract rules

Show two or three high-value local flows: success, failure or recovery, and lifecycle behavior. Every child-only contract must use an ID scoped to the current node and define owner, consumer, trigger, schema, side effects, dependencies, errors/timeouts/retries, idempotency, and compatibility behavior when architecturally relevant.

An inherited external contract may be realized by multiple child nodes, but its external meaning cannot be weakened, renamed, moved, or version-bumped locally.
