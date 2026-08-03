"""Mocktest v2 canonical input, state and artifact contract.

This module is the only authority for cross-stage Mocktest artifacts.  The
legacy strict engine may continue to produce its private ``plan.json`` /
``hops.json`` files while it is being migrated, but downstream consumers must
only read the v2 files defined here.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from mock_framework.models.arch import (
    ArchDoc,
    ComponentSpec,
    DataFlow,
    DataFlowStep,
    InterfaceDef,
)
from mock_framework.models.gap import GapReport
from mock_framework.models.gherkin import Feature, Scenario, Step
from mock_framework.models.loader import Expectations, TestCase

CONTRACT_VERSION = "mocktest/v2"
INPUT_VERSION = "mocktest-input/v2"
NORMALIZED_INPUT_VERSION = "mocktest-normalized-input/v2"

WORKSPACE_FILES = (
    "run_manifest.json",
    "normalized_input.json",
    "extraction_report.json",
    "execution_plan.json",
    "scenario_events.json",
    "contract_check.json",
    "validator_results.json",
    "strict_audit.json",
    "execution_log.json",
)

DELIVERY_FILES = (
    "mocktest_report.json",
    "mocktest_report.md",
    "leaf_gate_evidence.json",
    "execution_log.json",
    "bundle_manifest.json",
)

BindingStatus = Literal["BOUND", "AMBIGUOUS", "UNBOUND", "INVALID"]
ExecutionState = Literal["NOT_STARTED", "BLOCKED", "PARTIAL", "COMPLETED", "ERROR"]
ValidationVerdict = Literal["NOT_EVALUATED", "PASS", "WARNING", "FAIL"]
AuditState = Literal["NOT_RUN", "PASS", "FAIL"]
PublicationState = Literal["NOT_STARTED", "COMPLETE", "ERROR"]


def canonical_json_text(value: Any) -> str:
    """Return the repository-wide stable JSON representation."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(canonical_json_text(value), encoding="utf-8", newline="\n")
    temporary.replace(path)


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _unique_sorted(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def render_feature_v2(model: dict[str, Any]) -> str:
    """Render the byte contract owned by prd-to-gherkin without reparsing it."""
    lines = [
        f"# artifact_schema_version: {model['artifact_schema_version']}",
        f"# source_prd_artifact_id: {model['source_prd']['artifact_id']}",
        f"# source_prd_sha256: {model['source_prd']['sha256']}",
        f"Feature: {model['project_id']} acceptance tests",
    ]
    for testcase in model["testcases"]:
        tags = " ".join(
            [*(f"@{item}" for item in testcase["requirement_ids"]), f"@{testcase['tc_id']}"]
        )
        lines.extend(
            [
                "",
                f"  # {testcase['scenario_id']}",
                f"  # acceptance_contract_id: {testcase['acceptance_contract_id']}",
                f"  {tags}",
                f"  Scenario: {testcase['title']}",
            ]
        )
        lines.extend(f"    {step['keyword']} {step['text']}" for step in testcase["steps"])
    return unicodedata.normalize("NFC", "\n".join(lines) + "\n")


def resolve_testcases_authority(path: str | Path) -> tuple[Path, Path | None]:
    """Resolve a Feature v2 view to its sibling Testcases v2 authority.

    The Feature is compared byte-for-byte with a deterministic render; it is
    never parsed back into product facts.
    """
    target = Path(path).resolve()
    if target.suffix.lower() == ".json":
        return target, None
    if target.suffix.lower() != ".feature":
        raise ValueError("canonical testcase input must be testcases.json or its .feature view")
    authority = target.with_name("testcases.json")
    if not authority.is_file():
        raise FileNotFoundError(f"Feature v2 requires sibling testcase authority: {authority}")
    model = _read_json(authority, {})
    _require(model, "artifact_schema_version", "testcases/v2")
    expected = render_feature_v2(model).encode("utf-8")
    if target.read_bytes() != expected:
        raise ValueError("Feature v2 bytes do not match sibling testcases/v2 authority")
    return authority, target


def _require(value: dict[str, Any], field: str, expected: Any | None = None) -> Any:
    if field not in value:
        raise ValueError(f"missing required field: {field}")
    actual = value[field]
    if expected is not None and actual != expected:
        raise ValueError(f"{field} must be {expected!r}, got {actual!r}")
    return actual


def _verify_architecture_hash(model: dict[str, Any]) -> None:
    expected = str(_require(model, "content_sha256"))
    subject = dict(model)
    subject.pop("created_at", None)
    subject.pop("content_sha256", None)
    if "payload" in subject:
        subject["payload"] = dict(subject["payload"])
        subject["payload"].pop("review", None)
    actual = canonical_hash(subject)
    if actual != expected:
        raise ValueError("architecture content_sha256 does not match canonical semantic content")


def _architecture_to_arch_doc(model: dict[str, Any]) -> ArchDoc:
    payload = model["payload"]
    nodes = payload.get("nodes", [])
    node_ids = {str(item["id"]) for item in nodes}
    components = [
        ComponentSpec(
            name=str(item["id"]),
            responsibility=str(item.get("responsibility", "")),
            dispatch_kind="component",
        )
        for item in nodes
    ]

    interfaces: list[InterfaceDef] = []
    for contract in payload.get("contracts", []) + payload.get("inherited_contracts", []):
        provider = str(contract.get("provider_id", ""))
        consumers = _unique_sorted(contract.get("consumer_ids", []))
        direction: Literal["inbound", "outbound"] = (
            "inbound" if any(item not in node_ids for item in consumers) else "outbound"
        )
        interfaces.append(
            InterfaceDef(
                name=str(contract["id"]),
                direction=direction,
                protocol=str(contract.get("protocol", contract.get("type", "internal"))),
                contract={
                    "id": str(contract["id"]),
                    "provider": provider,
                    "consumer": ", ".join(consumers),
                    "required": _unique_sorted(contract.get("schema_fields", [])),
                    "response": [],
                    "trigger": str(contract.get("trigger", "")),
                    "side_effects": str(contract.get("side_effects", "")),
                    "error_semantics": str(contract.get("error_semantics", "")),
                    "timeout": str(contract.get("timeout", "")),
                    "retry": str(contract.get("retry", "")),
                    "idempotency": str(contract.get("idempotency", "")),
                    "requirement_ids": _unique_sorted(contract.get("requirement_ids", [])),
                    "source_refs": _unique_sorted(contract.get("source_refs", [])),
                },
            )
        )

    sequence: list[DataFlowStep] = []
    for flow in payload.get("runtime_flows", []):
        for step in sorted(flow.get("steps", []), key=lambda item: int(item.get("order", 0))):
            sequence.append(
                DataFlowStep(
                    from_component=str(step.get("from_id", "")),
                    to_component=str(step.get("to_id", "")),
                    action=str(step.get("action", "")),
                    message=str(step.get("contract_id") or ""),
                )
            )
    return ArchDoc(
        level_name=str(model["node_id"]),
        level_depth=int(model.get("depth", 0)),
        parent_ref=model.get("parent_node_id"),
        scope=str(payload.get("design_context", {}).get("scope", "")),
        responsibilities=[str(item.get("responsibility", "")) for item in nodes],
        interfaces=interfaces,
        data_flow=DataFlow(sequence=sequence),
        components=components,
        external_dependencies=_unique_sorted(
            item.get("id") for item in payload.get("design_context", {}).get("external_systems", [])
        ),
    )


def _feature_from_testcases(model: dict[str, Any]) -> tuple[Feature, list[TestCase]]:
    scenarios: list[Scenario] = []
    test_cases: list[TestCase] = []
    for item in model["testcases"]:
        steps = [
            Step(keyword=str(step["keyword"]), text=str(step["text"])) for step in item["steps"]
        ]
        tags = [f"@{requirement_id}" for requirement_id in item["requirement_ids"]]
        tags.append(f"@{item['tc_id']}")
        scenario = Scenario(
            id=str(item["tc_id"]),
            name=str(item["title"]),
            tags=tags,
            steps=steps,
            examples=None,
        )
        scenarios.append(scenario)
        test_cases.append(
            TestCase(
                test_case_id=str(item["tc_id"]),
                source_feature="testcases.feature",
                source_scenario=str(item["scenario_id"]),
                tags=tags,
                gherkin={
                    "feature": str(model.get("artifact_id", "testcases")),
                    "scenario": str(item["title"]),
                    "steps": [{"keyword": step.keyword, "text": step.text} for step in steps],
                    "requirement_ids": _unique_sorted(item["requirement_ids"]),
                    "acceptance_contract_id": str(item["acceptance_contract_id"]),
                    "evidence_refs": _unique_sorted(item.get("evidence_refs", [])),
                },
                technical_mapping={"given_steps": [], "when_steps": [], "then_steps": []},
                expectations=Expectations(),
            )
        )
    return (
        Feature(
            name=str(model.get("artifact_id", "testcases")),
            description=None,
            background=None,
            scenarios=scenarios,
        ),
        test_cases,
    )


def _binding_candidates(
    architecture: dict[str, Any], testcase: dict[str, Any]
) -> list[dict[str, Any]]:
    payload = architecture["payload"]
    requirement_ids = set(map(str, testcase.get("requirement_ids", [])))
    contracts = {
        str(item["id"]): item
        for item in payload.get("contracts", []) + payload.get("inherited_contracts", [])
    }
    candidates: list[dict[str, Any]] = []
    for flow in payload.get("runtime_flows", []):
        if requirement_ids and not requirement_ids.intersection(
            map(str, flow.get("requirement_ids", []))
        ):
            continue
        steps = sorted(flow.get("steps", []), key=lambda item: int(item.get("order", 0)))
        if not steps:
            continue
        first = steps[0]
        contract_id = str(first.get("contract_id") or "")
        contract = contracts.get(contract_id)
        if not contract:
            continue
        candidates.append(
            {
                "component_id": str(first.get("to_id") or contract.get("provider_id") or ""),
                "contract_id": contract_id,
                "flow_id": str(flow["id"]),
                "action": str(first.get("action") or contract.get("trigger") or "handle"),
                "provenance": [
                    f"architecture.payload.runtime_flows[id={flow['id']}].steps[order={first.get('order')}]",
                    f"architecture.payload.contracts[id={contract_id}]",
                    f"testcases.testcases[tc_id={testcase['tc_id']}].requirement_ids",
                ],
            }
        )
    unique = {canonical_hash(item): item for item in candidates}
    return sorted(
        unique.values(),
        key=lambda item: (item["component_id"], item["contract_id"], item["flow_id"]),
    )


def _bindings(architecture: dict[str, Any], testcases: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for testcase in testcases["testcases"]:
        candidates = _binding_candidates(architecture, testcase)
        if len(candidates) == 1:
            status: BindingStatus = "BOUND"
        elif len(candidates) > 1:
            status = "AMBIGUOUS"
        else:
            status = "UNBOUND"
        results.append(
            {
                "tc_id": str(testcase["tc_id"]),
                "status": status,
                "selected": candidates[0] if status == "BOUND" else None,
                "candidates": candidates,
                "confidence": 1.0 if status == "BOUND" else 0.0,
                "diagnostics": (
                    []
                    if status == "BOUND"
                    else ["no unique requirement-to-runtime-flow entry binding"]
                ),
            }
        )
    return results


def _input_fingerprint(normalized: dict[str, Any]) -> str:
    """Hash semantic input identity and bytes, independent of local file paths."""
    subject = dict(normalized)
    subject.pop("input_fingerprint", None)
    subject.pop("feature_projection", None)
    subject["inputs"] = [
        {key: value for key, value in item.items() if key != "path"}
        for item in normalized["inputs"]
    ]
    return canonical_hash(subject)


@dataclass
class CanonicalLoaderResult:
    test_cases: list[TestCase]
    feature: Feature
    arch_doc: ArchDoc
    gap_report: GapReport
    normalized_input: dict[str, Any]
    extraction_report: dict[str, Any]
    bindings: dict[str, dict[str, Any]]


def load_canonical_pair(
    architecture_path: str | Path,
    testcases_path: str | Path,
    *,
    feature_projection_path: str | Path | None = None,
) -> CanonicalLoaderResult:
    """Load Architecture v2 and Testcases v2 without Markdown inference."""
    arch_path = Path(architecture_path).resolve()
    test_path = Path(testcases_path).resolve()
    architecture = _read_json(arch_path, {})
    testcases = _read_json(test_path, {})
    _require(architecture, "artifact_schema_version", "architecture/v2")
    _require(testcases, "artifact_schema_version", "testcases/v2")
    _require(architecture, "status", "PASS")
    _require(testcases, "status", "PASS")
    if not architecture.get("ready_for_downstream"):
        raise ValueError("architecture is not ready_for_downstream")
    for field in ("project_id", "node_id", "parent_node_id"):
        if architecture.get(field) != testcases.get(field):
            raise ValueError(f"identity mismatch: architecture.{field} != testcases.{field}")
    testcase_prd_id = (testcases.get("source_prd") or {}).get("artifact_id")
    if architecture.get("source_prd_id") != testcase_prd_id:
        raise ValueError(
            "identity mismatch: architecture.source_prd_id != " "testcases.source_prd.artifact_id"
        )
    _verify_architecture_hash(architecture)

    feature, cases = _feature_from_testcases(testcases)
    bindings = _bindings(architecture, testcases)
    binding_map = {item["tc_id"]: item for item in bindings}
    normalized = {
        "schema_version": "1.0",
        "artifact_schema_version": NORMALIZED_INPUT_VERSION,
        "identity": {
            "project_id": architecture["project_id"],
            "node_id": architecture["node_id"],
            "parent_node_id": architecture.get("parent_node_id"),
            "source_prd_id": architecture["source_prd_id"],
        },
        "inputs": [
            {
                "artifact_id": architecture["artifact_id"],
                "artifact_type": "architecture",
                "artifact_schema_version": "architecture/v2",
                "path": str(arch_path),
                "sha256": file_sha256(arch_path),
            },
            {
                "artifact_id": testcases["artifact_id"],
                "artifact_type": "testcases",
                "artifact_schema_version": "testcases/v2",
                "path": str(test_path),
                "sha256": file_sha256(test_path),
            },
        ],
        "architecture": {
            "mode": architecture["architecture_mode"],
            "components": architecture["components"],
            "interfaces": architecture["interfaces"],
            "dependencies": architecture["dependencies"],
            "nodes": architecture["payload"]["nodes"],
            "contracts": architecture["payload"]["contracts"],
            "inherited_contracts": architecture["payload"]["inherited_contracts"],
            "runtime_flows": architecture["payload"]["runtime_flows"],
            "states": architecture["payload"]["state_ownership"],
        },
        "testcases": testcases["testcases"],
        "bindings": bindings,
    }
    if feature_projection_path is not None:
        projection = Path(feature_projection_path).resolve()
        if projection.read_bytes() != render_feature_v2(testcases).encode("utf-8"):
            raise ValueError("Feature v2 bytes do not match canonical testcases")
        normalized["feature_projection"] = {
            "artifact_id": f"{testcases['artifact_id']}:feature",
            "artifact_type": "feature_view",
            "artifact_schema_version": "feature/v2",
            "path": str(projection),
            "sha256": file_sha256(projection),
        }
    normalized["input_fingerprint"] = _input_fingerprint(normalized)
    blocked = [item["tc_id"] for item in bindings if item["status"] != "BOUND"]
    extraction = {
        "schema_version": "1.0",
        "artifact_schema_version": "mocktest-extraction/v2",
        "adapter": "canonical-v2",
        "status": "PASS" if not blocked else "BLOCKED",
        "bindings": bindings,
        "blocked_testcase_ids": blocked,
        "diagnostics": [],
    }
    return CanonicalLoaderResult(
        test_cases=cases,
        feature=feature,
        arch_doc=_architecture_to_arch_doc(architecture),
        gap_report=GapReport(total_gaps=0, gaps=[]),
        normalized_input=normalized,
        extraction_report=extraction,
        bindings=binding_map,
    )


def initialize_workspace(
    run_dir: str | Path,
    normalized: dict[str, Any],
    extraction: dict[str, Any],
    *,
    run_id: str | None = None,
) -> None:
    """Materialize every v2 intermediate, including empty blocked-run artifacts."""
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_json(
        root / "run_manifest.json",
        {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-run/v2",
            "run_id": run_id or normalized["input_fingerprint"][:16],
            "input_fingerprint": normalized["input_fingerprint"],
            "workspace_files": list(WORKSPACE_FILES),
        },
    )
    write_json(root / "normalized_input.json", normalized)
    write_json(root / "extraction_report.json", extraction)
    empty = {
        "execution_plan.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-plan/v2",
            "input_fingerprint": normalized["input_fingerprint"],
            "scenarios": [],
        },
        "scenario_events.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-events/v2",
            "events": [],
        },
        "contract_check.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-contract-check/v2",
            "status": "NOT_RUN",
            "findings": [],
        },
        "validator_results.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-validator-results/v2",
            "results": [],
        },
        "strict_audit.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-audit/v2",
            "audit_state": "NOT_RUN",
            "violations": [],
        },
        "execution_log.json": {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-execution-log/v2",
            "execution_state": "NOT_STARTED",
            "events": [],
        },
    }
    for name, payload in empty.items():
        write_json(root / name, payload)


def derive_overall(
    execution_state: ExecutionState,
    validation_verdict: ValidationVerdict,
    audit_state: AuditState,
) -> str:
    if execution_state == "ERROR" or audit_state == "FAIL":
        return "ERROR"
    if execution_state in {"NOT_STARTED", "BLOCKED", "PARTIAL"}:
        return "BLOCKED"
    if validation_verdict == "FAIL":
        return "FAIL"
    if validation_verdict == "WARNING":
        return "WARNING"
    if validation_verdict == "PASS" and audit_state == "PASS":
        return "PASS"
    return "BLOCKED"


def _legacy_findings(
    validator_rows: list[dict[str, Any]],
    contract_check: dict[str, Any],
    *,
    default_scope: Literal["TOP_LEVEL", "MODULE"],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in validator_rows:
        tc_id = str(row.get("test_case_id", ""))
        raw_result = row.get("result")
        result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {}
        analysis = result.get("failure_analysis")
        declared_scope = str(analysis.get("scope", "")) if isinstance(analysis, dict) else ""
        finding_scope = (
            "TOP_LEVEL"
            if declared_scope == "top_level"
            else "MODULE" if declared_scope == "module" else default_scope
        )
        for dimension in (
            "structure",
            "flow",
            "state",
            "contract",
            "performance",
            "interface_compat",
        ):
            value = result.get(dimension)
            if not isinstance(value, dict):
                continue
            status = str(value.get("status", "")).upper()
            if status not in {"FAIL", "WARNING"}:
                continue
            summary = str(value.get("detail") or value.get("reason") or f"{dimension} {status}")
            raw = {"origin": "VALIDATOR", "category": dimension, "tc_id": tc_id, "summary": summary}
            findings.append(
                {
                    "finding_id": "FND-" + canonical_hash(raw)[:12].upper(),
                    "origin": "VALIDATOR",
                    "category": dimension.upper(),
                    "severity": status,
                    "scope": finding_scope,
                    "tc_ids": [tc_id] if tc_id else [],
                    "requirement_ids": [],
                    "component_ids": [],
                    "contract_ids": [],
                    "summary": summary,
                    "evidence_refs": ["validator_results.json"],
                }
            )
    groups: list[tuple[str, Any]] = [("", contract_check.get("global_findings", []))]
    groups.extend(
        (str(tc_id), body.get("findings", []))
        for tc_id, body in (contract_check.get("per_scenario", {}) or {}).items()
        if isinstance(body, dict)
    )
    for tc_id, rows in groups:
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            severity = str(row.get("severity") or row.get("status") or "WARNING").upper()
            severity = severity if severity in {"INFO", "WARNING", "FAIL", "ERROR"} else "WARNING"
            summary = str(
                row.get("detail") or row.get("message") or row.get("type") or "contract finding"
            )
            raw = {"origin": "CONTRACT_CHECK", "tc_id": tc_id, "summary": summary}
            findings.append(
                {
                    "finding_id": "FND-" + canonical_hash(raw)[:12].upper(),
                    "origin": "CONTRACT_CHECK",
                    "category": str(row.get("type") or "CONTRACT_COMPATIBILITY").upper(),
                    "severity": severity,
                    "scope": (
                        "TOP_LEVEL"
                        if row.get("scope") == "top_level"
                        else "MODULE" if row.get("scope") == "module" else default_scope
                    ),
                    "tc_ids": [tc_id] if tc_id else [],
                    "requirement_ids": _unique_sorted(row.get("requirement_ids", [])),
                    "component_ids": _unique_sorted(
                        row.get("components", row.get("component_ids", [])) or []
                    ),
                    "contract_ids": _unique_sorted(row.get("contract_ids", [])),
                    "summary": summary,
                    "evidence_refs": ["contract_check.json"],
                }
            )
    return sorted(
        {item["finding_id"]: item for item in findings}.values(),
        key=lambda item: item["finding_id"],
    )


def _render_report(report: dict[str, Any], extraction: dict[str, Any]) -> str:
    identity = report["identity"]
    states = report["states"]
    coverage = report["coverage"]
    lines = [
        "# Mocktest Validation Report",
        "",
        "## 1. Identity",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Run ID | {report['run_id']} |",
        f"| Project ID | {identity['project_id']} |",
        f"| Node ID | {identity['node_id']} |",
        f"| Parent Node ID | {identity['parent_node_id'] or ''} |",
        f"| Source PRD ID | {identity['source_prd_id']} |",
        f"| Input fingerprint | {report['input_fingerprint']} |",
        "",
        "## 2. State Summary",
        "",
        "| Execution | Validation | Audit | Publication | Overall |",
        "|---|---|---|---|---|",
        f"| {states['execution_state']} | {states['validation_verdict']} | {states['audit_state']} | {states['publication_state']} | {states['overall']} |",
        "",
        "## 3. Coverage",
        "",
        "| Total | Evaluated | Passed | Warning | Failed | Blocked |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {coverage['total']} | {coverage['evaluated']} | {coverage['passed']} | {coverage['warning']} | {coverage['failed']} | {coverage['blocked']} |",
        "",
        "## 4. Findings",
        "",
        "| ID | Origin | Severity | Scope | Testcases | Summary |",
        "|---|---|---|---|---|---|",
    ]
    if report["findings"]:
        for finding in report["findings"]:
            summary = str(finding["summary"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {finding['finding_id']} | {finding['origin']} | {finding['severity']} | "
                f"{finding['scope']} | {', '.join(finding['tc_ids'])} | {summary} |"
            )
    else:
        lines.append("| — | — | — | — | — | None |")
    lines.extend(
        [
            "",
            "## 5. Extraction Diagnostics",
            "",
            f"- Adapter: {extraction['adapter']}",
            f"- Status: {extraction['status']}",
            f"- Blocked testcase IDs: {', '.join(extraction['blocked_testcase_ids']) or 'None'}",
            f"- Diagnostics: {'; '.join(extraction['diagnostics']) or 'None'}",
            "",
            "## 6. Evidence",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["evidence_refs"])
    lines.extend(["", "## 7. Errors", ""])
    lines.extend(f"- {item}" for item in report["errors"])
    if not report["errors"]:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def publish_canonical_bundle(run_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Publish the fixed v2 bundle from one strict-run workspace.

    Legacy filenames are read only as a migration adapter.  All public files
    derive from one result object and do not independently reinterpret status.
    """
    run_path = Path(run_dir).resolve()
    out = Path(output_dir).resolve()
    normalized = _read_json(run_path / "normalized_input.json", {})
    extraction = _read_json(run_path / "extraction_report.json", {})
    if normalized.get("artifact_schema_version") != NORMALIZED_INPUT_VERSION:
        raise ValueError("normalized_input.json must use mocktest-normalized-input/v2")
    if extraction.get("artifact_schema_version") != "mocktest-extraction/v2":
        raise ValueError("extraction_report.json must use mocktest-extraction/v2")

    plan = _read_json(run_path / "execution_plan.json", {"scenarios": []})
    hops = _read_json(run_path / "hops.json", {})
    compat = _read_json(run_path / "compat.json", {})
    validator_rows = _read_json(run_path / "val_results.json", [])
    old_audit = _read_json(run_path / "strict_audit.json", {})
    artifact_errors = []
    error_file = run_path / "artifact_errors.jsonl"
    if error_file.is_file():
        artifact_errors = [
            line
            for line in error_file.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]

    total = len(normalized.get("testcases", []))
    blocked = len(extraction.get("blocked_testcase_ids", []))
    evaluated = len(validator_rows)
    result_counts = {"PASS": 0, "WARNING": 0, "FAIL": 0}
    for row in validator_rows:
        status = str((row.get("result") or {}).get("overall", "")).upper()
        if status in result_counts:
            result_counts[status] += 1
    findings = _legacy_findings(
        validator_rows,
        compat,
        default_scope=(
            "TOP_LEVEL" if normalized["architecture"]["mode"] == "top_level" else "MODULE"
        ),
    )
    if artifact_errors:
        execution_state: ExecutionState = "ERROR"
    elif evaluated == total and total > 0:
        execution_state = "COMPLETED"
    elif evaluated > 0:
        execution_state = "PARTIAL"
    elif blocked or extraction.get("status") == "BLOCKED":
        execution_state = "BLOCKED"
    else:
        execution_state = "NOT_STARTED"
    audit_token = str(old_audit.get("audit_state") or old_audit.get("status") or "NOT_RUN").upper()
    audit_state: AuditState = audit_token if audit_token in {"NOT_RUN", "PASS", "FAIL"} else "NOT_RUN"  # type: ignore[assignment]
    if evaluated == 0:
        verdict: ValidationVerdict = "NOT_EVALUATED"
    elif result_counts["FAIL"] or any(item["severity"] == "FAIL" for item in findings):
        verdict = "FAIL"
    elif result_counts["WARNING"] or any(item["severity"] == "WARNING" for item in findings):
        verdict = "WARNING"
    else:
        verdict = "PASS"
    overall = derive_overall(execution_state, verdict, audit_state)
    states = {
        "execution_state": execution_state,
        "validation_verdict": verdict,
        "audit_state": audit_state,
        "publication_state": "COMPLETE",
        "overall": overall,
    }
    identity = normalized["identity"]
    run_manifest = _read_json(run_path / "run_manifest.json", {})
    run_id = str(run_manifest.get("run_id") or normalized["input_fingerprint"][:16])
    all_requirements = _unique_sorted(
        requirement_id
        for testcase in normalized["testcases"]
        for requirement_id in testcase.get("requirement_ids", [])
    )
    covered_requirements = _unique_sorted(
        requirement_id
        for row in validator_rows
        for testcase in normalized["testcases"]
        if testcase.get("tc_id") == row.get("test_case_id")
        for requirement_id in testcase.get("requirement_ids", [])
    )
    report = {
        "schema_version": "1.0",
        "artifact_schema_version": "mocktest-report/v2",
        "run_id": run_id,
        "identity": identity,
        "source_artifacts": [
            {key: value for key, value in item.items() if key != "path"}
            for item in normalized["inputs"]
        ],
        "input_fingerprint": normalized["input_fingerprint"],
        "states": states,
        "coverage": {
            "total": total,
            "evaluated": evaluated,
            "passed": result_counts["PASS"],
            "warning": result_counts["WARNING"],
            "failed": result_counts["FAIL"],
            "blocked": blocked,
            "requirement_ids": all_requirements,
            "covered_requirement_ids": covered_requirements,
        },
        "findings": findings,
        "evidence_refs": [
            "normalized_input.json",
            "extraction_report.json",
            "execution_plan.json",
            "scenario_events.json",
            "contract_check.json",
            "validator_results.json",
            "strict_audit.json",
        ],
        "errors": ["artifact response error"] if artifact_errors else [],
        "content_sha256": "",
    }
    report["content_sha256"] = canonical_hash(
        {key: value for key, value in report.items() if key != "content_sha256"}
    )
    leaf = {
        "schema_version": "1.0",
        "artifact_schema_version": "mocktest-leaf-evidence/v2",
        "run_id": run_id,
        "states": states,
        "gate_recommendation": (
            "ALLOW" if overall == "PASS" else ("ERROR" if overall == "ERROR" else "BLOCK")
        ),
        "finding_ids": [item["finding_id"] for item in findings],
        "evidence_refs": ["mocktest_report.json", "strict_audit.json"],
        "content_sha256": "",
    }
    leaf["content_sha256"] = canonical_hash(
        {key: value for key, value in leaf.items() if key != "content_sha256"}
    )
    events = []
    for tc_id in sorted(hops):
        for hop in sorted(hops[tc_id], key=lambda item: int(item.get("hop_index", 0))):
            events.append({"tc_id": tc_id, "kind": "COMPONENT_HOP", "payload": hop})
    execution_log = {
        "schema_version": "1.0",
        "artifact_schema_version": "mocktest-execution-log/v2",
        "execution_state": execution_state,
        "events": events,
    }

    # Replace migration-private filenames with their canonical v2 envelopes
    # only after all legacy evidence has been consumed.
    write_json(
        run_path / "scenario_events.json",
        {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-events/v2",
            "events": events,
        },
    )
    write_json(
        run_path / "contract_check.json",
        {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-contract-check/v2",
            "status": (
                "FAIL"
                if any(
                    item["severity"] == "FAIL" and item["origin"] == "CONTRACT_CHECK"
                    for item in findings
                )
                else (
                    "WARNING"
                    if any(
                        item["severity"] == "WARNING" and item["origin"] == "CONTRACT_CHECK"
                        for item in findings
                    )
                    else "PASS" if compat else "NOT_RUN"
                )
            ),
            "findings": [item for item in findings if item["origin"] == "CONTRACT_CHECK"],
        },
    )
    write_json(
        run_path / "validator_results.json",
        {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-validator-results/v2",
            "results": validator_rows,
        },
    )
    write_json(
        run_path / "strict_audit.json",
        {
            "schema_version": "1.0",
            "artifact_schema_version": "mocktest-audit/v2",
            "audit_state": audit_state,
            "violations": old_audit.get("errors", old_audit.get("violations", [])),
        },
    )
    write_json(run_path / "execution_log.json", execution_log)

    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "mocktest_report.json", report)
    (out / "mocktest_report.md").write_text(
        _render_report(report, extraction), encoding="utf-8", newline="\n"
    )
    write_json(out / "leaf_gate_evidence.json", leaf)
    write_json(out / "execution_log.json", execution_log)
    files = []
    for name, artifact_type, version in (
        ("mocktest_report.json", "mocktest_report", "mocktest-report/v2"),
        ("mocktest_report.md", "mocktest_report_view", "mocktest-report-markdown/v2"),
        ("leaf_gate_evidence.json", "leaf_gate_evidence", "mocktest-leaf-evidence/v2"),
        ("execution_log.json", "execution_log", "mocktest-execution-log/v2"),
    ):
        path = out / name
        files.append(
            {
                "artifact_id": f"{run_id}:{artifact_type}",
                "artifact_type": artifact_type,
                "artifact_schema_version": version,
                "path": name,
                "sha256": file_sha256(path),
            }
        )
    manifest_subject = {
        "schema_version": "1.0",
        "artifact_schema_version": "mocktest-bundle/v2",
        "run_id": run_id,
        "files": files,
    }
    manifest = {**manifest_subject, "bundle_sha256": canonical_hash(manifest_subject)}
    write_json(out / "bundle_manifest.json", manifest)
    return manifest
