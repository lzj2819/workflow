import json
import tempfile
import unittest
from pathlib import Path

from vibecode.adapters.root_coding_adapter import execute_adapter


class RootCodingAdapterTests(unittest.TestCase):
    def test_builds_public_request_and_preserves_semantic_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); prd = root / "prd.json"; prd.write_text("{}", encoding="utf-8")
            leaf = root / "leaf.json"; leaf.write_text("{}", encoding="utf-8")
            bundle = root / "bundle.json"; bundle.write_text(json.dumps({"records": [
                {"generator": "prd", "primary_artifact": str(prd), "requirement_ids": ["REQ-LEAF"]},
                {"generator": "leaf_gate", "primary_artifact": str(leaf), "decision": "STOP_LAYERING"},
            ]}), encoding="utf-8")

            def fake_coding(**kwargs):
                request = json.loads(kwargs["request_path"].read_text(encoding="utf-8"))
                self.assertEqual(request["requirement_ids"], ["REQ-LEAF"])
                self.assertTrue((kwargs["request_path"].parent / "public-tests" / "test_app.py").is_file())
                return {"status": "FAIL", "artifact_id": "r:leaf:coding:result", "artifact_type": "code"}

            result = execute_adapter(input_path=bundle, output_dir=root / "coding", run_id="r", project_id="p",
                                     node_id="leaf", parent_node_id="root", model="test", coding_runner=fake_coding)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["output_artifacts"], ["module-result.json"])
            self.assertTrue((root / "coding" / "module-result.json").is_file())


if __name__ == "__main__":
    unittest.main()
