import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from vibecode.adapters.common import PRODUCTION_MODULES
from vibecode.executors.evidence import write_json_evidence
from vibecode.executors.pytest_runner import run_pytest
from vibecode.executors.workspace import WorkspaceError, prepare_workspace
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]


class Day2ProductionSkeletonTests(unittest.TestCase):
    def test_config_is_complete_relative_and_fixture_free(self):
        config = json.loads((ROOT / "config/verilayer.production.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config["commands"]), set(PRODUCTION_MODULES))
        self.assertTrue(all("fixture" not in " ".join(command).lower() for command in config["commands"].values()))
        self.assertTrue(all(not Path(part).is_absolute() for command in config["commands"].values() for part in command))

    def test_every_adapter_writes_controlled_error(self):
        source = ROOT / "examples/day2_s1_requirement.json"
        schema = json.loads(
            (ROOT / "vibecode/schemas/verilayer-artifact.schema.json").read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema)
        with tempfile.TemporaryDirectory() as tmp:
            for module in PRODUCTION_MODULES:
                output = Path(tmp) / module
                completed = subprocess.run(
                    [sys.executable, "-m", "vibecode.adapters.production_adapter", "--module", module,
                     "--input", str(source), "--output-dir", str(output), "--run-id", "day2-run",
                     "--project-id", "verilayer", "--node-id", "s1"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads((output / "module-result.json").read_text(encoding="utf-8"))
                self.assertEqual(result["module"], module)
                self.assertEqual(result["status"], "ERROR")
                self.assertEqual(result["error_type"], "MODULE_NOT_IMPLEMENTED")
                self.assertEqual(result["schema_version"], "verilayer-artifact/v0.2")
                self.assertEqual(result["output_artifacts"], [])
                self.assertEqual(sorted(validator.iter_errors(result), key=lambda error: list(error.path)), [])

    def test_workspace_evidence_and_pytest_runner_are_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspaces"
            workspace = prepare_workspace(root, "day2-run", "s1")
            self.assertTrue(workspace.is_dir())
            with self.assertRaises(WorkspaceError):
                prepare_workspace(root, "../escape", "s1")
            evidence = write_json_evidence(workspace, "pytest-result.json", {"status": "PENDING"})
            self.assertEqual(evidence["path"], "pytest-result.json")
            test_file = workspace / "test_smoke.py"
            test_file.write_text("def test_smoke():\n    assert True\n", encoding="utf-8")
            result = run_pytest(python=sys.executable, workspace=workspace, timeout_seconds=30)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
