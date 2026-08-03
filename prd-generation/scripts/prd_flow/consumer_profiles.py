"""Fail-closed consumer profiles for the three immediate PRD consumers."""
from __future__ import annotations

from typing import Any

from prd_flow.canonical import validate_canonical_prd


CONSUMERS = {"canonical", "architecture", "gherkin", "leaf"}


def validate_consumer_profile(model: dict[str, Any], consumer: str) -> list[str]:
    if consumer not in CONSUMERS:
        return [f"unknown consumer profile: {consumer}"]
    errors = validate_canonical_prd(
        model,
        require_ready=consumer != "canonical" or model.get("status") == "PASS",
    )
    if errors or consumer == "canonical":
        return errors

    payload = model["payload"]
    requirements = payload["requirements"]
    current = [item for item in requirements if item["release_scope"] == "current"]
    if consumer == "architecture":
        if not payload["problem_statement"]["summary"]:
            errors.append("architecture profile requires problem_statement.summary")
        if not payload["scope"]["product"]:
            errors.append("architecture profile requires scope.product")
        if not current:
            errors.append("architecture profile requires at least one current requirement")
    elif consumer == "gherkin":
        for item in current:
            if item["requirement_kind"] != "atomic":
                errors.append(f"gherkin profile requires atomic requirement {item['id']}")
            if not item["evidence_refs"]:
                errors.append(f"gherkin profile requires evidence for {item['id']}")
        forbidden = {"feature", "scenario", "given", "when", "then", "gherkin", "testcase"}
        stack: list[object] = [payload]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                leaked = forbidden.intersection(str(key).casefold() for key in value)
                if leaked:
                    errors.append(f"gherkin profile forbids PRD fields: {sorted(leaked)}")
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
    elif consumer == "leaf":
        if model.get("schema_version") != "1.0":
            errors.append("leaf profile requires envelope schema_version 1.0")
        for field in ("depth", "max_depth", "node_history", "requirements"):
            if field not in model:
                errors.append(f"leaf profile missing {field}")
        if not isinstance(model.get("node_history"), list):
            errors.append("leaf profile node_history must be an array")
        if model.get("requirements") != model.get("requirement_ids"):
            errors.append("leaf profile requirement projection differs from envelope")
    return list(dict.fromkeys(errors))
