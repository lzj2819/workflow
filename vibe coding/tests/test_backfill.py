import hashlib
import unittest

from vibecode import backfill, orchestrator


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def complete_leaf(run, node_id):
    task_id = f"{run['run_id']}:{node_id}:coding"
    run["coding_queue"].append(
        {"task_id": task_id, "node_id": node_id, "status": "COMPLETED"}
    )
    node = run["nodes"][node_id]
    node["coding_task_id"] = task_id
    node["coding_task_queued"] = True
    node["coding_admission_pending"] = False
    orchestrator.mark_node_completed(run, node_id)


def record(run, node_id):
    return backfill.record_delivery(
        run,
        node_id,
        completion_artifact_id=f"{node_id}-completion",
        completion_hash=digest(f"{node_id}-completion"),
        contract_artifact_id=f"{node_id}-contract",
        contract_hash=digest(f"{node_id}-contract"),
        changed_paths=[f"modules/{node_id}/implementation.py"],
    )


def batch_args(parent_id, change=None):
    return {
        "parent_baseline_hash": digest(f"{parent_id}-baseline"),
        "canonical_version": 1,
        "allowed_write_set": [f"modules/{parent_id}/integration"],
        "protected_paths": [
            f"modules/{parent_id}/contracts",
            f"modules/{parent_id}/siblings",
        ],
        "planned_changes": [
            change or f"modules/{parent_id}/integration/wiring.py"
        ],
        "contract_snapshot_id": f"{parent_id}-contract-snapshot",
        "contract_snapshot_hash": digest(f"{parent_id}-contract-snapshot"),
        "rollback_snapshot_id": f"{parent_id}-rollback",
        "rollback_snapshot_hash": digest(f"{parent_id}-rollback"),
    }


def checks(overrides=None):
    overrides = overrides or {}
    results = {
        name: {
            "status": overrides.get(name, "PASS"),
            "artifact_id": f"{name}-report",
            "artifact_hash": digest(f"{name}-report"),
        }
        for name in backfill.REQUIRED_CHECKS
    }
    contract_status = results["contract"]["status"]
    results["contract"].update(
        {
            "semantic_diff_artifact_id": "semantic-contract-diff",
            "semantic_diff_hash": digest("semantic-contract-diff"),
            "semantic_outcome": "MATCH"
            if contract_status == "PASS"
            else ("LEAF_FIX_REQUIRED" if contract_status == "FAIL" else "ERROR"),
            "breaking_count": 0 if contract_status == "PASS" else 1,
        }
    )
    return results


def apply_args(batch):
    parent_id = batch["parent_node_id"]
    return {
        "current_parent_baseline_hash": batch["parent_baseline_hash"],
        "current_canonical_version": batch["canonical_version"],
        "actual_changed_paths": list(batch["planned_changes"]),
        "completion_artifact_id": f"{parent_id}-backfill-completion",
        "completion_hash": digest(f"{parent_id}-backfill-completion"),
        "contract_artifact_id": f"{parent_id}-backfill-contract",
        "contract_hash": digest(f"{parent_id}-backfill-contract"),
    }


class BackfillBatchTests(unittest.TestCase):
    def test_incomplete_children_are_not_eligible(self):
        run = orchestrator.create_run("run-1", "project-1", "root", 1)
        orchestrator.apply_leaf_decision(
            run,
            "root",
            "CONTINUE_LAYERING",
            [{"child_node_id": "a"}, {"child_node_id": "b"}],
        )
        for child in ("a", "b"):
            orchestrator.apply_leaf_decision(run, child, "STOP_LAYERING")
        complete_leaf(run, "a")
        record(run, "a")
        self.assertEqual(backfill.eligible_parents(run), [])
        with self.assertRaisesRegex(backfill.BackfillError, "not eligible"):
            backfill.prepare_batch(run, "root", **batch_args("root"))

    def test_eligible_parents_are_bottom_up_and_deterministic(self):
        run = orchestrator.create_run("run-2", "project-1", "root", 2)
        orchestrator.apply_leaf_decision(
            run,
            "root",
            "CONTINUE_LAYERING",
            [{"child_node_id": "parent-b"}, {"child_node_id": "parent-a"}],
        )
        for parent in ("parent-b", "parent-a"):
            leaf = f"{parent}-leaf"
            orchestrator.apply_leaf_decision(
                run, parent, "CONTINUE_LAYERING", [{"child_node_id": leaf}]
            )
            orchestrator.apply_leaf_decision(run, leaf, "STOP_LAYERING")
            complete_leaf(run, leaf)
            record(run, leaf)
        self.assertEqual(
            backfill.eligible_parents(run), ["parent-a", "parent-b"]
        )

    def test_preparation_is_idempotent_and_rejects_forbidden_or_changed_plan(self):
        run = self._one_parent_run("run-3")
        first = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        second = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        self.assertIs(first, second)
        changed = batch_args("parent")
        changed["parent_baseline_hash"] = digest("new-baseline")
        with self.assertRaisesRegex(backfill.BackfillError, "different evidence"):
            backfill.prepare_batch(run, "parent", **changed)

        run = self._one_parent_run("run-4")
        protected_args = batch_args(
            "parent", "modules/parent/contracts/api.json"
        )
        protected_args["allowed_write_set"] = ["modules/parent"]
        with self.assertRaisesRegex(backfill.BackfillError, "protected path"):
            backfill.prepare_batch(
                run,
                "parent",
                **protected_args,
            )
        run = self._one_parent_run("run-5")
        with self.assertRaisesRegex(backfill.BackfillError, "outside integration"):
            backfill.prepare_batch(
                run,
                "parent",
                **batch_args("parent", "modules/parent/sibling/internal.py"),
            )

    def test_checks_do_not_bypass_manual_gate(self):
        run = self._one_parent_run("run-6")
        batch = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        with self.assertRaisesRegex(backfill.BackfillError, "approval"):
            backfill.apply_batch(run, batch["batch_id"], **apply_args(batch))
        backfill.record_checks(
            run, batch["batch_id"], checks({"contract": "FAIL"})
        )
        self.assertEqual(batch["status"], "BLOCKED")
        with self.assertRaisesRegex(backfill.BackfillError, "checks"):
            backfill.approve_batch(
                run, batch["batch_id"], approver="owner", note="approve"
            )
        backfill.record_checks(run, batch["batch_id"], checks())
        self.assertEqual(len(batch["check_runs"]), 2)
        self.assertEqual(batch["status"], "CHECKS_PASSED")
        with self.assertRaisesRegex(backfill.BackfillError, "approval"):
            backfill.apply_batch(run, batch["batch_id"], **apply_args(batch))

    def test_contract_check_cannot_falsely_pass_breaking_semantic_diff(self):
        run = self._one_parent_run("run-semantic")
        batch = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        results = checks()
        results["contract"]["semantic_outcome"] = "LEAF_FIX_REQUIRED"
        results["contract"]["breaking_count"] = 1
        with self.assertRaisesRegex(backfill.BackfillError, "cannot PASS"):
            backfill.record_checks(run, batch["batch_id"], results)
        self.assertEqual(batch["status"], "PREPARED")

    def test_stale_child_evidence_blocks_approved_apply(self):
        run = self._one_parent_run("run-7")
        batch = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        backfill.record_checks(run, batch["batch_id"], checks())
        backfill.approve_batch(
            run, batch["batch_id"], approver="integration-owner", note="reviewed"
        )
        run["deliveries"]["leaf"]["completion_hash"] = digest("changed")
        with self.assertRaisesRegex(backfill.BackfillError, "child delivery changed"):
            backfill.apply_batch(run, batch["batch_id"], **apply_args(batch))
        self.assertEqual(batch["status"], "BLOCKED")
        self.assertIn("child delivery changed", batch["blocked_reason"])

    def test_stale_parent_baseline_is_recorded_and_not_applied(self):
        run = self._one_parent_run("run-stale")
        batch = backfill.prepare_batch(run, "parent", **batch_args("parent"))
        backfill.record_checks(run, batch["batch_id"], checks())
        backfill.approve_batch(
            run, batch["batch_id"], approver="integration-owner", note="reviewed"
        )
        arguments = apply_args(batch)
        arguments["current_parent_baseline_hash"] = digest("stale-parent")
        with self.assertRaisesRegex(backfill.BackfillError, "baseline is stale"):
            backfill.apply_batch(run, batch["batch_id"], **arguments)
        self.assertEqual(batch["status"], "BLOCKED")
        self.assertEqual(batch["blocked_reason"], "parent baseline is stale")
        self.assertEqual(run["nodes"]["parent"]["status"], "CONTINUE_LAYERING")

    def test_successful_two_level_backfill_completes_root(self):
        run = self._one_parent_run("run-8")
        parent_batch = backfill.prepare_batch(
            run, "parent", **batch_args("parent")
        )
        backfill.record_checks(run, parent_batch["batch_id"], checks())
        backfill.approve_batch(
            run,
            parent_batch["batch_id"],
            approver="integration-owner",
            note="parent checks reviewed",
        )
        backfill.apply_batch(
            run, parent_batch["batch_id"], **apply_args(parent_batch)
        )
        self.assertEqual(run["deliveries"]["leaf"]["status"], "INTEGRATED")
        self.assertEqual(backfill.eligible_parents(run), ["root"])

        root_batch = backfill.prepare_batch(run, "root", **batch_args("root"))
        backfill.record_checks(run, root_batch["batch_id"], checks())
        backfill.approve_batch(
            run,
            root_batch["batch_id"],
            approver="integration-owner",
            note="root checks reviewed",
        )
        backfill.apply_batch(run, root_batch["batch_id"], **apply_args(root_batch))
        self.assertEqual(run["nodes"]["root"]["status"], "COMPLETED")
        self.assertEqual(run["status"], "COMPLETED")
        self.assertEqual(root_batch["status"], "APPLIED")

    @staticmethod
    def _one_parent_run(run_id):
        run = orchestrator.create_run(run_id, "project-1", "root", 2)
        orchestrator.apply_leaf_decision(
            run,
            "root",
            "CONTINUE_LAYERING",
            [{"child_node_id": "parent"}],
        )
        orchestrator.apply_leaf_decision(
            run,
            "parent",
            "CONTINUE_LAYERING",
            [{"child_node_id": "leaf"}],
        )
        orchestrator.apply_leaf_decision(run, "leaf", "STOP_LAYERING")
        complete_leaf(run, "leaf")
        record(run, "leaf")
        return run


if __name__ == "__main__":
    unittest.main()
