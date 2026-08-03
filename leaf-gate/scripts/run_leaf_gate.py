#!/usr/bin/env python3
"""Canonical Leaf Gate v2.

Leaf Gate is a read-only admission and layering-decision boundary.  It never
repairs upstream artifacts, parses their Markdown views, or invents children.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
INPUT_VERSION = "leaf-gate-input/v2"
REPORT_VERSION = "leaf-gate-report/v2"
NEXT_ACTION_VERSION = "leaf-gate-next-action/v2"
EXECUTION_VERSION = "leaf-gate-execution-log/v2"
BUNDLE_VERSION = "leaf-gate-bundle/v2"

OUTPUT_FILES = (
    "leaf_gate_report.json",
    "leaf_gate_report.md",
    "next_action.json",
    "execution_log.json",
    "bundle_manifest.json",
)

CONTENT_FILES = OUTPUT_FILES[:-1]

DEFAULT_POLICY = {
    "max_leaf_complexity": 12,
    "max_leaf_contracts": 6,
    "max_leaf_states": 3,
    "max_recursion_depth": 4,
    "min_semantic_confidence": 0.75,
    "semantic_judgement": "OPTIONAL",
}

ARTIFACT_ROLES = (
    "prd",
    "architecture",
    "testcases",
    "mocktest_report",
    "mocktest_evidence",
)


class LeafGateError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def canonical_json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LeafGateError(
            "MISSING_ARTIFACT", f"Required artifact does not exist: {path.name}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LeafGateError(
            "INVALID_JSON", f"Artifact is not valid JSON: {path.name}", {"error": str(exc)}
        ) from exc
    if not isinstance(value, dict):
        raise LeafGateError("INVALID_JSON", f"Artifact must be a JSON object: {path.name}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json_text(value), encoding="utf-8", newline="\n")
    temporary.replace(path)


def require(value: Any, field: str, expected: Any) -> None:
    if value.get(field) != expected:
        raise LeafGateError(
            "SCHEMA_INCOMPATIBLE",
            f"{field} must be {expected!r}",
            {"actual": value.get(field)},
        )


def require_exact_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        actual = sorted(value) if isinstance(value, dict) else []
        raise LeafGateError(
            "SCHEMA_INCOMPATIBLE",
            f"{label} fields do not match the v2 contract",
            {"expected": sorted(expected), "actual": actual},
        )


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    require_exact_keys(
        manifest,
        {
            "schema_version", "artifact_schema_version", "run_id", "project_id",
            "node_id", "parent_node_id", "source_prd_id", "current_artifacts",
            "repair_history", "policy", "semantic_judgement",
        },
        "manifest",
    )
    for key in ("run_id", "project_id", "node_id", "source_prd_id"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise LeafGateError("SCHEMA_INCOMPATIBLE", f"manifest.{key} must be non-empty")
    refs = manifest.get("current_artifacts")
    if not isinstance(refs, dict) or set(refs) != set(ARTIFACT_ROLES):
        raise LeafGateError("SCHEMA_INCOMPATIBLE", "current_artifacts roles are invalid")
    for role, ref in refs.items():
        require_exact_keys(
            ref, {"artifact_id", "artifact_schema_version", "path", "sha256"},
            f"current_artifacts.{role}",
        )
        if not valid_sha256(ref["sha256"]):
            raise LeafGateError("SCHEMA_INCOMPATIBLE", f"current_artifacts.{role}.sha256 is invalid")
    require_exact_keys(manifest["policy"], set(DEFAULT_POLICY), "policy")
    history = manifest.get("repair_history")
    require_exact_keys(history, {"completeness", "mode", "cycles"}, "repair_history")
    if not isinstance(history["cycles"], list):
        raise LeafGateError("SCHEMA_INCOMPATIBLE", "repair_history.cycles must be an array")
    cycle_fields = {
        "failed_report_sha256", "before_architecture_sha256", "after_architecture_sha256",
        "finding_ids", "affected_testcase_ids", "revalidated_testcase_ids", "final_report_sha256",
    }
    for index, cycle in enumerate(history["cycles"]):
        require_exact_keys(cycle, cycle_fields, f"repair_history.cycles[{index}]")
        for field in cycle_fields:
            if field.endswith("_sha256") and not valid_sha256(cycle[field]):
                raise LeafGateError("SCHEMA_INCOMPATIBLE", f"repair cycle {index} has invalid {field}")
    semantic_ref = manifest.get("semantic_judgement")
    if semantic_ref is not None:
        require_exact_keys(
            semantic_ref, {"artifact_id", "artifact_schema_version", "path", "sha256"},
            "semantic_judgement",
        )
        if not valid_sha256(semantic_ref["sha256"]):
            raise LeafGateError("SCHEMA_INCOMPATIBLE", "semantic_judgement.sha256 is invalid")


def safe_artifact_path(node_dir: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise LeafGateError("UNSAFE_PATH", "Input artifact paths must be relative")
    resolved = (node_dir / candidate).resolve()
    try:
        resolved.relative_to(node_dir.resolve())
    except ValueError as exc:
        raise LeafGateError("UNSAFE_PATH", f"Input path escapes node directory: {relative}") from exc
    return resolved


def verify_architecture_hash(architecture: dict[str, Any]) -> None:
    subject = copy.deepcopy(architecture)
    expected = str(subject.pop("content_sha256", ""))
    subject.pop("created_at", None)
    payload = subject.get("payload")
    if isinstance(payload, dict):
        payload.pop("review", None)
    actual = canonical_hash(subject)
    if expected != actual:
        raise LeafGateError(
            "HASH_MISMATCH",
            "Architecture semantic content hash is invalid",
            {"expected": expected, "actual": actual},
        )


def verify_self_hash(value: dict[str, Any], label: str) -> None:
    expected = str(value.get("content_sha256") or "")
    actual = canonical_hash(
        {key: item for key, item in value.items() if key != "content_sha256"}
    )
    if expected != actual:
        raise LeafGateError(
            "HASH_MISMATCH",
            f"{label} content hash is invalid",
            {"expected": expected, "actual": actual},
        )


def load_policy(node_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    policy = dict(DEFAULT_POLICY)
    configured = manifest.get("policy") or {}
    if not isinstance(configured, dict):
        raise LeafGateError("SCHEMA_INCOMPATIBLE", "policy must be an object")
    policy.update(configured)
    for key in (
        "max_leaf_complexity",
        "max_leaf_contracts",
        "max_leaf_states",
        "max_recursion_depth",
    ):
        value = policy.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise LeafGateError("CONFIGURATION_ERROR", f"{key} must be a non-negative integer")
    confidence = policy.get("min_semantic_confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise LeafGateError(
            "CONFIGURATION_ERROR", "min_semantic_confidence must be between 0 and 1"
        )
    if policy.get("semantic_judgement") not in {"DISABLED", "OPTIONAL", "REQUIRED"}:
        raise LeafGateError(
            "CONFIGURATION_ERROR",
            "semantic_judgement must be DISABLED, OPTIONAL, or REQUIRED",
        )
    return policy


def load_current_artifacts(
    node_dir: Path, manifest: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], dict[str, Path], list[dict[str, Any]]]:
    refs = manifest.get("current_artifacts")
    if not isinstance(refs, dict) or set(refs) != set(ARTIFACT_ROLES):
        raise LeafGateError(
            "SCHEMA_INCOMPATIBLE",
            "current_artifacts must contain exactly the five canonical roles",
            {"expected": list(ARTIFACT_ROLES)},
        )
    values: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    source_artifacts: list[dict[str, Any]] = []
    for role in ARTIFACT_ROLES:
        ref = refs[role]
        if not isinstance(ref, dict):
            raise LeafGateError("SCHEMA_INCOMPATIBLE", f"current_artifacts.{role} must be an object")
        path = safe_artifact_path(node_dir, str(ref.get("path") or ""))
        actual_sha = file_sha256(path)
        if actual_sha != ref.get("sha256"):
            raise LeafGateError(
                "HASH_MISMATCH",
                f"Manifest hash does not match {role}",
                {"expected": ref.get("sha256"), "actual": actual_sha},
            )
        value = read_json(path)
        if value.get("artifact_id") and value.get("artifact_id") != ref.get("artifact_id"):
            raise LeafGateError("IDENTITY_MISMATCH", f"{role} artifact_id does not match manifest")
        actual_version = value.get("artifact_schema_version")
        if actual_version != ref.get("artifact_schema_version"):
            raise LeafGateError("SCHEMA_INCOMPATIBLE", f"{role} schema version does not match manifest")
        values[role], paths[role] = value, path
        source_artifacts.append(
            {
                "role": role,
                "artifact_id": ref.get("artifact_id"),
                "artifact_schema_version": ref.get("artifact_schema_version"),
                "sha256": actual_sha,
            }
        )
    return values, paths, source_artifacts


def validate_producer_contracts(values: dict[str, dict[str, Any]]) -> None:
    prd = values["prd"]
    architecture = values["architecture"]
    testcases = values["testcases"]
    report = values["mocktest_report"]
    evidence = values["mocktest_evidence"]

    require(prd, "artifact_schema_version", "prd/v3")
    require(architecture, "artifact_schema_version", "architecture/v2")
    require(testcases, "artifact_schema_version", "testcases/v2")
    require(report, "artifact_schema_version", "mocktest-report/v2")
    require(evidence, "artifact_schema_version", "mocktest-leaf-evidence/v2")
    if prd.get("status") != "PASS" or prd.get("prd_status") not in {"approved", "complete"}:
        raise LeafGateError("UPSTREAM_NOT_READY", "PRD is not approved/complete PASS")
    document = (prd.get("payload") or {}).get("document") or {}
    if not document.get("ready_for_test_generation") or document.get("oracle_blocked_count") != 0:
        raise LeafGateError("UPSTREAM_NOT_READY", "PRD has blocked test-generation evidence")
    if (prd.get("payload") or {}).get("blocking_questions"):
        raise LeafGateError("UPSTREAM_NOT_READY", "PRD still has blocking questions")
    if (
        architecture.get("status") != "PASS"
        or architecture.get("architecture_status") != "complete"
        or not architecture.get("ready_for_downstream")
    ):
        raise LeafGateError("UPSTREAM_NOT_READY", "Architecture is not downstream-ready PASS")
    if testcases.get("status") != "PASS" or testcases.get("blocked_items") != []:
        raise LeafGateError("UPSTREAM_NOT_READY", "Testcases are not canonical PASS")
    verify_architecture_hash(architecture)
    verify_self_hash(report, "Mocktest report")
    verify_self_hash(evidence, "Mocktest Leaf evidence")


def validate_lineage(
    manifest: dict[str, Any],
    values: dict[str, dict[str, Any]],
    paths: dict[str, Path],
) -> dict[str, Any]:
    prd = values["prd"]
    architecture = values["architecture"]
    testcases = values["testcases"]
    report = values["mocktest_report"]
    evidence = values["mocktest_evidence"]
    identity = {
        "project_id": prd.get("project_id"),
        "node_id": prd.get("node_id"),
        "parent_node_id": prd.get("parent_node_id"),
        "source_prd_id": prd.get("artifact_id"),
    }
    if manifest.get("source_prd_id") != identity["source_prd_id"]:
        raise LeafGateError("IDENTITY_MISMATCH", "manifest.source_prd_id does not match PRD")
    for key in ("project_id", "node_id", "parent_node_id"):
        if manifest.get(key) != identity[key]:
            raise LeafGateError("IDENTITY_MISMATCH", f"manifest.{key} does not match PRD")
        for role in ("architecture", "testcases"):
            if values[role].get(key) != identity[key]:
                raise LeafGateError("IDENTITY_MISMATCH", f"{role}.{key} does not match PRD")
    if architecture.get("source_prd_id") != prd.get("artifact_id"):
        raise LeafGateError("LINEAGE_MISMATCH", "Architecture does not reference current PRD")
    source_prd = testcases.get("source_prd") or {}
    if source_prd.get("artifact_id") != prd.get("artifact_id"):
        raise LeafGateError("LINEAGE_MISMATCH", "Testcases do not reference current PRD")
    if source_prd.get("sha256") != file_sha256(paths["prd"]):
        raise LeafGateError("LINEAGE_MISMATCH", "Testcases do not reference current PRD bytes")
    architecture_prd_refs = [
        item
        for item in architecture.get("input_artifacts", [])
        if item.get("artifact_id") == prd.get("artifact_id")
    ]
    if not architecture_prd_refs or architecture_prd_refs[0].get("sha256") != file_sha256(paths["prd"]):
        raise LeafGateError("LINEAGE_MISMATCH", "Architecture does not reference current PRD bytes")
    report_identity = report.get("identity") or {}
    for key in ("project_id", "node_id", "parent_node_id"):
        if report_identity.get(key) != identity[key]:
            raise LeafGateError("IDENTITY_MISMATCH", f"Mocktest identity.{key} does not match PRD")
    report_sources = {item.get("artifact_type"): item for item in report.get("source_artifacts", [])}
    for role, artifact_type in (("architecture", "architecture"), ("testcases", "testcases")):
        source = report_sources.get(artifact_type) or {}
        if source.get("artifact_id") != values[role].get("artifact_id"):
            raise LeafGateError("STALE_MOCKTEST", f"Mocktest does not reference current {role} artifact")
        if source.get("sha256") != file_sha256(paths[role]):
            raise LeafGateError("STALE_MOCKTEST", f"Mocktest was not run against current {role} bytes")
    if evidence.get("run_id") != report.get("run_id") or evidence.get("states") != report.get("states"):
        raise LeafGateError("STALE_MOCKTEST", "Mocktest report and Leaf evidence disagree")
    return identity


def mocktest_route(report: dict[str, Any], evidence: dict[str, Any]) -> tuple[str, list[str]]:
    states = report.get("states") or {}
    overall = states.get("overall")
    required = {
        "execution_state": "COMPLETED",
        "validation_verdict": "PASS",
        "audit_state": "PASS",
        "publication_state": "COMPLETE",
        "overall": "PASS",
    }
    failures = [f"{key}={states.get(key)}" for key, expected in required.items() if states.get(key) != expected]
    if evidence.get("gate_recommendation") != "ALLOW":
        failures.append(f"gate_recommendation={evidence.get('gate_recommendation')}")
    if not failures:
        return "ADMITTED", []
    if overall == "ERROR" or states.get("audit_state") == "FAIL" or states.get("publication_state") == "ERROR":
        return "RETURN_TO_VALIDATION", failures
    return "RETURN_TO_ARCHITECTURE", failures


def validate_coverage(values: dict[str, dict[str, Any]]) -> None:
    prd_ids = set(values["prd"].get("requirement_ids") or [])
    testcase_ids = set(values["testcases"].get("requirement_ids") or [])
    cases = values["testcases"].get("testcases") or []
    coverage = values["mocktest_report"].get("coverage") or {}
    if not cases or prd_ids != testcase_ids:
        raise LeafGateError(
            "COVERAGE_INCOMPLETE", "Current PRD and Testcases requirement sets must match"
        )
    if (
        coverage.get("total") != len(cases)
        or coverage.get("evaluated") != len(cases)
        or coverage.get("passed") != len(cases)
        or coverage.get("warning") != 0
        or coverage.get("failed") != 0
        or coverage.get("blocked") != 0
        or set(coverage.get("covered_requirement_ids") or []) != prd_ids
    ):
        raise LeafGateError(
            "COVERAGE_INCOMPLETE", "Latest Mocktest summary does not prove full-suite PASS"
        )


def validate_repair_history(
    manifest: dict[str, Any],
    values: dict[str, dict[str, Any]],
    paths: dict[str, Path],
) -> tuple[str, list[str]]:
    history = manifest.get("repair_history")
    if not isinstance(history, dict) or history.get("completeness") != "COMPLETE":
        raise LeafGateError("HISTORY_INCOMPLETE", "repair_history must declare COMPLETE history")
    mode = history.get("mode")
    cycles = history.get("cycles")
    if mode == "FIRST_PASS":
        if cycles != []:
            raise LeafGateError("HISTORY_INCOMPLETE", "FIRST_PASS cannot contain repair cycles")
        return mode, []
    if mode != "REPAIRED" or not isinstance(cycles, list) or not cycles:
        raise LeafGateError("HISTORY_INCOMPLETE", "REPAIRED history requires at least one cycle")
    previous_final = None
    for index, cycle in enumerate(cycles):
        required = (
            "failed_report_sha256",
            "before_architecture_sha256",
            "after_architecture_sha256",
            "finding_ids",
            "affected_testcase_ids",
            "revalidated_testcase_ids",
            "final_report_sha256",
        )
        missing = [key for key in required if not cycle.get(key)]
        if missing:
            raise LeafGateError(
                "REPAIR_CHAIN_INCOMPLETE", f"repair cycle {index} is incomplete", {"missing": missing}
            )
        affected = set(cycle["affected_testcase_ids"])
        if not affected.issubset(set(cycle["revalidated_testcase_ids"])):
            raise LeafGateError(
                "REPAIR_CHAIN_INCOMPLETE", "Every affected testcase must be revalidated"
            )
        if cycle["before_architecture_sha256"] == cycle["after_architecture_sha256"]:
            raise LeafGateError("REPAIR_CHAIN_INCOMPLETE", "Repair cycle did not change Architecture")
        if previous_final and cycle["failed_report_sha256"] != previous_final:
            raise LeafGateError("REPAIR_CHAIN_INCOMPLETE", "Repair cycles are not contiguous")
        previous_final = cycle["final_report_sha256"]
    current = cycles[-1]
    if current["after_architecture_sha256"] != file_sha256(paths["architecture"]):
        raise LeafGateError("STALE_REPAIR_CHAIN", "Repair chain does not end at current Architecture")
    if current["final_report_sha256"] != file_sha256(paths["mocktest_report"]):
        raise LeafGateError("STALE_REPAIR_CHAIN", "Repair chain does not end at current Mocktest report")
    known_cases = {item.get("tc_id") for item in values["testcases"].get("testcases", [])}
    if not set(current["revalidated_testcase_ids"]).issubset(known_cases):
        raise LeafGateError("REPAIR_CHAIN_INCOMPLETE", "Repair chain references unknown testcases")
    return mode, sorted(set(current["affected_testcase_ids"]))


def architecture_metrics(architecture: dict[str, Any]) -> dict[str, int]:
    payload = architecture.get("payload") or {}
    return {
        "complexity": int(architecture.get("complexity") or 0),
        "candidate_node_count": len(payload.get("nodes") or []),
        "contract_count": len(payload.get("contracts") or []),
        "state_count": len(payload.get("state_ownership") or []),
        "current_depth": int(architecture.get("depth") or 0),
        "artifact_max_depth": int(architecture.get("max_depth") or 0),
    }


def project_children(architecture: dict[str, Any]) -> list[dict[str, Any]]:
    payload = architecture.get("payload") or {}
    contracts = payload.get("contracts") or []
    children = []
    for node in sorted(payload.get("nodes") or [], key=lambda item: item.get("id", "")):
        node_id = str(node.get("id") or "")
        if not node_id or not node.get("responsibility") or not node.get("requirement_ids"):
            raise LeafGateError(
                "DECOMPOSITION_PLAN_INVALID", "Architecture child candidates require ID, responsibility, and requirements"
            )
        contract_ids = sorted(
            contract.get("id")
            for contract in contracts
            if contract.get("provider_id") == node_id or node_id in (contract.get("consumer_ids") or [])
        )
        children.append(
            {
                "child_node_id": node_id,
                "name": str(node.get("name") or node_id),
                "kind": str(node.get("kind") or ""),
                "responsibility": str(node.get("responsibility")),
                "exclusions": sorted(node.get("exclusions") or []),
                "requirement_ids": sorted(node.get("requirement_ids") or []),
                "state_ids": sorted(node.get("state_ids") or []),
                "dependency_ids": sorted(node.get("dependency_ids") or []),
                "contract_ids": contract_ids,
                "rationale": str(node.get("rationale") or ""),
                "source_refs": sorted(node.get("source_refs") or []),
                "priority": len(children) + 1,
            }
        )
    return children


def load_semantic_judgement(node_dir: Path, manifest: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    ref = manifest.get("semantic_judgement")
    mode = policy["semantic_judgement"]
    if ref is None:
        if mode == "REQUIRED":
            raise LeafGateError("SEMANTIC_JUDGEMENT_REQUIRED", "Policy requires semantic judgement")
        return None
    if mode == "DISABLED":
        raise LeafGateError("CONFIGURATION_ERROR", "Semantic judgement was supplied while disabled")
    if not isinstance(ref, dict):
        raise LeafGateError("SCHEMA_INCOMPATIBLE", "semantic_judgement must be an artifact reference")
    path = safe_artifact_path(node_dir, str(ref.get("path") or ""))
    if file_sha256(path) != ref.get("sha256"):
        raise LeafGateError("HASH_MISMATCH", "Semantic judgement hash does not match manifest")
    judgement = read_json(path)
    require(judgement, "artifact_schema_version", "leaf-gate-judgement/v2")
    require_exact_keys(
        judgement,
        {"schema_version", "artifact_schema_version", "node_id", "judge", "criteria"},
        "semantic judgement",
    )
    require(judgement, "schema_version", SCHEMA_VERSION)
    if judgement.get("node_id") != manifest.get("node_id"):
        raise LeafGateError("IDENTITY_MISMATCH", "Semantic judgement node_id does not match manifest")
    criteria = judgement.get("criteria") or {}
    expected = {"C1_behavior", "C2_boundary", "C3_context", "C4_verifiability", "C5_gain"}
    if set(criteria) != expected:
        raise LeafGateError("INVALID_SEMANTIC_JUDGEMENT", "Semantic judgement criteria are incomplete")
    for name, item in criteria.items():
        require_exact_keys(item, {"status", "confidence", "reason", "evidence_refs"}, name)
        if item.get("status") not in {"PASS", "FAIL"} or not item.get("evidence_refs"):
            raise LeafGateError("INVALID_SEMANTIC_JUDGEMENT", f"{name} lacks PASS/FAIL evidence")
        if float(item.get("confidence", 0)) < policy["min_semantic_confidence"]:
            raise LeafGateError("INVALID_SEMANTIC_JUDGEMENT", f"{name} confidence is too low")
    return judgement


def evaluate_layering(
    architecture: dict[str, Any],
    policy: dict[str, Any],
    judgement: dict[str, Any] | None,
) -> tuple[str | None, list[str], dict[str, int], list[dict[str, Any]], float | None]:
    metrics = architecture_metrics(architecture)
    effective_max_depth = min(metrics["artifact_max_depth"], policy["max_recursion_depth"])
    triggers = []
    if metrics["candidate_node_count"] >= 2:
        triggers.append("MULTIPLE_EXPLICIT_CHILD_CANDIDATES")
    if metrics["complexity"] > policy["max_leaf_complexity"]:
        triggers.append("COMPLEXITY_EXCEEDS_LEAF_POLICY")
    if metrics["contract_count"] > policy["max_leaf_contracts"]:
        triggers.append("CONTRACT_WIDTH_EXCEEDS_LEAF_POLICY")
    if metrics["state_count"] > policy["max_leaf_states"]:
        triggers.append("STATE_WIDTH_EXCEEDS_LEAF_POLICY")
    if judgement:
        failed = [name for name, item in judgement["criteria"].items() if item["status"] == "FAIL"]
        if failed:
            triggers.append("SEMANTIC_DECOMPOSITION_GAIN")
        elif not triggers:
            return "STOP_LAYERING", [], metrics, [], min(
                float(item["confidence"]) for item in judgement["criteria"].values()
            )
    children = project_children(architecture)
    if triggers:
        if metrics["current_depth"] >= effective_max_depth:
            raise LeafGateError(
                "MAX_DEPTH_REACHED", "Decomposition is required but maximum depth is reached", {"triggers": triggers}
            )
        if len(children) < 2:
            raise LeafGateError(
                "DECOMPOSITION_PLAN_REQUIRED",
                "Layering signals require at least two explicit Architecture child candidates",
                {"triggers": triggers},
            )
        return "CONTINUE_LAYERING", triggers, metrics, children, 1.0
    return "STOP_LAYERING", [], metrics, [], 1.0


def next_action_for(
    admission_state: str,
    decision: str | None,
    affected_testcase_ids: list[str],
    error_code: str | None = None,
) -> dict[str, Any]:
    if admission_state == "RETURN_TO_ARCHITECTURE":
        action = "RETURN_TO_ARCHITECTURE"
        target = "architecture-design"
    elif admission_state == "RETURN_TO_VALIDATION":
        action = "RETURN_TO_VALIDATION"
        target = "mocktest"
    elif admission_state == "INVALID":
        action = "FIX_INPUT_CONTRACT"
        target = "workflow-orchestrator"
    elif decision == "CONTINUE_LAYERING":
        action = "DECOMPOSE"
        target = "prd-derive"
    elif decision == "STOP_LAYERING":
        action = "VIBECODE"
        target = "vibe-coding"
    else:
        action = "MANUAL_REVIEW"
        target = "human-gate"
    return {
        "type": action,
        "target_stage": target,
        "affected_testcase_ids": affected_testcase_ids,
        "error_code": error_code,
        "notes": [],
    }


def error_report(
    manifest: dict[str, Any],
    source_artifacts: list[dict[str, Any]],
    error: LeafGateError,
) -> dict[str, Any]:
    identity = {
        "project_id": manifest.get("project_id") or "unknown",
        "node_id": manifest.get("node_id") or "unknown",
        "parent_node_id": manifest.get("parent_node_id"),
        "source_prd_id": manifest.get("source_prd_id") or "unknown",
    }
    return build_report_object(
        manifest,
        identity,
        source_artifacts,
        "INVALID",
        [error.code],
        "NOT_EVALUATED",
        None,
        None,
        {},
        [],
        [],
        "UNKNOWN",
        [],
        error,
    )


def build_report_object(
    manifest: dict[str, Any],
    identity: dict[str, Any],
    source_artifacts: list[dict[str, Any]],
    admission_state: str,
    admission_reasons: list[str],
    evaluation_state: str,
    decision: str | None,
    confidence: float | None,
    metrics: dict[str, Any],
    triggers: list[str],
    children: list[dict[str, Any]],
    repair_mode: str,
    affected_testcase_ids: list[str],
    error: LeafGateError | None = None,
) -> dict[str, Any]:
    next_action = next_action_for(
        admission_state, decision, affected_testcase_ids, error.code if error else None
    )
    overall = decision or next_action["type"]
    report = {
        "schema_version": SCHEMA_VERSION,
        "artifact_schema_version": REPORT_VERSION,
        "run_id": str(manifest.get("run_id") or "unknown"),
        "identity": identity,
        "source_artifacts": source_artifacts,
        "input_fingerprint": canonical_hash(source_artifacts),
        "admission": {
            "state": admission_state,
            "reason_codes": admission_reasons,
            "repair_history_mode": repair_mode,
            "affected_testcase_ids": affected_testcase_ids,
        },
        "evaluation": {
            "state": evaluation_state,
            "policy": manifest.get("policy") or {},
            "metrics": metrics,
            "triggered_rules": triggers,
        },
        "decision": {
            "value": decision,
            "confidence": confidence,
            "rationale_codes": triggers,
            "proposed_children": children,
        },
        "next_action": next_action,
        "overall": overall,
        "errors": (
            [{"code": error.code, "message": error.message, "details": error.details}]
            if error
            else []
        ),
        "content_sha256": "",
    }
    report["content_sha256"] = canonical_hash(
        {key: value for key, value in report.items() if key != "content_sha256"}
    )
    return report


def build_report(node_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    require(manifest, "artifact_schema_version", INPUT_VERSION)
    require(manifest, "schema_version", SCHEMA_VERSION)
    validate_manifest_shape(manifest)
    policy = load_policy(node_dir, manifest)
    manifest["policy"] = policy
    values, paths, source_artifacts = load_current_artifacts(node_dir, manifest)
    validate_producer_contracts(values)
    identity = validate_lineage(manifest, values, paths)
    repair_mode, affected = validate_repair_history(manifest, values, paths)
    admission_state, reasons = mocktest_route(
        values["mocktest_report"], values["mocktest_evidence"]
    )
    if admission_state != "ADMITTED":
        return build_report_object(
            manifest,
            identity,
            source_artifacts,
            admission_state,
            reasons,
            "NOT_EVALUATED",
            None,
            None,
            {},
            [],
            [],
            repair_mode,
            affected,
        )
    validate_coverage(values)
    judgement = load_semantic_judgement(node_dir, manifest, policy)
    decision, triggers, metrics, children, confidence = evaluate_layering(
        values["architecture"], policy, judgement
    )
    return build_report_object(
        manifest,
        identity,
        source_artifacts,
        "ADMITTED",
        [],
        "COMPLETED",
        decision,
        confidence,
        metrics,
        triggers,
        children,
        repair_mode,
        affected,
    )


def markdown_cell(value: Any) -> str:
    return str(value).replace("\r", "").replace("\n", "<br>").replace("|", "\\|")


def render_markdown(report: dict[str, Any]) -> str:
    identity = report["identity"]
    admission = report["admission"]
    evaluation = report["evaluation"]
    decision = report["decision"]
    next_action = report["next_action"]
    lines = [
        "# Leaf Gate Report",
        "",
        "## 1. Identity",
        "",
        "| Project | Node | Parent | Source PRD | Run |",
        "|---|---|---|---|---|",
        f"| {markdown_cell(identity['project_id'])} | {markdown_cell(identity['node_id'])} | {markdown_cell(identity['parent_node_id'] or '')} | {markdown_cell(identity['source_prd_id'])} | {markdown_cell(report['run_id'])} |",
        "",
        "## 2. Admission",
        "",
        "| State | Reasons |",
        "|---|---|",
        f"| {markdown_cell(admission['state'])} | {markdown_cell(', '.join(admission['reason_codes']) or 'None')} |",
        "",
        "## 3. Repair Chain",
        "",
        "| Mode | Affected testcases |",
        "|---|---|",
        f"| {markdown_cell(admission['repair_history_mode'])} | {markdown_cell(', '.join(admission['affected_testcase_ids']) or 'None')} |",
        "",
        "## 4. Evaluation",
        "",
        "| State | Triggered rules |",
        "|---|---|",
        f"| {markdown_cell(evaluation['state'])} | {markdown_cell(', '.join(evaluation['triggered_rules']) or 'None')} |",
        "",
        "## 5. Decision",
        "",
        "| Value | Confidence | Overall |",
        "|---|---:|---|",
        f"| {markdown_cell(decision['value'] or 'NOT_EVALUATED')} | {markdown_cell(decision['confidence'] if decision['confidence'] is not None else '')} | {markdown_cell(report['overall'])} |",
        "",
        "## 6. Proposed Children",
        "",
        "| ID | Kind | Responsibility | Requirements | Contracts |",
        "|---|---|---|---|---|",
    ]
    if decision["proposed_children"]:
        for child in decision["proposed_children"]:
            lines.append(
                f"| {markdown_cell(child['child_node_id'])} | {markdown_cell(child['kind'])} | {markdown_cell(child['responsibility'])} | {markdown_cell(', '.join(child['requirement_ids']))} | {markdown_cell(', '.join(child['contract_ids']) or 'None')} |"
            )
    else:
        lines.append("| None |  |  |  |  |")
    lines.extend(
        [
            "",
            "## 7. Next Action",
            "",
            "| Type | Target | Error code |",
            "|---|---|---|",
            f"| {markdown_cell(next_action['type'])} | {markdown_cell(next_action['target_stage'])} | {markdown_cell(next_action['error_code'] or '')} |",
            "",
        ]
    )
    return "\n".join(lines)


def content_hash_payload(value: dict[str, Any]) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != "content_sha256"})


def publish_bundle(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "leaf_gate_report.json", report)
    (output_dir / "leaf_gate_report.md").write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    next_action = {
        "schema_version": SCHEMA_VERSION,
        "artifact_schema_version": NEXT_ACTION_VERSION,
        "run_id": report["run_id"],
        "report_sha256": report["content_sha256"],
        **report["next_action"],
        "content_sha256": "",
    }
    next_action["content_sha256"] = content_hash_payload(next_action)
    write_json(output_dir / "next_action.json", next_action)
    execution = {
        "schema_version": SCHEMA_VERSION,
        "artifact_schema_version": EXECUTION_VERSION,
        "run_id": report["run_id"],
        "admission_state": report["admission"]["state"],
        "evaluation_state": report["evaluation"]["state"],
        "overall": report["overall"],
        "events": [
            {"order": 1, "type": "INPUT_VERIFIED"},
            {"order": 2, "type": "ADMISSION_DECIDED"},
            {"order": 3, "type": "LAYERING_EVALUATED"},
            {"order": 4, "type": "BUNDLE_PUBLISHED"},
        ],
        "content_sha256": "",
    }
    execution["content_sha256"] = content_hash_payload(execution)
    write_json(output_dir / "execution_log.json", execution)
    files = []
    for name in CONTENT_FILES:
        path = output_dir / name
        files.append({"path": name, "sha256": file_sha256(path)})
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_schema_version": BUNDLE_VERSION,
        "run_id": report["run_id"],
        "files": files,
        "bundle_sha256": canonical_hash(files),
    }
    write_json(output_dir / "bundle_manifest.json", manifest)


def run(node_dir: Path, manifest_path: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    manifest: dict[str, Any] = {}
    source_artifacts: list[dict[str, Any]] = []
    try:
        manifest = read_json(manifest_path)
        report = build_report(node_dir, manifest_path)
        code = 0 if report["decision"]["value"] in {"CONTINUE_LAYERING", "STOP_LAYERING"} else 2
    except LeafGateError as error:
        report = error_report(manifest, source_artifacts, error)
        code = 5 if error.code in {
            "SCHEMA_INCOMPATIBLE",
            "INVALID_JSON",
            "IDENTITY_MISMATCH",
            "LINEAGE_MISMATCH",
            "HASH_MISMATCH",
            "UNSAFE_PATH",
        } else 2
    except Exception as error:  # keep a deterministic, inspectable tool failure
        wrapped = LeafGateError("RUNTIME_ERROR", "Leaf Gate encountered an internal error", {"error": str(error)})
        report = error_report(manifest, source_artifacts, wrapped)
        code = 4
    publish_bundle(report, output_dir)
    return report, code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical Leaf Gate v2")
    parser.add_argument("node_dir", type=Path)
    parser.add_argument(
        "--input-manifest",
        type=Path,
        help="leaf-gate-input/v2 manifest; defaults to <node>/leaf_gate_input.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    node_dir = args.node_dir.resolve()
    if not node_dir.is_dir():
        print(f"ERROR: node directory does not exist: {node_dir}", file=sys.stderr)
        return 3
    manifest_path = (
        args.input_manifest.resolve()
        if args.input_manifest
        else node_dir / "leaf_gate_input.json"
    )
    report, code = run(node_dir, manifest_path, args.output_dir.resolve())
    print(
        json.dumps(
            {
                "overall": report["overall"],
                "decision": report["decision"]["value"],
                "next_action": report["next_action"]["type"],
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
