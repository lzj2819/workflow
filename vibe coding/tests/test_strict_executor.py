import json
import re
import tempfile
import unittest
from pathlib import Path

from vibecode.executors.strict_executor import execute_strict


class StrictExecutorTests(unittest.TestCase):
    def test_complete_pass_keeps_audit_and_semantics_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            feature, architecture, output = root / "task.feature", root / "architecture.md", root / "run"
            feature.write_text("Feature: x", encoding="utf-8")
            architecture.write_text("# x", encoding="utf-8")
            phase = {"component": False, "validator": False}

            def driver(args):
                command = args[0]
                output.mkdir(parents=True, exist_ok=True)
                if command == "next-components":
                    pending = []
                    if not phase["component"]:
                        folder = output / "scenarios/SC-1"; folder.mkdir(parents=True, exist_ok=True)
                        prompt, raw, pending_file = folder / "hop.txt", folder / "raw.json", folder / "pending.json"
                        prompt.write_text("component prompt", encoding="utf-8")
                        item = {"prompt_file": str(prompt), "raw_response_file": str(raw), "pending_file": str(pending_file)}
                        pending_file.write_text(json.dumps(item), encoding="utf-8"); pending = [item]
                    (output / "pending_components.json").write_text(json.dumps(pending), encoding="utf-8")
                elif command == "consume-component":
                    self.assertTrue((output / "scenarios/SC-1/raw.json").is_file()); phase["component"] = True
                elif command == "next-validators":
                    pending = []
                    if not phase["validator"]:
                        folder = output / "scenarios/SC-1"; folder.mkdir(parents=True, exist_ok=True)
                        prompt, raw, pending_file = folder / "validator.txt", folder / "validator.json", folder / "validator-pending.json"
                        prompt.write_text("validator prompt", encoding="utf-8")
                        item = {"prompt_file": str(prompt), "raw_response_file": str(raw), "pending_file": str(pending_file)}
                        pending_file.write_text(json.dumps(item), encoding="utf-8"); pending = [item]
                    (output / "pending_validators.json").write_text(json.dumps(pending), encoding="utf-8")
                elif command == "consume-validator":
                    self.assertTrue((output / "scenarios/SC-1/validator.json").is_file()); phase["validator"] = True
                elif command == "finalize":
                    formal = output / "formal"; formal.mkdir(exist_ok=True)
                    (formal / "mocktest_report.json").write_text(json.dumps({"execution_status": "COMPLETED", "validation_status": "PASS"}), encoding="utf-8")
                    (output / "strict_audit.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
                return 0

            def runner(*, prompt, workspace, model, timeout_seconds):
                path = re.search(r"`([^`]+)`", prompt).group(1)
                target = workspace / path; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}", encoding="utf-8")
                return {"status": "PASS"}

            result = execute_strict(feature_path=feature, architecture_path=architecture, output_dir=output,
                                    python="python", driver=root / "driver.py", model="test", run_id="r", project_id="p",
                                    node_id="n", parent_node_id=None, runner=runner, driver_call=driver)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["execution_complete"])
            self.assertEqual(result["semantic_status"], "PASS")
            self.assertEqual(result["strict_audit_status"], "PASS")
            self.assertEqual(len(result["model_events"]), 2)

    def test_semantic_gate_block_is_fail_not_tool_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); feature = root / "task.feature"; architecture = root / "architecture.md"
            feature.write_text("Feature: x", encoding="utf-8"); architecture.write_text("# x", encoding="utf-8")
            def driver(args):
                output = root / "run"; output.mkdir(exist_ok=True)
                if args[0] == "next-components":
                    (output / "pending_components.json").write_text("[]", encoding="utf-8")
                return 1 if args[0] == "prepare-validators" else 0
            result = execute_strict(feature_path=feature, architecture_path=architecture, output_dir=root / "run",
                                    python="python", driver=root / "driver.py", model="test", run_id="r", project_id="p",
                                    node_id="n", parent_node_id=None, driver_call=driver)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["error_type"], "STRICT_SEMANTIC_BLOCKED")


if __name__ == "__main__":
    unittest.main()
