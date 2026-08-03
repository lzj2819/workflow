"""Canonical Architecture v2 model, invariants, and deterministic renderer."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Iterable


ENVELOPE_SCHEMA_VERSION = "1.0"
ARTIFACT_SCHEMA_VERSION = "architecture/v2"

SECTION_ORDER = (
    "Design Context",
    "Authority and Boundary",
    "Requirement Allocation",
    "Decomposition and Node Registry",
    "State and Data Ownership",
    "Interfaces and Contracts",
    "Runtime Flows",
    "Technology and Deployment",
    "Decisions and Alternatives",
    "Risks, Assumptions, and Open Questions",
    "Traceability and Child Handoff",
    "Review and Human Gate",
)

TOP_AUTHORITY = {
    "can_define": [
        "cross_node_contracts",
        "deployment",
        "module_boundaries",
        "state_ownership",
        "system_boundary",
        "technology",
    ],
    "must_preserve": ["prd_product_scope", "prd_requirement_semantics"],
    "forbidden": ["implementation_code", "testcases"],
}

DECOMPOSE_AUTHORITY = {
    "can_define": [
        "internal_contracts",
        "internal_nodes",
        "local_decisions",
        "local_state_realization",
    ],
    "must_preserve": [
        "ancestor_invariants",
        "parent_deployment",
        "parent_exclusions",
        "parent_public_contracts",
        "parent_responsibility",
        "parent_state_ownership",
        "parent_technology",
        "sibling_boundaries",
    ],
    "forbidden": [
        "implementation_code",
        "parent_boundary_mutation",
        "sibling_redesign",
        "testcases",
    ],
}

NODE_ID_RE = re.compile(r"^(?:SYS|MOD|CMP|SUB|ADP)-[A-Z0-9][A-Z0-9._-]*$")
CONTRACT_ID_RE = re.compile(r"^(?:API|EVT|QRY|CMD|CBK|FILE|INT)-[A-Z0-9][A-Z0-9._-]*$")


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _nullable_text(value: Any) -> str | None:
    normalized = _text(value)
    return normalized or None


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return sorted({_text(item) for item in values if _text(item)})


def _objects(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _sorted(items: Iterable[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (_text(item.get(key)).casefold(), canonical_json_text(item)))


def canonical_json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_external_systems(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "name": _text(raw.get("name")),
                "responsibility": _text(raw.get("responsibility")),
                "source_refs": _text_list(raw.get("source_refs")),
            }
        )
    return _sorted(result)


def _normalize_nodes(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id") or raw.get("child_id")),
                "name": _text(raw.get("name")),
                "kind": _text(raw.get("kind"), "component").lower(),
                "responsibility": _text(raw.get("responsibility")),
                "exclusions": _text_list(raw.get("exclusions")),
                "requirement_ids": _text_list(
                    raw.get("requirement_ids", raw.get("requirement_refs"))
                ),
                "state_ids": _text_list(raw.get("state_ids", raw.get("owned_state_ids"))),
                "dependency_ids": _text_list(raw.get("dependency_ids", raw.get("dependencies"))),
                "source_refs": _text_list(raw.get("source_refs")),
                "rationale": _text(raw.get("rationale", raw.get("reason"))),
            }
        )
    return _sorted(result)


def _normalize_allocations(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "requirement_id": _text(raw.get("requirement_id") or raw.get("id")),
                "classification": _text(raw.get("classification"), "allocated").lower().replace("-", "_"),
                "owner_node_ids": _text_list(raw.get("owner_node_ids", raw.get("owners"))),
                "source_refs": _text_list(raw.get("source_refs")),
                "reason": _text(raw.get("reason")),
            }
        )
    return _sorted(result, "requirement_id")


def _normalize_state(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "name": _text(raw.get("name")),
                "owner_node_id": _text(raw.get("owner_node_id", raw.get("owner"))),
                "reader_node_ids": _text_list(raw.get("reader_node_ids", raw.get("readers"))),
                "writer_node_ids": _text_list(raw.get("writer_node_ids", raw.get("writers"))),
                "lifecycle": _text(raw.get("lifecycle")),
                "consistency_boundary": _text(raw.get("consistency_boundary")),
                "retention_and_privacy": _text(raw.get("retention_and_privacy")),
                "source_refs": _text_list(raw.get("source_refs")),
            }
        )
    return _sorted(result)


def _normalize_contracts(items: Any, *, inherited: bool = False) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id") or raw.get("contract_id")),
                "type": _text(raw.get("type", raw.get("contract_type")), "internal").lower(),
                "provider_id": _text(raw.get("provider_id", raw.get("provider"))),
                "consumer_ids": _text_list(raw.get("consumer_ids", raw.get("consumers"))),
                "trigger": _text(raw.get("trigger")),
                "protocol": _text(raw.get("protocol")),
                "interaction_style": _text(raw.get("interaction_style", raw.get("sync_async")), "sync").lower(),
                "schema_fields": _text_list(raw.get("schema_fields", raw.get("fields"))),
                "side_effects": _text(raw.get("side_effects"), "None; read-only"),
                "dependency_ids": _text_list(raw.get("dependency_ids", raw.get("dependencies"))),
                "error_semantics": _text(raw.get("error_semantics", raw.get("errors"))),
                "timeout": _text(raw.get("timeout")),
                "retry": _text(raw.get("retry")),
                "idempotency": _text(raw.get("idempotency")),
                "version": _text(raw.get("version"), "1"),
                "requirement_ids": _text_list(raw.get("requirement_ids")),
                "source_refs": _text_list(raw.get("source_refs")),
                # Contracts selected from a parent boundary are inherited even
                # when the parent artifact stores its own copy as non-inherited.
                "inherited": bool(inherited or raw.get("inherited")),
            }
        )
    return _sorted(result)


def _normalize_flows(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        steps = []
        for index, step in enumerate(_objects(raw.get("steps")), start=1):
            steps.append(
                {
                    "order": int(step.get("order", index)),
                    "from_id": _text(step.get("from_id")),
                    "to_id": _text(step.get("to_id")),
                    "contract_id": _nullable_text(step.get("contract_id")),
                    "action": _text(step.get("action")),
                    "failure_behavior": _text(step.get("failure_behavior")),
                }
            )
        result.append(
            {
                "id": _text(raw.get("id")),
                "name": _text(raw.get("name")),
                "kind": _text(raw.get("kind"), "success").lower(),
                "requirement_ids": _text_list(raw.get("requirement_ids")),
                "steps": sorted(steps, key=lambda item: (item["order"], item["from_id"], item["to_id"])),
                "source_refs": _text_list(raw.get("source_refs")),
            }
        )
    return _sorted(result)


def _normalize_technology(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "choice": _text(raw.get("choice")),
                "affected_node_ids": _text_list(raw.get("affected_node_ids")),
                "driver_refs": _text_list(raw.get("driver_refs")),
                "rationale": _text(raw.get("rationale")),
                "status": _text(raw.get("status"), "accepted").lower(),
            }
        )
    return _sorted(result)


def _normalize_deployment(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "name": _text(raw.get("name")),
                "node_ids": _text_list(raw.get("node_ids")),
                "scaling": _text(raw.get("scaling")),
                "isolation": _text(raw.get("isolation")),
                "operations": _text(raw.get("operations")),
                "source_refs": _text_list(raw.get("source_refs")),
            }
        )
    return _sorted(result)


def _normalize_decisions(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "classification": _text(raw.get("classification"), "decide_now").lower(),
                "question": _text(raw.get("question")),
                "decision": _text(raw.get("decision")),
                "alternatives": _text_list(raw.get("alternatives")),
                "consequences": _text_list(raw.get("consequences")),
                "affected_node_ids": _text_list(raw.get("affected_node_ids")),
                "source_refs": _text_list(raw.get("source_refs")),
                "status": _text(raw.get("status"), "decided").lower(),
            }
        )
    return _sorted(result)


def _normalize_risks(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "description": _text(raw.get("description")),
                "severity": _text(raw.get("severity"), "medium").lower(),
                "mitigation": _text(raw.get("mitigation")),
                "status": _text(raw.get("status"), "open").lower(),
                "source_refs": _text_list(raw.get("source_refs")),
            }
        )
    return _sorted(result)


def _normalize_traceability(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "source_id": _text(raw.get("source_id")),
                "target_ids": _text_list(raw.get("target_ids")),
                "relation": _text(raw.get("relation"), "realized_by").lower(),
                "evidence_refs": _text_list(raw.get("evidence_refs")),
            }
        )
    return _sorted(result, "source_id")


def _normalize_realizations(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "contract_id": _text(raw.get("contract_id")),
                "realizing_node_ids": _text_list(raw.get("realizing_node_ids")),
                "notes": _text(raw.get("notes")),
            }
        )
    return _sorted(result, "contract_id")


def _normalize_change_requests(items: Any) -> list[dict[str, Any]]:
    result = []
    for raw in _objects(items):
        result.append(
            {
                "id": _text(raw.get("id")),
                "trigger_requirement_id": _text(raw.get("trigger_requirement_id")),
                "affected_parent_field": _text(raw.get("affected_parent_field")),
                "current_rule": _text(raw.get("current_rule")),
                "proposed_change": _text(raw.get("proposed_change")),
                "impact": _text(raw.get("impact")),
                "blocked_decision_ids": _text_list(raw.get("blocked_decision_ids")),
                "status": "waiting_parent",
            }
        )
    return _sorted(result)


def _current_prd_requirement_ids(prd: dict[str, Any]) -> list[str]:
    payload = prd.get("payload", {}) if isinstance(prd.get("payload"), dict) else {}
    requirements = _objects(payload.get("requirements"))
    current = [
        _text(item.get("id"))
        for item in requirements
        if _text(item.get("release_scope"), "current") == "current" and _text(item.get("id"))
    ]
    return sorted(set(current or _text_list(prd.get("requirement_ids", prd.get("requirements")))))


def _parent_snapshot(parent: dict[str, Any], target_node_id: str) -> dict[str, Any]:
    payload = parent.get("payload", {}) if isinstance(parent.get("payload"), dict) else {}
    matches = [item for item in _objects(payload.get("nodes")) if item.get("id") == target_node_id]
    if len(matches) != 1:
        return {}
    node = copy.deepcopy(matches[0])
    realized_contract_ids = {
        _text(item.get("contract_id"))
        for item in _objects(payload.get("contract_realizations"))
        if target_node_id in item.get("realizing_node_ids", [])
    }
    contracts = [
        copy.deepcopy(item)
        for item in [
            *_objects(payload.get("inherited_contracts")),
            *_objects(payload.get("contracts")),
        ]
        if (
            item.get("provider_id") == target_node_id
            or target_node_id in item.get("consumer_ids", [])
            or item.get("id") in realized_contract_ids
        )
    ]
    states = [
        copy.deepcopy(item)
        for item in _objects(payload.get("state_ownership"))
        if target_node_id
        in {
            item.get("owner_node_id"),
            *item.get("reader_node_ids", []),
            *item.get("writer_node_ids", []),
        }
    ]
    technology = [
        copy.deepcopy(item)
        for item in _objects(payload.get("technology_decisions"))
        if target_node_id in item.get("affected_node_ids", [])
    ]
    deployment = [
        copy.deepcopy(item)
        for item in _objects(payload.get("deployment_units"))
        if target_node_id in item.get("node_ids", [])
    ]
    decisions = [
        copy.deepcopy(item)
        for item in _objects(payload.get("decisions"))
        if target_node_id in item.get("affected_node_ids", [])
    ]
    snapshot = {
        "selected_node": node,
        "contracts": _sorted(contracts),
        "state_ownership": _sorted(states),
        "technology_decisions": _sorted(technology),
        "deployment_units": _sorted(deployment),
        "decisions": _sorted(decisions),
    }
    return snapshot


def _semantic_subject(model: dict[str, Any]) -> dict[str, Any]:
    subject = copy.deepcopy(model)
    subject.pop("created_at", None)
    subject.pop("content_sha256", None)
    payload = subject.get("payload")
    if isinstance(payload, dict):
        payload.pop("review", None)
    return subject


def build_canonical_architecture(
    draft: dict[str, Any],
    prd: dict[str, Any],
    *,
    architecture_mode: str,
    operation: str = "new",
    parent_architecture: dict[str, Any] | None = None,
    target_node_id: str | None = None,
    input_artifacts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize one design draft into the single public Architecture model."""
    mode = architecture_mode.strip().lower().replace("-", "_")
    if mode not in {"top_level", "decompose"}:
        raise ValueError("architecture_mode must be top_level or decompose")
    if operation not in {"new", "revise", "migrate"}:
        raise ValueError("operation must be new, revise, or migrate")

    raw = draft.get("payload", draft)
    if not isinstance(raw, dict):
        raise ValueError("draft payload must be an object")
    declared_mode = _text(draft.get("architecture_mode", raw.get("architecture_mode")))
    if declared_mode and declared_mode.replace("-", "_").lower() != mode:
        raise ValueError(
            f"design draft declares architecture_mode={declared_mode}, but CLI selected {mode}"
        )
    design_schema_version = _text(
        draft.get("design_schema_version", raw.get("design_schema_version"))
    )
    if design_schema_version and design_schema_version != "architecture-design/v1":
        raise ValueError("design_schema_version must be architecture-design/v1")
    requirement_ids = _current_prd_requirement_ids(prd)
    prd_node_id = _text(prd.get("node_id"))
    node_id = prd_node_id if mode == "top_level" else _text(target_node_id or prd_node_id)
    parent_node_id = None
    parent_binding: dict[str, Any] | None = None
    inherited_contracts: list[dict[str, Any]] = []
    if mode == "decompose":
        if not parent_architecture:
            raise ValueError("decompose mode requires parent_architecture")
        if prd_node_id != node_id:
            raise ValueError(
                f"decompose current PRD node_id must equal target_node_id: {prd_node_id} != {node_id}"
            )
        if (
            parent_architecture.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION
            or parent_architecture.get("status") != "PASS"
            or not parent_architecture.get("ready_for_downstream")
        ):
            raise ValueError("decompose parent Architecture must be ready canonical architecture/v2")
        snapshot = _parent_snapshot(parent_architecture, node_id)
        parent_node_id = _text(parent_architecture.get("node_id")) or None
        parent_binding = {
            "parent_artifact_id": _text(parent_architecture.get("artifact_id")),
            "parent_node_id": parent_node_id,
            "target_node_id": node_id,
            "node_match_evidence": {
                "strategy": "exact_stable_id" if operation != "migrate" else "migration_exact_name",
                "source_artifact_id": _text(parent_architecture.get("artifact_id")),
                "matched_id": node_id,
            },
            "boundary_fingerprint": _sha256_json(snapshot) if snapshot else "",
            "immutable_snapshot": snapshot,
        }
        inherited_contracts = _normalize_contracts(snapshot.get("contracts", []), inherited=True)

    design_context_raw = raw.get("design_context", {})
    if not isinstance(design_context_raw, dict):
        design_context_raw = {}
    external_systems = _normalize_external_systems(
        design_context_raw.get("external_systems", raw.get("external_systems"))
    )
    nodes = _normalize_nodes(raw.get("nodes", raw.get("components")))
    state_ownership = _normalize_state(raw.get("state_ownership"))
    contracts = _normalize_contracts(raw.get("contracts"))
    flows = _normalize_flows(raw.get("runtime_flows"))
    technology = _normalize_technology(raw.get("technology_decisions"))
    deployment = _normalize_deployment(raw.get("deployment_units"))
    decisions = _normalize_decisions(raw.get("decisions"))
    risks = _normalize_risks(raw.get("risks"))
    change_requests = _normalize_change_requests(raw.get("change_requests"))
    review_raw = raw.get("review", {}) if isinstance(raw.get("review"), dict) else {}

    requested_status = _text(draft.get("status", raw.get("status")), "PASS").upper()
    architecture_status = _text(
        draft.get("architecture_status", raw.get("architecture_status")), "approved"
    ).lower()
    ready = bool(draft.get("ready_for_downstream", raw.get("ready_for_downstream", True)))
    if change_requests:
        requested_status, architecture_status, ready = "FAIL", "draft", False

    payload = {
        "design_context": {
            "summary": _text(design_context_raw.get("summary")),
            "scope": _text(design_context_raw.get("scope")),
            "goals": _text_list(design_context_raw.get("goals")),
            "non_goals": _text_list(design_context_raw.get("non_goals")),
            "responsibility": _text(design_context_raw.get("responsibility")),
            "exclusions": _text_list(design_context_raw.get("exclusions")),
            "external_systems": external_systems,
        },
        "parent_binding": parent_binding,
        "requirement_allocations": _normalize_allocations(raw.get("requirement_allocations")),
        "nodes": nodes,
        "state_ownership": state_ownership,
        "contracts": contracts,
        "inherited_contracts": inherited_contracts,
        "contract_realizations": _normalize_realizations(raw.get("contract_realizations")),
        "runtime_flows": flows,
        "technology_decisions": technology,
        "deployment_units": deployment,
        "decisions": decisions,
        "risks": risks,
        "assumptions": _text_list(raw.get("assumptions")),
        "open_questions": _text_list(raw.get("open_questions")),
        "traceability": _normalize_traceability(raw.get("traceability")),
        "child_handoff": {
            "recommended_target_ids": _text_list(
                (raw.get("child_handoff") or {}).get("recommended_target_ids")
                if isinstance(raw.get("child_handoff"), dict)
                else []
            ),
            "required_ancestor_context": _text_list(
                (raw.get("child_handoff") or {}).get("required_ancestor_context")
                if isinstance(raw.get("child_handoff"), dict)
                else []
            ),
        },
        "change_requests": change_requests,
        "review": {
            "status": _text(review_raw.get("status"), "approved" if ready else "pending").lower(),
            "reviewer": _text(review_raw.get("reviewer")),
            "evidence_ref": _text(review_raw.get("evidence_ref")),
            "semantic_hash": "",
        },
    }

    dependencies = []
    for node in nodes:
        for target in node["dependency_ids"]:
            dependencies.append(
                {
                    "id": f"DEP-{node['id']}-{target}",
                    "from_id": node["id"],
                    "to_id": target,
                    "source": "node_dependency",
                }
            )
    for contract in [*inherited_contracts, *contracts]:
        for target in contract["dependency_ids"]:
            dependencies.append(
                {
                    "id": f"DEP-{contract['id']}-{target}",
                    "from_id": contract["id"],
                    "to_id": target,
                    "source": "contract_dependency",
                }
            )
    dependencies = _sorted(dependencies)
    components = [
        {
            "id": item["id"],
            "name": item["name"],
            "kind": item["kind"],
            "responsibility": item["responsibility"],
            "requirement_ids": item["requirement_ids"],
        }
        for item in nodes
    ]
    interfaces = [
        {
            "id": item["id"],
            "type": item["type"],
            "provider_id": item["provider_id"],
            "consumer_ids": item["consumer_ids"],
            "inherited": item["inherited"],
        }
        for item in [*inherited_contracts, *contracts]
    ]
    interfaces = _sorted(interfaces)
    modules = [
        {
            "id": item["id"],
            "name": item["name"],
            "granularity": "deployable_module" if item["kind"] == "module" else "component",
            "responsibility": item["responsibility"],
            "exclusions": item["exclusions"],
            "requirement_refs": item["requirement_ids"],
            "dependencies": item["dependency_ids"],
        }
        for item in nodes
    ]
    depth = int(prd.get("depth", 0))
    model = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": _text(prd.get("run_id"), "run-unknown"),
        "project_id": _text(prd.get("project_id"), "project-unknown"),
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "artifact_id": f"ARCH-{node_id}",
        "artifact_type": "architecture",
        "created_at": _text(draft.get("created_at"), _text(prd.get("created_at"))),
        "generator": "prd-to-architecture-skill",
        "status": requested_status,
        "architecture_status": architecture_status,
        "ready_for_downstream": ready,
        "source_prd_id": _text(prd.get("artifact_id"), f"PRD-{prd_node_id}"),
        "input_artifacts": _sorted(input_artifacts or [], "artifact_id"),
        "requirement_ids": requirement_ids,
        "architecture_mode": mode,
        "operation": operation,
        "depth": depth,
        "max_depth": int(prd.get("max_depth", depth)),
        "node_history": list(prd.get("node_history", [])) if isinstance(prd.get("node_history"), list) else [],
        "authority_scope": copy.deepcopy(TOP_AUTHORITY if mode == "top_level" else DECOMPOSE_AUTHORITY),
        "section_order": list(SECTION_ORDER),
        "components": components,
        "interfaces": interfaces,
        "dependencies": dependencies,
        "complexity": len(nodes) + len(interfaces) + len(dependencies) + len(flows) + len(decisions),
        "risks": risks,
        "modules": modules,
        "payload": payload,
        "content_sha256": "",
    }
    semantic_hash = _sha256_json(_semantic_subject(model))
    model["content_sha256"] = semantic_hash
    model["payload"]["review"]["semantic_hash"] = semantic_hash
    return model


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return sorted(duplicate)


def validate_parent_immutability(
    model: dict[str, Any], parent_architecture: dict[str, Any]
) -> list[str]:
    if model.get("architecture_mode") != "decompose":
        return []
    payload = model.get("payload", {})
    binding = payload.get("parent_binding") if isinstance(payload, dict) else None
    if not isinstance(binding, dict):
        return ["decompose mode requires parent_binding"]
    target = _text(binding.get("target_node_id"))
    expected = _parent_snapshot(parent_architecture, target)
    errors = []
    if not expected:
        return [f"target_node_id must match exactly one parent node: {target or '<empty>'}"]
    if binding.get("immutable_snapshot") != expected:
        errors.append("parent immutable_snapshot differs from selected parent boundary")
    expected_fingerprint = _sha256_json(expected)
    if binding.get("boundary_fingerprint") != expected_fingerprint:
        errors.append("parent boundary_fingerprint differs from selected parent boundary")
    expected_contracts = _normalize_contracts(expected.get("contracts", []), inherited=True)
    if payload.get("inherited_contracts") != expected_contracts:
        errors.append("inherited public contracts differ from parent")
    return errors


def validate_canonical_architecture(
    model: dict[str, Any],
    *,
    require_ready: bool = False,
    parent_architecture: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if model.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ENVELOPE_SCHEMA_VERSION}")
    if model.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        errors.append(f"artifact_schema_version must be {ARTIFACT_SCHEMA_VERSION}")
    if model.get("artifact_type") != "architecture":
        errors.append("artifact_type must be architecture")
    if model.get("architecture_mode") not in {"top_level", "decompose"}:
        errors.append("architecture_mode must be top_level or decompose")
    if model.get("operation") not in {"new", "revise", "migrate"}:
        errors.append("operation must be new, revise, or migrate")
    if model.get("status") not in {"PASS", "FAIL", "ERROR"}:
        errors.append("status must be PASS, FAIL, or ERROR")
    if model.get("architecture_status") not in {"draft", "approved", "complete"}:
        errors.append("architecture_status must be draft, approved, or complete")
    if model.get("section_order") != list(SECTION_ORDER):
        errors.append("section_order differs from the canonical 12-section order")
    if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", _text(model.get("node_id"))):
        errors.append("node_id must be a non-empty stable artifact node identifier")
    if int(model.get("depth", -1)) > int(model.get("max_depth", -1)):
        errors.append("depth cannot exceed max_depth")
    payload = model.get("payload")
    if not isinstance(payload, dict):
        return [*errors, "payload must be an object"]

    nodes = _objects(payload.get("nodes"))
    node_ids = [_text(item.get("id")) for item in nodes]
    for duplicate in _duplicates(node_ids):
        errors.append(f"duplicate node id: {duplicate}")
    known_ids = set(node_ids)
    known_ids.add(_text(model.get("node_id")))
    for external in _objects(payload.get("design_context", {}).get("external_systems")):
        known_ids.add(_text(external.get("id")))
    binding = payload.get("parent_binding")
    if isinstance(binding, dict) and isinstance(binding.get("immutable_snapshot"), dict):
        snapshot = binding["immutable_snapshot"]
        for contract in _objects(snapshot.get("contracts")):
            known_ids.add(_text(contract.get("provider_id")))
            known_ids.update(_text_list(contract.get("consumer_ids")))
        for state in _objects(snapshot.get("state_ownership")):
            known_ids.add(_text(state.get("owner_node_id")))
            known_ids.update(_text_list(state.get("reader_node_ids")))
            known_ids.update(_text_list(state.get("writer_node_ids")))
    for node in nodes:
        if not NODE_ID_RE.fullmatch(_text(node.get("id"))):
            errors.append(f"invalid node id: {_text(node.get('id')) or '<empty>'}")
        if not _text(node.get("responsibility")):
            errors.append(f"node {_text(node.get('id'))} requires responsibility")
        for dependency in node.get("dependency_ids", []):
            if dependency not in known_ids:
                errors.append(f"node {_text(node.get('id'))} has unknown dependency {dependency}")

    mode = model.get("architecture_mode")
    if mode == "top_level":
        if model.get("depth") != 0:
            errors.append("top_level depth must be 0")
        if model.get("parent_node_id") is not None:
            errors.append("top_level parent_node_id must be null")
        if payload.get("parent_binding") is not None:
            errors.append("top_level parent_binding must be null")
        if payload.get("inherited_contracts"):
            errors.append("top_level inherited_contracts must be empty")
        if payload.get("change_requests"):
            errors.append("top_level change_requests are forbidden")
        for node in nodes:
            if node.get("kind") != "module" or not _text(node.get("id")).startswith("MOD-"):
                errors.append(f"top_level child {_text(node.get('id'))} must be a MOD-* module")
        if model.get("authority_scope") != TOP_AUTHORITY:
            errors.append("top_level authority_scope differs from contract")
    elif mode == "decompose":
        if not model.get("parent_node_id"):
            errors.append("decompose parent_node_id is required")
        if not isinstance(payload.get("parent_binding"), dict):
            errors.append("decompose parent_binding is required")
        for node in nodes:
            if _text(node.get("id")).startswith("MOD-") or node.get("kind") == "module":
                errors.append(f"decompose child {_text(node.get('id'))} cannot redefine a top-level module")
        if model.get("authority_scope") != DECOMPOSE_AUTHORITY:
            errors.append("decompose authority_scope differs from contract")
        if parent_architecture is not None:
            errors.extend(validate_parent_immutability(model, parent_architecture))
            expected_depth = int(parent_architecture.get("depth", -1)) + 1
            if model.get("depth") != expected_depth:
                errors.append(
                    f"decompose depth must equal parent depth + 1 ({expected_depth})"
                )

    requirement_ids = set(_text_list(model.get("requirement_ids")))
    allocations = _objects(payload.get("requirement_allocations"))
    allocation_ids = [_text(item.get("requirement_id")) for item in allocations]
    for duplicate in _duplicates(allocation_ids):
        errors.append(f"duplicate requirement allocation: {duplicate}")
    unknown_allocations = sorted(set(allocation_ids) - requirement_ids)
    if unknown_allocations:
        errors.append(f"unknown requirement allocations: {unknown_allocations}")
    missing_allocations = sorted(requirement_ids - set(allocation_ids))
    if missing_allocations:
        errors.append(f"requirements without allocation: {missing_allocations}")
    allowed_allocations = {"allocated", "local", "out_of_scope"}
    if mode == "decompose":
        allowed_allocations.add("inherited")
    for allocation in allocations:
        if allocation.get("classification") not in allowed_allocations:
            errors.append(
                f"invalid allocation classification for {allocation.get('requirement_id')}: "
                f"{allocation.get('classification')}"
            )
        for owner in allocation.get("owner_node_ids", []):
            if owner not in known_ids:
                errors.append(f"allocation {allocation.get('requirement_id')} has unknown owner {owner}")
        if allocation.get("classification") != "out_of_scope" and not allocation.get("owner_node_ids"):
            errors.append(f"allocation {allocation.get('requirement_id')} requires an owner")
        if allocation.get("classification") == "out_of_scope" and not allocation.get("reason"):
            errors.append(f"out_of_scope allocation {allocation.get('requirement_id')} requires reason")

    contracts = [*_objects(payload.get("inherited_contracts")), *_objects(payload.get("contracts"))]
    contract_ids = [_text(item.get("id")) for item in contracts]
    for duplicate in _duplicates(contract_ids):
        errors.append(f"duplicate contract id: {duplicate}")
    for contract in contracts:
        contract_id = _text(contract.get("id"))
        if not CONTRACT_ID_RE.fullmatch(contract_id):
            errors.append(f"invalid contract id: {contract_id or '<empty>'}")
        if contract.get("provider_id") not in known_ids:
            errors.append(f"contract {contract_id} has unknown provider {contract.get('provider_id')}")
        for consumer in contract.get("consumer_ids", []):
            if consumer not in known_ids:
                errors.append(f"contract {contract_id} has unknown consumer {consumer}")
        unknown_requirements = sorted(set(contract.get("requirement_ids", [])) - requirement_ids)
        if unknown_requirements and not contract.get("inherited"):
            errors.append(f"contract {contract_id} has unknown requirements {unknown_requirements}")

    state_ids = [_text(item.get("id")) for item in _objects(payload.get("state_ownership"))]
    for duplicate in _duplicates(state_ids):
        errors.append(f"duplicate state id: {duplicate}")
    for state in _objects(payload.get("state_ownership")):
        for role in [state.get("owner_node_id"), *state.get("reader_node_ids", []), *state.get("writer_node_ids", [])]:
            if role and role not in known_ids:
                errors.append(f"state {state.get('id')} references unknown node {role}")
    for node in nodes:
        unknown_requirements = sorted(set(node.get("requirement_ids", [])) - requirement_ids)
        if unknown_requirements:
            errors.append(f"node {node.get('id')} has unknown requirements {unknown_requirements}")
        unknown_states = sorted(set(node.get("state_ids", [])) - set(state_ids))
        if unknown_states:
            errors.append(f"node {node.get('id')} has unknown states {unknown_states}")

    contract_id_set = set(contract_ids)
    dependency_targets = known_ids | contract_id_set
    for contract in contracts:
        for dependency_id in contract.get("dependency_ids", []):
            if dependency_id not in dependency_targets:
                errors.append(
                    f"contract {contract.get('id')} has unknown dependency {dependency_id}"
                )
    for realization in _objects(payload.get("contract_realizations")):
        contract_id = _text(realization.get("contract_id"))
        if contract_id not in contract_id_set:
            errors.append(f"contract realization references unknown contract {contract_id}")
        for node_id in realization.get("realizing_node_ids", []):
            if node_id not in known_ids:
                errors.append(
                    f"contract realization {contract_id} references unknown node {node_id}"
                )
    for flow in _objects(payload.get("runtime_flows")):
        for step in _objects(flow.get("steps")):
            if step.get("from_id") not in known_ids or step.get("to_id") not in known_ids:
                errors.append(f"flow {flow.get('id')} has unknown endpoint")
            if step.get("contract_id") and step.get("contract_id") not in contract_id_set:
                errors.append(f"flow {flow.get('id')} has unknown contract {step.get('contract_id')}")

    for technology in _objects(payload.get("technology_decisions")):
        for node_id in technology.get("affected_node_ids", []):
            if node_id not in known_ids:
                errors.append(f"technology {technology.get('id')} references unknown node {node_id}")
    for deployment in _objects(payload.get("deployment_units")):
        for node_id in deployment.get("node_ids", []):
            if node_id not in known_ids:
                errors.append(f"deployment {deployment.get('id')} references unknown node {node_id}")
    for decision in _objects(payload.get("decisions")):
        for node_id in decision.get("affected_node_ids", []):
            if node_id not in known_ids:
                errors.append(f"decision {decision.get('id')} references unknown node {node_id}")
    for target_id in payload.get("child_handoff", {}).get("recommended_target_ids", []):
        if target_id not in set(node_ids):
            errors.append(f"child handoff references unknown child node {target_id}")

    expected_components = [
        {
            "id": item["id"],
            "name": item["name"],
            "kind": item["kind"],
            "responsibility": item["responsibility"],
            "requirement_ids": item["requirement_ids"],
        }
        for item in nodes
    ]
    expected_interfaces = _sorted(
        [
            {
                "id": item["id"],
                "type": item["type"],
                "provider_id": item["provider_id"],
                "consumer_ids": item["consumer_ids"],
                "inherited": item["inherited"],
            }
            for item in contracts
        ]
    )
    expected_modules = [
        {
            "id": item["id"],
            "name": item["name"],
            "granularity": "deployable_module" if item["kind"] == "module" else "component",
            "responsibility": item["responsibility"],
            "exclusions": item["exclusions"],
            "requirement_refs": item["requirement_ids"],
            "dependencies": item["dependency_ids"],
        }
        for item in nodes
    ]
    if model.get("components") != expected_components:
        errors.append("components projection differs from payload.nodes")
    if model.get("interfaces") != expected_interfaces:
        errors.append("interfaces projection differs from payload contracts")
    if model.get("modules") != expected_modules:
        errors.append("modules projection differs from payload.nodes")
    if model.get("risks") != payload.get("risks"):
        errors.append("risks projection differs from payload.risks")

    expected_dependencies = []
    for node in nodes:
        for target in node.get("dependency_ids", []):
            expected_dependencies.append(
                {
                    "id": f"DEP-{node['id']}-{target}",
                    "from_id": node["id"],
                    "to_id": target,
                    "source": "node_dependency",
                }
            )
    for contract in contracts:
        for target in contract.get("dependency_ids", []):
            expected_dependencies.append(
                {
                    "id": f"DEP-{contract['id']}-{target}",
                    "from_id": contract["id"],
                    "to_id": target,
                    "source": "contract_dependency",
                }
            )
    if model.get("dependencies") != _sorted(expected_dependencies):
        errors.append("dependencies projection differs from payload dependencies")
    expected_complexity = (
        len(nodes)
        + len(expected_interfaces)
        + len(expected_dependencies)
        + len(_objects(payload.get("runtime_flows")))
        + len(_objects(payload.get("decisions")))
    )
    if model.get("complexity") != expected_complexity:
        errors.append("complexity projection differs from canonical elements")

    trace_ids = (
        known_ids
        | requirement_ids
        | contract_id_set
        | set(state_ids)
        | {_text(item.get("id")) for item in _objects(payload.get("runtime_flows"))}
        | {_text(item.get("id")) for item in _objects(payload.get("technology_decisions"))}
        | {_text(item.get("id")) for item in _objects(payload.get("deployment_units"))}
        | {_text(item.get("id")) for item in _objects(payload.get("decisions"))}
        | {_text(item.get("id")) for item in _objects(payload.get("risks"))}
    )
    for trace in _objects(payload.get("traceability")):
        if trace.get("source_id") not in trace_ids:
            errors.append(f"traceability has unknown source {trace.get('source_id')}")
        for target_id in trace.get("target_ids", []):
            if target_id not in trace_ids:
                errors.append(f"traceability has unknown target {target_id}")

    change_requests = _objects(payload.get("change_requests"))
    change_request_ids = [_text(item.get("id")) for item in change_requests]
    for duplicate in _duplicates(change_request_ids):
        errors.append(f"duplicate parent change request id: {duplicate}")
    for request in change_requests:
        if request.get("trigger_requirement_id") not in requirement_ids:
            errors.append(
                f"parent change request {request.get('id')} has unknown trigger requirement"
            )
        if not request.get("affected_parent_field") or not request.get("proposed_change"):
            errors.append(
                f"parent change request {request.get('id')} requires field and proposed change"
            )
    unresolved_decisions = [
        item.get("id")
        for item in _objects(payload.get("decisions"))
        if item.get("classification") == "decide_now" and item.get("status") != "decided"
    ]
    ready = bool(model.get("ready_for_downstream"))
    review = payload.get("review", {}) if isinstance(payload.get("review"), dict) else {}
    if require_ready or model.get("status") == "PASS" or ready:
        if model.get("status") != "PASS":
            errors.append("ready architecture requires status PASS")
        if model.get("architecture_status") not in {"approved", "complete"}:
            errors.append("ready architecture requires approved or complete architecture_status")
        if not ready:
            errors.append("ready architecture requires ready_for_downstream true")
        if review.get("status") != "approved":
            errors.append("ready architecture requires approved review")
        if payload.get("open_questions"):
            errors.append("ready architecture cannot contain open questions")
        if change_requests:
            errors.append("ready architecture cannot contain parent change requests")
        if unresolved_decisions:
            errors.append(f"ready architecture has unresolved decide_now items: {unresolved_decisions}")
        if not nodes:
            errors.append("ready architecture requires at least one child node")

    actual_hash = _sha256_json(_semantic_subject(model))
    if model.get("content_sha256") != actual_hash:
        errors.append("content_sha256 does not match canonical semantic content")
    if review.get("semantic_hash") != actual_hash:
        errors.append("review.semantic_hash does not match canonical semantic content")
    return list(dict.fromkeys(errors))


def _cell(value: Any) -> str:
    if value is None or value == "" or value == []:
        return "None"
    if isinstance(value, list):
        value = ", ".join(_text(item) for item in value) or "None"
    elif isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _text(value).replace("|", "\\|").replace("\n", "<br>")


def _table(headers: list[str], rows: list[list[Any]], empty: str = "None") -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    if rows:
        lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    else:
        lines.append("| " + " | ".join([empty, *(["None"] * (len(headers) - 1))]) + " |")
    return lines


def render_canonical_architecture(model: dict[str, Any]) -> str:
    """Render the fixed twelve-section human view from the canonical model."""
    payload = model["payload"]
    context = payload["design_context"]
    lines = [
        "---",
        f"schema_version: {model['schema_version']}",
        f"artifact_schema_version: {model['artifact_schema_version']}",
        f"artifact_id: {model['artifact_id']}",
        f"architecture_mode: {model['architecture_mode']}",
        f"operation: {model['operation']}",
        f"run_id: {model['run_id']}",
        f"project_id: {model['project_id']}",
        f"node_id: {model['node_id']}",
        f"parent_node_id: {model['parent_node_id'] or 'null'}",
        f"source_prd_id: {model['source_prd_id']}",
        f"status: {model['status']}",
        f"architecture_status: {model['architecture_status']}",
        f"ready_for_downstream: {str(model['ready_for_downstream']).lower()}",
        f"content_sha256: {model['content_sha256']}",
        "---",
        "",
        f"# Canonical Architecture — {model['node_id']}",
        "",
        "## 1. Design Context",
        "",
        f"- Summary: {_cell(context['summary'])}",
        f"- Scope: {_cell(context['scope'])}",
        f"- Responsibility: {_cell(context['responsibility'])}",
        f"- Goals: {_cell(context['goals'])}",
        f"- Non-goals: {_cell(context['non_goals'])}",
        f"- Exclusions: {_cell(context['exclusions'])}",
        "",
        * _table(
            ["External System ID", "Name", "Responsibility", "Source refs"],
            [[item["id"], item["name"], item["responsibility"], item["source_refs"]] for item in context["external_systems"]],
        ),
        "",
        "## 2. Authority and Boundary",
        "",
        f"- Mode: `{model['architecture_mode']}`",
        f"- Can define: {_cell(model['authority_scope']['can_define'])}",
        f"- Must preserve: {_cell(model['authority_scope']['must_preserve'])}",
        f"- Forbidden: {_cell(model['authority_scope']['forbidden'])}",
        f"- Parent binding: {_cell(payload['parent_binding'])}",
        "",
        "## 3. Requirement Allocation",
        "",
        *_table(
            ["Requirement ID", "Classification", "Owner Node IDs", "Source refs", "Reason"],
            [[item["requirement_id"], item["classification"], item["owner_node_ids"], item["source_refs"], item["reason"]] for item in payload["requirement_allocations"]],
        ),
        "",
        "## 4. Decomposition and Node Registry",
        "",
        *_table(
            # Keep one table shape for both modes while retaining compatibility
            # with the existing PRD derive and Mocktest Markdown parsers.
            ["child_id", "Module", "Name", "Kind", "Responsibility", "Exclusions", "Requirement IDs", "State IDs", "Dependencies", "Rationale"],
            [[item["id"], item["id"], item["name"], item["kind"], item["responsibility"], item["exclusions"], item["requirement_ids"], item["state_ids"], item["dependency_ids"], item["rationale"]] for item in payload["nodes"]],
        ),
        "",
        "## 5. State and Data Ownership",
        "",
        *_table(
            ["State ID", "Name", "Owner", "Readers", "Writers", "Lifecycle", "Consistency", "Retention / Privacy", "Source refs"],
            [[item["id"], item["name"], item["owner_node_id"], item["reader_node_ids"], item["writer_node_ids"], item["lifecycle"], item["consistency_boundary"], item["retention_and_privacy"], item["source_refs"]] for item in payload["state_ownership"]],
        ),
        "",
        "## 6. Interfaces and Contracts",
        "",
        *_table(
            ["Contract ID", "Type", "Provider", "Consumers", "Trigger / Protocol", "Sync / Async", "Schema", "side_effects", "dependencies", "Error / Timeout / Retry", "Idempotency", "Version", "Requirement IDs", "Inherited"],
            [[item["id"], item["type"], item["provider_id"], item["consumer_ids"], f"{item['trigger']} / {item['protocol']}", item["interaction_style"], item["schema_fields"], item["side_effects"], item["dependency_ids"], f"{item['error_semantics']} / {item['timeout']} / {item['retry']}", item["idempotency"], item["version"], item["requirement_ids"], item["inherited"]] for item in [*payload["inherited_contracts"], *payload["contracts"]]],
        ),
        "",
        "## 7. Runtime Flows",
        "",
        *_table(
            ["Flow ID", "Name", "Kind", "Requirement IDs", "Steps", "Source refs"],
            [[item["id"], item["name"], item["kind"], item["requirement_ids"], item["steps"], item["source_refs"]] for item in payload["runtime_flows"]],
        ),
        "",
        "## 8. Technology and Deployment",
        "",
        "### Technology Decisions",
        "",
        *_table(
            ["Decision ID", "Choice", "Affected Nodes", "Driver refs", "Rationale", "Status"],
            [[item["id"], item["choice"], item["affected_node_ids"], item["driver_refs"], item["rationale"], item["status"]] for item in payload["technology_decisions"]],
        ),
        "",
        "### Deployment Units",
        "",
        *_table(
            ["Deployment ID", "Name", "Node IDs", "Scaling", "Isolation", "Operations", "Source refs"],
            [[item["id"], item["name"], item["node_ids"], item["scaling"], item["isolation"], item["operations"], item["source_refs"]] for item in payload["deployment_units"]],
        ),
        "",
        "## 9. Decisions and Alternatives",
        "",
        *_table(
            ["Decision ID", "Classification", "Question", "Decision", "Alternatives", "Consequences", "Affected Nodes", "Status", "Source refs"],
            [[item["id"], item["classification"], item["question"], item["decision"], item["alternatives"], item["consequences"], item["affected_node_ids"], item["status"], item["source_refs"]] for item in payload["decisions"]],
        ),
        "",
        "## 10. Risks, Assumptions, and Open Questions",
        "",
        *_table(
            ["Risk ID", "Description", "Severity", "Mitigation", "Status", "Source refs"],
            [[item["id"], item["description"], item["severity"], item["mitigation"], item["status"], item["source_refs"]] for item in payload["risks"]],
        ),
        "",
        f"- Assumptions: {_cell(payload['assumptions'])}",
        f"- Open questions: {_cell(payload['open_questions'])}",
        f"- Parent change requests: {_cell(payload['change_requests'])}",
        "",
        "## 11. Traceability and Child Handoff",
        "",
        *_table(
            ["Source ID", "Relation", "Target IDs", "Evidence refs"],
            [[item["source_id"], item["relation"], item["target_ids"], item["evidence_refs"]] for item in payload["traceability"]],
        ),
        "",
        f"- Recommended next target IDs: {_cell(payload['child_handoff']['recommended_target_ids'])}",
        f"- Required ancestor context: {_cell(payload['child_handoff']['required_ancestor_context'])}",
        "",
        "## 12. Review and Human Gate",
        "",
        f"- Review status: `{payload['review']['status']}`",
        f"- Reviewer: {_cell(payload['review']['reviewer'])}",
        f"- Evidence ref: {_cell(payload['review']['evidence_ref'])}",
        f"- Semantic hash: `{payload['review']['semantic_hash']}`",
        f"- Ready for downstream: `{str(model['ready_for_downstream']).lower()}`",
        "",
    ]
    return "\n".join(lines)
