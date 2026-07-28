"""Day-2 contract tests, intentionally xfail until A freezes the artifact profile.

These tests use only the independent S1 contract inputs.  They must become
ordinary passing tests before a production Adapter can be called ready.
"""

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


@pytest.mark.xfail(strict=True, reason="A Architecture profile and hash canonicalization are not frozen")
def test_architecture_adapter_preserves_identity_and_rejects_legacy_child_id():
    from vibecode.adapters.architecture_adapter import run_architecture_adapter

    result = run_architecture_adapter(PRD_ENVELOPE, executor="deterministic-test-double")
    assert result["run_id"] == PRD_ENVELOPE["run_id"]
    assert result["project_id"] == PRD_ENVELOPE["project_id"]
    assert result["node_id"] == PRD_ENVELOPE["node_id"]
    assert "child_node_id" not in result


@pytest.mark.xfail(strict=True, reason="A Architecture profile and hash canonicalization are not frozen")
def test_architecture_adapter_fails_closed_on_unknown_status_and_nonrelative_path():
    from vibecode.adapters.architecture_adapter import validate_prd_envelope

    bad = {**PRD_ENVELOPE, "status": "UNKNOWN", "content_path": "C:/private/input.md"}
    result = validate_prd_envelope(bad)
    assert result["status"] == "ERROR"
    assert result["error"]["category"] == "INVALID_ENVELOPE"


@pytest.mark.xfail(strict=True, reason="A Architecture profile and hash canonicalization are not frozen")
def test_architecture_adapter_returns_formal_executor_not_configured_error():
    from vibecode.adapters.architecture_adapter import run_architecture_adapter

    result = run_architecture_adapter(PRD_ENVELOPE, executor=None)
    assert result["status"] == "ERROR"
    assert result["error"]["category"] == "EXECUTOR_NOT_CONFIGURED"
    assert result["requirement_ids"] == ["REQ-S1-R1"]
