import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "vibecode_cli", ROOT / "vibecode" / "scripts" / "vibecode.py"
)
assert SPEC and SPEC.loader
VIBECODE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VIBECODE)
ORCHESTRATOR_SPEC = importlib.util.spec_from_file_location(
    "vibecode_orchestrator", ROOT / "vibecode" / "orchestrator.py"
)
assert ORCHESTRATOR_SPEC and ORCHESTRATOR_SPEC.loader
ORCHESTRATOR = importlib.util.module_from_spec(ORCHESTRATOR_SPEC)
ORCHESTRATOR_SPEC.loader.exec_module(ORCHESTRATOR)


def complete_test_leaf(run, node_id):
    task_id = f"{run['run_id']}:{node_id}:coding"
    run["coding_queue"].append(
        {"task_id": task_id, "node_id": node_id, "status": "COMPLETED"}
    )
    node = run["nodes"][node_id]
    node["coding_task_id"] = task_id
    node["coding_task_queued"] = True
    node["coding_admission_pending"] = False


class LeafDecisionTests(unittest.TestCase):
    def test_only_canonical_decisions_normalize(self) -> None:
        expected = {
            "STOP_LAYERING": "STOP_LAYERING",
            "CONTINUE_LAYERING": "CONTINUE_LAYERING",
        }
        for source, target in expected.items():
            with self.subTest(source=source):
                self.assertEqual(VIBECODE.normalize_leaf_decision(source), target)
        for legacy in ("ERROR", "LEAF_READY", "DONE_LAYERING", "NEEDS_DECOMPOSITION"):
            self.assertIsNone(VIBECODE.normalize_leaf_decision(legacy))

    def test_scanner_admits_only_stop_layering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_node(root / "stop", "STOP_LAYERING")
            self._write_node(root / "legacy", "LEAF_READY")
            self._write_node(root / "continue", "CONTINUE_LAYERING")
            self._write_node(root / "error", "ERROR")

            leaves = VIBECODE.scan_leaves(root)

        self.assertEqual({leaf["node_id"] for leaf in leaves}, {"stop"})
        self.assertTrue(all(leaf["decision"] == "STOP_LAYERING" for leaf in leaves))

    @staticmethod
    def _write_node(node: Path, decision: str) -> None:
        leaf_output = node / "leaf_gate" / "attempt-1"
        leaf_output.mkdir(parents=True)
        refs = {}
        for role, name in {
            "prd": "prd.json", "architecture": "architecture.json", "testcases": "testcases.json",
            "mocktest_report": "mocktest_report.json", "mocktest_evidence": "leaf_gate_evidence.json",
        }.items():
            path = node / name
            path.write_text(json.dumps({"artifact_id": f"{role}:{node.name}"}), encoding="utf-8")
            refs[role] = {"path": name, "sha256": VIBECODE.file_sha256(path)}
        (node / "testcases.feature").write_text("Feature: Acceptance\n", encoding="utf-8")
        (node / "leaf_gate_input.json").write_text(
            json.dumps({"current_artifacts": refs}), encoding="utf-8"
        )
        report = leaf_output / "leaf_gate_report.json"
        report.write_text(json.dumps({"artifact_schema_version": "leaf-gate-report/v2",
                                      "identity": {"node_id": node.name, "parent_node_id": None},
                                      "admission": {"state": "ADMITTED"},
                                      "decision": {"value": decision}}), encoding="utf-8")
        (leaf_output / "leaf_gate_report.md").write_text("# Leaf Gate\n", encoding="utf-8")
        (leaf_output / "next_action.json").write_text(json.dumps({"type": "VIBECODE"}), encoding="utf-8")
        (leaf_output / "execution_log.json").write_text("[]", encoding="utf-8")
        files = [{"path": name, "sha256": VIBECODE.file_sha256(leaf_output / name)} for name in
                 ("leaf_gate_report.json", "leaf_gate_report.md", "next_action.json", "execution_log.json")]
        (leaf_output / "bundle_manifest.json").write_text(
            json.dumps({"files": files, "bundle_sha256": VIBECODE.canonical_hash(files)}), encoding="utf-8"
        )


class SchemaTests(unittest.TestCase):
    def test_baseline_schemas_are_valid_json_and_share_public_statuses(self) -> None:
        schema_dir = ROOT / "vibecode" / "schemas"
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in schema_dir.glob("*.schema.json")
        }
        self.assertEqual(
            set(schemas),
            {
                "common-envelope.schema.json",
                "module-result.schema.json",
                "leaf-decision.schema.json",
                "state-event.schema.json",
                "node.schema.json",
                "run.schema.json",
                "attempt.schema.json",
                "coding-task.schema.json",
                "delivery.schema.json",
                "backfill-batch.schema.json",
                "contract.schema.json",
                "contract-diff.schema.json",
                "run-manifest.schema.json",
                "run-report.schema.json",
                "execution-log.schema.json",
                "experiment-metrics.schema.json",
                "node-tree.schema.json",
                "contract-diff-report.schema.json",
            },
        )
        status_enum = set(
            schemas["common-envelope.schema.json"]["properties"]["status"]["enum"]
        )
        self.assertEqual(status_enum, VIBECODE.PUBLIC_STATUSES)
        self.assertTrue(
            VIBECODE.LEAF_DECISIONS.issubset(status_enum)
        )


class RunGraphTests(unittest.TestCase):
    def test_single_stop_node_queues_once_and_completes_run(self) -> None:
        run = ORCHESTRATOR.create_run("run-1", "project-1", "root", 0)
        ORCHESTRATOR.apply_leaf_decision(run, "root", "STOP_LAYERING")
        ORCHESTRATOR.apply_leaf_decision(run, "root", "STOP_LAYERING")
        self.assertFalse(run["nodes"]["root"]["coding_task_queued"])
        self.assertTrue(run["nodes"]["root"]["coding_admission_pending"])
        self.assertEqual(run["nodes"]["root"]["children"], [])
        complete_test_leaf(run, "root")
        ORCHESTRATOR.mark_node_completed(run, "root")
        self.assertEqual(run["status"], "COMPLETED")

    def test_two_level_continue_is_idempotent_and_parent_waits(self) -> None:
        run = ORCHESTRATOR.create_run("run-2", "project-1", "root", 2)
        children = [{"child_node_id": "child", "parent_node_id": "root"}]
        ORCHESTRATOR.apply_leaf_decision(run, "root", "CONTINUE_LAYERING", children)
        ORCHESTRATOR.apply_leaf_decision(run, "root", "CONTINUE_LAYERING", children)
        self.assertEqual(run["nodes"]["root"]["children"], ["child"])
        with self.assertRaises(ORCHESTRATOR.GraphError):
            ORCHESTRATOR.mark_node_completed(run, "root")
        ORCHESTRATOR.apply_leaf_decision(run, "child", "STOP_LAYERING")
        complete_test_leaf(run, "child")
        ORCHESTRATOR.mark_node_completed(run, "child")
        ORCHESTRATOR.mark_node_completed(run, "root")
        self.assertEqual(run["status"], "COMPLETED")

    def test_duplicate_and_missing_parent_are_rejected(self) -> None:
        run = ORCHESTRATOR.create_run("run-3", "project-1", "root", 2)
        with self.assertRaisesRegex(ORCHESTRATOR.GraphError, "duplicate node_id"):
            ORCHESTRATOR.add_node(run, "root", None)
        with self.assertRaisesRegex(ORCHESTRATOR.GraphError, "missing parent"):
            ORCHESTRATOR.add_node(run, "child", "missing")

    def test_invalid_child_batch_does_not_partially_schedule(self) -> None:
        run = ORCHESTRATOR.create_run("run-atomic", "project-1", "root", 2)
        with self.assertRaisesRegex(ORCHESTRATOR.GraphError, "requirement_ids"):
            ORCHESTRATOR.apply_leaf_decision(
                run,
                "root",
                "CONTINUE_LAYERING",
                [
                    {"child_node_id": "valid"},
                    {"child_node_id": "invalid", "requirement_ids": "not-a-list"},
                ],
            )
        self.assertEqual(set(run["nodes"]), {"root"})
        self.assertEqual(run["nodes"]["root"]["children"], [])

    def test_cycle_or_broken_parent_graph_is_rejected(self) -> None:
        run = ORCHESTRATOR.create_run("run-4", "project-1", "root", 2)
        ORCHESTRATOR.add_node(run, "child", "root")
        run["nodes"]["child"]["children"].append("root")
        with self.assertRaises(ORCHESTRATOR.GraphError):
            ORCHESTRATOR.validate_run_graph(run)

        run = ORCHESTRATOR.create_run("run-5", "project-1", "root", 2)
        ORCHESTRATOR.add_node(run, "child", "root")
        run["nodes"]["root"]["children"].remove("child")
        run["nodes"]["child"]["parent_node_id"] = "missing"
        with self.assertRaisesRegex(ORCHESTRATOR.GraphError, "missing parent"):
            ORCHESTRATOR.validate_run_graph(run)

    def test_maximum_depth_and_error_failure_closure(self) -> None:
        run = ORCHESTRATOR.create_run("run-6", "project-1", "root", 0)
        with self.assertRaisesRegex(ORCHESTRATOR.GraphError, "max_depth"):
            ORCHESTRATOR.apply_leaf_decision(
                run,
                "root",
                "CONTINUE_LAYERING",
                [{"child_node_id": "too-deep"}],
            )
        ORCHESTRATOR.apply_leaf_decision(
            run, "root", "ERROR", error_message="gate failed"
        )
        self.assertEqual(run["status"], "ERROR")
        self.assertFalse(run["nodes"]["root"]["coding_task_queued"])
        self.assertEqual(run["nodes"]["root"]["children"], [])


class StateLedgerTests(unittest.TestCase):
    def test_legacy_state_migrates_only_when_explicitly_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            event_path = Path(tmp) / "execution-log.jsonl"
            with mock.patch.object(VIBECODE, "STATE_PATH", state_path), mock.patch.object(
                VIBECODE, "EVENT_LOG_PATH", event_path
            ):
                legacy = VIBECODE.default_state("workspace/nodes", ".", "single")
                for key in ("state_id", "revision", "last_event_id"):
                    legacy.pop(key)
                legacy["version"] = 1
                VIBECODE.write_json(state_path, legacy)
                self.assertEqual(VIBECODE.load_state()["version"], 1)

                VIBECODE.history(legacy, "legacy-migration", "test")
                VIBECODE.save_state(legacy)

                migrated = VIBECODE.load_state()
                self.assertEqual(migrated["version"], 2)
                self.assertEqual(migrated["revision"], 1)
                self.assertEqual(VIBECODE.audit_state(), [])

    def test_audit_detects_divergence_and_explicit_repair_records_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            event_path = Path(tmp) / "execution-log.jsonl"
            with mock.patch.object(VIBECODE, "STATE_PATH", state_path), mock.patch.object(
                VIBECODE, "EVENT_LOG_PATH", event_path
            ):
                state = VIBECODE.default_state("workspace/nodes", ".", "single")
                VIBECODE.history(state, "init", "test")
                VIBECODE.save_state(state)
                self.assertEqual(VIBECODE.audit_state(), [])

                corrupted = VIBECODE.load_state()
                corrupted["stage"] = "DONE"
                VIBECODE.write_json(state_path, corrupted)
                self.assertTrue(
                    any("diverges" in error for error in VIBECODE.audit_state())
                )

                self.assertEqual(VIBECODE.audit_state(repair=True), [])
                repaired = VIBECODE.load_state()
                self.assertEqual(repaired["stage"], "INIT")
                self.assertEqual(repaired["revision"], 2)
                self.assertEqual(repaired["history"][-1]["event"], "repair-state")
                self.assertEqual(len(event_path.read_text(encoding="utf-8").splitlines()), 2)

    def test_audit_detects_broken_event_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            event_path = Path(tmp) / "execution-log.jsonl"
            with mock.patch.object(VIBECODE, "STATE_PATH", state_path), mock.patch.object(
                VIBECODE, "EVENT_LOG_PATH", event_path
            ):
                state = VIBECODE.default_state("workspace/nodes", ".", "single")
                VIBECODE.history(state, "init", "test")
                VIBECODE.save_state(state)
                VIBECODE.history(state, "advance", "test")
                VIBECODE.save_state(state)

                events = [
                    json.loads(line)
                    for line in event_path.read_text(encoding="utf-8").splitlines()
                ]
                events[1]["previous_event_id"] = "broken"
                VIBECODE.atomic_write_text(
                    event_path,
                    "".join(
                        json.dumps(event, separators=(",", ":")) + "\n"
                        for event in events
                    ),
                )

                self.assertTrue(
                    any("broken previous_event_id" in error for error in VIBECODE.audit_state())
                )


if __name__ == "__main__":
    unittest.main()
