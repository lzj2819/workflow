"""Canonical PRD contract, normalization, validation, and Markdown rendering.

The legacy ``P1`` … ``P6`` dictionaries are collection state only.  They are
never serialized as a second public model.  Every public artifact is projected
from the single dictionary returned by :func:`build_canonical_prd`.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

from prd_flow import yaml_utils as yaml
from prd_flow.quality.oracle import build_coverage_ledger, validate_acceptance_contract


ENVELOPE_SCHEMA_VERSION = "1.0"
ARTIFACT_SCHEMA_VERSION = "prd/v3"
SECTION_ORDER = (
    "1. Problem Statement",
    "2. Scope and Non-goals",
    "3. Current Release — Functional Requirements",
    "4. Current Release — Non-functional Requirements",
    "5. Architecture Input Contract",
    "6. Success Metrics",
    "7. Acceptance Contracts",
    "8. Oracle Coverage Ledger",
    "9. Future Backlog / Documented Exclusions",
    "10. Risks, Dependencies, and Blocking Questions",
    "11. Traceability Index",
    "12. Review Report",
)

ENVELOPE_STATUSES = {"PASS", "FAIL", "ERROR"}
PRD_STATUSES = {"draft", "approved", "complete"}
MODES = {"root", "derive"}
RELEASE_SCOPES = {"current", "out_of_version", "not_applicable"}
SOURCE_KINDS = {"explicit", "valid_derivation"}
REQUIREMENT_KINDS = {"atomic", "aggregate"}
PRIORITIES = {"Must Have", "Should Have", "Could Have"}


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _nullable_text(value: object) -> str | None:
    rendered = _text(value)
    return rendered or None


def _list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _string_list(value: object) -> list[str]:
    return list(dict.fromkeys(item for item in (_text(item) for item in _list(value)) if item))


def _sorted_records(records: Iterable[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: (_text(item.get(key)).casefold(), json.dumps(item, ensure_ascii=False, sort_keys=True)))


def _source_kind(value: object, mode: str) -> str:
    normalized = _text(value).lower()
    if normalized in {"valid_derivation", "parent_requirement"}:
        return "valid_derivation"
    if normalized == "explicit":
        return "explicit"
    return "valid_derivation" if mode == "derive" else "explicit"


def _normalize_requirement(item: dict[str, Any], requirement_type: str, mode: str) -> dict[str, Any]:
    parent = item.get("parent_requirement_id") or item.get("parent_req") or item.get("parent_nfr")
    return {
        "id": _text(item.get("id")),
        "type": requirement_type,
        "text": _text(item.get("text")),
        "priority": _text(item.get("priority"), "Must Have") if requirement_type == "functional" else None,
        "release_scope": _text(item.get("release_scope"), "current"),
        "scope_reason": _nullable_text(item.get("scope_reason")),
        "requirement_kind": _text(item.get("requirement_kind"), "atomic"),
        "source_kind": _source_kind(item.get("source_kind"), mode),
        "evidence_refs": sorted(_string_list(item.get("evidence_refs"))),
        "parent_requirement_id": _nullable_text(parent),
        "implementation_surfaces": sorted(_string_list(item.get("implementation_surfaces"))),
        "related_requirement_ids": sorted(_string_list(item.get("related_reqs"))),
    }


def _normalize_pair_list(value: object) -> list[dict[str, str | None]]:
    pairs: list[dict[str, str | None]] = []
    for item in _list(value):
        if isinstance(item, dict):
            pairs.append({"condition": _nullable_text(item.get("condition")), "response": _nullable_text(item.get("response"))})
            continue
        rendered = _text(item)
        match = re.split(r"\s*(?:->|=>|→)\s*", rendered, maxsplit=1)
        pairs.append({
            "condition": _nullable_text(match[0]) if match else None,
            "response": _nullable_text(match[1]) if len(match) == 2 else None,
        })
    return pairs


def _normalize_contract(item: dict[str, Any]) -> dict[str, Any]:
    contract_type = _text(item.get("type"), "functional").lower()
    return {
        "id": _text(item.get("id") or item.get("ac_id")),
        "type": contract_type,
        "verifies": sorted(_string_list(item.get("verifies"))),
        "release_scope": _text(item.get("release_scope"), "current"),
        "actor": _nullable_text(item.get("actor")),
        "preconditions": _string_list(item.get("preconditions")),
        "trigger": _nullable_text(item.get("trigger")),
        "response": _string_list(item.get("response")),
        "observable_oracles": _string_list(item.get("observable_oracles")),
        "boundaries": _normalize_pair_list(item.get("boundaries")),
        "exceptions": _normalize_pair_list(item.get("exceptions")),
        "population": _nullable_text(item.get("population")),
        "measurement_start": _nullable_text(item.get("measurement_start")),
        "measurement_end": _nullable_text(item.get("measurement_end")),
        "unit": _nullable_text(item.get("unit")),
        "threshold": _nullable_text(item.get("threshold")),
        "exclusions": _string_list(item.get("exclusions")),
        "pass_rule": _nullable_text(item.get("pass_rule")),
        "evidence_refs": sorted(_string_list(item.get("evidence_refs"))),
    }


def _normalize_metric(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": _text(item.get("id"), f"METRIC-{index:03d}"),
        "name": _text(item.get("name")),
        "target": _text(item.get("target")),
        "measurement_method": _text(item.get("measurement_method") or item.get("method")),
        "verifies": sorted(_string_list(item.get("verifies"))),
        "evidence_refs": sorted(_string_list(item.get("evidence_refs"))),
    }


def _normalize_question(item: object, index: int) -> dict[str, Any]:
    if isinstance(item, dict):
        return {
            "id": _text(item.get("id"), f"Q-{index:03d}"),
            "requirement_id": _nullable_text(item.get("requirement_id")),
            "missing_field": _nullable_text(item.get("missing_field")),
            "question": _text(item.get("question") or item.get("message")),
            "owner": _nullable_text(item.get("owner")),
        }
    rendered = _text(item)
    requirement = re.search(r"\[((?:REQ|NFR)-[A-Z0-9-]+)\]", rendered, re.IGNORECASE)
    return {
        "id": f"Q-{index:03d}",
        "requirement_id": requirement.group(1).upper() if requirement else None,
        "missing_field": None,
        "question": rendered,
        "owner": None,
    }


def _review_record(value: object, mode: str) -> dict[str, Any]:
    review = value if isinstance(value, dict) else {}
    default_status = "inheritance_allocation_gate" if mode == "derive" else "pending"
    return {
        "method": "inheritance_allocation_gate" if mode == "derive" else "independent_agent",
        "status": _text(review.get("status"), default_status),
        "reviewer": _nullable_text(review.get("reviewer")),
        "model": _nullable_text(review.get("model")),
        "reviewed_at": _nullable_text(review.get("reviewed_at")),
        "input_hash": _nullable_text(review.get("input_hash")),
        "findings": _list(review.get("findings")),
    }


def build_canonical_prd(draft_content: dict[str, Any]) -> dict[str, Any]:
    """Normalize collection state into the only public PRD model."""
    p1 = dict(draft_content.get("P1", {}))
    p2 = dict(draft_content.get("P2", {}))
    p3 = dict(draft_content.get("P3", {}))
    p4 = dict(draft_content.get("P4", {}))
    p5 = dict(draft_content.get("P5", {}))
    p6 = dict(draft_content.get("P6", {}))
    mode = _text(p1.get("layer") or draft_content.get("mode"), "root").lower()
    if mode not in MODES:
        mode = "root"

    requirements = [
        *(_normalize_requirement(item, "functional", mode) for item in _list(p3.get("functional")) if isinstance(item, dict)),
        *(_normalize_requirement(item, "nfr", mode) for item in _list(p3.get("non_functional")) if isinstance(item, dict)),
    ]
    requirements = _sorted_records(requirements)
    requirement_ids = [item["id"] for item in requirements if item["id"]]
    contracts = _sorted_records(
        _normalize_contract(item) for item in _list(p4.get("contracts")) if isinstance(item, dict)
    )
    metrics = _sorted_records(
        _normalize_metric(item, index)
        for index, item in enumerate(_list(p5.get("metrics")), start=1)
        if isinstance(item, dict)
    )
    legacy_ledger = build_coverage_ledger(p3, p4.get("contracts", []))
    ledger_by_id = {row.get("requirement_id", ""): row for row in legacy_ledger}
    ledger = [
        {
            "requirement_id": item["id"],
            "requirement_type": item["type"],
            "release_scope": item["release_scope"],
            "acceptance_contract_ids": sorted(
                contract["id"] for contract in contracts if item["id"] in contract["verifies"]
            ),
            "status": _text(ledger_by_id.get(item["id"], {}).get("status"), "blocked"),
            "reason": _nullable_text(ledger_by_id.get(item["id"], {}).get("reason")),
        }
        for item in requirements
    ]
    blocked_count = sum(item["status"] == "blocked" for item in ledger)
    raw_status = _text(p1.get("status"), "draft").lower()
    prd_status = raw_status if raw_status in PRD_STATUSES else ("approved" if raw_status == "pass" else "draft")
    ready_requested = p1.get(
        "ready_for_test_generation",
        mode == "derive" and bool(p1.get("inheritance_complete", False)),
    )
    ready = bool(ready_requested) and blocked_count == 0 and prd_status in {"approved", "complete"}
    envelope_status = "PASS" if ready else "FAIL"
    questions = [
        _normalize_question(item, index)
        for index, item in enumerate(_list(p1.get("_blocking_questions")), start=1)
        if _text(item)
    ]
    review = _review_record(p1.get("_review"), mode)

    traceability = []
    for requirement in requirements:
        req_id = requirement["id"]
        traceability.append({
            "requirement_id": req_id,
            "acceptance_contract_ids": sorted(item["id"] for item in contracts if req_id in item["verifies"]),
            "success_metric_ids": sorted(item["id"] for item in metrics if req_id in item["verifies"]),
            "evidence_refs": requirement["evidence_refs"],
        })

    payload = {
        "document": {
            "doc_id": _text(p1.get("doc_id"), _text(p1.get("project_id"), "root-prd")),
            "title": _text(p1.get("title") or p1.get("project_name") or p1.get("module_name"), "Untitled PRD"),
            "version": _text(p1.get("version"), "1.0.0"),
            "author": _text(p1.get("author"), "unknown"),
            "priority": _text(p1.get("priority"), "P0"),
            "tags": sorted(_string_list(p1.get("tags"))),
            "release_scope_frozen": bool(p1.get("release_scope_frozen", False)),
            "ready_for_test_generation": ready,
            "oracle_blocked_count": blocked_count,
            "inheritance_complete": bool(p1.get("inheritance_complete", mode == "root")),
            "review_method": review["method"],
            "requirement_id_mapping": dict(sorted(dict(p1.get("requirement_id_mapping", {})).items())),
        },
        "problem_statement": {
            "summary": _text(p2.get("summary") or p2.get("pain_points")),
            "target_users": _text(p2.get("target_users")),
            "pain_points": _text(p2.get("pain_points")),
            "desired_outcomes": _text(p2.get("desired_outcomes") or p2.get("opportunity")),
            "current_alternatives": _string_list(p2.get("current_alternatives")),
            "assumptions": _string_list(p2.get("assumptions")),
        },
        "scope": {
            "product": _text(p1.get("project_name") or p1.get("module_name")),
            "release": _text(p1.get("version"), "1.0.0"),
            "current_release_boundary": _text(p2.get("current_release_boundary")),
            "in_scope": _string_list(p2.get("in_scope")),
            "non_goals": _string_list(p3.get("non_goals")),
            "dependencies": _string_list(p2.get("dependencies")),
            "data_availability": _string_list(p2.get("data_availability")),
            "retired_requirement_ids": sorted(_string_list(p3.get("retired_requirement_ids"))),
        },
        "requirements": requirements,
        "architecture_input_contract": {
            "system_boundary": _string_list(p6.get("system_boundary")),
            "external_dependencies": _string_list(p6.get("external_dependencies")),
            "data_and_storage_constraints": _string_list(p6.get("data_and_storage_constraints") or p6.get("data_constraints")),
            "runtime_and_capacity_constraints": _string_list(p6.get("runtime_and_capacity_constraints") or p6.get("runtime_constraints")),
            "security_and_privacy_constraints": _string_list(p6.get("security_and_privacy_constraints") or p6.get("security_constraints")),
            "deployment_constraints": _string_list(p6.get("deployment_constraints")),
            "open_decisions": _string_list(p6.get("open_decisions")),
        },
        "success_metrics": metrics,
        "acceptance_contracts": contracts,
        "oracle_coverage_ledger": ledger,
        "future_backlog_requirement_ids": [item["id"] for item in requirements if item["release_scope"] != "current"],
        "risks": _list(p2.get("risks")),
        "dependencies": _string_list(p2.get("dependencies")),
        "blocking_questions": questions,
        "traceability": traceability,
        "review": review,
    }
    depth = p1.get("depth", p1.get("current_depth", 0))
    max_depth = p1.get("max_depth", 4)
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": _text(p1.get("run_id"), "unknown-run"),
        "project_id": _text(p1.get("project_id") or p1.get("doc_id"), "unknown-project"),
        "node_id": _text(p1.get("node_id"), "root"),
        "parent_node_id": _nullable_text(p1.get("parent_node_id")),
        "artifact_id": _text(p1.get("artifact_id"), "unknown-artifact"),
        "artifact_type": "prd",
        "created_at": _text(p1.get("created_at")),
        "generator": _text(p1.get("generator"), "prd-generation"),
        "status": envelope_status,
        "input_artifacts": sorted(_string_list(p1.get("input_artifacts"))),
        "requirement_ids": requirement_ids,
        "prd_status": prd_status,
        "mode": mode,
        "depth": int(depth) if isinstance(depth, int) and not isinstance(depth, bool) and depth >= 0 else 0,
        "max_depth": int(max_depth) if isinstance(max_depth, int) and not isinstance(max_depth, bool) and max_depth >= 0 else 4,
        "node_history": _list(p1.get("node_history")),
        "requirements": requirement_ids,
        "section_order": list(SECTION_ORDER),
        "payload": payload,
    }


def canonical_json_text(model: dict[str, Any]) -> str:
    """Serialize with one byte-stable policy; callers append no hidden fields."""
    return json.dumps(model, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def validate_canonical_prd(model: dict[str, Any], *, require_ready: bool = False) -> list[str]:
    """Validate semantics JSON Schema cannot express (uniqueness/references/gates)."""
    errors: list[str] = []
    if model.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ENVELOPE_SCHEMA_VERSION}")
    if model.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        errors.append(f"artifact_schema_version must be {ARTIFACT_SCHEMA_VERSION}")
    if model.get("status") not in ENVELOPE_STATUSES:
        errors.append("invalid envelope status")
    if model.get("prd_status") not in PRD_STATUSES:
        errors.append("invalid prd_status")
    if model.get("mode") not in MODES:
        errors.append("invalid mode")
    if model.get("section_order") != list(SECTION_ORDER):
        errors.append("section_order differs from the canonical order")

    payload = model.get("payload") if isinstance(model.get("payload"), dict) else {}
    requirements = payload.get("requirements") if isinstance(payload.get("requirements"), list) else []
    ids = [_text(item.get("id")) for item in requirements if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("requirement IDs must be unique")
    retired = set(payload.get("scope", {}).get("retired_requirement_ids", []))
    if retired.intersection(ids):
        errors.append("retired requirement IDs must never be reused")
    for item in requirements:
        if not isinstance(item, dict):
            errors.append("requirements must be objects")
            continue
        prefix = "REQ" if item.get("type") == "functional" else "NFR"
        if not re.fullmatch(rf"{prefix}-[A-Z0-9]+(?:-[A-Z0-9]+)*", _text(item.get("id")), re.IGNORECASE):
            errors.append(f"invalid {prefix} ID: {item.get('id')}")
        if item.get("release_scope") not in RELEASE_SCOPES:
            errors.append(f"{item.get('id')}: invalid release_scope")
        if item.get("requirement_kind") not in REQUIREMENT_KINDS:
            errors.append(f"{item.get('id')}: invalid requirement_kind")
        if item.get("source_kind") not in SOURCE_KINDS:
            errors.append(f"{item.get('id')}: invalid source_kind")
        if item.get("type") == "functional" and item.get("priority") not in PRIORITIES:
            errors.append(f"{item.get('id')}: invalid priority")
        if item.get("release_scope") == "current" and item.get("requirement_kind") != "atomic":
            errors.append(f"{item.get('id')}: current requirement must be atomic")
        if item.get("release_scope") != "current" and not item.get("scope_reason"):
            errors.append(f"{item.get('id')}: non-current requirement needs scope_reason")
        if not item.get("text"):
            errors.append(f"{item.get('id')}: requirement text is empty")
        if not item.get("evidence_refs"):
            errors.append(f"{item.get('id')}: evidence_refs is empty")

    known_ids = set(ids)
    contracts = payload.get("acceptance_contracts") if isinstance(payload.get("acceptance_contracts"), list) else []
    contract_ids = [_text(item.get("id")) for item in contracts if isinstance(item, dict)]
    if len(contract_ids) != len(set(contract_ids)):
        errors.append("acceptance contract IDs must be unique")
    for contract in contracts:
        if not isinstance(contract, dict):
            errors.append("acceptance contracts must be objects")
            continue
        if not re.fullmatch(
            r"AC-(?:REQ|NFR)-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{2}",
            _text(contract.get("id")),
            re.IGNORECASE,
        ):
            errors.append(f"invalid acceptance contract ID: {contract.get('id')}")
        if contract.get("type") not in {"functional", "nfr"}:
            errors.append(f"{contract.get('id')}: invalid contract type")
        unknown = set(contract.get("verifies", [])) - known_ids
        if unknown:
            errors.append(f"{contract.get('id')}: unknown requirement refs {sorted(unknown)}")
        errors.extend(f"{contract.get('id')}: {issue}" for issue in validate_acceptance_contract(contract))

    metrics = payload.get("success_metrics") if isinstance(payload.get("success_metrics"), list) else []
    metric_ids = [_text(item.get("id")) for item in metrics if isinstance(item, dict)]
    if len(metric_ids) != len(set(metric_ids)):
        errors.append("success metric IDs must be unique")
    for metric in metrics:
        if not re.fullmatch(
            r"METRIC-[A-Z0-9]+(?:-[A-Z0-9]+)*",
            _text(metric.get("id")),
            re.IGNORECASE,
        ):
            errors.append(f"invalid success metric ID: {metric.get('id')}")
        unknown = set(metric.get("verifies", [])) - known_ids
        if unknown:
            errors.append(f"{metric.get('id')}: unknown requirement refs {sorted(unknown)}")

    ledger = payload.get("oracle_coverage_ledger", [])
    ledger_ids = [item.get("requirement_id") for item in ledger if isinstance(item, dict)]
    if ledger_ids != ids:
        errors.append("oracle coverage ledger must contain every requirement exactly once in canonical order")
    if model.get("requirement_ids") != ids or model.get("requirements") != ids:
        errors.append("envelope requirement ID projections differ from payload requirements")
    if require_ready:
        if not requirements:
            errors.append("ready PRD must contain at least one requirement")
        if model.get("status") != "PASS" or model.get("prd_status") not in {"approved", "complete"}:
            errors.append("ready PRD must have PASS and approved/complete status")
        if not payload.get("document", {}).get("ready_for_test_generation"):
            errors.append("ready PRD must allow downstream generation")
        if any(item.get("status") == "blocked" for item in ledger):
            errors.append("ready PRD cannot contain blocked ledger rows")
        if payload.get("blocking_questions"):
            errors.append("ready PRD cannot contain blocking questions")
    return list(dict.fromkeys(errors))


def _none(lines: list[str], values: list[Any]) -> None:
    if not values:
        lines.append("- None")


def _render_requirement(lines: list[str], item: dict[str, Any]) -> None:
    lines.append(f"- [{item['id']}] {item['text']}")
    lines.append(f"  - priority: {item['priority'] or 'N/A'}")
    lines.append(f"  - release_scope: {item['release_scope']}")
    lines.append(f"  - scope_reason: {item['scope_reason'] or 'N/A'}")
    lines.append(f"  - requirement_kind: {item['requirement_kind']}")
    lines.append(f"  - source_kind: {item['source_kind']}")
    lines.append(f"  - parent_req: {item['parent_requirement_id'] or 'N/A'}")
    lines.append(f"  - evidence_refs: [{', '.join(item['evidence_refs'])}]")
    lines.append(f"  - implementation_surfaces: [{', '.join(item['implementation_surfaces'])}]")
    lines.append(f"  - related_reqs: [{', '.join(item['related_requirement_ids'])}]")


def render_canonical_prd(model: dict[str, Any]) -> str:
    """Render the canonical model; all twelve top-level sections always exist."""
    payload = model["payload"]
    document = payload["document"]
    frontmatter = {
        key: model[key]
        for key in (
            "schema_version", "artifact_schema_version", "run_id", "project_id", "node_id",
            "parent_node_id", "artifact_id", "artifact_type", "created_at", "generator",
            "status", "input_artifacts", "requirement_ids", "prd_status", "mode", "depth",
            "max_depth", "node_history",
        )
    }
    frontmatter.update({
        "doc_type": "prd",
        "doc_id": document["doc_id"],
        "version": document["version"],
        "release_scope_frozen": document["release_scope_frozen"],
        "ready_for_test_generation": document["ready_for_test_generation"],
        "oracle_blocked_count": document["oracle_blocked_count"],
        "inheritance_complete": document["inheritance_complete"],
        "review_method": document["review_method"],
    })
    lines = ["---", yaml.dump(frontmatter, allow_unicode=True, sort_keys=False).rstrip(), "---", ""]

    problem = payload["problem_statement"]
    lines.extend(["# 1. Problem Statement", "", "## Summary", problem["summary"] or "TBD", "", "## Target Users", problem["target_users"] or "TBD", "", "## Pain Points", problem["pain_points"] or "TBD", "", "## Desired Outcomes", problem["desired_outcomes"] or "TBD", "", "## Current Alternatives"])
    lines.extend(f"- {item}" for item in problem["current_alternatives"]); _none(lines, problem["current_alternatives"])
    lines.extend(["", "## Assumptions"]); lines.extend(f"- {item}" for item in problem["assumptions"]); _none(lines, problem["assumptions"])

    scope = payload["scope"]
    lines.extend(["", "# 2. Scope and Non-goals", "", f"- Product: {scope['product'] or 'TBD'}", f"- Release: {scope['release']}", f"- Current release boundary: {scope['current_release_boundary'] or 'TBD'}", "", "## In Scope"])
    lines.extend(f"- {item}" for item in scope["in_scope"]); _none(lines, scope["in_scope"])
    lines.extend(["", "## Non-goals"]); lines.extend(f"- {item}" for item in scope["non_goals"]); _none(lines, scope["non_goals"])
    lines.extend(["", "## Data Availability"]); lines.extend(f"- {item}" for item in scope["data_availability"]); _none(lines, scope["data_availability"])

    functional = [item for item in payload["requirements"] if item["type"] == "functional" and item["release_scope"] == "current"]
    lines.extend(["", "# 3. Current Release — Functional Requirements", ""])
    for priority in ("Must Have", "Should Have", "Could Have"):
        lines.append(f"## {priority}")
        selected = [item for item in functional if item["priority"] == priority]
        for item in selected: _render_requirement(lines, item)
        _none(lines, selected); lines.append("")

    nfrs = [item for item in payload["requirements"] if item["type"] == "nfr" and item["release_scope"] == "current"]
    lines.extend(["# 4. Current Release — Non-functional Requirements", ""])
    for item in nfrs: _render_requirement(lines, item)
    _none(lines, nfrs)

    architecture = payload["architecture_input_contract"]
    lines.extend(["", "# 5. Architecture Input Contract", ""])
    for heading, key in (
        ("System Boundary", "system_boundary"), ("External Dependencies", "external_dependencies"),
        ("Data and Storage Constraints", "data_and_storage_constraints"),
        ("Runtime and Capacity Constraints", "runtime_and_capacity_constraints"),
        ("Security and Privacy Constraints", "security_and_privacy_constraints"),
        ("Deployment Constraints", "deployment_constraints"), ("Open Decisions", "open_decisions"),
    ):
        lines.append(f"## {heading}"); lines.extend(f"- {item}" for item in architecture[key]); _none(lines, architecture[key]); lines.append("")

    lines.extend(["# 6. Success Metrics", "", "| ID | Metric | Target | Measurement | Verifies | Evidence |", "|---|---|---|---|---|---|"])
    for item in payload["success_metrics"]:
        lines.append(f"| {item['id']} | {item['name']} | {item['target']} | {item['measurement_method']} | {', '.join(item['verifies']) or '-'} | {', '.join(item['evidence_refs']) or '-'} |")
    if not payload["success_metrics"]: lines.append("| - | None | - | - | - | - |")

    lines.extend(["", "# 7. Acceptance Contracts", "", "> Business oracles only; no test cases or Gherkin.", ""])
    for contract in payload["acceptance_contracts"]:
        lines.extend([f"## {contract['id']}", f"- type: {contract['type']}", f"- verifies: [{', '.join(contract['verifies'])}]", f"- release_scope: {contract['release_scope']}"])
        for key in ("actor", "preconditions", "trigger", "response", "observable_oracles", "boundaries", "exceptions", "population", "measurement_start", "measurement_end", "unit", "threshold", "exclusions", "pass_rule", "evidence_refs"):
            value = contract[key]
            if key in {"boundaries", "exceptions"}:
                rendered = " | ".join(f"{item['condition'] or ''} -> {item['response'] or ''}" for item in value)
            elif isinstance(value, list):
                rendered = " | ".join(_text(item) for item in value)
            else:
                rendered = _text(value)
            lines.append(f"- {key}: {rendered or 'N/A'}")
        lines.append("")
    if not payload["acceptance_contracts"]: lines.extend(["- None", ""])

    lines.extend(["# 8. Oracle Coverage Ledger", "", "| Requirement | Type | Release scope | Acceptance Contract | Status | Reason |", "|---|---|---|---|---|---|"])
    for item in payload["oracle_coverage_ledger"]:
        lines.append(f"| {item['requirement_id']} | {item['requirement_type']} | {item['release_scope']} | {', '.join(item['acceptance_contract_ids']) or '-'} | {item['status']} | {item['reason'] or '-'} |")
    if not payload["oracle_coverage_ledger"]: lines.append("| - | - | - | - | blocked | no requirements |")

    excluded = [item for item in payload["requirements"] if item["release_scope"] != "current"]
    lines.extend(["", "# 9. Future Backlog / Documented Exclusions", ""])
    for item in excluded: _render_requirement(lines, item)
    _none(lines, excluded)

    lines.extend(["", "# 10. Risks, Dependencies, and Blocking Questions", "", "## Risks"])
    lines.extend(f"- {_text(item)}" for item in payload["risks"]); _none(lines, payload["risks"])
    lines.extend(["", "## Dependencies"]); lines.extend(f"- {item}" for item in payload["dependencies"]); _none(lines, payload["dependencies"])
    lines.extend(["", "## Blocking Questions", "", "| ID | Requirement | Missing Field | Question | Owner |", "|---|---|---|---|---|"])
    for item in payload["blocking_questions"]:
        lines.append(f"| {item['id']} | {item['requirement_id'] or '-'} | {item['missing_field'] or '-'} | {item['question']} | {item['owner'] or '-'} |")
    if not payload["blocking_questions"]: lines.append("| - | - | - | None | - |")

    lines.extend(["", "# 11. Traceability Index", "", "| Requirement | Acceptance Contracts | Success Metrics | Evidence |", "|---|---|---|---|"])
    for item in payload["traceability"]:
        lines.append(f"| {item['requirement_id']} | {', '.join(item['acceptance_contract_ids']) or '-'} | {', '.join(item['success_metric_ids']) or '-'} | {', '.join(item['evidence_refs']) or '-'} |")
    if not payload["traceability"]: lines.append("| - | - | - | - |")

    review = payload["review"]
    lines.extend(["", "# 12. Review Report", "", f"- Method: {review['method']}", f"- Status: {review['status']}", f"- Reviewer: {review['reviewer'] or 'N/A'}", f"- Model: {review['model'] or 'N/A'}", f"- Reviewed at: {review['reviewed_at'] or 'N/A'}", f"- Input hash: {review['input_hash'] or 'N/A'}", f"- Findings count: {len(review['findings'])}", ""])
    return "\n".join(lines).rstrip() + "\n"
