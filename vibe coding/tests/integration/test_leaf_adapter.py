import unittest

from vibecode.adapters.leaf_adapter import adapt_proposed_children, prepare_leaf_formal_input


def artifact(kind: str, *, node_id: str = "S1-root", sha: str = "b" * 64) -> dict:
    return {
        "schema_version": "verilayer-contract/v0.1", "run_id": "run-s1", "project_id": "project-s1",
        "node_id": node_id, "parent_node_id": None, "artifact_id": f"{kind}-s1", "artifact_type": kind,
        "created_at": "2026-07-28T00:00:00Z", "generator": "fixture", "status": "PASS" if kind == "mocktest_report" else "COMPLETED",
        "input_artifacts": [], "requirement_ids": ["REQ-S1-001"], "content_path": f"artifacts/{kind}.json",
        "content_sha256": sha,
    }


class LeafAdapterTests(unittest.TestCase):
    def test_missing_any_formal_input_is_error(self):
        values = {kind: artifact(kind) for kind in ("prd", "architecture", "testcases", "mocktest_report")}
        values["mocktest_report"] = None
        result = prepare_leaf_formal_input(**values, strict_audit={"status": "PASS"}, contract_frozen=True, hash_verifier=lambda _: True)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["downstream_gate"], "BLOCK")

    def test_leaf_requires_matching_identity_and_hash_verification(self):
        values = {kind: artifact(kind) for kind in ("prd", "architecture", "testcases", "mocktest_report")}
        values["architecture"] = artifact("architecture", node_id="wrong-node")
        mismatch = prepare_leaf_formal_input(**values, strict_audit={"status": "PASS"}, contract_frozen=True, hash_verifier=lambda _: True)
        self.assertEqual(mismatch["tool_error"]["code"], "LEAF_INPUT_INCOMPLETE")
        values["architecture"] = artifact("architecture")
        bad_hash = prepare_leaf_formal_input(**values, strict_audit={"status": "PASS"}, contract_frozen=True, hash_verifier=lambda item: item["artifact_type"] != "architecture")
        self.assertEqual(bad_hash["tool_error"]["code"], "ARTIFACT_HASH_MISMATCH")

    def test_leaf_is_only_eligible_after_complete_pass_and_verified_hashes(self):
        values = {kind: artifact(kind) for kind in ("prd", "architecture", "testcases", "mocktest_report")}
        result = prepare_leaf_formal_input(**values, strict_audit={"status": "PASS"}, contract_frozen=True, hash_verifier=lambda _: True)
        self.assertEqual(result["status"], "READY_FOR_LEAF")
        self.assertTrue(result["eligible_for_leaf"])

    def test_child_node_id_is_read_only_compatibility_input(self):
        result = adapt_proposed_children([{"child_node_id": "S1-child", "name": "child"}], parent_node_id="S1-root")
        child = result["proposed_children"][0]
        self.assertEqual(child["node_id"], "S1-child")
        self.assertEqual(child["parent_node_id"], "S1-root")
        self.assertNotIn("child_node_id", child)

    def test_conflicting_child_identity_fails_closed(self):
        result = adapt_proposed_children([{"child_node_id": "S1-child", "node_id": "other"}], parent_node_id="S1-root")
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["downstream_gate"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
