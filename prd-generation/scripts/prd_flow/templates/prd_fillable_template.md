# PRD Evidence Worksheet

This is an input worksheet, not an alternative output template. The CLI always
normalizes completed input into `prd.json` (`prd/v3`) and renders the fixed
twelve-section `prd.md` view.

## Product and release boundary

- Product:
- Release:
- Target users:
- Problem and desired outcome:
- Current release boundary:
- In scope:
- Non-goals:
- Dependencies and available data:

## Atomic requirements

```yaml
- id: REQ-001
  type: functional
  text: <one independently verifiable obligation>
  priority: Must Have
  release_scope: current
  scope_reason: null
  requirement_kind: atomic
  source_kind: explicit
  evidence_refs: [<source locator>]
```

Use `NFR-###` for statistical non-functional requirements. Never reuse a
retired requirement ID; preserve removed obligations as documented exclusions.

## Acceptance contracts

```yaml
- id: AC-REQ-001-01
  type: functional
  verifies: [REQ-001]
  release_scope: current
  actor: <actor>
  preconditions: [<observable state>]
  trigger: <business action or event>
  response: [<required behavior>]
  observable_oracles: [<pass/fail observation>]
  boundaries:
    - condition: <boundary>
      response: <required boundary response>
  exceptions:
    - condition: <exception>
      response: <required exception response>
  evidence_refs: [<source locator>]
```

An NFR contract uses `population`, `measurement_start`, `measurement_end`,
`unit`, `threshold`, `exclusions`, `pass_rule`, and `evidence_refs`.

## Architecture-facing facts

Record only explicit system boundaries, external dependencies, data/storage,
runtime/capacity, security/privacy and deployment constraints. Put unresolved
technical choices in `open_decisions`; do not invent a database, queue, cloud,
framework, model host, or topology.

## Human gates

- Product owner freezes the release scope.
- Product owner resolves missing business oracles and NFR measurements.
- Architecture owner approves any split-contract projection in Derive mode.
- An independent reviewer approves the semantic review hash for Root mode.
