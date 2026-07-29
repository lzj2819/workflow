import json
import tempfile
import unittest
from pathlib import Path

from vibecode.artifact_contract import content_sha256
from vibecode.executors.generation_executor import execute_generation


class GenerationExecutorTests(unittest.TestCase):
    def test_prd_generation_is_workspace_bounded_and_evidenced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "requirement.json"
            source.write_text(json.dumps({"requirement_ids": ["REQ-FRESH-01"], "goal": "fresh task"}), encoding="utf-8")
            output = root / "attempt"

            def fake_runner(*, prompt, workspace, model, timeout_seconds):
                self.assertIn("REQ-FRESH-01", prompt)
                self.assertIn("hidden tests", prompt)
                self.assertEqual(workspace, output.resolve())
                (workspace / "prd.json").write_text(json.dumps({"requirements": ["REQ-FRESH-01"]}), encoding="utf-8")
                return {"status": "PASS", "exit_code": 0}

            result = execute_generation(
                module="prd", input_path=source, output_dir=output, run_id="day4-root",
                project_id="verilayer", node_id="root", parent_node_id=None,
                model="test-model", runner=fake_runner,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["output_artifacts"], ["prd.json"])
            self.assertEqual(result["requirement_ids"], ["REQ-FRESH-01"])
            self.assertEqual(result["content_sha256"], content_sha256(output / "prd.json"))
            evidence = json.loads((output / "generation-evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["model"]["status"], "PASS")

    def test_strict_compatible_generation_instructions_are_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "requirement.json"
            source.write_text('{"requirement_ids":["REQ-STRICT"]}', encoding="utf-8")
            seen = {}

            def fake_runner(*, prompt, workspace, model, timeout_seconds):
                seen["prompt"] = prompt
                (workspace / "architecture.md").write_text("# architecture", encoding="utf-8")
                return {"status": "PASS"}

            execute_generation(module="architecture", input_path=source, output_dir=root / "attempt", run_id="r",
                               project_id="p", node_id="n", parent_node_id=None, model="test", runner=fake_runner)
            self.assertIn("validate-arch-package", seen["prompt"])
            self.assertIn("public-api-service", seen["prompt"])
            self.assertIn("sequenceDiagram", seen["prompt"])
            self.assertIn("bare canonical child_ids", seen["prompt"])
            self.assertIn("must never name the same internal child_id", seen["prompt"])
            self.assertIn("backtick lists", seen["prompt"])
            self.assertIn("### GET /health", seen["prompt"])
            self.assertIn("top-level required key is `event`", seen["prompt"])
            self.assertIn("never declare `status_code` or `body` as an input", seen["prompt"])

    def test_missing_expected_artifact_is_a_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "requirement.md"
            source.write_text("REQ-FRESH-02 needs a root", encoding="utf-8")
            result = execute_generation(
                module="architecture", input_path=source, output_dir=Path(tmp) / "attempt",
                run_id="day4-root", project_id="verilayer", node_id="root", parent_node_id=None,
                model="test-model", runner=lambda **_: {"status": "PASS", "exit_code": 0},
            )
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["error_type"], "EXPECTED_ARTIFACT_MISSING")

    def test_architecture_contract_evidence_requires_parser_visible_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / "requirement.json"
            source.write_text('{"requirement_ids":["REQ-CONTRACT"]}', encoding="utf-8")

            def fake_runner(*, prompt, workspace, model, timeout_seconds):
                (workspace / "architecture.md").write_text(
                    "### GET /health\n**输入**\n```json\n{\"event\": \"health\"}\n```\n"
                    "**输出**\n```json\n{\"status_code\": 200}\n```\n", encoding="utf-8")
                return {"status": "PASS"}

            result = execute_generation(module="architecture", input_path=source, output_dir=root / "attempt", run_id="r",
                                        project_id="p", node_id="n", parent_node_id=None, model="test", runner=fake_runner)
            self.assertEqual(result["interfaces"], ["GET /health"])
            self.assertEqual(result["blocking_issues"], [])


if __name__ == "__main__":
    unittest.main()
