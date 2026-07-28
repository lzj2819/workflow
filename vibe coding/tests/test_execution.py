import hashlib
import tempfile
import unittest
from pathlib import Path

from vibecode import execution, orchestrator


HASH = hashlib.sha256(b"input").hexdigest()


def evidence_for(run, node_id="root"):
    def artifact(name, status="PASS"):
        return {
            "run_id": run["run_id"],
            "project_id": run["project_id"],
            "node_id": node_id,
            "artifact_id": f"{name}-artifact",
            "content_hash": hashlib.sha256(name.encode()).hexdigest(),
            "status": status,
        }

    evidence = {
        "prd": artifact("prd"),
        "architecture": artifact("architecture"),
        "testcases": artifact("testcases"),
        "mocktest": artifact("mocktest"),
        "leaf_gate": artifact("leaf-gate", "STOP_LAYERING"),
        "contract": artifact("contract"),
    }
    evidence["mocktest"].update(
        {
            "architecture_artifact_id": evidence["architecture"]["artifact_id"],
            "testcases_artifact_id": evidence["testcases"]["artifact_id"],
        }
    )
    evidence["contract"].update(
        {"interfaces": ["GET /demo"], "blocking_issues": []}
    )
    required = {
        evidence[key]["artifact_id"]: evidence[key]["content_hash"]
        for key in ("prd", "architecture", "testcases", "mocktest", "contract")
    }
    evidence["leaf_gate"].update(
        {
            "decision": "STOP_LAYERING",
            "evidence_complete": True,
            "input_artifacts": list(required),
            "input_hashes": required,
        }
    )
    return evidence


class CodingAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.run = orchestrator.create_run("run-1", "project-1", "root", 1)
        orchestrator.apply_leaf_decision(self.run, "root", "STOP_LAYERING")

    def test_success_is_idempotent_and_completion_requires_task(self):
        evidence = evidence_for(self.run)
        first = execution.admit_coding(self.run, "root", evidence)
        second = execution.admit_coding(self.run, "root", evidence)
        self.assertIs(first, second)
        self.assertEqual(len(self.run["coding_queue"]), 1)
        changed = evidence_for(self.run)
        changed["prd"]["content_hash"] = "f" * 64
        changed["leaf_gate"]["input_hashes"]["prd-artifact"] = "f" * 64
        with self.assertRaisesRegex(execution.AdmissionError, "evidence differs"):
            execution.admit_coding(self.run, "root", changed)
        with self.assertRaises(orchestrator.GraphError):
            orchestrator.mark_node_completed(self.run, "root")
        execution.complete_coding_task(self.run, first["task_id"])
        orchestrator.mark_node_completed(self.run, "root")
        self.assertEqual(self.run["status"], "COMPLETED")

    def test_missing_or_mismatched_evidence_is_rejected_without_queueing(self):
        evidence = evidence_for(self.run)
        evidence.pop("contract")
        with self.assertRaises(execution.AdmissionError):
            execution.admit_coding(self.run, "root", evidence)

        evidence = evidence_for(self.run)
        evidence["architecture"]["node_id"] = "other"
        with self.assertRaisesRegex(execution.AdmissionError, "node_id mismatch"):
            execution.admit_coding(self.run, "root", evidence)
        self.assertEqual(self.run["coding_queue"], [])

    def test_mocktest_fail_and_error_both_close_admission(self):
        for status in ("FAIL", "ERROR"):
            evidence = evidence_for(self.run)
            evidence["mocktest"]["status"] = status
            with self.subTest(status=status), self.assertRaisesRegex(
                execution.AdmissionError, "Mocktest must PASS"
            ):
                execution.admit_coding(self.run, "root", evidence)
        self.assertEqual(self.run["coding_queue"], [])

    def test_hash_provenance_and_blocking_contract_are_rejected(self):
        evidence = evidence_for(self.run)
        evidence["leaf_gate"]["input_hashes"]["prd-artifact"] = "0" * 64
        with self.assertRaisesRegex(execution.AdmissionError, "input hashes"):
            execution.admit_coding(self.run, "root", evidence)

        evidence = evidence_for(self.run)
        evidence["contract"]["blocking_issues"] = ["interface unresolved"]
        with self.assertRaisesRegex(execution.AdmissionError, "blocking issues"):
            execution.admit_coding(self.run, "root", evidence)


class AttemptRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.run = orchestrator.create_run("run-2", "project-1", "root", 1)

    def test_interrupted_attempt_resumes_same_stage_from_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "mocktest.json"
            checkpoint.write_text("{}", encoding="utf-8")
            checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

            first = execution.start_attempt(
                self.run, "root", "MOCKTEST", {"input": HASH}, max_retries=1
            )
            execution.finish_attempt(
                self.run,
                "root",
                first["attempt_id"],
                "PASS",
                output_hashes={"mocktest": checkpoint_hash},
                checkpoint_artifacts={"mocktest.json": checkpoint_hash},
            )
            leaf = execution.start_attempt(
                self.run, "root", "LEAF_GATE", {"mocktest": checkpoint_hash}, max_retries=1
            )
            execution.interrupt_attempt(
                self.run, "root", leaf["attempt_id"], ["partial-leaf.json"]
            )

            with self.assertRaisesRegex(execution.ExecutionError, "input hashes differ"):
                execution.resume_attempt(
                    self.run,
                    "root",
                    {"mocktest": "f" * 64},
                    root,
                    max_retries=1,
                )

            resumed = execution.resume_attempt(
                self.run,
                "root",
                {"mocktest": checkpoint_hash},
                root,
                max_retries=1,
            )
            self.assertEqual(resumed["stage"], "LEAF_GATE")
            self.assertEqual(resumed["retry_count"], 1)
            self.assertEqual(resumed["checkpoint_attempt_id"], first["attempt_id"])
            self.assertNotIn("partial-leaf.json", resumed["input_hashes"])

    def test_retry_is_bounded_and_failures_are_classified(self):
        first = execution.start_attempt(
            self.run, "root", "MOCKTEST", {"input": HASH}, max_retries=1
        )
        execution.finish_attempt(
            self.run,
            "root",
            first["attempt_id"],
            "FAIL",
            failure_class="BUSINESS_FAIL",
            failure_message="scenario failed",
        )
        with tempfile.TemporaryDirectory() as tmp:
            second = execution.resume_attempt(
                self.run, "root", {"input": HASH}, Path(tmp), max_retries=1
            )
            execution.finish_attempt(
                self.run,
                "root",
                second["attempt_id"],
                "ERROR",
                failure_class="TOOL_ERROR",
                failure_message="runner crashed",
            )
            with self.assertRaisesRegex(execution.ExecutionError, "retry limit"):
                execution.resume_attempt(
                    self.run, "root", {"input": HASH}, Path(tmp), max_retries=1
                )
        self.assertEqual(self.run["status"], "ERROR")
        with self.assertRaises(orchestrator.GraphError):
            orchestrator.apply_leaf_decision(self.run, "root", "STOP_LAYERING")

    def test_corrupt_checkpoint_blocks_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint = root / "stage.json"
            checkpoint.write_text("original", encoding="utf-8")
            expected = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            first = execution.start_attempt(
                self.run, "root", "PRD", {"input": HASH}, max_retries=1
            )
            execution.finish_attempt(
                self.run,
                "root",
                first["attempt_id"],
                "PASS",
                output_hashes={"prd": expected},
                checkpoint_artifacts={"stage.json": expected},
            )
            second = execution.start_attempt(
                self.run, "root", "MOCKTEST", {"prd": expected}, max_retries=1
            )
            execution.interrupt_attempt(self.run, "root", second["attempt_id"], [])
            checkpoint.write_text("corrupt", encoding="utf-8")
            with self.assertRaisesRegex(execution.ExecutionError, "hash mismatch"):
                execution.resume_attempt(
                    self.run, "root", {"prd": expected}, root, max_retries=1
                )

    def test_node_error_prevents_new_downstream_work(self):
        run = orchestrator.create_run("run-closure", "project-1", "root", 1)
        orchestrator.apply_leaf_decision(
            run,
            "root",
            "CONTINUE_LAYERING",
            [{"node_id": "child"}],
        )
        attempt = execution.start_attempt(
            run, "child", "MOCKTEST", {"input": HASH}, max_retries=0
        )
        execution.finish_attempt(
            run,
            "child",
            attempt["attempt_id"],
            "ERROR",
            failure_class="TOOL_ERROR",
            failure_message="mock runner crashed",
        )
        with self.assertRaisesRegex(execution.ExecutionError, "failed runs"):
            execution.start_attempt(
                run, "root", "BACKFILL", {"child": HASH}, max_retries=0
            )


if __name__ == "__main__":
    unittest.main()
