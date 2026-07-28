# Local Decision Queue

Use this reference after C1-C6 mapping. The queue handles only choices discovered during child refinement; it is not a substitute for parent architecture decisions.

## Queue record

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|

Use stable IDs such as `LCD-001`.

## Classifications

| Classification | Meaning | Required action |
|---|---|---|
| `decide_now` | A local structural choice is required for a coherent child package. | Compare two or three local alternatives and record the decision in `05-local-decisions.md`. |
| `defer_to_next_level` | The choice can be delegated to a selected child without changing current-level architecture. | Record the exact future target and trigger in `child-handoff.md`. |
| `implementation_detail` | Coding, framework configuration, or local implementation detail. | Exclude it from architecture decisions. |
| `return_to_parent` | The requirement changes parent responsibility, ownership, contract, dependency direction, ADR, technology, deployment, or public boundary. | Write `parent-change-request.md` and stop before authoritative decomposition. |

## Parent-return rules

`return_to_parent` is mandatory when the child needs to change any parent contract identifier, owner, path/topic, required or produced field, side effect, dependency, error semantics, retry semantics, or versioning. It is also mandatory for state transfer across parent nodes, a new independent service/container, or reversal of a parent technology or deployment decision.

`parent-change-request.md` must identify the triggering current requirement, affected parent artifact and source ID, current inherited rule, requested change, compatibility and operational impact, blocked child decisions, and recommended parent-level revision path.

Do not label an unresolved parent-impacting choice as `defer_to_next_level` or an implementation detail.
