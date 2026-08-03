from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mock_framework.canonical_contract import (
    DELIVERY_FILES,
    WORKSPACE_FILES,
    canonical_hash,
    derive_overall,
    initialize_workspace,
    load_canonical_pair,
    publish_canonical_bundle,
    render_feature_v2,
)


def architecture(*, mode: str = "top_level", flows: list[dict] | None = None) -> dict:
    payload = {
        "design_context": {"scope": "notes", "external_systems": [{"id": "EXT-CLIENT"}]},
        "nodes": [
            {"id": "CMP-API", "responsibility": "accept note requests"},
            {"id": "CMP-STORE", "responsibility": "store notes"},
        ],
        "contracts": [
            {
                "id": "API-NOTE-CREATE",
                "provider_id": "CMP-API",
                "consumer_ids": ["EXT-CLIENT"],
                "protocol": "HTTP",
                "type": "api",
                "schema_fields": ["text"],
                "trigger": "create note",
                "side_effects": "none",
                "error_semantics": "400",
                "timeout": "1s",
                "retry": "none",
                "idempotency": "key",
                "requirement_ids": ["REQ-NOTE-001"],
                "source_refs": ["REQ-NOTE-001"],
            },
            {
                "id": "CMD-NOTE-STORE",
                "provider_id": "CMP-STORE",
                "consumer_ids": ["CMP-API"],
                "protocol": "internal",
                "type": "command",
                "schema_fields": ["text"],
                "trigger": "store note",
                "side_effects": "write",
                "error_semantics": "error",
                "timeout": "1s",
                "retry": "none",
                "idempotency": "key",
                "requirement_ids": ["REQ-NOTE-001"],
                "source_refs": ["REQ-NOTE-001"],
            },
        ],
        "inherited_contracts": [],
        "runtime_flows": (
            flows
            if flows is not None
            else [
                {
                    "id": "FLOW-NOTE-CREATE",
                    "requirement_ids": ["REQ-NOTE-001"],
                    "steps": [
                        {
                            "order": 1,
                            "from_id": "EXT-CLIENT",
                            "to_id": "CMP-API",
                            "contract_id": "API-NOTE-CREATE",
                            "action": "create note",
                        },
                        {
                            "order": 2,
                            "from_id": "CMP-API",
                            "to_id": "CMP-STORE",
                            "contract_id": "CMD-NOTE-STORE",
                            "action": "store note",
                        },
                    ],
                }
            ]
        ),
        "state_ownership": [],
        "review": {"status": "approved", "semantic_hash": ""},
    }
    model = {
        "schema_version": "1.0",
        "artifact_schema_version": "architecture/v2",
        "run_id": "run-001",
        "project_id": "notes",
        "node_id": "SYS-NOTES",
        "parent_node_id": None,
        "artifact_id": "ARCH-NOTES",
        "artifact_type": "architecture",
        "created_at": "2026-08-02T00:00:00Z",
        "generator": "prd-to-architecture-skill",
        "status": "PASS",
        "architecture_status": "complete",
        "ready_for_downstream": True,
        "source_prd_id": "PRD-NOTES",
        "input_artifacts": [],
        "requirement_ids": ["REQ-NOTE-001"],
        "architecture_mode": mode,
        "operation": "new",
        "depth": 0 if mode == "top_level" else 1,
        "max_depth": 3,
        "node_history": [],
        "authority_scope": {},
        "section_order": [],
        "components": [],
        "interfaces": [],
        "dependencies": [],
        "complexity": 4,
        "risks": [],
        "modules": [],
        "payload": payload,
        "content_sha256": "",
    }
    subject = copy.deepcopy(model)
    subject.pop("created_at")
    subject.pop("content_sha256")
    subject["payload"].pop("review")
    model["content_sha256"] = canonical_hash(subject)
    model["payload"]["review"]["semantic_hash"] = model["content_sha256"]
    return model


def case_model(*, multiple_when: bool = False) -> dict:
    steps = [
        {
            "phase": "given",
            "keyword": "Given",
            "text": "the client is ready",
            "source_field": "given",
            "source_index": 0,
        },
        {
            "phase": "when",
            "keyword": "When",
            "text": "the client creates a note",
            "source_field": "when",
            "source_index": 0,
        },
    ]
    if multiple_when:
        steps.append(
            {
                "phase": "when",
                "keyword": "When",
                "text": "the client reads the note",
                "source_field": "when",
                "source_index": 1,
            }
        )
    steps.append(
        {
            "phase": "then",
            "keyword": "Then",
            "text": "the note is returned",
            "source_field": "then",
            "source_index": 0,
        }
    )
    return {
        "schema_version": "1.0",
        "artifact_schema_version": "testcases/v2",
        "run_id": "run-001",
        "project_id": "notes",
        "node_id": "SYS-NOTES",
        "parent_node_id": None,
        "artifact_id": "TEST-NOTES",
        "artifact_type": "testcases",
        "created_at": "2026-08-02T00:00:00Z",
        "generator": "prd-to-gherkin",
        "status": "PASS",
        "input_artifacts": ["PRD-NOTES"],
        "requirement_ids": ["REQ-NOTE-001"],
        "source_prd": {"artifact_id": "PRD-NOTES", "sha256": "a" * 64},
        "render_contract": {"feature_format_version": "feature/v2"},
        "blocked_items": [],
        "testcases": [
            {
                "tc_id": "TC-AC-REQ-NOTE-001-MAIN",
                "scenario_id": "SC-AC-REQ-NOTE-001-MAIN",
                "acceptance_contract_id": "AC-REQ-NOTE-001",
                "requirement_ids": ["REQ-NOTE-001"],
                "source_kinds": ["explicit"],
                "kind": "main",
                "source_index": 0,
                "title": "create note",
                "render_mode": "SCENARIO",
                "test_obligation": {},
                "steps": steps,
                "evidence_refs": ["REQ-NOTE-001"],
            }
        ],
    }


def write_pair(tmp_path: Path, arch: dict, tests: dict) -> tuple[Path, Path]:
    arch_path, test_path = tmp_path / "architecture.json", tmp_path / "testcases.json"
    arch_path.write_text(json.dumps(arch, ensure_ascii=False), encoding="utf-8")
    test_path.write_text(json.dumps(tests, ensure_ascii=False), encoding="utf-8")
    return arch_path, test_path


@pytest.mark.parametrize("mode", ["top_level", "decompose"])
def test_v2_modes_share_one_ir_and_unique_binding(tmp_path: Path, mode: str) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(mode=mode), case_model())
    result = load_canonical_pair(arch_path, test_path)
    binding = result.extraction_report["bindings"][0]
    assert result.normalized_input["architecture"]["mode"] == mode
    assert binding["status"] == "BOUND"
    assert binding["selected"]["component_id"] == "CMP-API"
    assert binding["selected"]["contract_id"] == "API-NOTE-CREATE"
    assert len(binding["selected"]["provenance"]) == 3


def test_cross_branch_prd_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    cases = case_model()
    cases["source_prd"]["artifact_id"] = "PRD-OTHER"
    arch_path, test_path = write_pair(tmp_path, architecture(), cases)
    with pytest.raises(ValueError, match="source_prd_id"):
        load_canonical_pair(arch_path, test_path)


def test_unbound_and_ambiguous_are_never_selected(tmp_path: Path) -> None:
    no_flow = architecture(flows=[])
    arch_path, test_path = write_pair(tmp_path, no_flow, case_model())
    result = load_canonical_pair(arch_path, test_path)
    assert result.extraction_report["bindings"][0]["status"] == "UNBOUND"
    assert result.extraction_report["bindings"][0]["selected"] is None

    duplicate = architecture()["payload"]["runtime_flows"]
    second = copy.deepcopy(duplicate[0])
    second["id"] = "FLOW-NOTE-CREATE-SECOND"
    arch_path, test_path = write_pair(
        tmp_path, architecture(flows=duplicate + [second]), case_model()
    )
    result = load_canonical_pair(arch_path, test_path)
    assert result.extraction_report["bindings"][0]["status"] == "AMBIGUOUS"
    assert result.extraction_report["bindings"][0]["selected"] is None


def test_multi_when_order_is_preserved(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(), case_model(multiple_when=True))
    result = load_canonical_pair(arch_path, test_path)
    steps = result.normalized_input["testcases"][0]["steps"]
    assert [step["text"] for step in steps if step["phase"] == "when"] == [
        "the client creates a note",
        "the client reads the note",
    ]


def test_blocked_workspace_has_fixed_empty_artifacts(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(flows=[]), case_model())
    result = load_canonical_pair(arch_path, test_path)
    run = tmp_path / "run"
    initialize_workspace(run, result.normalized_input, result.extraction_report)
    assert {path.name for path in run.iterdir()} == set(WORKSPACE_FILES)
    assert json.loads((run / "scenario_events.json").read_text())["events"] == []
    assert json.loads((run / "validator_results.json").read_text())["results"] == []


def test_bundle_is_fixed_and_deterministic(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(flows=[]), case_model())
    result = load_canonical_pair(arch_path, test_path)
    run = tmp_path / "run"
    initialize_workspace(run, result.normalized_input, result.extraction_report)
    one, two = tmp_path / "one", tmp_path / "two"
    publish_canonical_bundle(run, one)
    publish_canonical_bundle(run, two)
    assert {path.name for path in one.iterdir()} == set(DELIVERY_FILES)
    assert {name: (one / name).read_bytes() for name in DELIVERY_FILES} == {
        name: (two / name).read_bytes() for name in DELIVERY_FILES
    }
    report = json.loads((one / "mocktest_report.json").read_text())
    assert report["states"] == {
        "audit_state": "NOT_RUN",
        "execution_state": "BLOCKED",
        "overall": "BLOCKED",
        "publication_state": "COMPLETE",
        "validation_verdict": "NOT_EVALUATED",
    }
    headings = [
        line
        for line in (one / "mocktest_report.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "## 1. Identity",
        "## 2. State Summary",
        "## 3. Coverage",
        "## 4. Findings",
        "## 5. Extraction Diagnostics",
        "## 6. Evidence",
        "## 7. Errors",
    ]


def test_input_fingerprint_is_independent_of_source_path(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    arch = architecture()
    cases = case_model()
    first_arch, first_cases = write_pair(first, arch, cases)
    second_arch, second_cases = write_pair(second, arch, cases)
    one = load_canonical_pair(first_arch, first_cases)
    two = load_canonical_pair(second_arch, second_cases)
    assert one.normalized_input["input_fingerprint"] == two.normalized_input["input_fingerprint"]


@pytest.mark.parametrize(
    ("validator_status", "expected"),
    [("PASS", "PASS"), ("WARNING", "WARNING"), ("FAIL", "FAIL")],
)
def test_publisher_preserves_business_verdict_separate_from_audit(
    tmp_path: Path, validator_status: str, expected: str
) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(), case_model())
    result = load_canonical_pair(arch_path, test_path)
    run = tmp_path / validator_status.lower()
    initialize_workspace(run, result.normalized_input, result.extraction_report)
    case = result.normalized_input["testcases"][0]
    (run / "execution_plan.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "artifact_schema_version": "mocktest-plan/v2",
                "input_fingerprint": result.normalized_input["input_fingerprint"],
                "scenarios": [
                    {
                        "tc_id": case["tc_id"],
                        "scenario_id": case["scenario_id"],
                        "requirement_ids": case["requirement_ids"],
                        "binding": result.extraction_report["bindings"][0],
                        "steps": case["steps"],
                        "interaction_count": 1,
                        "state": "READY",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    dimension = {"status": validator_status, "detail": f"contract {validator_status.lower()}"}
    (run / "val_results.json").write_text(
        json.dumps(
            [
                {
                    "test_case_id": case["tc_id"],
                    "result": {"overall": validator_status, "contract": dimension},
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "strict_audit.json").write_text(
        json.dumps({"status": "PASS", "errors": []}), encoding="utf-8"
    )
    (run / "compat.json").write_text(json.dumps({}), encoding="utf-8")
    delivery = tmp_path / f"delivery-{validator_status.lower()}"
    publish_canonical_bundle(run, delivery)
    report = json.loads((delivery / "mocktest_report.json").read_text(encoding="utf-8"))
    assert report["states"]["execution_state"] == "COMPLETED"
    assert report["states"]["audit_state"] == "PASS"
    assert report["states"]["validation_verdict"] == validator_status
    assert report["states"]["overall"] == expected


def test_artifact_error_is_execution_error_not_architecture_fail(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(), case_model())
    result = load_canonical_pair(arch_path, test_path)
    run = tmp_path / "error-run"
    initialize_workspace(run, result.normalized_input, result.extraction_report)
    (run / "artifact_errors.jsonl").write_text('{"error":"invalid response"}\n', encoding="utf-8")
    delivery = tmp_path / "error-delivery"
    publish_canonical_bundle(run, delivery)
    report = json.loads((delivery / "mocktest_report.json").read_text(encoding="utf-8"))
    assert report["states"]["execution_state"] == "ERROR"
    assert report["states"]["overall"] == "ERROR"
    assert report["states"]["validation_verdict"] == "NOT_EVALUATED"


@pytest.mark.parametrize(
    ("execution", "validation", "audit", "expected"),
    [
        ("ERROR", "NOT_EVALUATED", "NOT_RUN", "ERROR"),
        ("COMPLETED", "PASS", "FAIL", "ERROR"),
        ("PARTIAL", "FAIL", "PASS", "BLOCKED"),
        ("COMPLETED", "FAIL", "PASS", "FAIL"),
        ("COMPLETED", "WARNING", "PASS", "WARNING"),
        ("COMPLETED", "PASS", "PASS", "PASS"),
    ],
)
def test_state_truth_table(execution: str, validation: str, audit: str, expected: str) -> None:
    assert derive_overall(execution, validation, audit) == expected


def test_strict_prepare_consumes_v2_without_markdown_parser(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(), case_model(multiple_when=True))
    run = tmp_path / "strict-run"
    script = (
        Path(__file__).resolve().parents[1]
        / ".agents"
        / "skills"
        / "validate-arch"
        / "run_subagent_skill.py"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "prepare",
            "--arch",
            str(arch_path),
            "--feature",
            str(test_path),
            "--output-dir",
            str(run),
            "--slim-prompts",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    plan = json.loads((run / "execution_plan.json").read_text(encoding="utf-8"))
    assert plan["scenarios"][0]["state"] == "READY"
    assert plan["scenarios"][0]["interaction_count"] == 2
    assert (
        json.loads((run / "extraction_report.json").read_text(encoding="utf-8"))["status"] == "PASS"
    )


def test_feature_v2_path_resolves_authority_without_reverse_parsing(tmp_path: Path) -> None:
    model = case_model()
    arch_path, test_path = write_pair(tmp_path, architecture(), model)
    feature_path = tmp_path / "testcases.feature"
    feature_path.write_text(render_feature_v2(model), encoding="utf-8", newline="\n")
    run = tmp_path / "strict-feature-run"
    script = (
        Path(__file__).resolve().parents[1]
        / ".agents"
        / "skills"
        / "validate-arch"
        / "run_subagent_skill.py"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "prepare",
            "--arch",
            str(arch_path),
            "--feature",
            str(feature_path),
            "--output-dir",
            str(run),
            "--slim-prompts",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    normalized = json.loads((run / "normalized_input.json").read_text(encoding="utf-8"))
    assert normalized["inputs"][1]["path"] == str(test_path.resolve())
    assert normalized["feature_projection"]["artifact_schema_version"] == "feature/v2"

    feature_path.write_text(
        render_feature_v2(model).replace("create note", "change note"),
        encoding="utf-8",
        newline="\n",
    )
    rejected = subprocess.run(
        [
            sys.executable,
            str(script),
            "prepare",
            "--arch",
            str(arch_path),
            "--feature",
            str(feature_path),
            "--output-dir",
            str(tmp_path / "rejected"),
            "--slim-prompts",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert rejected.returncode == 5
    assert "do not match sibling testcases/v2 authority" in rejected.stderr


def test_v2_input_manifest_preserves_mocktest_run_identity(tmp_path: Path) -> None:
    arch = architecture()
    cases = case_model()
    arch_path, test_path = write_pair(tmp_path, arch, cases)
    manifest = {
        "schema_version": "mocktest-input/v2",
        "run_id": "MOCK-RUN-001",
        "project_id": "notes",
        "node_id": "SYS-NOTES",
        "parent_node_id": None,
        "source_prd_id": "PRD-NOTES",
        "created_at": "2026-08-02T00:00:00Z",
        "generator": "mocktest",
        "status": "PASS",
        "mode": "strict",
        "architecture": {
            "artifact_id": arch["artifact_id"],
            "artifact_type": "architecture_json",
            "path": str(arch_path),
            "schema_version": "architecture/v2",
            "run_id": "run-001",
            "project_id": "notes",
            "node_id": "SYS-NOTES",
            "source_prd_id": "PRD-NOTES",
        },
        "testcases": {
            "artifact_id": cases["artifact_id"],
            "artifact_type": "testcases_json",
            "path": str(test_path),
            "schema_version": "testcases/v2",
            "run_id": "run-001",
            "project_id": "notes",
            "node_id": "SYS-NOTES",
            "source_prd_id": "PRD-NOTES",
        },
    }
    # Branch run IDs describe producer runs; the manifest run ID describes Mocktest.
    manifest_path = tmp_path / "mocktest-input.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run = tmp_path / "manifest-run"
    script = (
        Path(__file__).resolve().parents[1]
        / ".agents"
        / "skills"
        / "validate-arch"
        / "run_subagent_skill.py"
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "prepare",
            "--input-manifest",
            str(manifest_path),
            "--output-dir",
            str(run),
            "--slim-prompts",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert (
        json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))["run_id"]
        == "MOCK-RUN-001"
    )


def test_public_module_cli_is_canonical_v2(tmp_path: Path) -> None:
    arch_path, test_path = write_pair(tmp_path, architecture(), case_model())
    run = tmp_path / "public-cli-run"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mock_framework",
            "inspect-input",
            "--architecture",
            str(arch_path),
            "--testcases",
            str(test_path),
            "--output-dir",
            str(run),
            "--run-id",
            "PUBLIC-RUN-001",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert json.loads(completed.stdout)["status"] == "PASS"
    assert (
        json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))["run_id"]
        == "PUBLIC-RUN-001"
    )


def test_public_schema_validates_canonical_artifacts(tmp_path: Path) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "mocktest-run.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    arch_path, test_path = write_pair(tmp_path, architecture(flows=[]), case_model())
    result = load_canonical_pair(arch_path, test_path)
    run = tmp_path / "run"
    delivery = tmp_path / "delivery"
    initialize_workspace(run, result.normalized_input, result.extraction_report)
    publish_canonical_bundle(run, delivery)
    for path in (
        run / "run_manifest.json",
        run / "normalized_input.json",
        run / "extraction_report.json",
        run / "execution_plan.json",
        run / "scenario_events.json",
        run / "contract_check.json",
        run / "validator_results.json",
        run / "strict_audit.json",
        run / "execution_log.json",
        delivery / "mocktest_report.json",
        delivery / "leaf_gate_evidence.json",
        delivery / "execution_log.json",
        delivery / "bundle_manifest.json",
    ):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))
