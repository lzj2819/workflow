from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from prd_flow.canonical import (
    SECTION_ORDER,
    build_canonical_prd,
    canonical_json_text,
    render_canonical_prd,
    validate_canonical_prd,
)
from prd_flow.consumer_profiles import validate_consumer_profile
from prd_flow.derive.parser import parse_parent_prd


def ready_source(label: str = "Orders", requirement_id: str = "REQ-001") -> dict:
    return {
        "P1": {
            "doc_id": f"{label.upper()}-v1.0",
            "project_name": label,
            "version": "1.0.0",
            "layer": "root",
            "author": "Product Owner",
            "priority": "P0",
            "status": "approved",
            "release_scope_frozen": True,
            "ready_for_test_generation": True,
            "agent_review_passed": True,
            "run_id": "run-001",
            "project_id": "project-001",
            "node_id": "root",
            "parent_node_id": None,
            "artifact_id": "prd:project-001:root:run-001",
            "created_at": "2026-08-02T00:00:00Z",
            "generator": "prd-generation",
            "input_artifacts": ["inputs/request.json"],
            "depth": 0,
            "max_depth": 4,
            "node_history": [],
            "_review": {
                "status": "passed",
                "reviewer": "independent-reviewer",
                "model": "test-model",
                "reviewed_at": "2026-08-02T00:01:00Z",
                "input_hash": "a" * 64,
                "findings": [],
            },
        },
        "P2": {
            "summary": f"{label} workflow",
            "target_users": f"{label} operators",
            "pain_points": f"Manual {label.lower()} work",
            "desired_outcomes": f"Reliable {label.lower()} processing",
            "current_release_boundary": "Single-node release",
            "in_scope": ["Create one record"],
            "dependencies": ["Identity provider"],
            "data_availability": ["Synthetic public data"],
            "risks": ["Upstream dependency unavailable"],
        },
        "P3": {
            "functional": [{
                "id": requirement_id,
                "text": f"The system returns a recorded {label.lower()} identifier.",
                "priority": "Must Have",
                "release_scope": "current",
                "scope_reason": None,
                "requirement_kind": "atomic",
                "source_kind": "explicit",
                "evidence_refs": ["decision:001"],
            }],
            "non_functional": [],
            "non_goals": ["Bulk import"],
            "retired_requirement_ids": [],
        },
        "P4": {"contracts": [{
            "id": f"AC-{requirement_id}-01",
            "type": "functional",
            "verifies": [requirement_id],
            "release_scope": "current",
            "actor": "operator",
            "preconditions": ["operator is authenticated"],
            "trigger": "operator submits a valid request",
            "response": ["system persists the record"],
            "observable_oracles": ["response contains the persisted identifier"],
            "boundaries": [{"condition": "identifier space is available", "response": "allocate one identifier"}],
            "exceptions": [{"condition": "persistence is unavailable", "response": "reject without reporting success"}],
            "evidence_refs": ["decision:002"],
        }]},
        "P5": {"metrics": [{
            "id": "METRIC-001",
            "name": "Successful records",
            "target": "100% of accepted requests",
            "method": "Compare accepted responses with persisted records",
            "verifies": [requirement_id],
            "evidence_refs": ["decision:003"],
        }]},
        "P6": {
            "system_boundary": [f"Own the {label.lower()} write boundary"],
            "external_dependencies": ["Identity provider"],
            "data_and_storage_constraints": [],
            "runtime_and_capacity_constraints": [],
            "security_and_privacy_constraints": ["Do not expose credentials"],
            "deployment_constraints": [],
            "open_decisions": [],
        },
    }


class CanonicalPrdTests(unittest.TestCase):
    def test_cli_runs_with_different_content_emit_same_bundle_shape(self) -> None:
        models = []
        markdown_headings = []
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            for index, (label, requirement_id) in enumerate(
                (("Orders", "REQ-001"), ("Profiles", "REQ-900")),
                start=1,
            ):
                source = ready_source(label, requirement_id)
                source["P1"].pop("_review", None)
                source["P1"].update({
                    "status": "draft",
                    "release_scope_frozen": False,
                    "ready_for_test_generation": False,
                })
                input_path = temporary_root / f"input-{index}.json"
                output_dir = temporary_root / f"output-{index}"
                input_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
                base = [
                    sys.executable,
                    str(ROOT / "scripts" / "run_prd_flow.py"),
                    "--input", str(input_path),
                    "--output-dir", str(output_dir),
                    "--run-id", "run-001",
                    "--project-id", "project-001",
                    "--node-id", "root",
                    "--created-at", "2026-08-02T00:00:00Z",
                ]
                blocked = subprocess.run(base + ["--validate-only"], text=True, capture_output=True, encoding="utf-8")
                self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
                execution = json.loads((output_dir / "execution_log.json").read_text(encoding="utf-8"))
                review = {
                    "input_hash": execution["input_hash"],
                    "reviewer": "independent-reviewer",
                    "model": "test-model",
                    "reviewed_at": "2026-08-02T00:01:00Z",
                    "status": "passed",
                    "findings": [],
                }
                review_path = temporary_root / f"review-{index}.json"
                review_path.write_text(json.dumps(review), encoding="utf-8")
                ready = subprocess.run(base + ["--review-artifact", str(review_path)], text=True, capture_output=True, encoding="utf-8")
                self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
                expected_bundle = {
                    "prd.md", "prd.json", "prd_manifest.json",
                    "validation_report.json", "execution_log.json",
                }
                self.assertTrue(expected_bundle.issubset(item.name for item in output_dir.iterdir()))
                model = json.loads((output_dir / "prd.json").read_text(encoding="utf-8"))
                models.append(model)
                markdown_headings.append([
                    line[2:]
                    for line in (output_dir / "prd.md").read_text(encoding="utf-8").splitlines()
                    if line.startswith("# ")
                ])
        self.assertEqual(tuple(models[0]), tuple(models[1]))
        self.assertEqual(tuple(models[0]["payload"]), tuple(models[1]["payload"]))
        self.assertEqual(markdown_headings[0], list(SECTION_ORDER))
        self.assertEqual(markdown_headings[0], markdown_headings[1])

    def test_different_content_has_identical_shape_and_section_order(self) -> None:
        first = build_canonical_prd(ready_source("Orders", "REQ-001"))
        second = build_canonical_prd(ready_source("Profiles", "REQ-900"))
        self.assertEqual(tuple(first), tuple(second))
        self.assertEqual(tuple(first["payload"]), tuple(second["payload"]))
        self.assertEqual(tuple(first["payload"]["requirements"][0]), tuple(second["payload"]["requirements"][0]))
        self.assertEqual(tuple(first["payload"]["acceptance_contracts"][0]), tuple(second["payload"]["acceptance_contracts"][0]))
        self.assertEqual(first["section_order"], list(SECTION_ORDER))
        headings = [line[2:] for line in render_canonical_prd(first).splitlines() if line.startswith("# ")]
        self.assertEqual(headings, list(SECTION_ORDER))

    def test_input_array_order_does_not_change_canonical_bytes(self) -> None:
        source = ready_source()
        extra = copy.deepcopy(source["P3"]["functional"][0])
        extra.update({"id": "REQ-002", "text": "The system records an audit event.", "evidence_refs": ["decision:004"]})
        contract = copy.deepcopy(source["P4"]["contracts"][0])
        contract.update({"id": "AC-REQ-002-01", "verifies": ["REQ-002"], "evidence_refs": ["decision:005"]})
        source["P3"]["functional"].append(extra)
        source["P4"]["contracts"].append(contract)
        shuffled = copy.deepcopy(source)
        shuffled["P3"]["functional"].reverse()
        shuffled["P4"]["contracts"].reverse()
        self.assertEqual(
            canonical_json_text(build_canonical_prd(source)),
            canonical_json_text(build_canonical_prd(shuffled)),
        )

    def test_schema_semantics_and_consumer_profiles_accept_ready_artifact(self) -> None:
        model = build_canonical_prd(ready_source())
        self.assertEqual(validate_canonical_prd(model, require_ready=True), [])
        for consumer in ("canonical", "architecture", "gherkin", "leaf"):
            self.assertEqual(validate_consumer_profile(model, consumer), [], consumer)
        try:
            import jsonschema
        except ImportError:
            jsonschema = None
        if jsonschema is not None:
            schema = json.loads((ROOT / "schemas" / "canonical-prd.schema.json").read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator(schema).validate(model)

    def test_mutations_fail_closed(self) -> None:
        source = ready_source()
        source["P3"]["retired_requirement_ids"] = ["REQ-001"]
        source["P4"]["contracts"][0]["verifies"] = ["REQ-404"]
        source["P3"]["functional"][0]["evidence_refs"] = []
        errors = validate_canonical_prd(build_canonical_prd(source), require_ready=True)
        self.assertTrue(any("never be reused" in item for item in errors))
        self.assertTrue(any("unknown requirement refs" in item for item in errors))
        self.assertTrue(any("evidence_refs is empty" in item for item in errors))

    def test_markdown_round_trip_preserves_requirements_and_contracts(self) -> None:
        source = ready_source()
        model = build_canonical_prd(source)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prd.md"
            path.write_text(render_canonical_prd(model), encoding="utf-8")
            parsed = parse_parent_prd(path)
        self.assertEqual([item["id"] for item in parsed["requirements"]], ["REQ-001"])
        self.assertEqual([item["id"] for item in parsed["acceptance_contracts"]], ["AC-REQ-001-01"])

    def test_derive_all_delivers_complete_child_bundle(self) -> None:
        parent_model = build_canonical_prd(ready_source())
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            parent = temporary_root / "parent" / "prd.md"
            parent.parent.mkdir()
            parent.write_text(render_canonical_prd(parent_model), encoding="utf-8")
            architecture = temporary_root / "architecture.yaml"
            architecture.write_text(
                "\n".join([
                    "doc_id: ARCH-001",
                    "modules:",
                    "  - name: OrdersModule",
                    "    responsibility: Own order recording",
                    "    requirement_refs: [REQ-001]",
                ]),
                encoding="utf-8",
            )
            output = temporary_root / "children"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_prd_flow.py"),
                    "--derive-all",
                    "--parent-prd", str(parent),
                    "--architecture-package", str(architecture),
                    "--target-granularity", "deployable_module",
                    "--output-dir", str(output),
                    "--run-id", "derive-run-001",
                    "--project-id", "project-001",
                    "--node-id", "root.orders",
                    "--parent-node-id", "root",
                    "--created-at", "2026-08-02T00:02:00Z",
                ],
                text=True,
                capture_output=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            child = output / "L1-ordersmodule"
            expected = {
                "prd.md", "prd.json", "prd_manifest.json",
                "validation_report.json", "execution_log.json",
            }
            self.assertEqual({item.name for item in child.iterdir()}, expected)
            child_model = json.loads((child / "prd.json").read_text(encoding="utf-8"))
            self.assertEqual(child_model["mode"], "derive")
            self.assertEqual(child_model["status"], "PASS")
            self.assertEqual(validate_consumer_profile(child_model, "architecture"), [])

if __name__ == "__main__":
    unittest.main()
