# Leaf Gate v2 semantic rubric

Semantic judgement is conditional supporting evidence, never the admission authority. Each criterion must be `PASS` or `FAIL`, include a confidence at or above policy, and cite stable evidence references.

| ID | PASS means | FAIL means |
|---|---|---|
| C1_behavior | The node exposes one cohesive externally observable behaviour cluster. | Multiple independently valuable behaviour clusters remain. |
| C2_boundary | State, contracts, and responsibility have one clear owner boundary. | Ownership must be split to avoid ambiguity or unsafe coupling. |
| C3_context | Implementation fits within one bounded context and vocabulary. | Multiple bounded contexts or conflicting models remain. |
| C4_verifiability | One team can implement and verify the node as one unit. | Independent implementation or verification streams are required. |
| C5_gain | Further decomposition has no meaningful risk, clarity, or delivery gain. | Further decomposition yields material risk, clarity, or delivery gain. |

Any `FAIL` adds `SEMANTIC_DECOMPOSITION_GAIN`. Continuing still requires at least two explicit child nodes in `architecture/v2`; the judge cannot invent them. A judgement never changes Mocktest admission.

The judgement object uses `artifact_schema_version=leaf-gate-judgement/v2` and the `semanticJudgement` definition in `../schemas/leaf-gate-run.schema.json`.

