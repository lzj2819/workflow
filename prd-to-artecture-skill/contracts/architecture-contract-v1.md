# Canonical Architecture Contract

Status: implemented; verified by the contract tests in `tests/`.

## 1. Authority

`architecture.json` is the only machine authority. `architecture.md`,
`architecture-manifest.yaml`, `validation_report.json`, and `execution_log.json`
are deterministic projections or sidecars. No Markdown file may be parsed back to
silently change the canonical model.

The shared envelope uses `schema_version: "1.0"`. Architecture payload semantics
use `artifact_schema_version: "architecture/v2"`.

## 2. Fixed bundle

Every successful Top-level or Decompose run writes exactly:

```text
architecture.json
architecture.md
architecture-manifest.yaml
validation_report.json
execution_log.json
```

A blocked Decompose run may additionally write `parent-change-request.md`. It
must use `status: FAIL`, `architecture_status: draft`, and
`ready_for_downstream: false`.

The writer stages the whole package in a sibling temporary directory. It moves
the package into the requested destination only after schema, semantic, profile,
hash, and inventory checks pass.

## 3. Architecture modes

`architecture_mode` expresses design authority. It is not a filesystem operation.

| Rule | `top_level` | `decompose` |
|---|---|---|
| Source | One approved canonical PRD v3 | Approved current-node PRD v3, one approved parent Architecture, exact `target_node_id` |
| Owns | System boundary, first-level modules, cross-module contracts, state ownership, technology and deployment | Selected parent node internals, internal nodes/contracts, local realization and local decisions |
| Must preserve | Product scope and PRD requirements | Parent responsibility/exclusions, public contracts, state ownership, technology, deployment, siblings and ancestor invariants |
| Parent binding | Forbidden | Required, exact stable ID only outside migration |
| Parent impact | Not applicable | Create change request and stop; never emit a ready package |
| Child ID kind | `MOD-*` | `CMP-*`, `SUB-*`, or `ADP-*` |

`operation` separately expresses `new`, `revise`, or `migrate` output behavior.

## 4. Stable identity

- `node_id` is inherited from the current PRD and is never generated from a
  display name.
- Top-level nodes use stable `MOD-*` IDs.
- Decompose children use stable `CMP-*`, `SUB-*`, or `ADP-*` IDs.
- Contract, state, flow, decision, deployment, and risk IDs are unique inside
  one artifact and cannot be reused after retirement.
- Renaming a display label never changes its ID.
- Decompose selects exactly one parent `payload.nodes[].id`; zero or multiple
  matches fail closed.

## 5. Parent mutation policy

For Decompose, the producer derives a parent-boundary snapshot from the selected
parent node and all relevant public contracts, state ownership, technology
decisions, deployment units, and accepted decisions. The snapshot is hashed as
`boundary_fingerprint`.

The following mutations are forbidden locally:

- parent responsibility or exclusions;
- public contract ID, provider, consumers, fields, side effects, dependencies,
  failure/retry semantics, idempotency, or version;
- parent/sibling state owner;
- parent technology or deployment choice;
- sibling responsibility or dependency direction.

Any requested mutation creates `change_requests[]` and
`parent-change-request.md`, then stops before a ready handoff.

## 6. State transitions

| Envelope status | Architecture status | Review | Ready | Meaning |
|---|---|---|---|---|
| `PASS` | `approved` or `complete` | `approved` | `true` | May enter direct consumers |
| `FAIL` | `draft` | `pending` or `rejected` | `false` | Blocking decision, question, coverage gap, or parent change |
| `ERROR` | `draft` | any | `false` | Invalid input, schema, environment, or runtime failure |

No heuristic, migration fallback, or reviewer prose may turn `FAIL`/`ERROR` into
`PASS`.

## 7. Fixed Markdown sections

Both modes render the same sections in the same order:

1. Design Context
2. Authority and Boundary
3. Requirement Allocation
4. Decomposition and Node Registry
5. State and Data Ownership
6. Interfaces and Contracts
7. Runtime Flows
8. Technology and Deployment
9. Decisions and Alternatives
10. Risks, Assumptions, and Open Questions
11. Traceability and Child Handoff
12. Review and Human Gate

Empty content uses stable empty markers; sections are never omitted.

## 8. Consumers

- Decompose consumes the canonical parent model directly.
- Mocktest consumes `architecture.md`/the fixed manifest package, or an explicit
  adapter projection. Its existing `architecture/v1` normalization wrapper is
  not this producer's semantic schema.
- Leaf consumes the common envelope projections in `architecture.json`:
  `components`, `interfaces`, `dependencies`, `depth`, `complexity`, and `risks`.
- Gherkin is a parallel PRD consumer, not an Architecture consumer.
- Vibe Coding consumes a separate `module-result.json` adapter containing real
  bundle paths and hashes; it does not add fields to the Architecture payload.

## 9. Determinism

All canonical arrays are sorted by stable ID or an explicit stable key. JSON uses
UTF-8, sorted keys, two-space indentation, and one trailing newline. Markdown is
rendered only from canonical JSON. Semantic hashes exclude execution timestamps;
execution timing belongs in `execution_log.json`.
