import json
import tempfile
import unittest
from pathlib import Path

from vibecode.adapters.leaf_adapter import execute_adapter


class LeafAdapterTests(unittest.TestCase):
    def test_normalizes_legacy_child_field_to_node_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); output = root / "leaf"
            prd = root / "prd.json"; prd.write_text(json.dumps({"depth": 0, "max_depth": 2}), encoding="utf-8")
            architecture = root / "architecture.md"; architecture.write_text("# architecture", encoding="utf-8")
            feature = root / "testcases.feature"; feature.write_text("@REQ-ROOT @REQ-CHILD\nFeature: fresh", encoding="utf-8")
            report = root / "mocktest_report.json"; report.write_text(json.dumps({"execution_status": "COMPLETED", "validation_status": "PASS", "defects": []}), encoding="utf-8")
            bundle = root / "bundle.json"; bundle.write_text(json.dumps({"records": [
                {"generator": "prd", "primary_artifact": str(prd), "requirement_ids": ["REQ-ROOT", "REQ-CHILD"]},
                {"generator": "architecture", "primary_artifact": str(architecture)},
                {"generator": "gherkin", "primary_artifact": str(feature)},
                {"generator": "mocktest", "primary_artifact": str(report), "strict_audit_status": "PASS"},
            ]}), encoding="utf-8")

            def fake_leaf(script, package, decision_path):
                self.assertTrue((package / "architecture.json").is_file())
                decision_path.parent.mkdir(parents=True, exist_ok=True)
                decision_path.write_text(json.dumps({"status": "CONTINUE_LAYERING", "decision": "CONTINUE_LAYERING",
                    "proposed_children": [{"child_node_id": "root.01-a", "name": "a", "responsibility": "a",
                        "requirement_ids": ["REQ-ROOT"], "decomposition_rationale": "test",
                        "expected_interfaces": [], "priority": 1}]}), encoding="utf-8")
                return 0

            result = execute_adapter(input_path=bundle, output_dir=output, run_id="r", project_id="p", node_id="root",
                                     parent_node_id=None, leaf_runner=fake_leaf)
            self.assertEqual(result["status"], "CONTINUE_LAYERING")
            child = result["proposed_children"][0]
            self.assertEqual(child["node_id"], "root.01-a")
            self.assertNotIn("child_node_id", child)
            self.assertEqual(child["requirement"]["depth"], 1)

    def test_real_formal_leaf_script_can_continue_a_two_requirement_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"; prd.write_text(json.dumps({"depth": 0, "max_depth": 2}), encoding="utf-8")
            architecture = root / "architecture.md"; architecture.write_text("# architecture", encoding="utf-8")
            feature = root / "testcases.feature"; feature.write_text("@REQ-A @REQ-B\nFeature: fresh", encoding="utf-8")
            report = root / "mocktest_report.json"; report.write_text(json.dumps({"execution_status": "COMPLETED", "validation_status": "PASS", "defects": []}), encoding="utf-8")
            bundle = root / "bundle.json"; bundle.write_text(json.dumps({"records": [
                {"generator": "prd", "primary_artifact": str(prd), "requirement_ids": ["REQ-A", "REQ-B"]},
                {"generator": "architecture", "primary_artifact": str(architecture)},
                {"generator": "gherkin", "primary_artifact": str(feature)},
                {"generator": "mocktest", "primary_artifact": str(report), "strict_audit_status": "PASS"},
            ]}), encoding="utf-8")
            result = execute_adapter(input_path=bundle, output_dir=root / "leaf", run_id="r", project_id="p",
                                     node_id="root", parent_node_id=None)
            self.assertEqual(result["status"], "CONTINUE_LAYERING")
            self.assertEqual(len(result["proposed_children"]), 2)


if __name__ == "__main__":
    unittest.main()
