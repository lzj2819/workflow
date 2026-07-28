import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from vibecode import contracts


ROOT = Path(__file__).resolve().parents[1]


def base_contract(contract_id="contract"):
    return {
        "schema_version": "1.0",
        "contract_id": contract_id,
        "version": "1.0.0",
        "interfaces": [
            {
                "interface_id": "get-demo",
                "provider": "demo-service",
                "consumers": ["parent-service"],
                "request": {
                    "parameters": [
                        {"name": "user_id", "type": "string", "required": True}
                    ],
                    "data_schema": {
                        "type": "object",
                        "properties": {"user_id": {"type": "string"}},
                        "required": ["user_id"],
                    },
                },
                "response": {
                    "type": "DemoResponse",
                    "data_schema": {
                        "type": "object",
                        "properties": {"result": {"type": "string"}},
                        "required": ["result"],
                    },
                },
                "errors": [{"code": "NOT_FOUND", "type": "business"}],
                "preconditions": ["authenticated"],
                "postconditions": ["result returned"],
                "timeout_ms": 1000,
                "retry_policy": {"max_attempts": 1},
                "idempotency": "safe",
                "side_effects": [],
            }
        ],
    }


class SemanticContractTests(unittest.TestCase):
    def test_all_required_breaking_difference_classes(self):
        cases = {}

        child = base_contract("child")
        child["interfaces"] = []
        cases["INTERFACE_REMOVED"] = child

        child = base_contract("child")
        child["interfaces"][0]["request"]["parameters"].append(
            {"name": "tenant", "type": "string", "required": True}
        )
        cases["PARAMETER_ADDED_REQUIRED"] = child

        child = base_contract("child")
        child["interfaces"][0]["request"]["parameters"][0]["type"] = "integer"
        cases["PARAMETER_TYPE_CHANGED"] = child

        child = base_contract("child")
        child["interfaces"][0]["response"]["type"] = "OtherResponse"
        cases["RETURN_TYPE_CHANGED"] = child

        child = base_contract("child")
        child["interfaces"][0]["errors"].append({"code": "TIMEOUT"})
        cases["ERROR_CONTRACT_CHANGED"] = child

        child = base_contract("child")
        child["interfaces"][0]["request"]["data_schema"]["properties"]["user_id"]["type"] = "integer"
        cases["DATA_SCHEMA_INCOMPATIBLE"] = child

        child = base_contract("child")
        child["interfaces"][0]["provider"] = None
        cases["PROVIDER_MISSING"] = child

        child = base_contract("child")
        child["interfaces"][0]["consumers"] = []
        cases["CONSUMER_MISMATCH"] = child

        child = base_contract("child")
        child["interfaces"][0]["preconditions"].append("premium account")
        cases["PRECONDITION_STRENGTHENED"] = child

        child = base_contract("child")
        child["interfaces"][0]["postconditions"] = []
        cases["POSTCONDITION_WEAKENED"] = child

        for expected_type, child in cases.items():
            with self.subTest(expected_type=expected_type):
                result = contracts.compare_contracts(base_contract("parent"), child)
                types = {item["type"] for item in result["differences"]}
                self.assertIn(expected_type, types)
                self.assertEqual(result["status"], "FAIL")
                self.assertGreater(result["breaking_count"], 0)

    def test_optional_additions_are_compatible(self):
        parent = base_contract("parent")
        child = base_contract("child")
        child["interfaces"][0]["request"]["parameters"].append(
            {"name": "locale", "type": "string", "required": False}
        )
        result = contracts.compare_contracts(parent, child)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["outcome"], "ADDITIVE_ONLY")
        self.assertEqual(result["breaking_count"], 0)
        self.assertIn(
            "PARAMETER_ADDED_OPTIONAL",
            {item["type"] for item in result["differences"]},
        )

    def test_breaking_differences_map_to_explicit_resolution_outcomes(self):
        child = base_contract("child")
        child["interfaces"][0]["request"]["parameters"][0]["type"] = "integer"
        self.assertEqual(
            contracts.compare_contracts(base_contract("parent"), child)["outcome"],
            "ADAPTER_NEEDED",
        )

        child = base_contract("child")
        child["interfaces"][0]["provider"] = None
        self.assertEqual(
            contracts.compare_contracts(base_contract("parent"), child)["outcome"],
            "LEAF_FIX_REQUIRED",
        )

        child = base_contract("child")
        child["interfaces"][0]["preconditions"].append("premium")
        self.assertEqual(
            contracts.compare_contracts(base_contract("parent"), child)["outcome"],
            "CONTRACT_CHANGE_REQUIRED",
        )

    def test_ordering_does_not_change_semantics_or_hashes(self):
        parent = base_contract("same")
        parent["interfaces"][0]["consumers"].append("another-consumer")
        parent["interfaces"][0]["errors"].append({"code": "TIMEOUT"})
        child = deepcopy(parent)
        child["interfaces"][0]["consumers"].reverse()
        child["interfaces"][0]["errors"].reverse()
        result = contracts.compare_contracts(parent, child)
        self.assertEqual(result["outcome"], "MATCH")
        self.assertEqual(result["parent_hash"], result["child_hash"])

    def test_malformed_contract_returns_structured_error(self):
        child = base_contract("child")
        child["interfaces"] = "not-an-array"
        result = contracts.compare_contracts(base_contract("parent"), child)
        self.assertEqual(result["status"], "ERROR")
        self.assertTrue(result["validation_errors"])
        self.assertEqual(result["differences"], [])

    def test_json_and_markdown_reports_are_deterministic_and_consistent(self):
        result = contracts.compare_contracts(
            base_contract("parent"), base_contract("child")
        )
        self.assertEqual(result, contracts.compare_contracts(base_contract("parent"), base_contract("child")))
        markdown = contracts.render_markdown(result)
        self.assertIn(f"outcome: `{result['outcome']}`", markdown)
        self.assertIn(f"breaking_count: {result['breaking_count']}", markdown)
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "contract-diff.json"
            md_path = Path(tmp) / "contract-diff.md"
            contracts.write_reports(result, json_path, md_path)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), result)
            self.assertEqual(md_path.read_text(encoding="utf-8"), markdown)

    def test_cli_writes_authoritative_semantic_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "parent.json"
            child = root / "child.json"
            json_output = root / "diff.json"
            markdown_output = root / "diff.md"
            parent.write_text(json.dumps(base_contract("parent")), encoding="utf-8")
            child.write_text(json.dumps(base_contract("child")), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "vibecode" / "scripts" / "vibecode.py"),
                    "contract-diff",
                    "--parent",
                    str(parent),
                    "--child",
                    str(child),
                    "--json-output",
                    str(json_output),
                    "--output",
                    str(markdown_output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(json_output.read_text(encoding="utf-8"))
            self.assertEqual(result["outcome"], "MATCH")
            self.assertEqual(markdown_output.read_text(encoding="utf-8"), contracts.render_markdown(result))


if __name__ == "__main__":
    unittest.main()
