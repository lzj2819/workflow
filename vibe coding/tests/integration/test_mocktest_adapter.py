import unittest

from vibecode.adapters.mocktest_adapter import allocate_strict_run_layout, build_mocktest_formal_input, evaluate_mocktest_gate


def artifact(kind: str, *, node_id: str = "S1-root", sha: str = "a" * 64) -> dict:
    return {
        "schema_version": "verilayer-contract/v0.1", "run_id": "run-s1", "project_id": "project-s1",
        "node_id": node_id, "parent_node_id": None, "artifact_id": f"{kind}-s1", "artifact_type": kind,
        "created_at": "2026-07-28T00:00:00Z", "generator": "fixture", "status": "COMPLETED",
        "input_artifacts": [], "requirement_ids": ["REQ-S1-001"], "content_path": f"artifacts/{kind}.json",
        "content_sha256": sha,
    }


class MocktestAdapterTests(unittest.TestCase):
    def test_missing_any_upstream_artifact_is_error(self):
        for missing in ("prd", "architecture", "testcases"):
            values = {kind: artifact(kind) for kind in ("prd", "architecture", "testcases")}
            values[missing] = None
            result = build_mocktest_formal_input(**values, contract_frozen=True)
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["downstream_gate"], "BLOCK")

    def test_contract_not_frozen_blocks_input_preparation(self):
        result = build_mocktest_formal_input(artifact("prd"), artifact("architecture"), artifact("testcases"), contract_frozen=False)
        self.assertEqual(result["tool_error"]["code"], "CONTRACT_NOT_FROZEN")

    def test_missing_strict_audit_blocks_even_if_semantic_pass(self):
        result = evaluate_mocktest_gate({"status": "PASS"}, None)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["semantic_mocktest_status"], "PASS")
        self.assertEqual(result["downstream_gate"], "BLOCK")

    def test_completed_audit_with_semantic_fail_is_not_tool_error(self):
        result = evaluate_mocktest_gate({"status": "FAIL"}, {"status": "PASS"})
        self.assertEqual(result["execution_completeness"], "COMPLETE")
        self.assertEqual(result["architecture_status"], "FAIL")
        self.assertIsNone(result["tool_error"])
        self.assertEqual(result["downstream_gate"], "BLOCK")

    def test_tool_error_never_becomes_architecture_fail(self):
        result = evaluate_mocktest_gate({}, None, tool_error={"category": "import", "code": "IMPORT_ERROR", "message": "missing dependency"})
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["architecture_status"], "NOT_RUN")
        self.assertEqual(result["downstream_gate"], "BLOCK")

    def test_only_complete_audit_and_semantic_pass_allow_leaf(self):
        result = evaluate_mocktest_gate({"status": "PASS"}, {"status": "PASS"})
        self.assertEqual(result["downstream_gate"], "ALLOW")

    def test_strict_paths_are_unique_and_delivery_is_not_work_dir(self):
        first, second = allocate_strict_run_layout(), allocate_strict_run_layout()
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertTrue(first["output_dir"].startswith(".work/"))
        self.assertNotEqual(first["output_dir"], first["report_dir"])


if __name__ == "__main__":
    unittest.main()
