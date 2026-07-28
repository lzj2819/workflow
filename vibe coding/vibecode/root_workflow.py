"""Recoverable root workflow orchestration and experiment reporting."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecode.backfill import (REQUIRED_CHECKS, apply_batch, approve_batch, prepare_batch,
                               record_checks, record_delivery)
from vibecode.execution import admit_coding, complete_coding_task
from vibecode.orchestrator import GraphError, apply_leaf_decision, create_run, mark_node_completed


EXIT_SUCCESS = 0
EXIT_VALIDATION = 2
EXIT_CONFIG = 3
EXIT_RUNTIME = 4
EXIT_CONTRACT = 5
MODES = {"full_recursive", "non_recursive", "no_mock", "no_leaf_gate"}
BRANCH_MODES = {"parallel", "sequential"}
MODULES = ("prd", "architecture", "gherkin", "mocktest", "leaf_gate", "coding", "backfill", "integration")
Adapter = Callable[[str, Path, Path, dict[str, Any]], dict[str, Any]]


class WorkflowError(ValueError):
    exit_code = EXIT_VALIDATION


class ConfigurationError(WorkflowError):
    exit_code = EXIT_CONFIG


class ContractError(WorkflowError):
    exit_code = EXIT_CONTRACT


class WorkflowInterrupted(BaseException):
    """Testable interruption that leaves the checkpoint resumable."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def command_adapter(commands: dict[str, list[str]], *, cwd: str | None = None) -> Adapter:
    def run(module: str, input_path: Path, output_dir: Path, context: dict[str, Any]) -> dict[str, Any]:
        command = commands.get(module)
        if not command:
            raise ConfigurationError(f"missing command adapter for module: {module}")
        output_dir.mkdir(parents=True, exist_ok=True)
        values = {**context, "module": module, "input": str(input_path), "output_dir": str(output_dir)}
        rendered = [str(item).format_map(values) for item in command]
        try:
            completed = subprocess.run(rendered, cwd=cwd, capture_output=True, text=True,
                                       timeout=context.get("timeout_seconds"), check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"status": "ERROR", "error_type": type(exc).__name__, "error_message": str(exc)}
        if completed.returncode != 0:
            return {"status": "ERROR", "error_type": "NONZERO_EXIT",
                    "error_message": f"{module} exited with {completed.returncode}"}
        result_path = output_dir / "module-result.json"
        if not result_path.is_file():
            return {"status": "ERROR", "error_type": "MISSING_RESULT",
                    "error_message": f"{module} did not write module-result.json"}
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "ERROR", "error_type": "INVALID_RESULT", "error_message": str(exc)}
        return result
    setattr(run, "configured_modules", frozenset(commands))
    setattr(run, "raw_commands", commands)
    return run


class RootWorkflow:
    def __init__(self, *, output_root: Path, run_id: str, project_id: str,
                 root_node_id: str, input_path: Path, input_kind: str,
                 config: dict[str, Any], adapter: Adapter, mode: str = "full_recursive",
                 branch_mode: str = "parallel", max_depth: int = 8,
                 retry_limit: int = 0, model: str | None = None,
                 model_parameters: dict[str, Any] | None = None, random_seed: int = 0,
                 resume: bool = False, dry_run: bool = False) -> None:
        if mode not in MODES:
            raise ConfigurationError(f"unsupported experiment mode: {mode}")
        if branch_mode not in BRANCH_MODES:
            raise ConfigurationError(f"unsupported branch mode: {branch_mode}")
        if input_kind not in {"requirement", "prd"} or not input_path.is_file():
            raise ConfigurationError("input_kind must be requirement/prd and input must exist")
        if max_depth < 0 or retry_limit < 0:
            raise ConfigurationError("max_depth and retry_limit must be non-negative")
        self._require_safe_id(run_id, "run_id")
        self._require_safe_id(root_node_id, "root_node_id")
        self.output_root = output_root.resolve()
        self.run_dir = self.output_root / run_id
        self.run_id, self.project_id, self.root_node_id = run_id, project_id, root_node_id
        self.input_path, self.input_kind = input_path.resolve(), input_kind
        self.config, self.adapter = config, adapter
        self.mode, self.branch_mode = mode, branch_mode
        self.max_depth, self.retry_limit = max_depth, retry_limit
        self.model, self.model_parameters, self.random_seed = model, self._redact(model_parameters or {}), random_seed
        self.resume, self.dry_run = resume, dry_run
        self.log: list[dict[str, Any]] = []
        self._state_lock = threading.RLock()
        self.metrics = self._empty_metrics()
        self.manifest = self._manifest()
        self.state: dict[str, Any]

    def run(self) -> int:
        started = time.perf_counter()
        previous_duration = 0.0
        try:
            self._prepare()
            previous_duration = float(self.metrics.get("total_duration_ms", 0) or 0)
            if self.dry_run:
                self._write_dry_run()
                return EXIT_SUCCESS
            self._process_node(self.root_node_id, self.input_path, self.input_kind)
            self._integrate_root()
            self.state["status"] = "COMPLETED"
            self.state["lifecycle_stage"] = "COMPLETED"
            return EXIT_SUCCESS
        except WorkflowInterrupted:
            self.state["status"] = "ERROR"
            self.state["lifecycle_stage"] = "FAILED"
            self.state["failed_stage"] = "INTERRUPTED"
            self._checkpoint()
            raise
        except WorkflowError as exc:
            if not hasattr(self, "state"):
                return exc.exit_code
            self.state["status"] = "ERROR" if exc.exit_code != EXIT_VALIDATION else "FAIL"
            self.state["lifecycle_stage"] = "FAILED"
            self.state["failed_stage"] = self.state.get("active_stage")
            self.state["error_message"] = str(exc)
            self._event(self.state.get("active_node_id"), self.state.get("active_stage"), self.state["status"], str(exc))
            return exc.exit_code
        except GraphError as exc:
            if not hasattr(self, "state"):
                return EXIT_VALIDATION
            self.state["status"] = "FAIL"
            self.state["lifecycle_stage"] = "FAILED"
            self.state["failed_stage"] = self.state.get("active_stage")
            self.state["error_message"] = str(exc)
            self._event(self.state.get("active_node_id"), self.state.get("active_stage"), "FAIL", str(exc), "GRAPH_VALIDATION")
            return EXIT_VALIDATION
        except Exception as exc:
            if not hasattr(self, "state"):
                return EXIT_RUNTIME
            self.state["status"] = "ERROR"
            self.state["lifecycle_stage"] = "FAILED"
            self.state["failed_stage"] = self.state.get("active_stage")
            self.state["error_message"] = str(exc)
            self._event(self.state.get("active_node_id"), self.state.get("active_stage"), "ERROR", str(exc), type(exc).__name__)
            return EXIT_RUNTIME
        finally:
            if hasattr(self, "state") and not self.dry_run:
                self.metrics["total_duration_ms"] = round(previous_duration + (time.perf_counter() - started) * 1000, 3)
                self._write_reports()
                self._checkpoint()

    def _prepare(self) -> None:
        configured = getattr(self.adapter, "configured_modules", None)
        if configured is not None:
            required = {"architecture", "gherkin", "coding", "integration"}
            if self.input_kind == "requirement": required.add("prd")
            if self.mode != "no_mock": required.add("mocktest")
            if self.mode not in {"no_leaf_gate", "non_recursive"}: required.update({"leaf_gate", "backfill"})
            missing = required - set(configured)
            if missing:
                raise ConfigurationError(f"missing required module commands: {', '.join(sorted(missing))}")
            for module, command in getattr(self.adapter, "raw_commands", {}).items():
                if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
                    raise ConfigurationError(f"invalid command adapter for module: {module}")
                if shutil.which(command[0]) is None and not Path(command[0]).is_file():
                    raise ConfigurationError(f"module executable is unavailable: {command[0]}")
                for part in command[1:]:
                    if part.endswith(".py") and "{" not in part and not Path(part).is_file():
                        raise ConfigurationError(f"module script is unavailable: {part}")
        if self.dry_run:
            if self.run_dir.exists() and any(self.run_dir.iterdir()):
                raise ConfigurationError("dry-run output directory must be absent or empty")
            self.state = {"status": "PENDING"}
            return
        if self.resume:
            self._load_checkpoint()
            return
        if self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise ConfigurationError("run directory already contains artifacts; use --resume")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state = create_run(self.run_id, self.project_id, self.root_node_id, self.max_depth)
        self.state.update({"active_node_id": None, "active_stage": None, "lifecycle_stage": "INIT", "failed_stage": None,
                           "error_message": None, "completed_stages": {}})
        self._atomic_json(self.run_dir / "run_manifest.json", self.manifest)
        self._checkpoint()

    def _load_checkpoint(self) -> None:
        manifest_path, checkpoint_path = self.run_dir / "run_manifest.json", self.run_dir / "checkpoint.json"
        if not manifest_path.is_file() or not checkpoint_path.is_file():
            raise ConfigurationError("resume requires run_manifest.json and checkpoint.json")
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("identity_hash") != self.manifest["identity_hash"]:
            raise ConfigurationError("resume manifest does not match input/config/experiment identity")
        envelope = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        state = envelope.get("state")
        if canonical_hash(state) != envelope.get("state_hash"):
            raise ConfigurationError("checkpoint state hash mismatch")
        for relative, expected in envelope.get("artifact_hashes", {}).items():
            path = (self.run_dir / relative).resolve()
            try:
                path.relative_to(self.run_dir)
            except ValueError as exc:
                raise ConfigurationError("checkpoint artifact escapes run directory") from exc
            if not path.is_file() or sha256_file(path) != expected:
                raise ConfigurationError(f"checkpoint artifact mismatch: {relative}")
        log_path = self.run_dir / "execution_log.json"
        if not log_path.is_file() or sha256_file(log_path) != envelope.get("execution_log_hash"):
            raise ConfigurationError("checkpoint execution log hash mismatch")
        self.state = state
        self.log = json.loads((self.run_dir / "execution_log.json").read_text(encoding="utf-8")) if (self.run_dir / "execution_log.json").is_file() else []
        metrics_path = self.run_dir / "experiment_metrics.json"
        if metrics_path.is_file():
            self.metrics.update(json.loads(metrics_path.read_text(encoding="utf-8")))
        self.state["status"] = "RUNNING"
        self.state["error_message"] = None

    def _process_node(self, node_id: str, source: Path, source_kind: str) -> None:
        node = self.state["nodes"][node_id]
        if node["status"] == "COMPLETED":
            return
        node_dir = self.run_dir / "nodes" / node_id
        node_dir.mkdir(parents=True, exist_ok=True)
        prd = self._stage(node_id, "prd", source, node_dir / "prd", passthrough=source_kind == "prd")
        architecture, gherkin = self._design(node_id, prd, node_dir)
        if self.mode == "no_mock":
            mock = self._synthetic(node_id, "mocktest", "PASS", {"ablation": True})
        else:
            mock_input = self._bundle(node_dir / "mocktest-input.json", [architecture, gherkin])
            mock = self._stage(node_id, "mocktest", mock_input, node_dir / "mocktest")
            self.metrics["mock_defect_count"] += int(mock.get("defect_count", 0) or 0)
        if mock["status"] != "PASS":
            raise WorkflowError(f"Mocktest {mock['status']} at {node_id}")
        if self.mode == "no_leaf_gate":
            leaf = self._synthetic(node_id, "leaf_gate", "STOP_LAYERING", {"decision": "STOP_LAYERING", "ablation": True})
        elif self.mode == "non_recursive":
            leaf = self._synthetic(node_id, "leaf_gate", "STOP_LAYERING", {"decision": "STOP_LAYERING", "ablation": True})
        else:
            leaf_input = self._bundle(node_dir / "leaf-input.json", [prd, architecture, gherkin, mock])
            leaf = self._stage(node_id, "leaf_gate", leaf_input, node_dir / "leaf_gate")
        decision = leaf.get("decision") or leaf.get("status")
        if decision == "CONTINUE_LAYERING":
            children = leaf.get("proposed_children")
            if not isinstance(children, list):
                raise ContractError("CONTINUE_LAYERING requires structured proposed_children")
            for child in children:
                self._require_safe_id(child.get("node_id"), "proposed child node_id")
            apply_leaf_decision(self.state, node_id, decision, children)
            self.state["lifecycle_stage"] = "LAYERING_CONTINUES"
            self.metrics["continue_layering_count"] += 1
            self._checkpoint()
            for child in children:
                child_input = node_dir / f"child-{child['node_id']}.json"
                self._atomic_json(child_input, child.get("requirement", {"requirement_ids": child.get("requirement_ids", [])}))
                self._process_node(child["node_id"], child_input, "requirement")
            self._backfill(node_id, node_dir)
        elif decision == "STOP_LAYERING":
            apply_leaf_decision(self.state, node_id, decision)
            self.state["lifecycle_stage"] = "LEAF_READY"
            self.metrics["stop_layering_count"] += 1
            task = admit_coding(self.state, node_id, self._coding_evidence(node_id, prd, architecture, gherkin, mock, leaf))
            self.state["lifecycle_stage"] = "CODING_RUNNING"
            coding_input = self._bundle(node_dir / "coding-input.json", [prd, architecture, gherkin, mock, leaf, task])
            coding = self._stage(node_id, "coding", coding_input, node_dir / "coding")
            if coding["status"] != "PASS":
                raise WorkflowError(f"coding {coding['status']} at {node_id}")
            complete_coding_task(self.state, task["task_id"])
            mark_node_completed(self.state, node_id)
            record_delivery(
                self.state, node_id,
                completion_artifact_id=coding["artifact_id"],
                completion_hash=sha256_file(Path(coding["primary_artifact"])),
                contract_artifact_id=f"{architecture['artifact_id']}:contract",
                contract_hash=sha256_file(Path(architecture["primary_artifact"])),
                changed_paths=coding.get("changed_paths", []),
            )
            self.metrics["coding_acceptance"][node_id] = "PASS"
            self.state["lifecycle_stage"] = "CODING_COMPLETED"
        else:
            raise WorkflowError(f"invalid Leaf Gate decision at {node_id}: {decision}")
        self._checkpoint()

    def _design(self, node_id: str, prd: dict[str, Any], node_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        completed = self.state["completed_stages"].get(node_id, {})
        if "architecture" in completed and "gherkin" in completed:
            return self._read_result(completed["architecture"]), self._read_result(completed["gherkin"])
        input_path = Path(prd["primary_artifact"])
        started = time.perf_counter()
        if self.branch_mode == "parallel":
            with ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(self._stage, node_id, "architecture", input_path, node_dir / "architecture")
                fg = pool.submit(self._stage, node_id, "gherkin", input_path, node_dir / "gherkin")
                architecture, gherkin = fa.result(), fg.result()
        else:
            architecture = self._stage(node_id, "architecture", input_path, node_dir / "architecture")
            gherkin = self._stage(node_id, "gherkin", input_path, node_dir / "gherkin")
        wall = round((time.perf_counter() - started) * 1000, 3)
        self.metrics["parallel_wall_time_ms"] += wall
        seq = architecture["duration_ms"] + gherkin["duration_ms"]
        self.metrics["sequential_time_ms"] += seq
        self.metrics["sequential_time_label"] = "measured" if self.branch_mode == "sequential" else "estimated_sum_of_branch_durations"
        if architecture["status"] != "PASS" or gherkin["status"] != "PASS":
            raise WorkflowError("Architecture/Gherkin join failed; Mocktest is blocked")
        self.state["lifecycle_stage"] = "DESIGN_AND_TEST_COMPLETED"
        return architecture, gherkin

    def _stage(self, node_id: str, module: str, input_path: Path, output_dir: Path, *, passthrough: bool = False) -> dict[str, Any]:
        completed = self.state["completed_stages"].setdefault(node_id, {})
        if module in completed:
            return self._read_result(completed[module])
        self.state.update({"active_node_id": node_id, "active_stage": module, "status": "RUNNING"})
        running_stage = {"prd": "PRD_RUNNING", "architecture": "DESIGN_AND_TEST_RUNNING",
                         "gherkin": "DESIGN_AND_TEST_RUNNING", "mocktest": "MOCKTEST_RUNNING",
                         "leaf_gate": "LEAF_GATE_RUNNING", "coding": "CODING_RUNNING",
                         "backfill": "BACKFILL_RUNNING", "integration": "INTEGRATION_RUNNING"}[module]
        self.state["lifecycle_stage"] = running_stage
        if output_dir.exists() and any(output_dir.iterdir()) and not self.resume:
            raise ConfigurationError(f"stale current-attempt directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        stage_started_at = self._now()
        existing_attempts = sorted(output_dir.glob("attempt-*"))
        retry_count = len(existing_attempts)
        result: dict[str, Any]
        attempt_dir: Path
        while True:
            attempt_started = time.perf_counter()
            attempt_started_at = self._now()
            attempt_dir = output_dir / f"attempt-{retry_count + 1}"
            if attempt_dir.exists():
                raise ConfigurationError(f"attempt directory already exists: {attempt_dir}")
            attempt_dir.mkdir()
            if passthrough:
                target = attempt_dir / "prd.json"
                shutil.copyfile(input_path, target)
                result = {"status": "PASS", "output_artifacts": [str(target)]}
            else:
                result = self.adapter(module, input_path, attempt_dir, self._context(node_id))
            if not isinstance(result, dict):
                raise ContractError(f"{module} returned an invalid structured result")
            if result.get("status") != "ERROR" or retry_count >= self.retry_limit:
                break
            retry_record = {"created_at": attempt_started_at, "duration_ms": round((time.perf_counter() - attempt_started) * 1000, 3), "input_artifacts": [str(input_path)],
                            "output_artifacts": [], "input_hash": sha256_file(input_path), "output_hash": None,
                            "retry_count": retry_count, "token_usage": result.get("token_usage"),
                            "estimated_cost": result.get("estimated_cost"), "human_interventions": result.get("human_interventions", 0),
                            "warning_count": result.get("warning_count", 0)}
            self._event(node_id, module, "ERROR", result.get("error_message"), result.get("error_type"), retry_record)
            self.metrics["model_call_count"] += 1
            self.metrics["total_tokens"] += int(result.get("token_usage") or 0)
            self.metrics["total_cost"] += float(result.get("estimated_cost") or 0)
            retry_count += 1
        duration = round((time.perf_counter() - started) * 1000, 3)
        if not isinstance(result, dict) or result.get("status") not in {"PASS", "FAIL", "ERROR", "CONTINUE_LAYERING", "STOP_LAYERING"}:
            raise ContractError(f"{module} returned an invalid structured result")
        artifacts = self._validate_outputs(attempt_dir, result.get("output_artifacts", []), result["status"] in {"PASS", "CONTINUE_LAYERING", "STOP_LAYERING"})
        record = {"schema_version": "1.0", "run_id": self.run_id, "project_id": self.project_id,
                  "node_id": node_id, "parent_node_id": self.state["nodes"][node_id]["parent_node_id"],
                  "artifact_id": f"{self.run_id}:{node_id}:{module}:result", "artifact_type": "module_result",
                  "created_at": stage_started_at, "generator": module, "status": result["status"],
                  "input_artifacts": [str(input_path)], "requirement_ids": self.state["nodes"][node_id]["requirement_ids"],
                  "input_hash": sha256_file(input_path), "output_artifacts": artifacts,
                  "output_hash": canonical_hash({p: sha256_file(Path(p)) for p in artifacts}),
                  "primary_artifact": artifacts[0] if artifacts else None, "duration_ms": duration,
                  "model": self.model, "model_parameters": self.model_parameters, "random_seed": self.random_seed,
                  "retry_count": retry_count, "token_usage": result.get("token_usage"), "estimated_cost": result.get("estimated_cost"),
                  "human_interventions": result.get("human_interventions", 0), "warning_count": result.get("warning_count", 0),
                  "error_type": result.get("error_type"), "error_message": result.get("error_message"),
                  "model_call": not passthrough,
                  **{k: v for k, v in result.items() if k not in {"status", "output_artifacts"}}}
        result_path = output_dir / "result.json"
        self._atomic_json(result_path, record)
        with self._state_lock:
            self._event(node_id, module, record["status"], record.get("error_message"), record.get("error_type"), record)
            self._accumulate(record)
        if record["status"] in {"ERROR", "FAIL"}:
            with self._state_lock:
                self.state["nodes"][node_id]["status"] = record["status"]
                self.state["failed_stage"] = module
                self._checkpoint()
            error = ConfigurationError if record["status"] == "ERROR" else WorkflowError
            raise error(f"{module} returned {record['status']}: {record.get('error_message') or ''}")
        with self._state_lock:
            completed[module] = str(result_path.relative_to(self.run_dir))
            completed_stage = {"prd": "PRD_COMPLETED", "mocktest": "MOCKTEST_COMPLETED",
                               "coding": "CODING_COMPLETED"}.get(module)
            if completed_stage:
                self.state["lifecycle_stage"] = completed_stage
            self._checkpoint()
        return record

    def _backfill(self, node_id: str, node_dir: Path) -> None:
        approval = self.config.get("backfill_approvals", {}).get(node_id)
        if not isinstance(approval, dict) or not approval.get("approver") or not approval.get("note"):
            self.metrics["human_intervention_count"] += 1
            raise WorkflowError(f"backfill for {node_id} requires recorded Integration Owner approval")
        self.metrics["human_intervention_count"] += 1
        self.state["lifecycle_stage"] = "BACKFILL_RUNNING"
        source = self._bundle(node_dir / "backfill-input.json", [self._node_summary(child) for child in self.state["nodes"][node_id]["children"]])
        settings = self.config.get("backfill", {}).get(node_id, {})
        baseline_hash = canonical_hash(self.state["nodes"][node_id])
        planned_changes = settings.get("planned_changes", [f"integration/{node_id}/wiring.json"])
        batch = prepare_batch(
            self.state, node_id, parent_baseline_hash=baseline_hash,
            canonical_version=int(settings.get("canonical_version", 1)),
            allowed_write_set=settings.get("allowed_write_set", [f"integration/{node_id}"]),
            protected_paths=settings.get("protected_paths", ["contracts/shared"]),
            planned_changes=planned_changes,
            contract_snapshot_id=f"{self.run_id}:{node_id}:contracts",
            contract_snapshot_hash=canonical_hash({child: self.state["deliveries"][child]["contract_hash"] for child in self.state["nodes"][node_id]["children"]}),
            rollback_snapshot_id=f"{self.run_id}:{node_id}:rollback",
            rollback_snapshot_hash=baseline_hash,
        )
        result = self._stage(node_id, "backfill", source, node_dir / "backfill")
        raw_checks = result.get("checks")
        if not isinstance(raw_checks, dict) or set(raw_checks) != REQUIRED_CHECKS:
            raise ContractError("backfill adapter must return the complete Phase F check set")
        diff = result.get("contract_diff")
        self._validate_semantic_diff(diff)
        artifact_hash = sha256_file(Path(result["primary_artifact"]))
        checks = {}
        for name in REQUIRED_CHECKS:
            status = raw_checks[name]
            checks[name] = {"status": status, "artifact_id": f"{result['artifact_id']}:{name}", "artifact_hash": artifact_hash}
        checks["contract"].update({"semantic_diff_artifact_id": f"{result['artifact_id']}:semantic-diff",
                                   "semantic_diff_hash": canonical_hash(diff),
                                   "semantic_outcome": diff.get("outcome"),
                                   "breaking_count": diff.get("breaking_count")})
        checked = record_checks(self.state, batch["batch_id"], checks)
        self.state.setdefault("contract_diffs", []).append(diff)
        violations = int(diff.get("breaking_count", 0) or 0)
        self.metrics["contract_violation_count"] += violations
        if checked["status"] != "CHECKS_PASSED":
            raise ContractError(f"backfill contract conflict at {node_id}")
        approve_batch(self.state, batch["batch_id"], approver=approval["approver"], note=approval["note"])
        apply_batch(
            self.state, batch["batch_id"], current_parent_baseline_hash=baseline_hash,
            current_canonical_version=int(settings.get("canonical_version", 1)),
            actual_changed_paths=planned_changes,
            completion_artifact_id=result["artifact_id"], completion_hash=artifact_hash,
            contract_artifact_id=f"{result['artifact_id']}:contract", contract_hash=canonical_hash(diff),
        )

    def _integrate_root(self) -> None:
        root_dir = self.run_dir / "nodes" / self.root_node_id
        source = self._node_summary(self.root_node_id)
        result = self._stage(self.root_node_id, "integration", source, root_dir / "integration")
        if result["status"] != "PASS":
            raise WorkflowError("final integration did not PASS")

    def _manifest(self) -> dict[str, Any]:
        identity = {"run_id": self.run_id, "project_id": self.project_id, "root_node_id": self.root_node_id,
                    "input_kind": self.input_kind, "input_hash": sha256_file(self.input_path),
                    "config_hash": canonical_hash(self.config), "mode": self.mode, "branch_mode": self.branch_mode,
                    "max_depth": self.max_depth, "retry_limit": self.retry_limit, "model": self.model,
                    "model_parameters": self.model_parameters, "random_seed": self.random_seed,
                    "schema_version": "1.0", "module_versions": self.config.get("module_versions", {})}
        return {**identity, "identity_hash": canonical_hash(identity), "created_at": self._now(),
                "is_ablation": self.mode != "full_recursive", "full_run": self.mode == "full_recursive",
                "determinism_note": self.config.get("determinism_note", "seed recorded; external model determinism is adapter-dependent"),
                "code_version": self.config.get("code_version"), "git_commit": self.config.get("git_commit")}

    def _empty_metrics(self) -> dict[str, Any]:
        return {"total_duration_ms": 0.0, "module_durations_ms": {}, "parallel_wall_time_ms": 0.0,
                "sequential_time_ms": 0.0, "sequential_time_label": None, "total_tokens": 0,
                "total_cost": 0.0, "model_call_count": 0, "retry_count": 0,
                "human_intervention_count": 0, "node_count": 0, "max_depth_reached": 0,
                "continue_layering_count": 0, "stop_layering_count": 0, "mock_defect_count": 0,
                "coding_acceptance": {}, "contract_violation_count": 0, "failed_stage": None,
                "final_status": "PENDING"}

    def _accumulate(self, record: dict[str, Any]) -> None:
        module = record["generator"]
        self.metrics["module_durations_ms"][module] = round(self.metrics["module_durations_ms"].get(module, 0) + record["duration_ms"], 3)
        self.metrics["model_call_count"] += int(record.get("model_call", True))
        self.metrics["total_tokens"] += int(record.get("token_usage") or 0)
        self.metrics["total_cost"] += float(record.get("estimated_cost") or 0)
        self.metrics["retry_count"] += int(record.get("retry_count") or 0)
        self.metrics["human_intervention_count"] += int(record.get("human_interventions") or 0)

    def _write_reports(self) -> None:
        self.metrics.update({"node_count": len(self.state.get("nodes", {})),
                             "max_depth_reached": max((n["depth"] for n in self.state.get("nodes", {}).values()), default=0),
                             "failed_stage": self.state.get("failed_stage"), "final_status": self.state.get("status")})
        contract_report = {"schema_version": "1.0", "run_id": self.run_id, "status": "PASS" if not self.metrics["contract_violation_count"] else "FAIL",
                           "violation_count": self.metrics["contract_violation_count"], "diffs": self.state.get("contract_diffs", [])}
        report = {"schema_version": "1.0", "run_id": self.run_id, "project_id": self.project_id,
                  "status": self.state.get("status"), "experiment_mode": self.mode, "branch_mode": self.branch_mode,
                  "lifecycle_stage": self.state.get("lifecycle_stage"),
                  "is_ablation": self.mode != "full_recursive", "full_run": self.mode == "full_recursive",
                  "model": self.model, "model_parameters": self.model_parameters, "random_seed": self.random_seed,
                  "input_hash": self.manifest["input_hash"], "config_hash": self.manifest["config_hash"],
                  "output_hashes": self._completed_output_hashes(), **self.metrics}
        self._atomic_json(self.run_dir / "execution_log.json", self.log)
        self._atomic_json(self.run_dir / "node_tree.json", {"schema_version": "1.0", "run_id": self.run_id, "root_node_id": self.root_node_id, "nodes": self.state.get("nodes", {})})
        self._atomic_json(self.run_dir / "contract_diff_report.json", contract_report)
        self._atomic_json(self.run_dir / "experiment_metrics.json", self.metrics)
        self._atomic_json(self.run_dir / "run_report.json", report)
        lines = ["# Workflow Run Report", "", f"- Run: `{self.run_id}`", f"- Status: `{report['status']}`",
                 f"- Experiment: `{self.mode}`", f"- Branch mode: `{self.branch_mode}`",
                 f"- Full run: `{str(report['full_run']).lower()}`", f"- Nodes: `{self.metrics['node_count']}`",
                 f"- Failed stage: `{self.metrics['failed_stage']}`", "", "Machine-readable authority: `run_report.json`.\n"]
        self._atomic_text(self.run_dir / "run_report.md", "\n".join(lines))

    def _checkpoint(self) -> None:
        if not hasattr(self, "state") or self.dry_run or not self.run_dir.exists():
            return
        with self._state_lock:
            self._atomic_json(self.run_dir / "execution_log.json", self.log)
            artifacts = {}
            for stages in self.state.get("completed_stages", {}).values():
                for relative in stages.values():
                    path = self.run_dir / relative
                    if path.is_file():
                        artifacts[relative] = sha256_file(path)
                        try:
                            record = json.loads(path.read_text(encoding="utf-8"))
                        except (OSError, json.JSONDecodeError):
                            record = {}
                        for raw in record.get("output_artifacts", []):
                            output = Path(raw).resolve()
                            try: output_relative = output.relative_to(self.run_dir).as_posix()
                            except ValueError as exc: raise ConfigurationError("checkpoint output escapes run directory") from exc
                            if not output.is_file(): raise ConfigurationError(f"checkpoint output is missing: {output_relative}")
                            artifacts[output_relative] = sha256_file(output)
            envelope = {"schema_version": "1.0", "state": self.state,
                        "state_hash": canonical_hash(self.state), "artifact_hashes": dict(sorted(artifacts.items())),
                        "execution_log_hash": sha256_file(self.run_dir / "execution_log.json"),
                        "updated_at": self._now()}
            self._atomic_json(self.run_dir / "checkpoint.json", envelope)

    def _write_dry_run(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        plan = {"schema_version": "1.0", "status": "PASS", "dry_run": True,
                "manifest": self.manifest, "validated_modules": sorted(self.config.get("commands", {})),
                "note": "No module invoked and no success run artifacts created."}
        self._atomic_json(self.run_dir / "dry_run_plan.json", plan)

    def _validate_outputs(self, root: Path, raw: Any, required: bool) -> list[str]:
        if not isinstance(raw, list) or (required and not raw):
            raise ContractError("successful module result requires output_artifacts")
        paths = []
        for item in raw:
            path = Path(item)
            if not path.is_absolute(): path = root / path
            path = path.resolve()
            try: path.relative_to(root.resolve())
            except ValueError as exc: raise ContractError(f"module output escapes attempt directory: {item}") from exc
            if not path.is_file(): raise ContractError(f"declared module output is missing: {item}")
            paths.append(str(path))
        return paths

    def _bundle(self, path: Path, records: list[Any]) -> Path:
        normalized = [str(item) if isinstance(item, Path) else item for item in records]
        self._atomic_json(path, {"schema_version": "1.0", "run_id": self.run_id, "records": normalized})
        return path

    def _node_summary(self, node_id: str) -> Path:
        path = self.run_dir / "nodes" / node_id / "node-summary.json"
        self._atomic_json(path, {"schema_version": "1.0", "run_id": self.run_id, "project_id": self.project_id,
                                 "node": self.state["nodes"][node_id]})
        return path

    def _coding_evidence(self, node_id: str, prd: dict[str, Any], architecture: dict[str, Any],
                         gherkin: dict[str, Any], mock: dict[str, Any], leaf: dict[str, Any]) -> dict[str, dict[str, Any]]:
        def base(record: dict[str, Any], kind: str) -> dict[str, Any]:
            primary = record.get("primary_artifact")
            digest = sha256_file(Path(primary)) if primary else canonical_hash(record)
            return {"run_id": self.run_id, "project_id": self.project_id, "node_id": node_id,
                    "artifact_id": record.get("artifact_id", f"{self.run_id}:{node_id}:{kind}"),
                    "content_hash": digest, "status": record["status"]}
        evidence = {"prd": base(prd, "prd"), "architecture": base(architecture, "architecture"),
                    "testcases": base(gherkin, "testcases"), "mocktest": base(mock, "mocktest"),
                    "leaf_gate": base(leaf, "leaf_gate"), "contract": base(architecture, "contract")}
        evidence["contract"]["artifact_id"] = f"{architecture['artifact_id']}:contract"
        evidence["contract"].update({"interfaces": architecture.get("interfaces", []),
                                     "blocking_issues": architecture.get("blocking_issues", [])})
        evidence["mocktest"].update({"architecture_artifact_id": evidence["architecture"]["artifact_id"],
                                     "testcases_artifact_id": evidence["testcases"]["artifact_id"]})
        required = {evidence[key]["artifact_id"]: evidence[key]["content_hash"]
                    for key in ("prd", "architecture", "testcases", "mocktest", "contract")}
        evidence["leaf_gate"].update({"decision": "STOP_LAYERING", "status": "STOP_LAYERING",
                                      "evidence_complete": leaf.get("evidence_complete") is True or leaf.get("ablation") is True,
                                      "input_artifacts": sorted(required), "input_hashes": required})
        return evidence

    def _read_result(self, relative: str) -> dict[str, Any]:
        return json.loads((self.run_dir / relative).read_text(encoding="utf-8"))

    def _completed_output_hashes(self) -> dict[str, str]:
        hashes = {}
        for stages in self.state.get("completed_stages", {}).values():
            for relative in stages.values():
                path = self.run_dir / relative
                if path.is_file():
                    record = json.loads(path.read_text(encoding="utf-8"))
                    hashes[record["artifact_id"]] = record["output_hash"]
        return dict(sorted(hashes.items()))

    @staticmethod
    def _validate_semantic_diff(diff: Any) -> None:
        required = {"schema_version", "status", "outcome", "parent_contract_id", "child_contract_id",
                    "parent_hash", "child_hash", "breaking_count", "compatible_count", "differences", "validation_errors"}
        if not isinstance(diff, dict) or set(diff) != required:
            raise ContractError("backfill adapter must return the complete semantic contract diff")
        if diff["status"] not in {"PASS", "FAIL", "ERROR"} or diff["outcome"] not in {
                "MATCH", "ADDITIVE_ONLY", "ADAPTER_NEEDED", "LEAF_FIX_REQUIRED", "CONTRACT_CHANGE_REQUIRED"}:
            raise ContractError("semantic contract diff status/outcome is invalid")
        for name in ("parent_hash", "child_hash"):
            value = diff[name]
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ContractError(f"semantic contract diff {name} is invalid")
        if not isinstance(diff["differences"], list) or not isinstance(diff["validation_errors"], list):
            raise ContractError("semantic contract diff arrays are invalid")
        breaking = sum(1 for item in diff["differences"] if isinstance(item, dict) and item.get("breaking") is True)
        compatible = sum(1 for item in diff["differences"] if isinstance(item, dict) and item.get("breaking") is False)
        if breaking != diff["breaking_count"] or compatible != diff["compatible_count"]:
            raise ContractError("semantic contract diff counts do not match differences")

    def _synthetic(self, node_id: str, module: str, status: str, extra: dict[str, Any]) -> dict[str, Any]:
        return {"schema_version": "1.0", "run_id": self.run_id, "project_id": self.project_id,
                "node_id": node_id, "status": status, "generator": module, **extra}

    def _context(self, node_id: str) -> dict[str, Any]:
        return {"run_id": self.run_id, "project_id": self.project_id, "node_id": node_id,
                "parent_node_id": self.state["nodes"][node_id]["parent_node_id"], "model": self.model,
                "model_parameters": self.model_parameters, "random_seed": self.random_seed,
                "timeout_seconds": self.config.get("timeout_seconds")}

    def _event(self, node_id: str | None, module: str | None, status: str, message: str | None = None,
               error_type: str | None = None, record: dict[str, Any] | None = None) -> None:
        event = {"run_id": self.run_id, "project_id": self.project_id, "node_id": node_id,
                         "module": module, "start_time": record.get("created_at") if record else None,
                         "end_time": self._now(), "duration_ms": record.get("duration_ms") if record else None,
                         "status": status, "input_artifacts": record.get("input_artifacts", []) if record else [],
                         "output_artifacts": record.get("output_artifacts", []) if record else [],
                         "input_hash": record.get("input_hash") if record else None, "output_hash": record.get("output_hash") if record else None,
                         "model": self.model, "model_parameters": self.model_parameters, "random_seed": self.random_seed,
                         "retry_count": record.get("retry_count", 0) if record else 0, "token_usage": record.get("token_usage") if record else None,
                         "estimated_cost": record.get("estimated_cost") if record else None,
                         "human_interventions": record.get("human_interventions", 0) if record else 0,
                         "warning_count": record.get("warning_count", 0) if record else 0,
                         "error_type": error_type, "error_message": message}
        with self._state_lock:
            self.log.append(event)

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _require_safe_id(value: Any, label: str) -> None:
        invalid = '<>:"/\\|?*'
        if (not isinstance(value, str) or not value or value in {".", ".."}
                or value[-1] in {".", " "} or any(char in invalid or ord(char) < 32 for char in value)):
            raise ConfigurationError(f"{label} must be a safe path segment")

    @classmethod
    def _redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if re.search(r"token|secret|password|api[_-]?key|auth", str(key), re.I) else cls._redact(item))
                    for key, item in value.items()}
        if isinstance(value, list): return [cls._redact(item) for item in value]
        return value

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        RootWorkflow._atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(value); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
            raise
