---
schema_version: "1.0"
artifact_schema_version: prd/v3
run_id: {{run_id}}
project_id: {{project_id}}
node_id: {{node_id}}
parent_node_id: {{parent_node_id}}
artifact_id: {{artifact_id}}
artifact_type: prd
created_at: {{created_at}}
generator: prd-generation
status: {{PASS_or_FAIL}}
input_artifacts: []
requirement_ids: []
prd_status: {{draft_approved_or_complete}}
mode: {{root_or_derive}}
depth: 0
max_depth: 4
node_history: []
doc_type: prd
doc_id: {{doc_id}}
version: {{document_version}}
release_scope_frozen: false
ready_for_test_generation: false
oracle_blocked_count: 0
inheritance_complete: false
review_method: independent_agent
---

# 1. Problem Statement

# 2. Scope and Non-goals

# 3. Current Release — Functional Requirements

# 4. Current Release — Non-functional Requirements

# 5. Architecture Input Contract

# 6. Success Metrics

# 7. Acceptance Contracts

# 8. Oracle Coverage Ledger

# 9. Future Backlog / Documented Exclusions

# 10. Risks, Dependencies, and Blocking Questions

# 11. Traceability Index

# 12. Review Report

<!--
Normative note: this file documents the fixed outline only. The executable
authority is schemas/canonical-prd.schema.json plus
scripts/prd_flow/canonical.py. Never hand-edit a generated Markdown file and
treat it as a change to the machine-authoritative prd.json.
-->
