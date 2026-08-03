# Council Report — PRD-to-Gherkin Refactor

## 1 Selected Panel

- Aristotle (1.0): obligation boundaries and evidence ownership.
- Ada (1.5, pre-locked domain weight): formal transformation and deterministic formatting.
- Feynman (1.0): minimal executable chain and real consumer behavior.

## 2 Chairman

Independent Meadows, not a participant in Rounds 1–3. Decision: conditionally adopt the canonical-testcase core.

After the vote, direct inspection found that Mocktest already uses a different, loose envelope named `testcases/v1`; implementation therefore uses `testcases/v2`. This evidence-based version correction preserves the chairman's authority-chain decision and avoids a same-name/different-shape contract.

## 3 Acceptable Compromises

- Keep one minimal evidence-only `test_obligation` inside each TC; no independent TO truth store.
- Keep ontology/pattern/graph only as future non-authoritative diagnostics outside the bundle.
- Feature tags are consumer-proven `@REQ/@NFR` followed by one `@TC`; AC and source evidence stay in JSON.
- Multiple Given/Then are allowed with fixed `And`; When is exactly one.
- Composition and Outline are disabled in v2. They require a future versioned input contract and real consumer proof.
- Generation bundle excludes Mocktest execution evidence.

## 4 Kill Criteria

- If Mocktest contract-name collision is unresolved by 2026-08-04, invalidated → do not freeze the producer schema name.
- If canonical bytes, Unicode, LF, ordering and hashes are untested by 2026-08-05, invalidated → do not claim deterministic output.
- If `test_obligation` can add facts outside PRD v3 by 2026-08-06, invalidated → remove it or block generation.
- If multi-Given/Then and one When fail the real loader by 2026-08-08, invalidated → reduce the Feature grammar.
- If an incomplete NFR/AC still emits a Scenario by 2026-08-09, invalidated → return `GENERATION_BLOCKED`.
- If identical PRD bytes produce different bundles by 2026-08-10, invalidated → do not replace the old chain.
- If structural validation is reported as strict PASS by 2026-08-10, invalidated → split the state spaces.

All pre-release criteria were exercised on 2026-08-02. Mocktest strict remains an external stage, not a generator criterion.

## 5 Concrete Next Step

Create and freeze `contracts/testcases-v2-and-feature-contract.md` as the one normative transformation contract. (Completed.)

## 6 Unresolved Questions

- Which future PRD version will carry explicit approved table rows for Outline?
- Is there a proven production composition case that cannot be represented as atomic PRD contracts?
- Which NFR categories should later receive executable adapters rather than structural acceptance projections?

## 7 Key Agreements

- PRD v3 is the sole product-fact source; `testcases/v2` is the sole derived testcase authority.
- Feature is a one-way deterministic view.
- Duplicate Group/Clause/FACT/IR/baseline/ontology/coverage graphs leave the authority path.
- Stable IDs, order, Unicode/LF and hashes are contract fields.
- Missing or ambiguous facts block rather than invite completion.
- Structure and Mocktest strict use different status spaces.

## 8 Key Disagreements

- Aristotle wanted to retain obligation reasoning; the accepted form is a minimal, source-only record inside each TC.
- Rich Feature evidence tags were rejected because only REQ/TC tags had consumer evidence.
- Execution logs were excluded from the generation bundle.
- Composition and Outline were not deleted as concepts, but are forbidden in v2 pending evidence.

## 9 Decision Options

1. Canonical testcase core (selected).
2. Feature remains authority (rejected: unstable identity/evidence).
3. Retain all old graphs plus synchronizers (rejected: multiplies truth sources).
4. Direct PRD→Feature with no testcase model (rejected: loses stable TC identity).

## 10 Recommended Next Steps

- Maintain golden/roundtrip/hash/error-boundary tests with every contract change.
- Version any future Outline/composition support instead of silently widening feature/v2.
- Pass the frozen Feature to Mocktest and keep strict results outside this bundle.

## 11 Confidence

High for the authority chain and formatter contract. Strict business validity is intentionally not claimed.

## 12 Execution Reliability

High for current implementation: Node contract tests, independent JSON Schema validation, official Gherkin parsing and the real sibling Mocktest loader all pass. Mocktest strict remains `NOT_RUN` by design.

## Vote Tally

- Aristotle: support-with-condition, 1.0, high, dealbreaker yes.
- Ada: support-with-condition, 1.5, high, dealbreaker no.
- Feynman: support-with-condition, 1.0, high, dealbreaker no.
- Weighted support: 3.5/3.5; threshold: 2.333.

## Minority Report

There was no oppose vote. Preserved dissent: obligation reasoning must not disappear; deterministic rendering must not be confused with deterministic semantic interpretation; AC/SOURCE tags, composition, Outline and complex NFR compatibility require evidence rather than intuition.

## Session Metadata

```yaml
schema_version: 1
mode: full
panel_size: 3
rounds_run: 3
chairman: Meadows
chairman_independent: true
domain_weight_member: Ada
weighted_support: 3.5
consensus_threshold: 2.333
recommendation: canonical-testcase-core
recommendation_status: support-with-condition
implemented_schema: testcases/v2
```
