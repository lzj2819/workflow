import json
import sys
import tempfile
import unittest
from pathlib import Path

from vibecode.artifact_contract import content_sha256
from vibecode.executors.coding_executor import execute_coding


class CodingExecutorTests(unittest.TestCase):
    def test_public_tests_are_copied_and_passing_run_is_evidenced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request_dir = root / "input"
            tests_dir = request_dir / "public_tests"
            tests_dir.mkdir(parents=True)
            (tests_dir / "test_notes.py").write_text(
                """from notes import normalize

def test_normalize():
    assert normalize('  ok ') == 'ok'
""",
                encoding="utf-8",
            )
            request = request_dir / "coding-request.json"
            request.write_text(json.dumps({
                "requirement_ids": ["REQ-S1"],
                "model": "test-model",
                "public_prompt": "Implement normalize.",
                "public_tests_dir": "public_tests",
            }), encoding="utf-8")

            def fake_runner(*, prompt, workspace, model, timeout_seconds):
                self.assertIn("hidden tests", prompt)
                self.assertEqual(model, "test-model")
                (workspace / "notes.py").write_text(
                    """def normalize(value):
    return value.strip()
""", encoding="utf-8"
                )
                return {"status": "PASS", "exit_code": 0}

            result = execute_coding(
                request_path=request,
                workspace_root=root / "workspaces",
                output_dir=root / "output",
                run_id="day3-s1",
                project_id="verilayer",
                node_id="s1",
                python=sys.executable,
                max_repairs=0,
                runner=fake_runner,
            )
            self.assertEqual(result["status"], "PASS", result)
            self.assertEqual(result["attempt_count"], 1)
            self.assertEqual(result["pytest_status"], "PASS")
            evidence = json.loads((root / "output/coding-evidence.json").read_text(encoding="utf-8"))
            self.assertEqual(evidence["attempts"][0]["pytest"]["status"], "PASS")
            self.assertIn("tests/test_notes.py", {item["path"] for item in evidence["workspace"]})
            result_path = root / "output/module-result.json"
            self.assertEqual(result["content_sha256"], content_sha256(result_path))


if __name__ == "__main__":
    unittest.main()
