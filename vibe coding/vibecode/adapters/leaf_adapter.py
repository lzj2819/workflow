"""Fail-closed Leaf handoff preparation; this module never runs Leaf-gate."""

from __future__ import annotations

from typing import Any, Callable

from .mocktest_adapter import AdapterInputError, _error, evaluate_mocktest_gate, validate_artifact, validate_identity


HashVerifier = Callable[[dict[str, Any]], bool]


def prepare_leaf_formal_input(
    prd: Any,
    architecture: Any,
    testcases: Any,
    mocktest_report: Any,
    strict_audit: Any,
    *,
    contract_frozen: bool,
    hash_verifier: HashVerifier | None,
) -> dict[str, Any]:
    """Validate four formal artifacts and return eligibility, never a Leaf decision."""

    if not contract_frozen:
        return _error("CONTRACT_NOT_FROZEN", "A must freeze Leaf artifact profiles before a Leaf handoff.")
    try:
        artifacts = [
            validate_artifact(prd, "prd"),
            validate_artifact(architecture, "architecture"),
            validate_artifact(testcases, "testcases"),
            validate_artifact(mocktest_report, "mocktest_report"),
        ]
        identity = validate_identity(artifacts)
    except AdapterInputError as exc:
        return _error("LEAF_INPUT_INCOMPLETE", str(exc))
    gate = evaluate_mocktest_gate(mocktest_report, strict_audit)
    if gate["downstream_gate"] != "ALLOW":
        return gate
    if hash_verifier is None:
        return _error("HASH_RULE_NOT_FROZEN", "A-provided artifact hash verifier is required for Leaf eligibility.")
    invalid = [artifact["artifact_type"] for artifact in artifacts if not hash_verifier(artifact)]
    if invalid:
        return _error("ARTIFACT_HASH_MISMATCH", f"hash verification failed: {', '.join(invalid)}")
    return {
        "status": "READY_FOR_LEAF",
        "downstream_gate": "ALLOW",
        "eligible_for_leaf": True,
        "identity": identity,
        "input_artifacts": [
            {"artifact_type": artifact["artifact_type"], "content_path": artifact["content_path"], "content_sha256": artifact["content_sha256"]}
            for artifact in artifacts
        ],
        "strict_evidence": {
            "strict_audit_status": gate["strict_audit_status"],
            "semantic_mocktest_status": gate["semantic_mocktest_status"],
        },
    }


def adapt_proposed_children(native_children: Any, *, parent_node_id: str) -> dict[str, Any]:
    """Read native `child_node_id` only; emit canonical `node_id` only."""

    if not isinstance(native_children, list):
        return _error("INVALID_CHILDREN", "proposed_children must be an array")
    adapted: list[dict[str, Any]] = []
    for index, child in enumerate(native_children):
        if not isinstance(child, dict):
            return _error("INVALID_CHILDREN", f"proposed_children[{index}] must be an object")
        legacy = child.get("child_node_id")
        explicit = child.get("node_id")
        if not isinstance(legacy, str) or not legacy:
            return _error("CHILD_NODE_ID_REQUIRED", f"proposed_children[{index}].child_node_id is required for native input")
        if explicit is not None and explicit != legacy:
            return _error("ARTIFACT_IDENTITY_MISMATCH", f"proposed_children[{index}] has conflicting node identities")
        normalized = {key: value for key, value in child.items() if key not in {"child_node_id", "node_id", "parent_node_id"}}
        normalized["node_id"] = legacy
        normalized["parent_node_id"] = parent_node_id
        adapted.append(normalized)
    return {"status": "PASS", "proposed_children": adapted}
