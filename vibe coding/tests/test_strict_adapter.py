import json
import tempfile
import unittest
from pathlib import Path

from vibecode.artifact_contract import content_sha256
from vibecode.adapters.strict_adapter import execute_adapter


class StrictAdapterTests(unittest.TestCase):
    def test_reads_actual_bundle_artifacts_and_preserves_semantic_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            architecture = root / "architecture.md"; architecture.write_text("# architecture", encoding="utf-8")
            feature = root / "testcases.feature"; feature.write_text("Feature: fresh", encoding="utf-8")
            bundle = root / "bundle.json"
            bundle.write_text(json.dumps({"records": [
                {"generator": "architecture", "primary_artifact": str(architecture)},
                {"generator": "gherkin", "primary_artifact": str(feature)},
            ]}), encoding="utf-8")
            output = root / "strict"

            def fake_strict(**kwargs):
                self.assertEqual(kwargs["architecture_path"], architecture.resolve())
                self.assertEqual(kwargs["feature_path"], feature.resolve())
                report = kwargs["output_dir"] / "formal" / "mocktest_report.json"
                report.parent.mkdir(parents=True)
                report.write_text(json.dumps({"execution_status": "COMPLETED", "validation_status": "FAIL"}), encoding="utf-8")
                return {"status": "FAIL", "error_type": "STRICT_SEMANTIC_BLOCKED",
                        "error_message": "defects found", "execution_complete": True,
                        "semantic_status": "FAIL", "strict_audit_status": "PASS", "finalize_exit": 2}

            result = execute_adapter(input_path=bundle, output_dir=output, run_id="r", project_id="p",
                                     node_id="root", parent_node_id=None, model="test", driver=root / "driver.py",
                                     strict_runner=fake_strict)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["execution_complete"], True)
            self.assertEqual(result["semantic_status"], "FAIL")
            self.assertEqual(result["strict_audit_status"], "PASS")
            self.assertEqual(result["content_sha256"], content_sha256(output / "formal/mocktest_report.json"))
            self.assertTrue((output / "module-result.json").is_file())


if __name__ == "__main__":
    unittest.main()
