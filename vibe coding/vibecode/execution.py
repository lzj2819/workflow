"""Node attempts, recovery checkpoints, and strict coding admission."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecode.orchestrator import GraphError, refresh_run_status, validate_run_graph


FAILURE_CLASSES = {
    "BUSINESS_FAIL",
    "TOOL_ERROR",
    "CONTRACT_INCOMPATIBLE",
    "INTERRUPTED",
}
EVIDENCE_KEYS = (
    "prd",
    "architecture",
    "testcases",
    "mocktest",
    "leaf_gate",
    "contract",
)


class ExecutionError(ValueError):
    """An attempt or resume transition is unsafe."""


class AdmissionError(ValueError):
    """Current-node evidence is insufficient or inconsistent for coding."""


def start_attempt(
    run: dict[str, Any],
    node_id: str,
    stage: str,
    input_hashes: dict[str, str],
    *,
    max_retries: int,
) -> dict[str, Any]:
    validate_run_graph(run)
    if run["status"] in {"FAIL", "ERROR"}:
        raise ExecutionError("failed runs must resume the failed node before new work")
    node = _node(run, node_id)
    if node["status"] in {"FAIL", "ERROR"}:
        raise ExecutionError("failed nodes must use resume_attempt")
    return _start_attempt(run, node, stage, input_hashes, max_retries=max_retries)


def finish_attempt(
    run: dict[str, Any],
    node_id: str,
    attempt_id: str,
    status: str,
    *,
    output_hashes: dict[str, str] | None = None,
    checkpoint_artifacts: dict[str, str] | None = None,
    partial_artifacts: list[str] | None = None,
    failure_class: str | None = None,
    failure_message: str | None = None,
) -> dict[str, Any]:
    validate_run_graph(run)
    node = _node(run, node_id)
    attempt = _attempt(node, attempt_id)
    if attempt["status"] != "RUNNING":
        raise ExecutionError(f"attempt is already terminal: {attempt_id}")
    if status not in {"PASS", "FAIL", "ERROR"}:
        raise ExecutionError(f"unsupported attempt status: {status}")
    outputs = output_hashes or {}
    checkpoints = checkpoint_artifacts or {}
    partials = partial_artifacts or []
    _validate_hashes(outputs, "output_hashes", allow_empty=status != "PASS")
    _validate_hashes(checkpoints, "checkpoint_artifacts", allow_empty=status != "PASS")
    if not isinstance(partials, list) or not all(isinstance(item, str) for item in partials):
        raise ExecutionError("partial_artifacts must be a list of strings")
    if status == "PASS":
        if failure_class or failure_message or partials:
            raise ExecutionError("PASS cannot contain failure or partial-output metadata")
    else:
        if failure_class not in FAILURE_CLASSES:
            raise ExecutionError("terminal failure requires a known failure_class")
        if not failure_message:
            raise ExecutionError("terminal failure requires failure_message")
        if status == "FAIL" and failure_class not in {
            "BUSINESS_FAIL",
            "CONTRACT_INCOMPATIBLE",
        }:
            raise ExecutionError("FAIL must be business or contract failure")
        if status == "ERROR" and failure_class == "BUSINESS_FAIL":
            raise ExecutionError("business validation must use FAIL, not ERROR")
    attempt.update(
        {
            "status": status,
            "ended_at": _now(),
            "output_hashes": dict(outputs),
            "checkpoint_artifacts": dict(checkpoints),
            "partial_artifacts": list(partials),
            "failure_class": failure_class,
            "failure_message": failure_message,
        }
    )
    node["status"] = status
    node["error_message"] = failure_message
    refresh_run_status(run)
    return attempt


def interrupt_attempt(
    run: dict[str, Any],
    node_id: str,
    attempt_id: str,
    partial_artifacts: list[str],
) -> dict[str, Any]:
    return finish_attempt(
        run,
        node_id,
        attempt_id,
        "ERROR",
        partial_artifacts=partial_artifacts,
        failure_class="INTERRUPTED",
        failure_message="attempt was interrupted",
    )


def resume_attempt(
    run: dict[str, Any],
    node_id: str,
    input_hashes: dict[str, str],
    artifact_root: Path,
    *,
    max_retries: int,
) -> dict[str, Any]:
    validate_run_graph(run)
    node = _node(run, node_id)
    if not node["attempts"]:
        raise ExecutionError("node has no attempt to resume")
    failed = node["attempts"][-1]
    if failed["status"] not in {"FAIL", "ERROR"}:
        raise ExecutionError("only a failed or interrupted terminal attempt can resume")
    if input_hashes != failed["input_hashes"]:
        raise ExecutionError("resume input hashes differ from the failed attempt")
    successful = next(
        (attempt for attempt in reversed(node["attempts"][:-1]) if attempt["status"] == "PASS"),
        None,
    )
    if successful:
        validate_checkpoint(successful, artifact_root)
    resumed = _start_attempt(
        run,
        node,
        failed["stage"],
        input_hashes,
        max_retries=max_retries,
    )
    resumed["resumed_from_attempt_id"] = failed["attempt_id"]
    resumed["checkpoint_attempt_id"] = successful["attempt_id"] if successful else None
    return resumed


def validate_checkpoint(attempt: dict[str, Any], artifact_root: Path) -> None:
    if attempt.get("status") != "PASS":
        raise ExecutionError("only PASS attempts can be recovery checkpoints")
    root = artifact_root.resolve()
    for relative, expected_hash in attempt.get("checkpoint_artifacts", {}).items():
        artifact = (root / relative).resolve()
        try:
            artifact.relative_to(root)
        except ValueError as exc:
            raise ExecutionError(f"checkpoint escapes artifact root: {relative}") from exc
        if not artifact.is_file():
            raise ExecutionError(f"checkpoint artifact is missing: {relative}")
        if _file_hash(artifact) != expected_hash:
            raise ExecutionError(f"checkpoint artifact hash mismatch: {relative}")


def admit_coding(
    run: dict[str, Any], node_id: str, evidence: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    validate_run_graph(run)
    node = _node(run, node_id)
    if run["status"] in {"FAIL", "ERROR"}:
        raise AdmissionError("failed run cannot admit downstream coding")
    if node.get("decision") != "STOP_LAYERING" or node.get("status") != "STOP_LAYERING":
        raise AdmissionError("node is not in STOP_LAYERING coding-admission state")
    if set(evidence) != set(EVIDENCE_KEYS):
        missing = set(EVIDENCE_KEYS) - set(evidence)
        extra = set(evidence) - set(EVIDENCE_KEYS)
        raise AdmissionError(
            f"evidence set mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    for key in EVIDENCE_KEYS:
        _validate_evidence_artifact(run, node, key, evidence[key])
    mocktest = evidence["mocktest"]
    if mocktest["status"] != "PASS":
        raise AdmissionError(f"Mocktest must PASS, got {mocktest['status']}")
    leaf_gate = evidence["leaf_gate"]
    if leaf_gate.get("decision") != "STOP_LAYERING" or leaf_gate["status"] != "STOP_LAYERING":
        raise AdmissionError("Leaf Gate evidence must be STOP_LAYERING")
    if leaf_gate.get("evidence_complete") is not True:
        raise AdmissionError("Leaf Gate evidence is incomplete")
    contract = evidence["contract"]
    if contract["status"] != "PASS" or not contract.get("interfaces"):
        raise AdmissionError("interface contract is not clear and complete")
    if contract.get("blocking_issues"):
        raise AdmissionError("interface contract has blocking issues")
    for key in ("prd", "architecture", "testcases"):
        if evidence[key]["status"] not in {"PASS", "COMPLETED"}:
            raise AdmissionError(f"{key} evidence is not successful")

    required_inputs = {
        evidence[key]["artifact_id"]: evidence[key]["content_hash"]
        for key in ("prd", "architecture", "testcases", "mocktest", "contract")
    }
    if set(leaf_gate.get("input_artifacts", [])) != set(required_inputs):
        raise AdmissionError("Leaf Gate input artifact IDs do not match current-node evidence")
    if leaf_gate.get("input_hashes") != required_inputs:
        raise AdmissionError("Leaf Gate input hashes do not match current-node evidence")
    if mocktest.get("architecture_artifact_id") != evidence["architecture"]["artifact_id"]:
        raise AdmissionError("Mocktest architecture provenance mismatch")
    if mocktest.get("testcases_artifact_id") != evidence["testcases"]["artifact_id"]:
        raise AdmissionError("Mocktest testcase provenance mismatch")

    task_id = f"{run['run_id']}:{node_id}:coding"
    existing = next(
        (task for task in run["coding_queue"] if task["task_id"] == task_id), None
    )
    if existing:
        if existing.get("evidence_hashes") != required_inputs:
            raise AdmissionError("existing coding task evidence differs from current evidence")
        node["coding_task_queued"] = True
        node["coding_task_id"] = task_id
        node["coding_admission_pending"] = False
        return existing
    task = {
        "schema_version": "1.0",
        "task_id": task_id,
        "run_id": run["run_id"],
        "project_id": run["project_id"],
        "node_id": node_id,
        "status": "PENDING",
        "created_at": _now(),
        "evidence_artifacts": sorted(required_inputs),
        "evidence_hashes": required_inputs,
        "attempts": [],
    }
    run["coding_queue"].append(task)
    node["coding_task_queued"] = True
    node["coding_task_id"] = task_id
    node["coding_admission_pending"] = False
    validate_run_graph(run)
    return task


def complete_coding_task(run: dict[str, Any], task_id: str) -> None:
    validate_run_graph(run)
    task = next((item for item in run["coding_queue"] if item["task_id"] == task_id), None)
    if task is None:
        raise ExecutionError(f"unknown coding task: {task_id}")
    if task["status"] not in {"PENDING", "RUNNING"}:
        raise ExecutionError(f"coding task is already terminal: {task_id}")
    task["status"] = "COMPLETED"


def _start_attempt(
    run: dict[str, Any],
    node: dict[str, Any],
    stage: str,
    input_hashes: dict[str, str],
    *,
    max_retries: int,
) -> dict[str, Any]:
    if not isinstance(stage, str) or not stage:
        raise ExecutionError("stage must be a non-empty string")
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
        raise ExecutionError("max_retries must be a non-negative integer")
    _validate_hashes(input_hashes, "input_hashes", allow_empty=False)
    previous = [attempt for attempt in node["attempts"] if attempt["stage"] == stage]
    if previous and previous[-1]["status"] == "RUNNING":
        raise ExecutionError("stage already has a running attempt")
    retry_count = len(previous)
    if retry_count > max_retries:
        raise ExecutionError(f"retry limit exceeded for stage {stage}")
    attempt = {
        "attempt_id": f"{node['node_id']}:{stage}:{retry_count + 1}",
        "node_id": node["node_id"],
        "stage": stage,
        "status": "RUNNING",
        "started_at": _now(),
        "ended_at": None,
        "retry_count": retry_count,
        "input_hashes": dict(input_hashes),
        "output_hashes": {},
        "checkpoint_artifacts": {},
        "partial_artifacts": [],
        "failure_class": None,
        "failure_message": None,
        "resumed_from_attempt_id": None,
        "checkpoint_attempt_id": None,
    }
    node["attempts"].append(attempt)
    node["status"] = "RUNNING"
    node["error_message"] = None
    refresh_run_status(run)
    return attempt


def _validate_evidence_artifact(
    run: dict[str, Any], node: dict[str, Any], key: str, artifact: dict[str, Any]
) -> None:
    if not isinstance(artifact, dict):
        raise AdmissionError(f"{key} evidence must be an object")
    for field, expected in {
        "run_id": run["run_id"],
        "project_id": run["project_id"],
        "node_id": node["node_id"],
    }.items():
        if artifact.get(field) != expected:
            raise AdmissionError(f"{key} {field} mismatch")
    if not isinstance(artifact.get("artifact_id"), str) or not artifact["artifact_id"]:
        raise AdmissionError(f"{key} artifact_id is missing")
    if not _is_hash(artifact.get("content_hash")):
        raise AdmissionError(f"{key} content_hash is invalid")
    if artifact.get("status") not in {
        "PASS",
        "FAIL",
        "ERROR",
        "STOP_LAYERING",
        "COMPLETED",
    }:
        raise AdmissionError(f"{key} status is invalid")


def _validate_hashes(value: Any, label: str, *, allow_empty: bool) -> None:
    if not isinstance(value, dict) or (not value and not allow_empty):
        raise ExecutionError(f"{label} must be a non-empty hash map")
    if not all(isinstance(key, str) and key and _is_hash(item) for key, item in value.items()):
        raise ExecutionError(f"{label} contains an invalid SHA-256")


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _node(run: dict[str, Any], node_id: str) -> dict[str, Any]:
    try:
        return run["nodes"][node_id]
    except KeyError as exc:
        raise GraphError(f"unknown node_id: {node_id}") from exc


def _attempt(node: dict[str, Any], attempt_id: str) -> dict[str, Any]:
    attempt = next(
        (item for item in node["attempts"] if item["attempt_id"] == attempt_id), None
    )
    if attempt is None:
        raise ExecutionError(f"unknown attempt: {attempt_id}")
    return attempt


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
