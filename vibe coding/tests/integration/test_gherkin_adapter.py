"""Day-2 Gherkin contract tests, intentionally xfail pending A's frozen profile."""

import pytest


PRD_ENVELOPE = {
    "schema_version": "0.1",
    "run_id": "s1-adapter-contract-001",
    "project_id": "verilayer-contract-fixtures",
    "node_id": "S1-NOTE-CAPTURE",
    "parent_node_id": None,
    "artifact_id": "prd:S1-NOTE-CAPTURE:s1-adapter-contract-001",
    "artifact_type": "prd",
    "status": "PASS",
    "created_at": "2026-07-28T00:00:00Z",
    "generator": "deterministic-test-double",
    "input_artifacts": [],
    "requirement_ids": ["REQ-S1-R1"],
    "content_path": "vibe coding/tests/fixtures/contracts/requirement-model.example.yaml",
}


@pytest.mark.xfail(strict=True, reason="A Testcases profile and hash canonicalization are not frozen")
def test_gherkin_adapter_preserves_identity_and_emits_traceable_testcases():
    from vibecode.adapters.gherkin_adapter import run_gherkin_adapter

    result = run_gherkin_adapter(PRD_ENVELOPE, executor="deterministic-test-double")
    assert result["run_id"] == PRD_ENVELOPE["run_id"]
    assert result["project_id"] == PRD_ENVELOPE["project_id"]
    assert result["node_id"] == PRD_ENVELOPE["node_id"]
    assert "child_node_id" not in result
    assert result["output_artifacts"]


@pytest.mark.xfail(strict=True, reason="A Testcases profile and hash canonicalization are not frozen")
def test_gherkin_adapter_returns_formal_dependency_missing_error():
    from vibecode.adapters.gherkin_adapter import run_gherkin_adapter

    result = run_gherkin_adapter(PRD_ENVELOPE, executor="missing-dependency")
    assert result["status"] == "ERROR"
    assert result["error"]["category"] == "DEPENDENCY_MISSING"
    assert result["requirement_ids"] == ["REQ-S1-R1"]


@pytest.mark.xfail(strict=True, reason="A Testcases profile and hash canonicalization are not frozen")
def test_gherkin_adapter_records_feature_and_graph_validator_evidence():
    from vibecode.adapters.gherkin_adapter import validate_outputs

    result = validate_outputs(
        "vibe coding/tests/fixtures/contracts/s1.feature",
        "vibe coding/tests/fixtures/contracts/requirement-model.example.yaml",
    )
    assert result["status"] == "PASS"
    assert result["validators"]["validate_feature"]["exit_code"] == 0
    assert result["validators"]["validate_requirement_graph"]["exit_code"] == 0
