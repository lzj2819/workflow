# Day 4 deterministic Architecture repair fixture

## Frozen source boundary

- Source run: `day4-root-actual-20260729-d` (read-only; never resumed or overwritten).
- Frozen Feature source: `../runs/day4-root-actual-20260729-d/nodes/root/gherkin/attempt-1/testcases.feature`.
- This fixture copies that Feature byte-for-byte and repairs only its Architecture counterpart.

## Report-driven changes

1. Use the strict parser's exact `contract_id` / `owner → consumer` table headers.
2. Use bare canonical component IDs in Provider/Consumer positions; explanatory prose remains in the responsibility column, not ownership cells.
3. Put every input and output field in backticks after `输入:` / `输出:` so the parser materializes required and response fields.
4. Remove the three components that the frozen Feature never invokes, and give the remaining `public-api-service` explicit inbound and outbound contracts with `health-client`.

## Acceptance

- The Feature hash matches the frozen source hash.
- Strict planning materializes both contract rows into the public component card.
- The `public-api-service` card has an inbound required-field contract.
- The deterministic replay records the sole strict component as reached and has no orphan or contract-coverage findings.
- This fixture is repair-loop evidence only. It is not a Day 4 production root run, Leaf decision, Coding result, or C0-C5 observation.
