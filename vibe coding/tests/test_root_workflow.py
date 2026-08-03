import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from vibecode.root_workflow import (
    ConfigurationError,
    ContractError,
    EXIT_CONTRACT,
    EXIT_SUCCESS,
    EXIT_VALIDATION,
    RootWorkflow,
    WorkflowInterrupted,
    adapt_canonical_bundle,
    canonical_hash,
    command_adapter,
    sha256_file,
)


class FixtureAdapter:
    def __init__(self, scenario="single", delay=0.0):
        self.scenario = scenario
        self.delay = delay
        self.calls = []
        self.interrupted = False
        self.lock = threading.Lock()
        self.active_design = 0
        self.max_active_design = 0
        self.last_leaf_input = None

    def __call__(self, module, input_path, output_dir, context):
        with self.lock:
            self.calls.append((context["node_id"], module))
        if module in {"architecture", "gherkin"} and self.delay:
            with self.lock:
                self.active_design += 1
                self.max_active_design = max(self.max_active_design, self.active_design)
            time.sleep(self.delay)
            with self.lock:
                self.active_design -= 1
        if self.scenario == "interrupt" and module == "architecture" and not self.interrupted:
            self.interrupted = True
            raise WorkflowInterrupted()
        if self.scenario == "branch_failure" and module == "architecture":
            return {"status": "ERROR", "error_type": "FIXTURE", "error_message": "architecture failed", "output_artifacts": []}
        if self.scenario in {"mock_fail", "mock_error"} and module == "mocktest":
            status = "ERROR" if self.scenario == "mock_error" else "FAIL"
            return {"status": status, "error_type": "DEFECT", "error_message": "architecture defect",
                    "defect_count": 1, "next_action": "RETURN_TO_VALIDATION" if status == "ERROR" else "RETURN_TO_ARCHITECTURE",
                    "output_artifacts": []}
        artifact = output_dir / f"{module}.json"
        node_id = context["node_id"]
        prd_id = f"prd:{node_id}"
        payload = {"artifact_schema_version": "fixture/v1", "artifact_id": f"{module}:{node_id}",
                   "run_id": context["run_id"], "project_id": context["project_id"], "node_id": node_id,
                   "status": "PASS"}
        if module == "prd":
            payload.update({"artifact_schema_version": "prd/v3", "artifact_id": prd_id})
        elif module == "architecture":
            payload.update({"artifact_schema_version": "architecture/v2", "source_prd_id": prd_id,
                            "ready_for_downstream": True, "payload": {"contracts": [{"id": "fixture.api"}]},
                            "revision": 2 if context.get("workflow_action") == "repair" else 1})
        elif module == "gherkin":
            payload.update({"artifact_schema_version": "testcases/v2", "source_prd": {"artifact_id": prd_id},
                            "blocked_items": [], "testcases": [{"tc_id": "TC-1"}]})
        elif module == "mocktest":
            first_repair_failure = self.scenario == "mock_repair" and sum(
                1 for _, called_module in self.calls if called_module == "mocktest"
            ) == 1
            payload.update({"artifact_schema_version": "mocktest-report/v2",
                            "states": {"overall": "FAIL" if first_repair_failure else "PASS"},
                            "coverage": {"total": 1, "evaluated": 1},
                            "findings": ([{"finding_id": "F-1", "tc_ids": ["TC-1"]}]
                                         if first_repair_failure else [])})
        artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        artifacts = [str(artifact)]
        if module == "mocktest":
            evidence = output_dir / "leaf_gate_evidence.json"
            evidence.write_text(json.dumps({"artifact_schema_version": "mocktest-leaf-evidence/v2", "status": "PASS"}), encoding="utf-8")
            artifacts.append(str(evidence))
        result = {"status": "PASS", "output_artifacts": artifacts, "token_usage": 2, "estimated_cost": 0.01}
        if module == "mocktest":
            result["coverage"] = payload["coverage"]
        if module == "mocktest" and payload["states"]["overall"] == "FAIL":
            result.update({"status": "FAIL", "next_action": "RETURN_TO_ARCHITECTURE",
                           "defect_count": 1, "finding_ids": ["F-1"], "affected_testcase_ids": ["TC-1"],
                           "coverage": payload["coverage"]})
        if module == "architecture":
            result.update({"interfaces": ["fixture.api"], "blocking_issues": []})
        if module == "leaf_gate":
            self.last_leaf_input = json.loads(input_path.read_text(encoding="utf-8"))
            if self.scenario in {"recursive", "contract_conflict"} and context["node_id"] == "root":
                result.update({"decision": "CONTINUE_LAYERING", "admission_state": "ADMITTED", "bundle_verified": True,
                               "proposed_children": [
                                   {"child_node_id": "child-a", "parent_node_id": "root", "requirement_ids": ["R1"], "requirement": {"text": "A"}},
                                   {"child_node_id": "child-b", "parent_node_id": "root", "requirement_ids": ["R2"], "requirement": {"text": "B"}},
                               ]})
            else:
                result.update({"decision": "STOP_LAYERING", "admission_state": "ADMITTED", "bundle_verified": True})
        if module == "backfill":
            conflict = self.scenario == "contract_conflict"
            difference = [{"type": "PARAMETER_TYPE_CHANGED", "interface_id": "fixture.api", "path": "parameters.id.type",
                           "breaking": True, "parent": "string", "child": "integer"}] if conflict else []
            result["contract_diff"] = {"schema_version": "1.0", "status": "FAIL" if conflict else "PASS",
                                       "outcome": "CONTRACT_CHANGE_REQUIRED" if conflict else "MATCH",
                                       "parent_contract_id": "parent", "child_contract_id": "child",
                                       "parent_hash": "a" * 64, "child_hash": "b" * 64,
                                       "breaking_count": int(conflict), "compatible_count": 0,
                                       "differences": difference, "validation_errors": []}
            result["checks"] = {name: ("FAIL" if conflict and name == "contract" else "PASS") for name in
                                ("contract", "provider_compatibility", "consumer_compatibility", "parent_integration", "feature_smoke", "regression")}
        if module == "coding":
            result["changed_paths"] = [f"nodes/{context['node_id']}/implementation.py"]
        return result


class RootWorkflowTests(unittest.TestCase):
    def make(self, base, adapter, **overrides):
        source = Path(base) / "requirement.json"
        if not source.exists():
            source.write_text('{"requirement":"demo"}', encoding="utf-8")
        values = dict(output_root=Path(base) / "artifacts", run_id="run-1", project_id="project-1",
                      root_node_id="root", input_path=source, input_kind="requirement",
                      config={"module_versions": {name: "fixture-1" for name in ("prd", "architecture", "gherkin", "mocktest", "leaf_gate", "coding", "backfill", "integration")},
                              "backfill_approvals": {"root": {"approver": "integration-owner", "note": "fixture approval"}}},
                      adapter=adapter, mode="full_recursive", branch_mode="parallel", max_depth=2,
                      retry_limit=1, model="fixture-model", model_parameters={"temperature": 0}, random_seed=7)
        values.update(overrides)
        return RootWorkflow(**values)

    def test_single_layer_emits_authoritative_reports(self):
        with tempfile.TemporaryDirectory() as base:
            workflow = self.make(base, FixtureAdapter())
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            run_dir = Path(base) / "artifacts" / "run-1"
            expected = {"run_manifest.json", "run_report.json", "run_report.md", "node_tree.json",
                        "contract_diff_report.json", "experiment_metrics.json", "execution_log.json"}
            self.assertTrue(expected.issubset({item.name for item in run_dir.iterdir()}))
            report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "COMPLETED")
            self.assertEqual(report["node_count"], 1)
            self.assertEqual(report["stop_layering_count"], 1)
            self.assertTrue(report["full_run"])
            self.assertGreater(report["model_call_count"], 0)
            self.assertTrue(json.loads((run_dir / "execution_log.json").read_text(encoding="utf-8")))
            required_log_fields = set(json.loads((Path(__file__).resolve().parents[1] / "vibecode/schemas/execution-log.schema.json").read_text(encoding="utf-8"))["items"]["required"])
            for event in json.loads((run_dir / "execution_log.json").read_text(encoding="utf-8")):
                self.assertTrue(required_log_fields.issubset(event))

    def test_two_layer_recursive_backfill_reaches_root(self):
        with tempfile.TemporaryDirectory() as base:
            workflow = self.make(base, FixtureAdapter("recursive"))
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            report = json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["node_count"], 3)
            self.assertEqual(report["max_depth_reached"], 1)
            self.assertEqual(report["continue_layering_count"], 1)
            self.assertEqual(report["stop_layering_count"], 2)
            self.assertEqual(report["human_intervention_count"], 1)

    def test_parallel_join_is_concurrent_and_sequential_is_labelled(self):
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter(delay=0.12)
            self.assertEqual(self.make(base, adapter).run(), EXIT_SUCCESS)
            self.assertEqual(adapter.max_active_design, 2)
        with tempfile.TemporaryDirectory() as base:
            workflow = self.make(base, FixtureAdapter(delay=0.02), branch_mode="sequential")
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            report = json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["sequential_time_label"], "measured")
            self.assertEqual(report["branch_mode"], "sequential")

    def test_branch_error_and_mock_fail_close_downstream(self):
        for scenario in ("branch_failure", "mock_fail", "mock_error"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as base:
                adapter = FixtureAdapter(scenario)
                expected = EXIT_VALIDATION if scenario == "mock_fail" else 3
                self.assertEqual(self.make(base, adapter).run(), expected)
                self.assertNotIn(("root", "coding"), adapter.calls)
                report = json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))
                self.assertNotEqual(report["status"], "COMPLETED")
                if scenario == "branch_failure":
                    self.assertEqual(report["retry_count"], 1)

    def test_mocktest_failure_repairs_architecture_then_revalidates_before_leaf(self):
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter("mock_repair")
            workflow = self.make(base, adapter, config={
                "module_versions": {name: "fixture-1" for name in
                                    ("prd", "architecture", "gherkin", "mocktest", "leaf_gate", "coding", "backfill", "integration")},
                "backfill_approvals": {"root": {"approver": "integration-owner", "note": "fixture approval"}},
                "max_architecture_repairs": 1,
            })
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            self.assertEqual([module for node, module in adapter.calls if node == "root"].count("architecture"), 2)
            self.assertEqual([module for node, module in adapter.calls if node == "root"].count("mocktest"), 2)
            self.assertIsNotNone(adapter.last_leaf_input)
            history = adapter.last_leaf_input["repair_history"]
            self.assertEqual(history["mode"], "REPAIRED")
            self.assertEqual(history["cycles"][0]["affected_testcase_ids"], ["TC-1"])
            self.assertEqual(history["cycles"][0]["revalidated_testcase_ids"], ["TC-1"])

    def test_unhandled_adapter_exception_uses_runtime_exit_four(self):
        with tempfile.TemporaryDirectory() as base:
            fallback = FixtureAdapter()
            def broken(module, input_path, output_dir, context):
                if module == "integration":
                    raise RuntimeError("unexpected fixture crash")
                return fallback(module, input_path, output_dir, context)
            self.assertEqual(self.make(base, broken).run(), 4)
            report = json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "ERROR")

    def test_interrupted_run_resumes_without_rerunning_successes(self):
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter("interrupt")
            workflow = self.make(base, adapter)
            with self.assertRaises(WorkflowInterrupted):
                workflow.run()
            prd_calls = adapter.calls.count(("root", "prd"))
            resumed = self.make(base, adapter, resume=True)
            self.assertEqual(resumed.run(), EXIT_SUCCESS)
            self.assertEqual(adapter.calls.count(("root", "prd")), prd_calls)
            self.assertEqual(json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))["status"], "COMPLETED")

    def test_resume_rejects_changed_input_identity(self):
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter("interrupt")
            with self.assertRaises(WorkflowInterrupted):
                self.make(base, adapter).run()
            (Path(base) / "requirement.json").write_text('{"requirement":"changed"}', encoding="utf-8")
            self.assertEqual(self.make(base, adapter, resume=True).run(), 3)

    def test_resume_rejects_tampered_log_or_declared_output(self):
        for target in ("execution_log.json", "nodes/root/prd/attempt-1/prd.json"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as base:
                adapter = FixtureAdapter()
                self.assertEqual(self.make(base, adapter).run(), EXIT_SUCCESS)
                path = Path(base) / "artifacts/run-1" / target
                path.write_text("tampered", encoding="utf-8")
                self.assertEqual(self.make(base, adapter, resume=True).run(), 3)

    def test_ids_and_dry_run_commands_are_validated_before_artifacts(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaises(ConfigurationError):
                self.make(base, FixtureAdapter(), run_id="../escape")
        with tempfile.TemporaryDirectory() as base:
            missing = command_adapter({name: ["definitely-missing-vibecode-executable"] for name in
                                       ("prd", "architecture", "gherkin", "mocktest", "leaf_gate", "coding", "backfill", "integration")})
            workflow = self.make(base, missing, dry_run=True)
            self.assertEqual(workflow.run(), 3)
            self.assertFalse((Path(base) / "artifacts/run-1").exists())

    def test_sensitive_model_parameter_values_are_not_persisted(self):
        with tempfile.TemporaryDirectory() as base:
            workflow = self.make(base, FixtureAdapter(), model_parameters={"temperature": 0, "api_key": "secret-value"})
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            manifest_text = (Path(base) / "artifacts/run-1/run_manifest.json").read_text(encoding="utf-8")
            log_text = (Path(base) / "artifacts/run-1/execution_log.json").read_text(encoding="utf-8")
            self.assertNotIn("secret-value", manifest_text + log_text)
            self.assertIn("[REDACTED]", manifest_text)

    def test_contract_conflict_uses_contract_exit_and_never_completes(self):
        with tempfile.TemporaryDirectory() as base:
            workflow = self.make(base, FixtureAdapter("contract_conflict"))
            self.assertEqual(workflow.run(), EXIT_CONTRACT)
            report = json.loads((Path(base) / "artifacts/run-1/run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["contract_violation_count"], 1)
            self.assertEqual(report["status"], "ERROR")

    def test_ablation_label_and_dry_run_do_not_invoke_modules(self):
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter()
            workflow = self.make(base, adapter, mode="no_mock")
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            manifest = json.loads((Path(base) / "artifacts/run-1/run_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["is_ablation"])
            self.assertFalse(manifest["full_run"])
            self.assertNotIn(("root", "mocktest"), adapter.calls)
        with tempfile.TemporaryDirectory() as base:
            adapter = FixtureAdapter()
            workflow = self.make(base, adapter, dry_run=True)
            self.assertEqual(workflow.run(), EXIT_SUCCESS)
            run_dir = Path(base) / "artifacts/run-1"
            self.assertEqual({item.name for item in run_dir.iterdir()}, {"dry_run_plan.json"})
            self.assertFalse(adapter.calls)

    def test_public_cli_runs_external_process_fixture(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(__file__).resolve().parents[1]
            completed = subprocess.run(
                [sys.executable, "vibecode/scripts/vibecode.py", "run-workflow",
                 "--requirement", "tests/fixtures/root_workflow/requirement.json",
                 "--config", "tests/fixtures/root_workflow/project-config.single.json",
                 "--output-dir", base, "--run-id", "cli-run", "--project-id", "fixture",
                 "--experiment-mode", "parallel"],
                cwd=root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((Path(base) / "cli-run/run_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "COMPLETED")
            self.assertEqual(report["lifecycle_stage"], "COMPLETED")

    def test_canonical_bundle_adapter_works_without_module_result_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as base:
            output = Path(base)
            for name in ("prd.md", "prd_manifest.json", "validation_report.json", "execution_log.json"):
                (output / name).write_text("{}", encoding="utf-8")
            (output / "prd.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            result = adapt_canonical_bundle("prd", output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(result["output_artifacts"]), 5)

        with tempfile.TemporaryDirectory() as base:
            output = Path(base)
            for name in ("mocktest_report.json", "mocktest_report.md", "leaf_gate_evidence.json", "execution_log.json"):
                (output / name).write_text("{}", encoding="utf-8")
            files = [{"path": name, "sha256": sha256_file(output / name)} for name in
                     ("mocktest_report.json", "mocktest_report.md", "leaf_gate_evidence.json", "execution_log.json")]
            subject = {"schema_version": "1.0", "artifact_schema_version": "mocktest-bundle/v2",
                       "run_id": "run-1", "files": files}
            (output / "bundle_manifest.json").write_text(
                json.dumps({**subject, "bundle_sha256": canonical_hash(subject)}), encoding="utf-8"
            )
            self.assertEqual(adapt_canonical_bundle("mocktest", output)["status"], "FAIL")
            (output / "mocktest_report.md").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ContractError):
                adapt_canonical_bundle("mocktest", output)


if __name__ == "__main__":
    unittest.main()
