"""Deterministic bottom-up backfill batches with a mandatory apply gate."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from vibecode.orchestrator import GraphError, mark_node_completed, validate_run_graph


REQUIRED_CHECKS = {
    "contract",
    "provider_compatibility",
    "consumer_compatibility",
    "parent_integration",
    "feature_smoke",
    "regression",
}


class BackfillError(ValueError):
    """A backfill transition is incomplete, stale, or unauthorized."""


def record_delivery(
    run: dict[str, Any],
    node_id: str,
    *,
    completion_artifact_id: str,
    completion_hash: str,
    contract_artifact_id: str,
    contract_hash: str,
    changed_paths: list[str],
    source: str = "CODING",
) -> dict[str, Any]:
    validate_run_graph(run)
    node = _node(run, node_id)
    if node["status"] != "COMPLETED":
        raise BackfillError(f"node delivery is not completed: {node_id}")
    for label, value in {
        "completion_artifact_id": completion_artifact_id,
        "contract_artifact_id": contract_artifact_id,
    }.items():
        if not isinstance(value, str) or not value:
            raise BackfillError(f"{label} must be a non-empty string")
    _require_hash(completion_hash, "completion_hash")
    _require_hash(contract_hash, "contract_hash")
    paths = _normalize_paths(changed_paths, "changed_paths")
    if source not in {"CODING", "BACKFILL"}:
        raise BackfillError(f"unsupported delivery source: {source}")
    delivery = {
        "schema_version": "1.0",
        "delivery_id": f"{run['run_id']}:{node_id}:delivery",
        "run_id": run["run_id"],
        "project_id": run["project_id"],
        "node_id": node_id,
        "parent_node_id": node["parent_node_id"],
        "status": "READY",
        "source": source,
        "completion_artifact_id": completion_artifact_id,
        "completion_hash": completion_hash,
        "contract_artifact_id": contract_artifact_id,
        "contract_hash": contract_hash,
        "changed_paths": paths,
        "created_at": _now(),
        "integrated_by_batch_id": None,
    }
    existing = run["deliveries"].get(node_id)
    if existing:
        comparable = {key: value for key, value in delivery.items() if key != "created_at"}
        old = {key: value for key, value in existing.items() if key != "created_at"}
        if comparable != old:
            raise BackfillError(f"delivery evidence changed for node {node_id}")
        return existing
    run["deliveries"][node_id] = delivery
    return delivery


def eligible_parents(run: dict[str, Any]) -> list[str]:
    validate_run_graph(run)
    eligible: list[str] = []
    for node_id, node in run["nodes"].items():
        if not node["children"] or node["status"] == "COMPLETED":
            continue
        if _active_batch(run, node_id):
            continue
        if all(
            run["nodes"][child_id]["status"] == "COMPLETED"
            and run["deliveries"].get(child_id, {}).get("status") == "READY"
            for child_id in node["children"]
        ):
            eligible.append(node_id)
    return sorted(eligible, key=lambda item: (-run["nodes"][item]["depth"], item))


def prepare_batch(
    run: dict[str, Any],
    parent_node_id: str,
    *,
    parent_baseline_hash: str,
    canonical_version: int,
    allowed_write_set: list[str],
    protected_paths: list[str],
    planned_changes: list[str],
    contract_snapshot_id: str,
    contract_snapshot_hash: str,
    rollback_snapshot_id: str,
    rollback_snapshot_hash: str,
) -> dict[str, Any]:
    validate_run_graph(run)
    parent = _node(run, parent_node_id)
    if not parent["children"] or parent["status"] == "COMPLETED" or not all(
        run["nodes"][child_id]["status"] == "COMPLETED"
        and run["deliveries"].get(child_id, {}).get("status") == "READY"
        for child_id in parent["children"]
    ):
        raise BackfillError(f"parent is not eligible for backfill: {parent_node_id}")
    _require_hash(parent_baseline_hash, "parent_baseline_hash")
    _require_hash(contract_snapshot_hash, "contract_snapshot_hash")
    _require_hash(rollback_snapshot_hash, "rollback_snapshot_hash")
    if not isinstance(canonical_version, int) or isinstance(canonical_version, bool) or canonical_version < 0:
        raise BackfillError("canonical_version must be a non-negative integer")
    for label, value in {
        "contract_snapshot_id": contract_snapshot_id,
        "rollback_snapshot_id": rollback_snapshot_id,
    }.items():
        if not isinstance(value, str) or not value:
            raise BackfillError(f"{label} must be a non-empty string")
    allowed = _normalize_paths(allowed_write_set, "allowed_write_set")
    protected = _normalize_paths(protected_paths, "protected_paths")
    changes = _normalize_paths(planned_changes, "planned_changes")
    if not allowed or not changes:
        raise BackfillError("allowed_write_set and planned_changes cannot be empty")
    for change in changes:
        if not _covered(change, allowed):
            raise BackfillError(f"planned change is outside integration write set: {change}")
        if _covered(change, protected):
            raise BackfillError(f"planned change touches protected path: {change}")

    child_deliveries = [run["deliveries"][child] for child in sorted(parent["children"])]
    frozen_children = [
        {
            "node_id": delivery["node_id"],
            "delivery_id": delivery["delivery_id"],
            "completion_artifact_id": delivery["completion_artifact_id"],
            "completion_hash": delivery["completion_hash"],
            "contract_artifact_id": delivery["contract_artifact_id"],
            "contract_hash": delivery["contract_hash"],
        }
        for delivery in child_deliveries
    ]
    frozen = {
        "parent_node_id": parent_node_id,
        "children": frozen_children,
        "parent_baseline_hash": parent_baseline_hash,
        "canonical_version": canonical_version,
        "allowed_write_set": allowed,
        "protected_paths": protected,
        "planned_changes": changes,
        "contract_snapshot_id": contract_snapshot_id,
        "contract_snapshot_hash": contract_snapshot_hash,
        "rollback_snapshot_id": rollback_snapshot_id,
        "rollback_snapshot_hash": rollback_snapshot_hash,
    }
    fingerprint = hashlib.sha256(
        json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    batch_id = f"{run['run_id']}:{parent_node_id}:backfill:{fingerprint[:16]}"
    existing = next(
        (batch for batch in run["backfill_batches"] if batch["batch_id"] == batch_id), None
    )
    if existing:
        return existing
    active = _active_batch(run, parent_node_id)
    if active:
        raise BackfillError(
            f"parent already has an active batch with different evidence: {active['batch_id']}"
        )
    batch = {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "run_id": run["run_id"],
        "project_id": run["project_id"],
        **frozen,
        "fingerprint": fingerprint,
        "status": "PREPARED",
        "checks": {},
        "check_runs": [],
        "gate": "PENDING",
        "approval": None,
        "blocked_reason": None,
        "created_at": _now(),
        "applied_at": None,
    }
    run["backfill_batches"].append(batch)
    return batch


def record_checks(
    run: dict[str, Any], batch_id: str, checks: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    batch = _batch(run, batch_id)
    if batch["status"] not in {"PREPARED", "BLOCKED"}:
        raise BackfillError(f"batch cannot accept checks in status {batch['status']}")
    if set(checks) != REQUIRED_CHECKS:
        raise BackfillError("checks must contain the complete required check set")
    normalized = {}
    failures = []
    for name in sorted(checks):
        result = checks[name]
        if not isinstance(result, dict) or result.get("status") not in {"PASS", "FAIL", "ERROR"}:
            raise BackfillError(f"invalid check result: {name}")
        _require_hash(result.get("artifact_hash"), f"{name}.artifact_hash")
        if not isinstance(result.get("artifact_id"), str) or not result["artifact_id"]:
            raise BackfillError(f"{name}.artifact_id is required")
        if name == "contract":
            if not isinstance(result.get("semantic_diff_artifact_id"), str) or not result["semantic_diff_artifact_id"]:
                raise BackfillError("contract semantic_diff_artifact_id is required")
            _require_hash(
                result.get("semantic_diff_hash"), "contract.semantic_diff_hash"
            )
            outcome = result.get("semantic_outcome")
            breaking_count = result.get("breaking_count")
            if outcome not in {
                "MATCH",
                "ADDITIVE_ONLY",
                "ADAPTER_NEEDED",
                "LEAF_FIX_REQUIRED",
                "CONTRACT_CHANGE_REQUIRED",
                "ERROR",
            } or not isinstance(breaking_count, int) or isinstance(breaking_count, bool) or breaking_count < 0:
                raise BackfillError("contract semantic result is invalid")
            if result["status"] == "PASS" and (
                breaking_count != 0 or outcome not in {"MATCH", "ADDITIVE_ONLY"}
            ):
                raise BackfillError("contract check cannot PASS a breaking semantic diff")
        normalized[name] = dict(result)
        if result["status"] != "PASS":
            failures.append(f"{name}={result['status']}")
    batch["checks"] = normalized
    batch["check_runs"].append({"at": _now(), "results": normalized})
    batch["status"] = "BLOCKED" if failures else "CHECKS_PASSED"
    batch["blocked_reason"] = ", ".join(failures) if failures else None
    return batch


def approve_batch(
    run: dict[str, Any], batch_id: str, *, approver: str, note: str
) -> dict[str, Any]:
    batch = _batch(run, batch_id)
    if batch["status"] != "CHECKS_PASSED":
        raise BackfillError("all automated checks must PASS before approval")
    if not isinstance(approver, str) or not isinstance(note, str) or not approver.strip() or not note.strip():
        raise BackfillError("human approval requires approver and note")
    batch["gate"] = "PASSED"
    batch["status"] = "APPROVED"
    batch["approval"] = {"approver": approver, "note": note, "at": _now()}
    return batch


def apply_batch(
    run: dict[str, Any],
    batch_id: str,
    *,
    current_parent_baseline_hash: str,
    current_canonical_version: int,
    actual_changed_paths: list[str],
    completion_artifact_id: str,
    completion_hash: str,
    contract_artifact_id: str,
    contract_hash: str,
) -> dict[str, Any]:
    batch = _batch(run, batch_id)
    if batch["status"] != "APPROVED" or batch["gate"] != "PASSED":
        raise BackfillError("Integration Owner approval is required before apply")
    if current_parent_baseline_hash != batch["parent_baseline_hash"]:
        _reject_apply(batch, "parent baseline is stale")
    if current_canonical_version != batch["canonical_version"]:
        _reject_apply(batch, "canonical version is stale")
    changes = _normalize_paths(actual_changed_paths, "actual_changed_paths")
    if changes != batch["planned_changes"]:
        _reject_apply(batch, "actual changed paths differ from the frozen plan")
    for label, value in {
        "completion_artifact_id": completion_artifact_id,
        "contract_artifact_id": contract_artifact_id,
    }.items():
        if not isinstance(value, str) or not value:
            _reject_apply(batch, f"{label} must be a non-empty string")
    try:
        _require_hash(completion_hash, "completion_hash")
        _require_hash(contract_hash, "contract_hash")
    except BackfillError as exc:
        _reject_apply(batch, str(exc))
    for frozen in batch["children"]:
        current = run["deliveries"].get(frozen["node_id"])
        if current is None or any(
            current.get(key) != frozen[key]
            for key in (
                "delivery_id",
                "completion_artifact_id",
                "completion_hash",
                "contract_artifact_id",
                "contract_hash",
            )
        ):
            _reject_apply(batch, f"child delivery changed: {frozen['node_id']}")
    parent_id = batch["parent_node_id"]
    if parent_id in run["deliveries"]:
        _reject_apply(batch, f"parent already has a delivery: {parent_id}")
    mark_node_completed(run, parent_id)
    for frozen in batch["children"]:
        delivery = run["deliveries"][frozen["node_id"]]
        delivery["status"] = "INTEGRATED"
        delivery["integrated_by_batch_id"] = batch_id
    parent_delivery = record_delivery(
        run,
        parent_id,
        completion_artifact_id=completion_artifact_id,
        completion_hash=completion_hash,
        contract_artifact_id=contract_artifact_id,
        contract_hash=contract_hash,
        changed_paths=changes,
        source="BACKFILL",
    )
    batch["status"] = "APPLIED"
    batch["applied_at"] = _now()
    batch["parent_delivery_id"] = parent_delivery["delivery_id"]
    return batch


def _active_batch(run: dict[str, Any], parent_node_id: str) -> dict[str, Any] | None:
    return next(
        (
            batch
            for batch in run["backfill_batches"]
            if batch["parent_node_id"] == parent_node_id
            and batch["status"] in {"PREPARED", "CHECKS_PASSED", "APPROVED", "BLOCKED"}
        ),
        None,
    )


def _reject_apply(batch: dict[str, Any], reason: str) -> None:
    batch["status"] = "BLOCKED"
    batch["blocked_reason"] = reason
    raise BackfillError(reason)


def _covered(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def _normalize_paths(paths: Any, label: str) -> list[str]:
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise BackfillError(f"{label} must be a list of paths")
    normalized = []
    for raw in paths:
        candidate = raw.replace("\\", "/")
        if candidate.startswith("/") or re.match(r"^[A-Za-z]:/", candidate):
            raise BackfillError(f"unsafe path in {label}: {raw}")
        path = candidate.strip("/")
        pure = PurePosixPath(path)
        if not path or pure.is_absolute() or ".." in pure.parts:
            raise BackfillError(f"unsafe path in {label}: {raw}")
        normalized.append(pure.as_posix())
    if len(normalized) != len(set(normalized)):
        raise BackfillError(f"{label} contains duplicate paths")
    return sorted(normalized)


def _require_hash(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise BackfillError(f"{label} must be a lowercase SHA-256")


def _node(run: dict[str, Any], node_id: str) -> dict[str, Any]:
    try:
        return run["nodes"][node_id]
    except KeyError as exc:
        raise GraphError(f"unknown node_id: {node_id}") from exc


def _batch(run: dict[str, Any], batch_id: str) -> dict[str, Any]:
    batch = next(
        (item for item in run["backfill_batches"] if item["batch_id"] == batch_id), None
    )
    if batch is None:
        raise BackfillError(f"unknown backfill batch: {batch_id}")
    return batch


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
