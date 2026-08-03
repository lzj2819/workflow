"""Legacy v1 delivery adapter for retained strict validate-arch runs.

This module deliberately consumes the canonical strict-run artifacts.  It does
not simulate components or judge architecture itself.

New public runs use :mod:`mock_framework.canonical_contract` (`mocktest/v2`).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "mocktest/v1"
MockStatus = Literal["PASS", "FAIL", "ERROR"]
ExecutionStatus = Literal["COMPLETED", "ERROR"]
ValidationStatus = Literal["PASS", "FAIL", "NOT_RUN"]
GateRecommendation = Literal["ALLOW", "BLOCK", "ERROR"]
DEFECT_TYPES = {
    "MISSING_COMPONENT",
    "SCENARIO_NOT_SUPPORTED",
    "PRECONDITION_UNSUPPORTED",
    "POSTCONDITION_UNSUPPORTED",
    "MISSING_INTERFACE",
    "ERROR_CONTRACT_MISSING",
    "DATA_SCHEMA_MISMATCH",
    "INVALID_DEPENDENCY",
    "RESPONSIBILITY_GAP",
    "REQUIREMENT_NOT_COVERED",
    "QUALITY_ATTRIBUTE_VIOLATION",
    "TOOL_EXECUTION_ERROR",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class RunIdentity(StrictModel):
    project_id: str = ""
    node_id: str = ""
    parent_node_id: str = ""
    branch_id: str = ""
    architecture_artifact_id: str = ""
    testcase_artifact_id: str = ""
    source_prd_id: str = ""


class ArtifactRecord(StrictModel):
    artifact_id: str
    artifact_type: str
    path: str
    sha256: str = ""
    schema_version: str | None = None


class Finding(StrictModel):
    finding_id: str
    defect_type: str
    severity: Literal["FAIL", "WARNING", "ERROR"]
    scenario_id: str = ""
    dimension: str = ""
    components: list[str] = Field(default_factory=list)
    detail: str
    evidence_refs: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    scenario_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    interface_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    expected_behavior: str | None = None
    observed_or_simulated_behavior: str | None = None
    remediation_hint: str | None = None
    confidence: float | None = None


class Coverage(StrictModel):
    total_scenarios: int
    evaluated_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    warning_scenarios: int
    scenario_coverage: float
    requirement_ids: list[str] = Field(default_factory=list)
    covered_requirement_ids: list[str] = Field(default_factory=list)
    uncovered_requirement_ids: list[str] = Field(default_factory=list)


class MocktestReport(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    input_fingerprint: str = ""
    created_at: str
    status: MockStatus
    execution_status: ExecutionStatus
    validation_status: ValidationStatus
    identity: RunIdentity
    coverage: Coverage
    findings: list[Finding] = Field(default_factory=list)
    defect_counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    project_id: str = ""
    node_id: str = ""
    parent_node_id: str | None = None
    artifact_id: str = ""
    artifact_type: str = "mocktest_report"
    generator: str = "validate-arch"
    input_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    architecture_artifact_id: str = ""
    testcase_artifact_id: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    evaluated_scenarios: int = 0
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    requirement_coverage: dict[str, Any] = Field(default_factory=dict)
    scenario_coverage: float = 0.0
    unresolved_errors: list[str] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class LeafGateEvidence(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    mocktest_status: MockStatus
    gate_recommendation: GateRecommendation
    architecture_defect_count: int
    severe_defect_count: int
    uncovered_requirement_ids: list[str] = Field(default_factory=list)
    unvalidated_scenario_ids: list[str] = Field(default_factory=list)
    high_risk_components: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    project_id: str = ""
    node_id: str = ""
    parent_node_id: str | None = None
    artifact_id: str = ""
    artifact_type: str = "leaf_gate_evidence"
    created_at: str = ""
    generator: str = "validate-arch"
    status: MockStatus
    input_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    error_status: bool = False


class ExecutionLog(StrictModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    execution_status: ExecutionStatus
    started_at: str | None = None
    finished_at: str
    duration_ms: int | None = None
    model_context: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    component_calls: int = 0
    validator_calls: int = 0
    retry_count: int = 0
    cache_hits: int = 0
    human_interventions: int = 0
    input_hashes: dict[str, str] = Field(default_factory=dict)
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    project_id: str = ""
    node_id: str = ""
    parent_node_id: str | None = None
    artifact_id: str = ""
    artifact_type: str = "execution_log"
    created_at: str = ""
    generator: str = "validate-arch"
    status: MockStatus
    module: str = "mocktest"
    start_time: str | None = None
    end_time: str
    input_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    output_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    input_hash: str | None = None
    output_hash: str | None = None
    model: dict[str, Any] = Field(default_factory=dict)
    model_parameters: dict[str, Any] = Field(default_factory=dict)
    token_usage: int | None = None
    estimated_cost: float | None = None
    warning_count: int = 0
    error_type: str | None = None
    error_message: str | None = None


class FormalArtifactRef(StrictModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: Literal[
        "markdown_directory",
        "markdown_file",
        "architecture_json",
        "gherkin_file",
        "gherkin_directory",
        "testcases_json",
    ]
    path: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    source_prd_id: str = Field(min_length=1)


class FormalInputManifest(StrictModel):
    schema_version: Literal["mocktest-input/v1", "mocktest-input/v2"] = "mocktest-input/v2"
    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    parent_node_id: str | None = None
    source_prd_id: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    generator: str = Field(min_length=1)
    status: Literal["COMPLETED", "PASS"] = "PASS"
    mode: Literal["strict", "validate-only"] = "strict"
    architecture: FormalArtifactRef
    testcases: FormalArtifactRef

    @model_validator(mode="after")
    def validate_branches(self) -> "FormalInputManifest":
        if self.architecture.artifact_type not in {
            "markdown_directory",
            "markdown_file",
            "architecture_json",
        }:
            raise ValueError("architecture branch must contain an architecture artifact")
        if self.testcases.artifact_type not in {
            "gherkin_file",
            "gherkin_directory",
            "testcases_json",
        }:
            raise ValueError("testcases branch must contain a testcase artifact")
        identity_fields = (
            ("project_id", "node_id", "source_prd_id")
            if self.schema_version == "mocktest-input/v2"
            else ("run_id", "project_id", "node_id", "source_prd_id")
        )
        for name, artifact in (
            ("architecture", self.architecture),
            ("testcases", self.testcases),
        ):
            for field in identity_fields:
                if getattr(artifact, field) != getattr(self, field):
                    raise ValueError(f"{name}.{field} does not match manifest.{field}")
        expected_v1 = {
            "markdown_directory": "architecture-source/v1",
            "markdown_file": "architecture-source/v1",
            "architecture_json": "architecture/v1",
            "gherkin_file": "testcases-source/v1",
            "gherkin_directory": "testcases-source/v1",
            "testcases_json": "testcases/v1",
        }
        expected_v2 = {
            "markdown_directory": "architecture-source/v1",
            "markdown_file": "architecture-source/v1",
            "architecture_json": "architecture/v2",
            "gherkin_file": "feature/v2",
            "gherkin_directory": "feature/v2",
            "testcases_json": "testcases/v2",
        }
        expected = expected_v2 if self.schema_version == "mocktest-input/v2" else expected_v1
        for artifact in (self.architecture, self.testcases):
            if artifact.schema_version != expected[artifact.artifact_type]:
                raise ValueError(
                    f"{artifact.artifact_type} requires schema {expected[artifact.artifact_type]}"
                )
        return self


class NormalizedArchitecture(StrictModel):
    schema_version: Literal["architecture/v1"] = "architecture/v1"
    run_id: str
    project_id: str
    node_id: str
    source_prd_id: str
    artifact_id: str
    artifact_type: Literal["architecture"] = "architecture"
    created_at: str
    generator: str = "validate-arch"
    status: Literal["COMPLETED"] = "COMPLETED"
    source: ArtifactRecord
    requirement_ids: list[str] = Field(default_factory=list)
    architecture: dict[str, Any]


class NormalizedTestcases(StrictModel):
    schema_version: Literal["testcases/v1"] = "testcases/v1"
    run_id: str
    project_id: str
    node_id: str
    source_prd_id: str
    artifact_id: str
    artifact_type: Literal["testcases"] = "testcases"
    created_at: str
    generator: str = "validate-arch"
    status: Literal["COMPLETED"] = "COMPLETED"
    source: ArtifactRecord
    requirement_ids: list[str] = Field(default_factory=list)
    testcases: list[dict[str, Any]]


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"parse_status": "invalid_jsonl", "raw": line[:200]})
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_formal_input_manifest(path: str | Path) -> tuple[FormalInputManifest, Path]:
    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"formal input manifest not found: {manifest_path}")
    manifest = FormalInputManifest.model_validate(_read_json(manifest_path, {}))
    return manifest, manifest_path


def _source_path(ref: FormalArtifactRef, base_dir: Path) -> Path:
    path = Path(ref.path)
    path = path if path.is_absolute() else (base_dir / path).resolve()
    if ref.artifact_type in {"architecture_json", "testcases_json"}:
        raw = _read_json(path, {})
        artifact_version = str(raw.get("artifact_schema_version") or raw.get("schema_version") or "")
        if artifact_version in {"architecture/v2", "testcases/v2"}:
            if artifact_version != ref.schema_version:
                raise ValueError(
                    f"{ref.artifact_type}.schema_version does not match canonical artifact"
                )
            if str(raw.get("artifact_id") or "") != ref.artifact_id:
                raise ValueError(f"{ref.artifact_type}.artifact_id does not match artifact reference")
            for field in ("run_id", "project_id", "node_id"):
                if str(raw.get(field) or "") != str(getattr(ref, field) or ""):
                    raise ValueError(f"{ref.artifact_type}.{field} does not match artifact reference")
            if not path.exists():
                raise FileNotFoundError(f"formal input artifact not found: {path}")
            return path
        normalized: NormalizedArchitecture | NormalizedTestcases
        if ref.artifact_type == "architecture_json":
            normalized = NormalizedArchitecture.model_validate(_read_json(path, {}))
        else:
            normalized = NormalizedTestcases.model_validate(_read_json(path, {}))
        for field in ("run_id", "project_id", "node_id", "source_prd_id"):
            if getattr(normalized, field) != getattr(ref, field):
                raise ValueError(f"{ref.artifact_type}.{field} does not match artifact reference")
        if normalized.artifact_id != ref.artifact_id:
            raise ValueError(f"{ref.artifact_type}.artifact_id does not match artifact reference")
        source = Path(normalized.source.path)
        path = source if source.is_absolute() else (path.parent / source).resolve()
    if not path.exists():
        raise FileNotFoundError(f"formal input artifact not found: {path}")
    return path


def resolve_formal_sources(
    manifest: FormalInputManifest, manifest_path: str | Path
) -> tuple[str, str]:
    base = Path(manifest_path).resolve().parent
    architecture = _source_path(manifest.architecture, base)
    testcases = _source_path(manifest.testcases, base)
    return str(architecture), str(testcases)


def formal_protocol_metadata(manifest: FormalInputManifest) -> dict[str, Any]:
    identity = {
        "project_id": manifest.project_id,
        "node_id": manifest.node_id,
        "parent_node_id": manifest.parent_node_id or "",
        "source_prd_id": manifest.source_prd_id,
        "architecture_artifact_id": manifest.architecture.artifact_id,
        "testcase_artifact_id": manifest.testcases.artifact_id,
    }
    return {
        "formal_mode": True,
        "schema_version": manifest.schema_version,
        "run_id": manifest.run_id,
        "identity": identity,
        "architecture": {
            **identity,
            "run_id": manifest.architecture.run_id,
            "schema_version": manifest.architecture.schema_version,
        },
        "testcase": {
            **identity,
            "run_id": manifest.testcases.run_id,
            "schema_version": manifest.testcases.schema_version,
        },
    }


def exit_code_for_report(report: MocktestReport) -> int:
    if report.status == "PASS":
        return 0
    if report.status == "FAIL":
        return 2
    error_text = " ".join(report.errors).lower()
    if any(token in error_text for token in ("schema", "identity", "does not match")):
        return 5
    if any(token in error_text for token in ("dependency", "configuration", "not found")):
        return 3
    return 4


def validate_branch_identity(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Reject only explicit conflicts; missing optional IDs remain compatible."""
    errors = []
    for key in RunIdentity.model_fields:
        left, right = str(expected.get(key) or ""), str(actual.get(key) or "")
        if left and right and left != right:
            errors.append(f"branch identity mismatch: {key} expected={left!r} actual={right!r}")
    return errors


def _defect_type(kind: str, dimension: str) -> str:
    kind_token = kind.lower()
    token = f"{kind_token} {dimension}".lower()
    if "missing_component" in kind_token or "component_missing" in kind_token:
        return "MISSING_COMPONENT"
    if "uncovered_requirement" in kind_token or "requirement_not_covered" in kind_token:
        return "REQUIREMENT_NOT_COVERED"
    if "missing_error" in kind_token or "error_contract" in kind_token:
        return "ERROR_CONTRACT_MISSING"
    if "precondition" in kind_token:
        return "PRECONDITION_UNSUPPORTED"
    if "missing_interface" in kind_token or "endpoint_missing" in kind_token:
        return "MISSING_INTERFACE"
    if "depend" in kind_token or "orphan" in kind_token:
        return "INVALID_DEPENDENCY"
    if any(word in kind_token for word in ("schema", "field", "type_conflict", "return_value")):
        return "DATA_SCHEMA_MISMATCH"
    if "interface" in token or "endpoint" in token:
        return "MISSING_INTERFACE"
    if dimension == "performance":
        return "QUALITY_ATTRIBUTE_VIOLATION"
    if dimension == "state":
        return "POSTCONDITION_UNSUPPORTED"
    if dimension == "structure":
        return "RESPONSIBILITY_GAP"
    if dimension == "flow":
        return "SCENARIO_NOT_SUPPORTED"
    if dimension == "contract":
        return "PRECONDITION_UNSUPPORTED"
    return "SCENARIO_NOT_SUPPORTED"


def _finding_id(item: dict[str, Any]) -> str:
    stable = {
        key: item.get(key)
        for key in ("defect_type", "scenario_id", "dimension", "components", "detail")
    }
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "DEF-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def _requirements(plan: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for case in plan.get("test_cases", []):
        blob = json.dumps(case, ensure_ascii=False)
        found.update(re.findall(r"(?:REQ|FR|NFR)-[A-Za-z0-9_.-]+", blob, flags=re.I))
    return sorted(found)


def _collect_findings(
    vals: list[dict[str, Any]], compat: dict[str, Any], plan: dict[str, Any]
) -> list[Finding]:
    raw_findings: list[dict[str, Any]] = []
    cases = {str(case.get("test_case_id")): case for case in plan.get("test_cases", [])}
    for item in vals:
        tc_id, result = str(item.get("test_case_id", "")), item.get("result", {})
        case = cases.get(tc_id, {})
        requirement_ids = sorted(
            set(re.findall(r"(?:REQ|FR|NFR)-[A-Za-z0-9_.-]+", json.dumps(case), re.I))
        )
        component_ids = [str(x) for x in case.get("expectations", {}).get("touched_components", [])]
        failure_analysis = result.get("failure_analysis", {})
        if isinstance(failure_analysis, list):
            failure_analysis = next(
                (entry for entry in failure_analysis if isinstance(entry, dict)), {}
            )
        if not isinstance(failure_analysis, dict):
            failure_analysis = {}
        for dimension in (
            "structure",
            "flow",
            "state",
            "contract",
            "performance",
            "interface_compat",
        ):
            verdict = result.get(dimension, {})
            status = str(verdict.get("status", "PASS")).upper()
            if status not in {"FAIL", "WARNING"}:
                continue
            detail = str(verdict.get("detail") or verdict.get("reason") or f"{dimension} {status}")
            raw_findings.append(
                {
                    "defect_type": _defect_type("", dimension),
                    "severity": status,
                    "scenario_id": tc_id,
                    "dimension": dimension,
                    "components": [],
                    "detail": detail,
                    "evidence_refs": ["val_results.json"],
                    "requirement_ids": requirement_ids,
                    "scenario_ids": [tc_id],
                    "component_ids": component_ids,
                    "evidence": [{"artifact": "val_results.json", "dimension": dimension}],
                    "expected_behavior": str(verdict.get("expected") or "scenario must pass"),
                    "observed_or_simulated_behavior": detail,
                    "remediation_hint": str(
                        failure_analysis.get("suggestion")
                        or "review architecture evidence"
                    ),
                    "confidence": verdict.get("confidence"),
                }
            )
    groups = [("", compat.get("global_findings", []))]
    groups.extend(
        (str(tc), data.get("findings", [])) for tc, data in compat.get("per_scenario", {}).items()
    )
    for tc_id, findings in groups:
        for finding in findings:
            status = str(finding.get("severity", "WARNING")).upper()
            raw_findings.append(
                {
                    "defect_type": _defect_type(str(finding.get("kind", "")), "interface_compat"),
                    "severity": status if status in {"FAIL", "WARNING"} else "WARNING",
                    "scenario_id": tc_id,
                    "dimension": "interface_compat",
                    "components": [str(x) for x in finding.get("components", [])],
                    "detail": str(
                        finding.get("detail") or finding.get("kind") or "compatibility finding"
                    ),
                    "evidence_refs": ["compat.json"],
                    "requirement_ids": [str(x) for x in finding.get("requirement_ids", [])],
                    "scenario_ids": [tc_id] if tc_id else [],
                    "component_ids": [str(x) for x in finding.get("components", [])],
                    "interface_ids": [str(x) for x in finding.get("interfaces", [])],
                    "evidence": [{"artifact": "compat.json", "kind": finding.get("kind", "")}],
                    "expected_behavior": str(
                        finding.get("expected") or "interface contract must match"
                    ),
                    "observed_or_simulated_behavior": str(
                        finding.get("detail") or finding.get("kind") or "compatibility finding"
                    ),
                    "remediation_hint": str(
                        finding.get("remediation_hint") or "align interface contract"
                    ),
                    "confidence": finding.get("confidence"),
                }
            )
    unique: dict[str, Finding] = {}
    for item in raw_findings:
        item["finding_id"] = _finding_id(item)
        unique[item["finding_id"]] = Finding.model_validate(item)
    return sorted(unique.values(), key=lambda finding: finding.finding_id)


def _markdown(report: MocktestReport) -> str:
    lines = [
        "# Mocktest Report",
        "",
        f"- Schema: `{report.schema_version}`",
        f"- Run: `{report.run_id}`",
        f"- Status: **{report.status}**",
        f"- Execution: `{report.execution_status}`",
        f"- Validation: `{report.validation_status}`",
        "",
        "## Coverage",
        "",
        f"- Scenarios: {report.coverage.evaluated_scenarios}/{report.coverage.total_scenarios} evaluated",
        f"- Passed / failed / warning: {report.coverage.passed_scenarios} / {report.coverage.failed_scenarios} / {report.coverage.warning_scenarios}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("No architecture defects were found.")
    for finding in report.findings:
        lines.append(
            f"- `{finding.finding_id}` {finding.severity} `{finding.defect_type}`: {finding.detail}"
        )
    if report.errors:
        lines.extend(["", "## Execution errors", ""] + [f"- {error}" for error in report.errors])
    return "\n".join(lines) + "\n"


def _ground_truth_metrics(
    run_path: Path, findings: list[Finding], duration_ms: int | None
) -> dict[str, Any]:
    path = run_path / "ground_truth.json"
    if not path.is_file():
        return {
            "injected_defect_count": None,
            "detected_defect_count": None,
            "true_positive_count": None,
            "false_positive_count": None,
            "false_negative_count": None,
            "detection_time_ms": duration_ms,
        }
    truth = _read_json(path, {})
    injected = truth.get("injected_defects", [])
    matched_findings: set[str] = set()
    detected = 0
    for defect in injected:
        for finding in findings:
            if finding.finding_id in matched_findings:
                continue
            same_type = finding.defect_type == defect.get("defect_type")
            scenario_match = not defect.get("scenario_ids") or bool(
                set(defect.get("scenario_ids", [])) & set(finding.scenario_ids)
            )
            component_match = not defect.get("component_ids") or bool(
                set(defect.get("component_ids", [])) & set(finding.component_ids)
            )
            if same_type and scenario_match and component_match:
                detected += 1
                matched_findings.add(finding.finding_id)
                break
    return {
        "injected_defect_count": len(injected),
        "detected_defect_count": detected,
        "true_positive_count": detected,
        "false_positive_count": len(
            [
                finding
                for finding in findings
                if finding.defect_type != "TOOL_EXECUTION_ERROR"
                and finding.finding_id not in matched_findings
            ]
        ),
        "false_negative_count": max(0, len(injected) - detected),
        "detection_time_ms": duration_ms,
    }


def _numeric_call_total(calls: list[dict[str, Any]], field: str) -> int | float | None:
    values: list[int | float] = []
    for row in calls:
        value = row.get(field)
        if isinstance(value, (int, float)):
            values.append(value)
    return sum(values) if values else None


def _active_artifact_errors(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return failures that have not been superseded by a successful retry.

    Strict runs retain every attempt for auditability.  A transient malformed
    response must not turn a successfully re-consumed scenario into an ERROR.
    """
    active: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("event") == "artifact_recovered":
            key = str(record.get("attempt_key") or "")
            if key:
                active.pop(key, None)
            continue
        if not record.get("artifact_error"):
            continue
        key = str(record.get("attempt_key") or "")
        if not key:
            tc_id = str(record.get("test_case_id") or "")
            if record.get("artifact_error") == "invalid_validator_response":
                key = f"validator:{tc_id}"
            else:
                key = f"component:{tc_id}:{record.get('hop_index', '')}"
        active[key] = record
    return list(active.values())


def publish_strict_run(
    run_dir: str | Path,
    output_dir: str | Path,
    expected_identity: dict[str, Any] | None = None,
    run_id: str | None = None,
    random_seed: int | None = None,
    model_context: dict[str, Any] | None = None,
    include_source_refs: bool = True,
) -> MocktestReport:
    """Publish the four formal artifacts from one canonical strict run."""
    run_path, delivery = Path(run_dir), Path(output_dir)
    delivery.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    plan = _read_json(run_path / "plan_with_val.json", _read_json(run_path / "plan.json", {}))
    vals = _read_json(run_path / "val_results.json", [])
    compat = _read_json(run_path / "compat.json", {})
    audit = _read_json(run_path / "strict_audit.json", {})
    state = _read_json(run_path / "driver_state.json", {})
    manifest = plan.get("run_manifest", {})
    protocol_metadata = plan.get("protocol_metadata", {})
    architecture_identity = protocol_metadata.get("architecture", {})
    testcase_identity = protocol_metadata.get("testcase", {})
    actual_identity = (
        protocol_metadata.get("identity", {}) or architecture_identity or testcase_identity
    )
    expected = expected_identity or {}
    identity_errors = validate_branch_identity(expected, actual_identity)
    identity_errors.extend(validate_branch_identity(architecture_identity, testcase_identity))
    identity_errors.extend(validate_branch_identity(actual_identity, architecture_identity))
    identity_errors.extend(validate_branch_identity(actual_identity, testcase_identity))
    if protocol_metadata.get("formal_mode"):
        required = ("project_id", "node_id", "source_prd_id")
        for key in required:
            if not actual_identity.get(key):
                identity_errors.append(f"formal identity missing: {key}")
        formal_run_id = str(protocol_metadata.get("run_id") or "")
        for branch_name, branch in (
            ("architecture", architecture_identity),
            ("testcase", testcase_identity),
        ):
            if branch.get("run_id") != formal_run_id:
                identity_errors.append(f"{branch_name}.run_id does not match formal run_id")
            if not branch.get("schema_version"):
                identity_errors.append(f"{branch_name}.schema_version is missing")
    identity = RunIdentity.model_validate(
        {**actual_identity, **{k: v for k, v in expected.items() if v}}
    )
    calls = _read_jsonl(run_path / "subagent_calls.jsonl")
    artifact_errors = _active_artifact_errors(_read_jsonl(run_path / "artifact_errors.jsonl"))
    errors = list(identity_errors)
    audit_errors = [str(x) for x in audit.get("errors", [])]
    semantic_errors = _read_json(run_path / "semantic_errors.json", [])
    audit_status = str(audit.get("status", "UNKNOWN"))
    architecture_gate_failure = bool(semantic_errors) and not identity_errors
    execution_error = (
        bool(identity_errors)
        or bool(artifact_errors)
        or audit_status != "PASS"
        and not architecture_gate_failure
    )
    if audit_status == "UNKNOWN":
        errors.append("strict audit artifact is missing or has no status")
    if execution_error:
        errors.extend(audit_errors or [str(x) for x in semantic_errors])
        errors.extend(
            str(item.get("artifact_error") or item.get("parse_status") or "artifact error")
            for item in artifact_errors
        )

    findings = _collect_findings(vals, compat, plan)
    for artifact_error in artifact_errors:
        item = {
            "defect_type": "TOOL_EXECUTION_ERROR",
            "severity": "ERROR",
            "scenario_id": str(artifact_error.get("test_case_id", "")),
            "dimension": "execution",
            "components": (
                [str(artifact_error["component"])] if artifact_error.get("component") else []
            ),
            "detail": str(
                artifact_error.get("artifact_error")
                or artifact_error.get("parse_status")
                or "artifact error"
            ),
            "evidence_refs": ["artifact_errors.jsonl"],
        }
        item["finding_id"] = _finding_id(item)
        findings.append(Finding.model_validate(item))
    if architecture_gate_failure:
        for detail in semantic_errors:
            item = {
                "defect_type": "SCENARIO_NOT_SUPPORTED",
                "severity": "FAIL",
                "scenario_id": "",
                "dimension": "semantic_gate",
                "components": [],
                "detail": str(detail),
                "evidence_refs": ["semantic_errors.json"],
            }
            item["finding_id"] = _finding_id(item)
            findings.append(Finding.model_validate(item))
    counts = {key: 0 for key in sorted(DEFECT_TYPES)}
    for finding in findings:
        counts[finding.defect_type] = counts.get(finding.defect_type, 0) + 1
    scenario_status = {
        str(item.get("test_case_id")): str(item.get("result", {}).get("overall", "MISSING")).upper()
        for item in vals
    }
    total = len(plan.get("plans", [])) or len(plan.get("test_cases", []))
    evaluated = len(scenario_status)
    requirements = _requirements(plan)
    covered_requirements = requirements if evaluated == total and total else []
    coverage = Coverage(
        total_scenarios=total,
        evaluated_scenarios=evaluated,
        passed_scenarios=sum(v == "PASS" for v in scenario_status.values()),
        failed_scenarios=sum(v in {"FAIL", "MISSING"} for v in scenario_status.values()),
        warning_scenarios=sum(v == "WARNING" for v in scenario_status.values()),
        scenario_coverage=round(evaluated / total, 4) if total else 0.0,
        requirement_ids=requirements,
        covered_requirement_ids=covered_requirements,
        uncovered_requirement_ids=sorted(set(requirements) - set(covered_requirements)),
    )
    started_at = state.get("started_at")
    duration_ms = None
    if started_at:
        try:
            duration_ms = max(
                0,
                int(
                    (
                        datetime.fromisoformat(now) - datetime.fromisoformat(str(started_at))
                    ).total_seconds()
                    * 1000
                ),
            )
        except ValueError:
            duration_ms = None
    if execution_error:
        top_status: MockStatus = "ERROR"
        execution_status: ExecutionStatus = "ERROR"
        validation_status: ValidationStatus = "NOT_RUN"
    elif findings or any(v != "PASS" for v in scenario_status.values()) or evaluated != total:
        top_status, execution_status, validation_status = "FAIL", "COMPLETED", "FAIL"
    else:
        top_status, execution_status, validation_status = "PASS", "COMPLETED", "PASS"
    actual_run_id = run_id or str(protocol_metadata.get("run_id") or uuid.uuid4())
    source_evidence = [
        name
        for name in (
            "plan_with_val.json",
            "hops.json",
            "compat.json",
            "val_results.json",
            "strict_audit.json",
        )
        if (run_path / name).is_file()
    ]
    evidence = source_evidence if include_source_refs else []
    input_artifacts = [
        ArtifactRecord(
            artifact_id=str(name),
            artifact_type=str(name),
            path=str(item.get("path", "")),
            sha256=str(item.get("sha256", "")),
            schema_version=item.get("schema_version"),
        )
        for name, item in manifest.get("inputs", {}).items()
    ]
    experiment_metrics = _ground_truth_metrics(run_path, findings, duration_ms)
    execution_metadata = {
        "duration_ms": duration_ms,
        "component_calls": sum(row.get("role") == "component" for row in calls),
        "validator_calls": sum(row.get("role") == "validator" for row in calls),
        "token_usage": _numeric_call_total(calls, "token_usage"),
        "estimated_cost": _numeric_call_total(calls, "estimated_cost"),
        "human_interventions": int(state.get("human_interventions", 0)),
        **experiment_metrics,
    }
    report = MocktestReport(
        run_id=actual_run_id,
        input_fingerprint=str(manifest.get("run_id", "")),
        created_at=now,
        status=top_status,
        execution_status=execution_status,
        validation_status=validation_status,
        identity=identity,
        coverage=coverage,
        findings=findings,
        defect_counts=counts,
        metrics={
            "strict_audit_status": audit_status,
            "component_hops": sum(len(v) for v in _read_json(run_path / "hops.json", {}).values()),
            "validator_results": len(vals),
            **experiment_metrics,
        },
        evidence_refs=evidence,
        errors=sorted(set(errors)),
        project_id=identity.project_id,
        node_id=identity.node_id,
        parent_node_id=identity.parent_node_id or None,
        artifact_id=f"mocktest-report-{actual_run_id}",
        input_artifacts=input_artifacts,
        requirement_ids=requirements,
        architecture_artifact_id=identity.architecture_artifact_id,
        testcase_artifact_id=identity.testcase_artifact_id,
        summary={
            "total_scenarios": total,
            "evaluated_scenarios": evaluated,
            "passed_scenarios": coverage.passed_scenarios,
            "failed_scenarios": coverage.failed_scenarios,
            "warning_scenarios": coverage.warning_scenarios,
            "defect_count": len(findings),
        },
        evaluated_scenarios=evaluated,
        passed_scenarios=coverage.passed_scenarios,
        failed_scenarios=coverage.failed_scenarios,
        requirement_coverage={
            "total": len(requirements),
            "covered": len(covered_requirements),
            "uncovered_requirement_ids": coverage.uncovered_requirement_ids,
            "rate": (
                round(len(covered_requirements) / len(requirements), 4) if requirements else 0.0
            ),
        },
        scenario_coverage=coverage.scenario_coverage,
        unresolved_errors=sorted(set(errors)),
        execution_metadata=execution_metadata,
    )
    report_file = delivery / "mocktest_report.json"
    report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (delivery / "mocktest_report.md").write_text(_markdown(report), encoding="utf-8")
    component_counts: dict[str, int] = {}
    for finding in findings:
        for component in finding.components:
            component_counts[component] = component_counts.get(component, 0) + 1
    recommendations: dict[MockStatus, GateRecommendation] = {
        "PASS": "ALLOW",
        "FAIL": "BLOCK",
        "ERROR": "ERROR",
    }
    architecture_findings = [
        finding for finding in findings if finding.defect_type != "TOOL_EXECUTION_ERROR"
    ]
    leaf = LeafGateEvidence(
        run_id=actual_run_id,
        mocktest_status=top_status,
        gate_recommendation=recommendations[top_status],
        architecture_defect_count=len(architecture_findings),
        severe_defect_count=sum(f.severity == "FAIL" for f in architecture_findings),
        uncovered_requirement_ids=coverage.uncovered_requirement_ids,
        unvalidated_scenario_ids=sorted(
            set(str(p.get("test_case_id", "")) for p in plan.get("plans", []))
            - set(scenario_status)
        ),
        high_risk_components=sorted(component_counts, key=lambda c: (-component_counts[c], c))[:10],
        evidence_refs=["mocktest_report.json", *evidence],
        errors=report.errors,
        project_id=identity.project_id,
        node_id=identity.node_id,
        parent_node_id=identity.parent_node_id or None,
        artifact_id=f"leaf-gate-evidence-{actual_run_id}",
        created_at=now,
        status=top_status,
        input_artifacts=input_artifacts,
        requirement_ids=requirements,
        error_status=top_status == "ERROR",
    )
    (delivery / "leaf_gate_evidence.json").write_text(
        leaf.model_dump_json(indent=2), encoding="utf-8"
    )
    input_hashes = {str(k): str(v.get("sha256", "")) for k, v in manifest.get("inputs", {}).items()}
    artifacts = {name: _sha256(run_path / name) for name in source_evidence}
    role_counts = {
        role: sum(row.get("role") == role for row in calls) for role in ("component", "validator")
    }
    retries = sum(
        max(0, int(row.get("attempt", 1)) - 1)
        for row in calls
        if str(row.get("attempt", "1")).isdigit()
    )
    resolved_model_context = dict(plan.get("model_context", {}))
    resolved_model_context.update(
        {key: value for key, value in (model_context or {}).items() if value not in (None, "")}
    )
    output_artifacts = [
        ArtifactRecord(
            artifact_id=report.artifact_id,
            artifact_type=report.artifact_type,
            path=str(report_file),
            sha256=_sha256(report_file),
            schema_version=report.schema_version,
        ),
        ArtifactRecord(
            artifact_id=leaf.artifact_id,
            artifact_type=leaf.artifact_type,
            path=str(delivery / "leaf_gate_evidence.json"),
            sha256=_sha256(delivery / "leaf_gate_evidence.json"),
            schema_version=leaf.schema_version,
        ),
    ]
    output_hash = hashlib.sha256(
        "".join(sorted(item.sha256 for item in output_artifacts)).encode("utf-8")
    ).hexdigest()
    log = ExecutionLog(
        run_id=actual_run_id,
        execution_status=execution_status,
        finished_at=now,
        model_context=resolved_model_context,
        random_seed=random_seed,
        component_calls=role_counts["component"],
        validator_calls=role_counts["validator"],
        retry_count=retries,
        cache_hits=len(state.get("cache_hits", [])),
        input_hashes=input_hashes,
        artifact_hashes=artifacts,
        events=[
            {"event": "strict_audit", "status": audit_status},
            {"event": "publish", "status": top_status},
        ],
        project_id=identity.project_id,
        node_id=identity.node_id,
        parent_node_id=identity.parent_node_id or None,
        artifact_id=f"execution-log-{actual_run_id}",
        created_at=now,
        status=top_status,
        started_at=str(started_at) if started_at else None,
        start_time=str(started_at) if started_at else None,
        end_time=now,
        duration_ms=duration_ms,
        input_artifacts=input_artifacts,
        output_artifacts=output_artifacts,
        input_hash=str(manifest.get("run_id") or "") or None,
        output_hash=output_hash,
        model=resolved_model_context,
        model_parameters=plan.get("model_parameters", {}),
        token_usage=(
            int(execution_metadata["token_usage"])
            if execution_metadata["token_usage"] is not None
            else None
        ),
        estimated_cost=(
            float(execution_metadata["estimated_cost"])
            if execution_metadata["estimated_cost"] is not None
            else None
        ),
        human_interventions=int(execution_metadata["human_interventions"]),
        warning_count=coverage.warning_scenarios,
        error_type=("CONTRACT_ERROR" if top_status == "ERROR" else None),
        error_message=("; ".join(report.errors) if report.errors else None),
    )
    (delivery / "execution_log.json").write_text(log.model_dump_json(indent=2), encoding="utf-8")
    return report


def write_schemas(output_dir: str | Path) -> None:
    """Copy the checked-in v2 schema registry.

    Schemas are no longer regenerated from several overlapping legacy models;
    doing so previously recreated v1 files and silently changed the public
    contract depending on which CLI command ran last.
    """
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    registry = Path(__file__).resolve().parents[2] / "schemas"
    for source in sorted(registry.glob("*.schema.json"), key=lambda item: item.name):
        destination = target / source.name
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
