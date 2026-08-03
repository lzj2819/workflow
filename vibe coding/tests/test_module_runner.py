import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "module_runner", ROOT / "vibecode" / "module_runner.py"
)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def pass_result(module, input_hash, output_dir):
    artifact = output_dir / f"{module}.json"
    artifact.write_text(json.dumps({"module": module}), encoding="utf-8")
    return {
        "module": module,
        "status": "PASS",
        "input_hash": input_hash,
        "output_artifacts": [artifact.name],
        "error_type": None,
        "error_message": None,
    }


class DesignJoinTests(unittest.TestCase):
    def test_parallel_workers_overlap_and_join_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text('{"requirement":"demo"}', encoding="utf-8")
            barrier = threading.Barrier(2)
            started = {}

            def overlapping(module, spec, input_path, output_dir, context):
                started[module] = time.perf_counter()
                barrier.wait(timeout=1)
                return pass_result(module, context["input_hash"], output_dir)

            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                None,
                None,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
                runner=overlapping,
            )

            self.assertEqual(joined["status"], "PASS")
            self.assertTrue(joined["mocktest_allowed"])
            self.assertEqual(set(started), {"architecture", "gherkin"})
            self.assertEqual(
                joined["branches"]["architecture"]["project_id"], "project-1"
            )
            self.assertEqual(
                joined["branches"]["architecture"]["artifact_type"], "module_result"
            )
            self.assertTrue((root / "attempt-1" / "design-join.json").is_file())

    def test_sequential_mode_has_deterministic_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")
            order = []

            def ordered(module, spec, input_path, output_dir, context):
                order.append(module)
                return pass_result(module, context["input_hash"], output_dir)

            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                None,
                None,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
                mode="sequential",
                runner=ordered,
            )
            self.assertEqual(order, ["architecture", "gherkin"])
            self.assertEqual(joined["status"], "PASS")

    def test_one_branch_failure_closes_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")

            def one_fails(module, spec, input_path, output_dir, context):
                if module == "gherkin":
                    return {
                        "module": module,
                        "status": "ERROR",
                        "input_hash": context["input_hash"],
                        "output_artifacts": [],
                        "error_type": "TEST_FAILURE",
                        "error_message": "gherkin failed",
                    }
                return pass_result(module, context["input_hash"], output_dir)

            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                None,
                None,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
                runner=one_fails,
            )
            self.assertEqual(joined["status"], "ERROR")
            self.assertFalse(joined["mocktest_allowed"])

    def test_stale_attempt_is_rejected_before_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")
            attempt = root / "attempt-1"
            attempt.mkdir()
            (attempt / "old.json").write_text("{}", encoding="utf-8")
            called = []

            def should_not_run(*args):
                called.append(True)
                raise AssertionError("runner should not execute")

            with self.assertRaisesRegex(RUNNER.JoinError, "stale artifacts"):
                RUNNER.execute_design_branches(
                    prd,
                    attempt,
                    None,
                    None,
                    run_id="run-1",
                    project_id="project-1",
                    node_id="root",
                    runner=should_not_run,
                )
            self.assertEqual(called, [])

    def test_hash_mismatch_and_output_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")

            def invalid(module, spec, input_path, output_dir, context):
                if module == "architecture":
                    result = pass_result(module, "wrong-hash", output_dir)
                else:
                    outside = output_dir.parent / "outside.json"
                    outside.write_text("{}", encoding="utf-8")
                    result = pass_result(module, context["input_hash"], output_dir)
                    result["output_artifacts"] = ["../outside.json"]
                return result

            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                None,
                None,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
                runner=invalid,
            )
            self.assertEqual(joined["status"], "ERROR")
            self.assertEqual(joined["branches"]["architecture"]["status"], "ERROR")
            self.assertEqual(joined["branches"]["gherkin"]["status"], "ERROR")

    def test_input_snapshot_mutation_closes_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")

            def mutating(module, spec, input_path, output_dir, context):
                if module == "gherkin":
                    input_path.write_text('{"mutated":true}', encoding="utf-8")
                return pass_result(module, context["input_hash"], output_dir)

            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                None,
                None,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
                mode="sequential",
                runner=mutating,
            )
            self.assertEqual(joined["status"], "ERROR")
            self.assertFalse(joined["mocktest_allowed"])
            self.assertIn("PRD input changed", joined["errors"][-1])

    def test_command_adapter_reads_current_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prd = root / "prd.json"
            prd.write_text("{}", encoding="utf-8")
            adapter = root / "adapter.py"
            adapter.write_text(
                "\n".join(
                    [
                        "import json, sys",
                        "from pathlib import Path",
                        "output = Path(sys.argv[2])",
                        "module = sys.argv[4]",
                        "artifact = output / (module + '.json')",
                        "artifact.write_text('{}', encoding='utf-8')",
                        "result = {'module': module, 'status': 'PASS', 'input_hash': sys.argv[3], 'output_artifacts': [artifact.name], 'error_type': None, 'error_message': None}",
                        "(output / 'module-result.json').write_text(json.dumps(result), encoding='utf-8')",
                    ]
                ),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(adapter),
                "{input}",
                "{output_dir}",
                "{input_hash}",
                "{module}",
            ]
            joined = RUNNER.execute_design_branches(
                prd,
                root / "attempt-1",
                command,
                command,
                run_id="run-1",
                project_id="project-1",
                node_id="root",
            )
            self.assertEqual(joined["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
