"""Fail-closed profiles for direct Architecture consumers and adapters."""

from __future__ import annotations

from typing import Any

from .canonical import validate_canonical_architecture


CONSUMERS = {"canonical", "decompose", "mocktest", "leaf", "vibe_adapter"}


def validate_prd_v3(prd: dict[str, Any]) -> list[str]:
    """Validate only the Architecture-facing portion of canonical PRD v3."""
    errors: list[str] = []
    if prd.get("schema_version") != "1.0":
        errors.append("PRD envelope schema_version must be 1.0")
    if prd.get("artifact_schema_version") != "prd/v3":
        errors.append("Architecture input must use artifact_schema_version prd/v3")
    if prd.get("artifact_type") != "prd":
        errors.append("Architecture input artifact_type must be prd")
    if prd.get("status") != "PASS":
        errors.append("Architecture input PRD must have status PASS")
    if prd.get("prd_status") not in {"approved", "complete"}:
        errors.append("Architecture input PRD must be approved or complete")
    for field in ("run_id", "project_id", "node_id", "artifact_id"):
        if not prd.get(field):
            errors.append(f"Architecture input PRD missing {field}")
    payload = prd.get("payload")
    if not isinstance(payload, dict):
        return [*errors, "Architecture input PRD payload must be an object"]
    problem = payload.get("problem_statement", {})
    scope = payload.get("scope", {})
    requirements = payload.get("requirements", [])
    if not isinstance(problem, dict) or not problem.get("summary"):
        errors.append("Architecture input PRD requires problem_statement.summary")
    if not isinstance(scope, dict) or not scope.get("product"):
        errors.append("Architecture input PRD requires scope.product")
    current = [
        item
        for item in requirements
        if isinstance(item, dict) and item.get("release_scope") == "current"
    ] if isinstance(requirements, list) else []
    if not current:
        errors.append("Architecture input PRD requires at least one current requirement")
    return list(dict.fromkeys(errors))


def validate_consumer_profile(
    model: dict[str, Any],
    consumer: str,
    *,
    parent_architecture: dict[str, Any] | None = None,
) -> list[str]:
    if consumer not in CONSUMERS:
        return [f"unknown Architecture consumer profile: {consumer}"]
    errors = validate_canonical_architecture(
        model,
        require_ready=consumer != "canonical" or model.get("status") == "PASS",
        parent_architecture=parent_architecture,
    )
    if errors or consumer == "canonical":
        return errors

    payload = model["payload"]
    if consumer == "decompose":
        if not model["components"]:
            errors.append("decompose profile requires at least one stable child node")
        if any(not item["requirement_ids"] for item in model["components"]):
            errors.append("decompose profile requires requirement allocation on every child node")
    elif consumer == "mocktest":
        if not model["components"]:
            errors.append("mocktest profile requires components")
        if not model["interfaces"]:
            errors.append("mocktest profile requires interfaces")
        if not payload["runtime_flows"]:
            errors.append("mocktest profile requires at least one runtime flow")
        for contract in [*payload["inherited_contracts"], *payload["contracts"]]:
            for field in (
                "id", "type", "provider_id", "consumer_ids", "protocol", "interaction_style",
                "schema_fields", "side_effects", "dependency_ids", "error_semantics",
                "timeout", "retry", "idempotency", "version", "requirement_ids",
            ):
                if field not in contract:
                    errors.append(f"mocktest contract {contract.get('id')} missing {field}")
    elif consumer == "leaf":
        if model.get("schema_version") != "1.0":
            errors.append("leaf profile requires schema_version 1.0")
        for field in (
            "components", "interfaces", "dependencies", "depth", "complexity", "risks"
        ):
            if field not in model:
                errors.append(f"leaf profile missing {field}")
        projected_components = [
            {
                "id": item["id"],
                "name": item["name"],
                "kind": item["kind"],
                "responsibility": item["responsibility"],
                "requirement_ids": item["requirement_ids"],
            }
            for item in payload["nodes"]
        ]
        if model.get("components") != projected_components:
            errors.append("leaf components projection differs from payload.nodes")
        if model.get("risks") != payload["risks"]:
            errors.append("leaf risks projection differs from payload.risks")
    elif consumer == "vibe_adapter":
        if not model.get("content_sha256"):
            errors.append("vibe adapter requires canonical content_sha256")
        if not model.get("input_artifacts"):
            errors.append("vibe adapter requires hashed input_artifacts")
    return list(dict.fromkeys(errors))
