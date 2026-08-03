from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from run_leaf_gate import OUTPUT_FILES, canonical_hash, file_sha256, run


ZERO = "0" * 64
ONE = "1" * 64


def dump(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def with_self_hash(value: dict) -> dict:
    value = deepcopy(value)
    value["content_sha256"] = canonical_hash({k: v for k, v in value.items() if k != "content_sha256"})
    return value


def architecture_hash(value: dict) -> str:
    projected = deepcopy(value)
    projected.pop("created_at", None)
    projected.pop("content_sha256", None)
    if isinstance(projected.get("payload"), dict):
        projected["payload"].pop("review", None)
    return canonical_hash(projected)


def make_node(
    root: Path,
    *,
    nodes: int = 1,
    overall: str = "PASS",
    audit: str = "PASS",
    repaired: bool = False,
    partial_coverage: bool = False,
    complexity: int = 1,
    depth: int = 0,
    max_depth: int = 4,
) -> tuple[Path, Path]:
    node = root / "node"
    node.mkdir(parents=True)
    prd = {
        "schema_version": "1.0", "artifact_schema_version": "prd/v3",
        "artifact_id": "PRD-001", "run_id": "prd-run", "project_id": "P1",
        "node_id": "N1", "parent_node_id": None, "status": "PASS", "prd_status": "approved",
        "requirement_ids": ["REQ-001", "REQ-002"],
        "payload": {"document": {"ready_for_test_generation": True, "oracle_blocked_count": 0}, "blocking_questions": []},
    }
    dump(node / "prd.json", prd)
    prd_sha = file_sha256(node / "prd.json")

    arch_nodes = []
    for index in range(nodes):
        arch_nodes.append({
            "id": f"CMP-{index + 1:02d}", "name": f"Component {index + 1}", "kind": "component",
            "responsibility": f"Own behaviour {index + 1}", "exclusions": [],
            "requirement_ids": [f"REQ-{index + 1:03d}"], "state_ids": [], "dependency_ids": [],
            "rationale": "Explicit architecture boundary", "source_refs": [f"REQ-{index + 1:03d}"],
        })
    architecture = {
        "schema_version": "1.0", "artifact_schema_version": "architecture/v2",
        "artifact_id": "ARCH-001", "run_id": "arch-run", "project_id": "P1", "node_id": "N1",
        "parent_node_id": None, "source_prd_id": "PRD-001", "status": "PASS",
        "architecture_status": "complete", "ready_for_downstream": True,
        "depth": depth, "max_depth": max_depth, "complexity": complexity,
        "input_artifacts": [{"artifact_id": "PRD-001", "sha256": prd_sha}],
        "payload": {"nodes": arch_nodes, "contracts": [], "state_ownership": [], "runtime": {}, "review": {}},
    }
    architecture["content_sha256"] = architecture_hash(architecture)
    dump(node / "architecture.json", architecture)

    cases = [
        {"tc_id": "TC-001", "requirement_ids": ["REQ-001"]},
        {"tc_id": "TC-002", "requirement_ids": ["REQ-002"]},
    ]
    testcases = {
        "schema_version": "1.0", "artifact_schema_version": "testcases/v2",
        "artifact_id": "TEST-001", "run_id": "test-run", "project_id": "P1", "node_id": "N1",
        "parent_node_id": None, "status": "PASS", "blocked_items": [],
        "source_prd": {"artifact_id": "PRD-001", "sha256": prd_sha},
        "requirement_ids": ["REQ-001", "REQ-002"], "testcases": cases,
    }
    dump(node / "testcases.json", testcases)
    arch_sha = file_sha256(node / "architecture.json")
    tests_sha = file_sha256(node / "testcases.json")

    validation = "PASS" if overall == "PASS" else ("FAIL" if overall in {"FAIL", "WARNING"} else "BLOCKED")
    states = {
        "execution_state": "COMPLETED", "validation_verdict": validation,
        "audit_state": audit, "publication_state": "COMPLETE", "overall": overall,
    }
    passed = 1 if partial_coverage else (2 if overall == "PASS" else 1)
    report = with_self_hash({
        "schema_version": "1.0", "artifact_schema_version": "mocktest-report/v2", "run_id": "mock-run",
        "identity": {"project_id": "P1", "node_id": "N1", "parent_node_id": None},
        "source_artifacts": [
            {"artifact_type": "architecture", "artifact_id": "ARCH-001", "sha256": arch_sha},
            {"artifact_type": "testcases", "artifact_id": "TEST-001", "sha256": tests_sha},
        ],
        "states": states,
        "coverage": {"total": 2, "evaluated": 2, "passed": passed, "warning": 0,
                     "failed": 0 if overall == "PASS" else 1, "blocked": 0,
                     "covered_requirement_ids": ["REQ-001", "REQ-002"]},
        "findings": [] if overall == "PASS" else [{"finding_id": "F-1", "testcase_ids": ["TC-001"]}],
        "errors": [],
    })
    dump(node / "mocktest_report.json", report)
    evidence = with_self_hash({
        "schema_version": "1.0", "artifact_schema_version": "mocktest-leaf-evidence/v2",
        "run_id": "mock-run", "states": states, "gate_recommendation": "ALLOW" if overall == "PASS" and audit == "PASS" else "BLOCK",
    })
    dump(node / "leaf_gate_evidence.json", evidence)

    report_sha = file_sha256(node / "mocktest_report.json")
    refs = {
        "prd": ("PRD-001", "prd/v3", "prd.json"),
        "architecture": ("ARCH-001", "architecture/v2", "architecture.json"),
        "testcases": ("TEST-001", "testcases/v2", "testcases.json"),
        "mocktest_report": ("MOCK-REPORT-001", "mocktest-report/v2", "mocktest_report.json"),
        "mocktest_evidence": ("MOCK-EVIDENCE-001", "mocktest-leaf-evidence/v2", "leaf_gate_evidence.json"),
    }
    current = {
        role: {"artifact_id": aid, "artifact_schema_version": version, "path": path,
               "sha256": file_sha256(node / path)}
        for role, (aid, version, path) in refs.items()
    }
    cycles = []
    if repaired:
        cycles = [{
            "failed_report_sha256": ZERO, "before_architecture_sha256": ONE,
            "after_architecture_sha256": arch_sha, "finding_ids": ["F-1"],
            "affected_testcase_ids": ["TC-001"], "revalidated_testcase_ids": ["TC-001"],
            "final_report_sha256": report_sha,
        }]
    manifest = {
        "schema_version": "1.0", "artifact_schema_version": "leaf-gate-input/v2",
        "run_id": "leaf-run", "project_id": "P1", "node_id": "N1", "parent_node_id": None,
        "source_prd_id": "PRD-001", "current_artifacts": current,
        "repair_history": {"completeness": "COMPLETE", "mode": "REPAIRED" if repaired else "FIRST_PASS", "cycles": cycles},
        "policy": {"max_leaf_complexity": 4, "max_leaf_contracts": 8, "max_leaf_states": 6,
                   "max_recursion_depth": 4, "min_semantic_confidence": 0.8,
                   "semantic_judgement": "DISABLED"},
        "semantic_judgement": None,
    }
    dump(node / "leaf_gate_input.json", manifest)
    return node, node / "leaf_gate_input.json"


def execute(tmp_path: Path, **kwargs):
    node, manifest = make_node(tmp_path, **kwargs)
    out = tmp_path / "out"
    report, code = run(node, manifest, out)
    return node, out, report, code


class LeafGateV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_stop_layering_and_fixed_bundle(self) -> None:
        _, out, report, code = execute(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(report["decision"]["value"], "STOP_LAYERING")
        self.assertEqual(report["next_action"]["type"], "VIBECODE")
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted(OUTPUT_FILES))
        markdown = (out / "leaf_gate_report.md").read_text(encoding="utf-8")
        self.assertEqual([line for line in markdown.splitlines() if line.startswith("## ")], [
            "## 1. Identity", "## 2. Admission", "## 3. Repair Chain", "## 4. Evaluation",
            "## 5. Decision", "## 6. Proposed Children", "## 7. Next Action",
        ])

    def test_continue_projects_exact_architecture_children(self) -> None:
        _, _, report, code = execute(self.root, nodes=2)
        self.assertEqual(code, 0)
        self.assertEqual(report["decision"]["value"], "CONTINUE_LAYERING")
        self.assertEqual([child["child_node_id"] for child in report["decision"]["proposed_children"]], ["CMP-01", "CMP-02"])
        self.assertEqual(report["next_action"]["type"], "DECOMPOSE")

    def test_business_non_pass_returns_to_architecture(self) -> None:
        for overall in ("WARNING", "FAIL", "BLOCKED"):
            with self.subTest(overall=overall):
                _, _, report, code = execute(self.root / overall, overall=overall)
                self.assertEqual(code, 2)
                self.assertIsNone(report["decision"]["value"])
                self.assertEqual(report["admission"]["state"], "RETURN_TO_ARCHITECTURE")

    def test_audit_failure_returns_to_validation(self) -> None:
        _, _, report, code = execute(self.root, overall="ERROR", audit="FAIL")
        self.assertEqual(code, 2)
        self.assertEqual(report["admission"]["state"], "RETURN_TO_VALIDATION")
        self.assertIsNone(report["decision"]["value"])

    def test_repaired_chain_requires_affected_revalidation(self) -> None:
        node, manifest = make_node(self.root, repaired=True)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["repair_history"]["cycles"][0]["revalidated_testcase_ids"] = ["TC-002"]
        dump(manifest, data)
        report, code = run(node, manifest, self.root / "out")
        self.assertEqual(code, 2)
        self.assertEqual(report["errors"][0]["code"], "REPAIR_CHAIN_INCOMPLETE")

    def test_repaired_chain_can_admit_current_pass(self) -> None:
        _, _, report, code = execute(self.root, repaired=True)
        self.assertEqual(code, 0)
        self.assertEqual(report["admission"]["repair_history_mode"], "REPAIRED")
        self.assertEqual(report["admission"]["affected_testcase_ids"], ["TC-001"])

    def test_stale_mocktest_hash_is_rejected(self) -> None:
        node, manifest = make_node(self.root)
        report_path = node / "mocktest_report.json"
        data = json.loads(report_path.read_text(encoding="utf-8"))
        data["source_artifacts"][0]["sha256"] = ZERO
        dump(report_path, with_self_hash(data))
        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        manifest_data["current_artifacts"]["mocktest_report"]["sha256"] = file_sha256(report_path)
        dump(manifest, manifest_data)
        result, code = run(node, manifest, self.root / "out")
        self.assertEqual(code, 2)
        self.assertEqual(result["errors"][0]["code"], "STALE_MOCKTEST")

    def test_incomplete_full_suite_coverage_is_rejected(self) -> None:
        _, _, report, code = execute(self.root, partial_coverage=True)
        self.assertEqual(code, 2)
        self.assertEqual(report["errors"][0]["code"], "COVERAGE_INCOMPLETE")

    def test_decomposition_needs_explicit_child_plan(self) -> None:
        _, _, report, code = execute(self.root, complexity=9)
        self.assertEqual(code, 2)
        self.assertEqual(report["errors"][0]["code"], "DECOMPOSITION_PLAN_REQUIRED")

    def test_max_depth_is_fail_closed(self) -> None:
        _, _, report, code = execute(self.root, nodes=2, depth=4, max_depth=4)
        self.assertEqual(code, 2)
        self.assertEqual(report["errors"][0]["code"], "MAX_DEPTH_REACHED")

    def test_identical_inputs_produce_byte_identical_outputs(self) -> None:
        node, manifest = make_node(self.root)
        out_a, out_b = self.root / "a", self.root / "b"
        self.assertEqual(run(node, manifest, out_a)[1], 0)
        self.assertEqual(run(node, manifest, out_b)[1], 0)
        for name in OUTPUT_FILES:
            self.assertEqual((out_a / name).read_bytes(), (out_b / name).read_bytes())

    def test_central_registry_contains_every_output_contract(self) -> None:
        _, out, _, _ = execute(self.root, nodes=2)
        schema = json.loads((Path(__file__).parents[1] / "schemas" / "leaf-gate-run.schema.json").read_text(encoding="utf-8"))
        versions = {definition.get("properties", {}).get("artifact_schema_version", {}).get("const")
                    for definition in schema["$defs"].values() if isinstance(definition, dict)}
        for name in OUTPUT_FILES:
            if name.endswith(".json"):
                value = json.loads((out / name).read_text(encoding="utf-8"))
                self.assertIn(value["artifact_schema_version"], versions)

    def test_cli_publishes_the_same_canonical_bundle(self) -> None:
        node, _ = make_node(self.root)
        out = self.root / "cli-out"
        command = [
            sys.executable,
            str(Path(__file__).parents[1] / "scripts" / "run_leaf_gate.py"),
            str(node),
            "--output-dir",
            str(out),
        ]
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=environment)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["decision"], "STOP_LAYERING")
        self.assertEqual(sorted(path.name for path in out.iterdir()), sorted(OUTPUT_FILES))


if __name__ == "__main__":
    unittest.main()
