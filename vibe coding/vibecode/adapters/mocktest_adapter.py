"""Fail-closed, no-execution normalization for the Mocktest strict boundary.

This module never invokes the strict driver and never creates strict evidence.
It prepares an input manifest and classifies evidence supplied by a completed
strict run.  Contract-policy values are deliberately explicit arguments until
A freezes the shared Artifact Contract profiles.
"""

from __future__ import annotations

import re
import uuid
from pathlib import PurePosixPath
from typing import Any, Iterable


IDENTITY_FIELDS = ("run_id", "project_id", "node_id", "parent_node_id")
COMMON_FIELDS = (
    "schema_version",
    *IDENTITY_FIELDS,
    "artifact_id",
    "artifact_type",
    "created_at",
    "generator",
    "status",
    "input_artifacts",
    "requirement_ids",
    "content_path",
    "content_sha256",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SEMANTIC_STATUSES = {"PASS", "FAIL", "NOT_RUN"}


class AdapterInputError(ValueError):
    """Raised only for malformed in-memory handoff data."""


def _error(code: str, message: str, *, semantic_status: str = "NOT_RUN") -> dict[str, Any]:
    return {
        "status": "ERROR",
        "execution_completeness": "INCOMPLETE",
        "strict_audit_status": "MISSING",
        "semantic_mocktest_status": semantic_status,
        "architecture_status": "NOT_RUN" if semantic_status != "FAIL" else "FAIL",
        "tool_error": {"category": "adapter", "code": code, "message": message},
        "downstream_gate": "BLOCK",
    }


def _validate_relative_path(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise AdapterInputError(f"{field}: non-empty repository-relative path required")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise AdapterInputError(f"{field}: repository-relative POSIX path required")


def validate_artifact(artifact: Any, expected_type: str) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise AdapterInputError(f"{expected_type}: artifact object required")
    missing = [field for field in COMMON_FIELDS if field not in artifact]
    if missing:
        raise AdapterInputError(f"{expected_type}: missing fields {', '.join(missing)}")
    if artifact.get("artifact_type") != expected_type:
        raise AdapterInputError(
            f"{expected_type}: artifact_type must be {expected_type!r}, got {artifact.get('artifact_type')!r}"
        )
    for field in ("schema_version", "run_id", "project_id", "node_id", "artifact_id", "created_at"):
        if not isinstance(artifact.get(field), str) or not artifact[field]:
            raise AdapterInputError(f"{expected_type}.{field}: non-empty string required")
    if artifact.get("parent_node_id") is not None and not isinstance(artifact["parent_node_id"], str):
        raise AdapterInputError(f"{expected_type}.parent_node_id: string or null required")
    if not isinstance(artifact.get("requirement_ids"), list) or not artifact["requirement_ids"] or not all(
        isinstance(value, str) and value for value in artifact["requirement_ids"]
    ):
        raise AdapterInputError(f"{expected_type}.requirement_ids: non-empty string array required")
    _validate_relative_path(artifact["content_path"], f"{expected_type}.content_path")
    if not isinstance(artifact.get("content_sha256"), str) or not SHA256.fullmatch(artifact["content_sha256"]):
        raise AdapterInputError(f"{expected_type}.content_sha256: lowercase SHA-256 required")
    return artifact


def validate_identity(artifacts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = list(artifacts)
    if not values:
        raise AdapterInputError("at least one artifact required")
    identity = {field: values[0][field] for field in IDENTITY_FIELDS}
    schema_version = values[0]["schema_version"]
    for artifact in values[1:]:
        for field, expected in identity.items():
            if artifact[field] != expected:
                raise AdapterInputError(f"identity mismatch: {field}")
        if artifact["schema_version"] != schema_version:
            raise AdapterInputError("identity mismatch: schema_version")
    return {"schema_version": schema_version, **identity}


def build_mocktest_formal_input(
    prd: Any,
    architecture: Any,
    testcases: Any,
    *,
    contract_frozen: bool,
) -> dict[str, Any]:
    """Build a no-execution formal Mocktest input from three canonical artifacts."""

    if not contract_frozen:
        return _error("CONTRACT_NOT_FROZEN", "A must freeze Mocktest artifact profiles before strict initialization.")
    try:
        artifacts = [
            validate_artifact(prd, "prd"),
            validate_artifact(architecture, "architecture"),
            validate_artifact(testcases, "testcases"),
        ]
        identity = validate_identity(artifacts)
    except AdapterInputError as exc:
        return _error("INPUT_INCOMPLETE", str(exc))
    return {
        "schema_version": "mocktest-input/v1",
        "status": "PENDING",
        **identity,
        "source_prd": _artifact_ref(artifacts[0]),
        "architecture": _artifact_ref(artifacts[1]),
        "testcases": _artifact_ref(artifacts[2]),
        "requirement_ids": sorted(set().union(*(set(item["requirement_ids"]) for item in artifacts))),
        "input_artifacts": [_artifact_ref(item) for item in artifacts],
        "execution": {"strict_audit_status": "MISSING", "completeness": "NOT_RUN"},
    }


def _artifact_ref(artifact: dict[str, Any]) -> dict[str, str]:
    return {
        "artifact_id": artifact["artifact_id"],
        "artifact_type": artifact["artifact_type"],
        "content_path": artifact["content_path"],
        "content_sha256": artifact["content_sha256"],
    }


def evaluate_mocktest_gate(
    mocktest_report: Any,
    strict_audit: Any,
    *,
    tool_error: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Keep execution completeness, semantic outcome, and tool errors separate."""

    if tool_error:
        return {
            "status": "ERROR",
            "execution_completeness": "INCOMPLETE",
            "strict_audit_status": "MISSING",
            "semantic_mocktest_status": "NOT_RUN",
            "architecture_status": "NOT_RUN",
            "tool_error": tool_error,
            "downstream_gate": "BLOCK",
        }
    semantic = "NOT_RUN"
    if isinstance(mocktest_report, dict):
        candidate = mocktest_report.get("semantic_status", mocktest_report.get("status", "NOT_RUN"))
        if isinstance(candidate, str) and candidate in SEMANTIC_STATUSES:
            semantic = candidate
    audit_status = strict_audit.get("status") if isinstance(strict_audit, dict) else None
    if audit_status != "PASS":
        return {
            "status": "ERROR",
            "execution_completeness": "INCOMPLETE",
            "strict_audit_status": audit_status if isinstance(audit_status, str) else "MISSING",
            "semantic_mocktest_status": semantic,
            "architecture_status": "FAIL" if semantic == "FAIL" else "NOT_RUN",
            "tool_error": {
                "category": "strict_execution",
                "code": "STRICT_AUDIT_INCOMPLETE",
                "message": "strict audit PASS evidence is required before Leaf eligibility.",
            },
            "downstream_gate": "BLOCK",
        }
    if semantic == "FAIL":
        return {
            "status": "FAIL",
            "execution_completeness": "COMPLETE",
            "strict_audit_status": "PASS",
            "semantic_mocktest_status": "FAIL",
            "architecture_status": "FAIL",
            "tool_error": None,
            "downstream_gate": "BLOCK",
        }
    if semantic != "PASS":
        return _error("SEMANTIC_RESULT_MISSING", "a completed strict run requires semantic PASS or FAIL evidence.")
    return {
        "status": "PASS",
        "execution_completeness": "COMPLETE",
        "strict_audit_status": "PASS",
        "semantic_mocktest_status": "PASS",
        "architecture_status": "PASS",
        "tool_error": None,
        "downstream_gate": "ALLOW",
    }


def allocate_strict_run_layout(run_id: str | None = None) -> dict[str, str]:
    """Return unique, non-delivery strict paths without creating a run directory."""

    resolved = run_id or str(uuid.uuid4())
    try:
        uuid.UUID(resolved)
    except (ValueError, AttributeError) as exc:
        raise AdapterInputError("run_id must be a UUID for a new strict run") from exc
    return {
        "run_id": resolved,
        "output_dir": f".work/validate-arch/runs/{resolved}",
        "report_dir": f"reports/mocktest/{resolved}",
        "delivery_rule": "report_dir is formal delivery; output_dir is mutable evidence only",
    }
