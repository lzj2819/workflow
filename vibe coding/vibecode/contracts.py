"""Canonical structured contract validation, semantic diff, and rendering."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


BREAKING_OUTCOMES = {
    "PARAMETER_ADDED_REQUIRED": "CONTRACT_CHANGE_REQUIRED",
    "PRECONDITION_STRENGTHENED": "CONTRACT_CHANGE_REQUIRED",
    "POSTCONDITION_WEAKENED": "CONTRACT_CHANGE_REQUIRED",
    "PARAMETER_TYPE_CHANGED": "ADAPTER_NEEDED",
    "RETURN_TYPE_CHANGED": "ADAPTER_NEEDED",
    "CONSUMER_MISMATCH": "ADAPTER_NEEDED",
    "OPERATIONAL_CONTRACT_CHANGED": "ADAPTER_NEEDED",
}
DEFAULT_BREAKING_OUTCOME = "LEAF_FIX_REQUIRED"


def compare_contracts(parent: Any, child: Any) -> dict[str, Any]:
    parent_errors = validate_contract(parent, "parent")
    child_errors = validate_contract(child, "child")
    if parent_errors or child_errors:
        return {
            "schema_version": "1.0",
            "status": "ERROR",
            "outcome": "CONTRACT_CHANGE_REQUIRED",
            "parent_contract_id": parent.get("contract_id") if isinstance(parent, dict) else None,
            "child_contract_id": child.get("contract_id") if isinstance(child, dict) else None,
            "parent_hash": _hash(parent),
            "child_hash": _hash(child),
            "breaking_count": 0,
            "compatible_count": 0,
            "differences": [],
            "validation_errors": sorted(parent_errors + child_errors),
        }
    parent = canonical_contract(parent)
    child = canonical_contract(child)
    differences: list[dict[str, Any]] = []
    if parent["version"] != child["version"]:
        _add(
            differences,
            "CONTRACT_VERSION_CHANGED",
            "*",
            "version",
            parent["version"],
            child["version"],
            breaking=False,
        )
    parent_interfaces = {item["interface_id"]: item for item in parent["interfaces"]}
    child_interfaces = {item["interface_id"]: item for item in child["interfaces"]}
    for interface_id in sorted(parent_interfaces.keys() - child_interfaces.keys()):
        _add(differences, "INTERFACE_REMOVED", interface_id, "interface", parent_interfaces[interface_id], None)
    for interface_id in sorted(child_interfaces.keys() - parent_interfaces.keys()):
        _add(
            differences,
            "INTERFACE_ADDED",
            interface_id,
            "interface",
            None,
            child_interfaces[interface_id],
            breaking=False,
        )
    for interface_id in sorted(parent_interfaces.keys() & child_interfaces.keys()):
        _compare_interface(
            parent_interfaces[interface_id], child_interfaces[interface_id], differences
        )
    differences.sort(
        key=lambda item: (
            item["interface_id"],
            item["type"],
            item["path"],
            json.dumps(item.get("parent"), sort_keys=True),
            json.dumps(item.get("child"), sort_keys=True),
        )
    )
    breaking = [item for item in differences if item["breaking"]]
    compatible = [item for item in differences if not item["breaking"]]
    if not differences:
        outcome = "MATCH"
    elif not breaking:
        outcome = "ADDITIVE_ONLY"
    else:
        outcomes = {
            BREAKING_OUTCOMES.get(item["type"], DEFAULT_BREAKING_OUTCOME)
            for item in breaking
        }
        outcome = next(
            value
            for value in (
                "CONTRACT_CHANGE_REQUIRED",
                "LEAF_FIX_REQUIRED",
                "ADAPTER_NEEDED",
            )
            if value in outcomes
        )
    return {
        "schema_version": "1.0",
        "status": "PASS" if not breaking else "FAIL",
        "outcome": outcome,
        "parent_contract_id": parent["contract_id"],
        "child_contract_id": child["contract_id"],
        "parent_hash": _hash(parent),
        "child_hash": _hash(child),
        "breaking_count": len(breaking),
        "compatible_count": len(compatible),
        "differences": differences,
        "validation_errors": [],
    }


def validate_contract(value: Any, label: str = "contract") -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{label}: contract must be an object"]
    for field in ("schema_version", "contract_id", "version"):
        if not isinstance(value.get(field), str) or not value[field]:
            errors.append(f"{label}.{field}: non-empty string required")
    interfaces = value.get("interfaces")
    if not isinstance(interfaces, list):
        return errors + [f"{label}.interfaces: array required"]
    ids: set[str] = set()
    for index, interface in enumerate(interfaces):
        path = f"{label}.interfaces[{index}]"
        if not isinstance(interface, dict):
            errors.append(f"{path}: object required")
            continue
        interface_id = interface.get("interface_id")
        if not isinstance(interface_id, str) or not interface_id:
            errors.append(f"{path}.interface_id: non-empty string required")
        elif interface_id in ids:
            errors.append(f"{path}.interface_id: duplicate {interface_id}")
        else:
            ids.add(interface_id)
        provider = interface.get("provider")
        if provider is not None and (not isinstance(provider, str) or not provider):
            errors.append(f"{path}.provider: string or null required")
        consumers = interface.get("consumers")
        if not _string_list(consumers, unique=True):
            errors.append(f"{path}.consumers: unique string array required")
        request = interface.get("request")
        response = interface.get("response")
        if not isinstance(request, dict):
            errors.append(f"{path}.request: object required")
            continue
        if not isinstance(response, dict):
            errors.append(f"{path}.response: object required")
            continue
        parameters = request.get("parameters")
        if not isinstance(parameters, list):
            errors.append(f"{path}.request.parameters: array required")
        else:
            names = set()
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    errors.append(f"{path}.request.parameters: objects required")
                    continue
                name = parameter.get("name")
                if not isinstance(name, str) or not name or name in names:
                    errors.append(f"{path}.request.parameters: unique names required")
                else:
                    names.add(name)
                if not isinstance(parameter.get("type"), str) or not parameter["type"]:
                    errors.append(f"{path}.request.parameters[{name!r}].type: required")
                if not isinstance(parameter.get("required"), bool):
                    errors.append(f"{path}.request.parameters[{name!r}].required: boolean required")
        if not isinstance(response.get("type"), str) or not response["type"]:
            errors.append(f"{path}.response.type: non-empty string required")
        for schema_path, schema in (
            (f"{path}.request.data_schema", request.get("data_schema")),
            (f"{path}.response.data_schema", response.get("data_schema")),
        ):
            if not isinstance(schema, dict):
                errors.append(f"{schema_path}: object required")
        error_items = interface.get("errors")
        if not isinstance(error_items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("code"), str) or not item["code"]
            for item in (error_items or [])
        ):
            errors.append(f"{path}.errors: array of coded objects required")
        for field in ("preconditions", "postconditions", "side_effects"):
            if not _string_list(interface.get(field), unique=True):
                errors.append(f"{path}.{field}: unique string array required")
        if not isinstance(interface.get("timeout_ms"), int) or isinstance(interface.get("timeout_ms"), bool) or interface["timeout_ms"] < 0:
            errors.append(f"{path}.timeout_ms: non-negative integer required")
        if not isinstance(interface.get("retry_policy"), dict):
            errors.append(f"{path}.retry_policy: object required")
        if not isinstance(interface.get("idempotency"), str) or not interface["idempotency"]:
            errors.append(f"{path}.idempotency: non-empty string required")
    return errors


def canonical_contract(value: dict[str, Any]) -> dict[str, Any]:
    contract = json.loads(json.dumps(value))
    for interface in contract["interfaces"]:
        interface["consumers"] = sorted(interface["consumers"])
        interface["preconditions"] = sorted(interface["preconditions"])
        interface["postconditions"] = sorted(interface["postconditions"])
        interface["side_effects"] = sorted(interface["side_effects"])
        interface["errors"] = sorted(
            interface["errors"], key=lambda item: (item["code"], json.dumps(item, sort_keys=True))
        )
        interface["request"]["parameters"] = sorted(
            interface["request"]["parameters"], key=lambda item: item["name"]
        )
    contract["interfaces"] = sorted(
        contract["interfaces"], key=lambda item: item["interface_id"]
    )
    return contract


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Semantic Contract Diff",
        "",
        f"- status: `{result['status']}`",
        f"- outcome: `{result['outcome']}`",
        f"- parent_contract_id: `{result.get('parent_contract_id')}`",
        f"- child_contract_id: `{result.get('child_contract_id')}`",
        f"- breaking_count: {result['breaking_count']}",
        f"- compatible_count: {result['compatible_count']}",
        "",
    ]
    if result.get("validation_errors"):
        lines.extend(["## Validation Errors", ""])
        lines.extend(f"- {error}" for error in result["validation_errors"])
        lines.append("")
    lines.extend(["## Differences", ""])
    if not result["differences"]:
        lines.append("- None")
    else:
        for item in result["differences"]:
            kind = "BREAKING" if item["breaking"] else "COMPATIBLE"
            lines.append(
                f"- **{item['type']}** [{kind}] `{item['interface_id']}` `{item['path']}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def write_reports(result: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    _atomic_write(json_path, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    _atomic_write(markdown_path, render_markdown(result))


def _compare_interface(parent: dict[str, Any], child: dict[str, Any], differences: list[dict[str, Any]]) -> None:
    interface_id = parent["interface_id"]
    if parent["provider"] and not child["provider"]:
        _add(differences, "PROVIDER_MISSING", interface_id, "provider", parent["provider"], child["provider"])
    elif parent["provider"] != child["provider"]:
        _add(differences, "PROVIDER_MISMATCH", interface_id, "provider", parent["provider"], child["provider"])
    missing_consumers = sorted(set(parent["consumers"]) - set(child["consumers"]))
    if missing_consumers:
        _add(differences, "CONSUMER_MISMATCH", interface_id, "consumers", missing_consumers, child["consumers"])
    extra_consumers = sorted(set(child["consumers"]) - set(parent["consumers"]))
    if extra_consumers:
        _add(differences, "CONSUMER_ADDED", interface_id, "consumers", None, extra_consumers, breaking=False)
    parent_params = {item["name"]: item for item in parent["request"]["parameters"]}
    child_params = {item["name"]: item for item in child["request"]["parameters"]}
    for name in sorted(parent_params.keys() - child_params.keys()):
        _add(differences, "PARAMETER_REMOVED", interface_id, f"request.parameters.{name}", parent_params[name], None)
    for name in sorted(child_params.keys() - parent_params.keys()):
        kind = "PARAMETER_ADDED_REQUIRED" if child_params[name]["required"] else "PARAMETER_ADDED_OPTIONAL"
        _add(
            differences,
            kind,
            interface_id,
            f"request.parameters.{name}",
            None,
            child_params[name],
            breaking=child_params[name]["required"],
        )
    for name in sorted(parent_params.keys() & child_params.keys()):
        expected, actual = parent_params[name], child_params[name]
        if expected["type"] != actual["type"]:
            _add(differences, "PARAMETER_TYPE_CHANGED", interface_id, f"request.parameters.{name}.type", expected["type"], actual["type"])
        if not expected["required"] and actual["required"]:
            _add(differences, "PARAMETER_REQUIREDNESS_STRENGTHENED", interface_id, f"request.parameters.{name}.required", False, True)
    if parent["response"]["type"] != child["response"]["type"]:
        _add(differences, "RETURN_TYPE_CHANGED", interface_id, "response.type", parent["response"]["type"], child["response"]["type"])
    if parent["errors"] != child["errors"]:
        _add(differences, "ERROR_CONTRACT_CHANGED", interface_id, "errors", parent["errors"], child["errors"])
    for path, expected, actual in (
        ("request.data_schema", parent["request"]["data_schema"], child["request"]["data_schema"]),
        ("response.data_schema", parent["response"]["data_schema"], child["response"]["data_schema"]),
    ):
        direction = "request" if path.startswith("request") else "response"
        if not _schema_compatible(expected, actual, direction=direction):
            _add(differences, "DATA_SCHEMA_INCOMPATIBLE", interface_id, path, expected, actual)
        elif expected != actual:
            _add(differences, "DATA_SCHEMA_ADDITIVE", interface_id, path, expected, actual, breaking=False)
    added_preconditions = sorted(set(child["preconditions"]) - set(parent["preconditions"]))
    if added_preconditions:
        _add(differences, "PRECONDITION_STRENGTHENED", interface_id, "preconditions", parent["preconditions"], child["preconditions"])
    missing_postconditions = sorted(set(parent["postconditions"]) - set(child["postconditions"]))
    if missing_postconditions:
        _add(differences, "POSTCONDITION_WEAKENED", interface_id, "postconditions", parent["postconditions"], child["postconditions"])
    for field in ("timeout_ms", "retry_policy", "idempotency", "side_effects"):
        if parent[field] != child[field]:
            _add(differences, "OPERATIONAL_CONTRACT_CHANGED", interface_id, field, parent[field], child[field])


def _schema_compatible(parent: Any, child: Any, *, direction: str) -> bool:
    if not isinstance(parent, dict) or not isinstance(child, dict):
        return parent == child
    if parent.get("type") != child.get("type"):
        return False
    parent_properties = parent.get("properties", {})
    child_properties = child.get("properties", {})
    if not isinstance(parent_properties, dict) or not isinstance(child_properties, dict):
        return parent == child
    parent_required = set(parent.get("required", []))
    child_required = set(child.get("required", []))
    if direction == "request" and not child_required.issubset(parent_required):
        return False
    if direction == "response" and not parent_required.issubset(child_required):
        return False
    for name, expected in parent_properties.items():
        if name not in child_properties or not _schema_compatible(
            expected, child_properties[name], direction=direction
        ):
            return False
    return True


def _add(
    differences: list[dict[str, Any]],
    kind: str,
    interface_id: str,
    path: str,
    parent: Any,
    child: Any,
    *,
    breaking: bool = True,
) -> None:
    differences.append(
        {
            "type": kind,
            "interface_id": interface_id,
            "path": path,
            "breaking": breaking,
            "parent": parent,
            "child": child,
        }
    )


def _string_list(value: Any, *, unique: bool) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value) and (
        not unique or len(value) == len(set(value))
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
