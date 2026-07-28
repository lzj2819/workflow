"""Pure run/node graph rules for recursive workflow orchestration."""

from __future__ import annotations

from typing import Any


NODE_STATUSES = {
    "PENDING",
    "RUNNING",
    "PASS",
    "FAIL",
    "ERROR",
    "CONTINUE_LAYERING",
    "STOP_LAYERING",
    "COMPLETED",
}
LEAF_DECISIONS = {"CONTINUE_LAYERING", "STOP_LAYERING", "ERROR"}


class GraphError(ValueError):
    """The requested graph mutation would violate a workflow invariant."""


def create_run(
    run_id: str,
    project_id: str,
    root_node_id: str,
    max_depth: int,
) -> dict[str, Any]:
    for label, value in {
        "run_id": run_id,
        "project_id": project_id,
        "root_node_id": root_node_id,
    }.items():
        if not isinstance(value, str) or not value.strip():
            raise GraphError(f"{label} must be a non-empty string")
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 0:
        raise GraphError("max_depth must be a non-negative integer")
    run = {
        "schema_version": "1.0",
        "run_id": run_id,
        "project_id": project_id,
        "root_node_id": root_node_id,
        "max_depth": max_depth,
        "status": "PENDING",
        "nodes": {},
        "coding_queue": [],
        "deliveries": {},
        "backfill_batches": [],
    }
    add_node(run, root_node_id, None)
    return run


def add_node(
    run: dict[str, Any],
    node_id: str,
    parent_node_id: str | None,
    requirement_ids: list[str] | None = None,
) -> dict[str, Any]:
    nodes = run["nodes"]
    if not isinstance(node_id, str) or not node_id.strip():
        raise GraphError("node_id must be a non-empty string")
    if node_id in nodes:
        raise GraphError(f"duplicate node_id: {node_id}")
    if parent_node_id == node_id:
        raise GraphError(f"node cannot be its own parent: {node_id}")
    if parent_node_id is None:
        if nodes:
            raise GraphError("only the root node may omit parent_node_id")
        depth = 0
    else:
        parent = nodes.get(parent_node_id)
        if parent is None:
            raise GraphError(f"missing parent node: {parent_node_id}")
        depth = parent["depth"] + 1
    if depth > run["max_depth"]:
        raise GraphError(
            f"node {node_id} depth {depth} exceeds max_depth {run['max_depth']}"
        )
    requirements = requirement_ids or []
    if not isinstance(requirements, list) or not all(
        isinstance(item, str) for item in requirements
    ):
        raise GraphError("requirement_ids must be a list of strings")
    node = {
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "depth": depth,
        "status": "PENDING",
        "decision": None,
        "children": [],
        "requirement_ids": list(requirements),
        "coding_task_queued": False,
        "coding_admission_pending": False,
        "coding_task_id": None,
        "attempts": [],
        "error_message": None,
    }
    nodes[node_id] = node
    if parent_node_id is not None:
        nodes[parent_node_id]["children"].append(node_id)
    return node


def apply_leaf_decision(
    run: dict[str, Any],
    node_id: str,
    decision: str,
    proposed_children: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    validate_run_graph(run)
    node = _node(run, node_id)
    if node["status"] in {"FAIL", "ERROR"}:
        raise GraphError(f"failed node cannot accept a Leaf Gate decision: {node_id}")
    if decision not in LEAF_DECISIONS:
        raise GraphError(f"unsupported leaf decision: {decision}")
    children = proposed_children or []
    if not isinstance(children, list) or not all(isinstance(item, dict) for item in children):
        raise GraphError("proposed_children must be a list of objects")
    if node["decision"] is not None and node["decision"] != decision:
        raise GraphError(
            f"node {node_id} decision is already {node['decision']}, cannot change to {decision}"
        )

    if decision == "CONTINUE_LAYERING":
        if not children:
            raise GraphError("CONTINUE_LAYERING requires proposed_children")
        _validate_proposed_children(run, node, children)
        for child in children:
            child_id = child["node_id"]
            if child_id not in run["nodes"]:
                add_node(
                    run,
                    child_id,
                    node_id,
                    child.get("requirement_ids", []),
                )
        node["status"] = "CONTINUE_LAYERING"
    elif decision == "STOP_LAYERING":
        if children:
            raise GraphError("STOP_LAYERING cannot propose children")
        if node["children"]:
            raise GraphError("STOP_LAYERING node cannot already have children")
        node["status"] = "STOP_LAYERING"
        node["coding_admission_pending"] = True
    else:
        if children:
            raise GraphError("ERROR cannot propose children")
        node["status"] = "ERROR"
        node["error_message"] = error_message or "Leaf Gate returned ERROR"
    node["decision"] = decision
    refresh_run_status(run)
    validate_run_graph(run)
    return node


def mark_node_completed(run: dict[str, Any], node_id: str) -> None:
    node = _node(run, node_id)
    if node["status"] == "ERROR":
        raise GraphError(f"failed node cannot complete: {node_id}")
    if node["children"]:
        incomplete = [
            child_id
            for child_id in node["children"]
            if run["nodes"][child_id]["status"] != "COMPLETED"
        ]
        if incomplete:
            raise GraphError(
                f"node {node_id} has incomplete children: {', '.join(incomplete)}"
            )
    else:
        if node["status"] != "STOP_LAYERING":
            raise GraphError(f"leaf node is not coding-ready: {node_id}")
        task_id = node.get("coding_task_id")
        task = next(
            (item for item in run.get("coding_queue", []) if item.get("task_id") == task_id),
            None,
        )
        if task is None or task.get("status") != "COMPLETED":
            raise GraphError(f"leaf coding task is not completed: {node_id}")
    node["status"] = "COMPLETED"
    refresh_run_status(run)


def refresh_run_status(run: dict[str, Any]) -> str:
    nodes = run["nodes"].values()
    if any(node["status"] == "ERROR" for node in nodes):
        run["status"] = "ERROR"
    elif any(node["status"] == "FAIL" for node in nodes):
        run["status"] = "FAIL"
    elif run["nodes"][run["root_node_id"]]["status"] == "COMPLETED":
        run["status"] = "COMPLETED"
    elif any(node["status"] != "PENDING" for node in nodes):
        run["status"] = "RUNNING"
    else:
        run["status"] = "PENDING"
    return run["status"]


def validate_run_graph(run: dict[str, Any]) -> None:
    nodes = run.get("nodes")
    root_id = run.get("root_node_id")
    max_depth = run.get("max_depth")
    if not isinstance(nodes, dict) or root_id not in nodes:
        raise GraphError("run must contain its root node")
    queue = run.get("coding_queue")
    if not isinstance(queue, list):
        raise GraphError("run coding_queue must be a list")
    task_ids = [task.get("task_id") for task in queue if isinstance(task, dict)]
    if len(task_ids) != len(queue) or len(task_ids) != len(set(task_ids)):
        raise GraphError("coding queue contains invalid or duplicate task IDs")
    tasks = {task["task_id"]: task for task in queue}
    root = nodes[root_id]
    if root.get("parent_node_id") is not None or root.get("depth") != 0:
        raise GraphError("root node must have no parent and depth 0")
    for key, node in nodes.items():
        if key != node.get("node_id"):
            raise GraphError(f"node key/id mismatch: {key}")
        if node.get("status") not in NODE_STATUSES:
            raise GraphError(f"invalid node status: {node.get('status')!r}")
        if node.get("coding_admission_pending") and node.get("coding_task_queued"):
            raise GraphError(f"node {key} cannot be pending admission and queued")
        if node.get("coding_task_queued"):
            task = tasks.get(node.get("coding_task_id"))
            if task is None or task.get("node_id") != key:
                raise GraphError(f"node {key} has an invalid coding task reference")
        if node.get("depth", -1) > max_depth:
            raise GraphError(f"node {key} exceeds max_depth {max_depth}")
        children = node.get("children")
        if not isinstance(children, list) or len(children) != len(set(children)):
            raise GraphError(f"node {key} has invalid or duplicate children")
        parent_id = node.get("parent_node_id")
        if key != root_id:
            if parent_id not in nodes:
                raise GraphError(f"node {key} has missing parent {parent_id!r}")
            parent = nodes[parent_id]
            if key not in parent["children"]:
                raise GraphError(f"parent {parent_id} does not reference child {key}")
            if node.get("depth") != parent.get("depth") + 1:
                raise GraphError(f"node {key} has inconsistent depth")
        for child_id in children:
            child = nodes.get(child_id)
            if child is None:
                raise GraphError(f"node {key} references missing child {child_id}")
            if child.get("parent_node_id") != key:
                raise GraphError(f"child {child_id} does not reference parent {key}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise GraphError(f"cycle detected at node {node_id}")
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in nodes[node_id]["children"]:
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    visit(root_id)
    unreachable = set(nodes) - visited
    if unreachable:
        raise GraphError(f"unreachable nodes: {', '.join(sorted(unreachable))}")


def _validate_proposed_children(
    run: dict[str, Any], node: dict[str, Any], children: list[dict[str, Any]]
) -> None:
    seen: set[str] = set()
    for child in children:
        child_id = child.get("node_id")
        if not isinstance(child_id, str) or not child_id.strip():
            raise GraphError("each proposed child requires a non-empty node_id")
        if child_id in seen:
            raise GraphError(f"duplicate proposed child: {child_id}")
        seen.add(child_id)
        declared_parent = child.get("parent_node_id", node["node_id"])
        if declared_parent != node["node_id"]:
            raise GraphError(
                f"child {child_id} parent must be {node['node_id']}, got {declared_parent!r}"
            )
        existing = run["nodes"].get(child_id)
        requirements = child.get("requirement_ids", [])
        if not isinstance(requirements, list) or not all(
            isinstance(item, str) for item in requirements
        ):
            raise GraphError(f"child {child_id} requirement_ids must be a list of strings")
        if existing and (
            existing["parent_node_id"] != node["node_id"]
            or child_id not in node["children"]
        ):
            raise GraphError(f"node_id already belongs elsewhere: {child_id}")
        if existing and existing["requirement_ids"] != requirements:
            raise GraphError(f"child {child_id} requirement_ids changed on repeat scheduling")
        if not existing and node["depth"] + 1 > run["max_depth"]:
            raise GraphError(
                f"child {child_id} would exceed max_depth {run['max_depth']}"
            )


def _node(run: dict[str, Any], node_id: str) -> dict[str, Any]:
    try:
        return run["nodes"][node_id]
    except KeyError as exc:
        raise GraphError(f"unknown node_id: {node_id}") from exc
