"""Automation helpers for layered vibe coding.

The script is intentionally small and dependency-free. It does not implement
business logic; it keeps the workflow state explicit and generates the files
that coding agents must follow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VIBECODE_DIR = ROOT / "vibecode"
STATE_PATH = VIBECODE_DIR / "state.json"
EVENT_LOG_PATH = VIBECODE_DIR / "execution-log.jsonl"
TEMPLATES_DIR = VIBECODE_DIR / "templates"

EXIT_OK = 0
EXIT_HUMAN_GATE = 10
EXIT_BLOCKED = 20
EXIT_ERROR = 1

STAGE_INIT = "INIT"
STAGE_MATRIX_PENDING_APPROVAL = "MATRIX_PENDING_APPROVAL"
STAGE_LEAF_TASKS_READY = "LEAF_TASKS_READY"
STAGE_LEAF_IMPLEMENTATION = "LEAF_IMPLEMENTATION"
STAGE_LEAF_COMPLETION_REVIEW = "LEAF_COMPLETION_REVIEW"
STAGE_BACKFILL = "BACKFILL"
STAGE_PARENT_COMPATIBILITY = "PARENT_COMPATIBILITY"
STAGE_FINAL_ACCEPTANCE = "FINAL_ACCEPTANCE"
STAGE_DONE = "DONE"
STAGE_BLOCKED = "BLOCKED"

HUMAN_GATES = {"matrix", "leaf_completion", "contract_change", "final"}

PUBLIC_STATUSES = {
    "PENDING",
    "RUNNING",
    "PASS",
    "FAIL",
    "ERROR",
    "CONTINUE_LAYERING",
    "STOP_LAYERING",
    "COMPLETED",
}

LEAF_DECISIONS = {"CONTINUE_LAYERING", "STOP_LAYERING"}

COMPLETION_FILES = [
    "completion-report.md",
    "contract-diff.md",
    "test-results.md",
    "risk-resolution.md",
    "child-completion-package.md",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def json_text(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json_text(data))


def load_state() -> dict[str, Any]:
    return read_json(STATE_PATH, {})


def save_state(state: dict[str, Any], *, allow_repair: bool = False) -> None:
    if not allow_repair and STATE_PATH.exists() and EVENT_LOG_PATH.exists():
        disk_state = load_state()
        if disk_state.get("state_id") and disk_state.get("state_id") == state.get("state_id"):
            errors = audit_state()
            if errors:
                raise RuntimeError("state audit failed before commit: " + "; ".join(errors))
    state["version"] = max(int(state.get("version", 1)), 2)
    state.setdefault("state_id", str(uuid.uuid4()))
    state["updated_at"] = now()
    state["revision"] = int(state.get("revision", 0)) + 1
    previous_event_id = state.get("last_event_id")
    event_id = str(uuid.uuid4())
    state["last_event_id"] = event_id
    latest_history = state.get("history", [])[-1] if state.get("history") else {}
    projection_text = json_text(state)
    event = {
        "event_id": event_id,
        "previous_event_id": previous_event_id,
        "state_id": state["state_id"],
        "revision": state["revision"],
        "at": state["updated_at"],
        "event": latest_history.get("event", "state-save"),
        "detail": latest_history.get("detail", ""),
        "stage": state.get("stage"),
        "state_sha256": sha256_text(projection_text),
        "projection": state,
    }
    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    atomic_write_text(STATE_PATH, projection_text)


def history(state: dict[str, Any], event: str, detail: str = "") -> None:
    state.setdefault("history", []).append({"at": now(), "event": event, "detail": detail})


def default_state(leaf_root: str, target_repo: str, mode: str) -> dict[str, Any]:
    return {
        "version": 2,
        "state_id": str(uuid.uuid4()),
        "revision": 0,
        "last_event_id": None,
        "stage": STAGE_INIT,
        "created_at": now(),
        "updated_at": now(),
        "config": {
            "leaf_root": leaf_root,
            "target_repo": target_repo,
            "mode": mode,
        },
        "gates": {
            "matrix": "pending",
            "leaf_completion": "pending",
            "contract_change": "pending",
            "final": "pending",
        },
        "active_wave": 1,
        "active_leaf": None,
        "active_parent": None,
        "leaves": [],
        "blocked_reason": None,
        "history": [],
    }


def read_event_log() -> tuple[list[dict[str, Any]], list[str]]:
    if not EVENT_LOG_PATH.exists():
        return [], [f"missing event log: {rel(EVENT_LOG_PATH)}"]
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(EVENT_LOG_PATH.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid event JSON at line {line_number}: {exc.msg}")
            continue
        if not isinstance(event, dict):
            errors.append(f"event at line {line_number} is not an object")
            continue
        events.append(event)
    return events, errors


def audit_state(repair: bool = False) -> list[str]:
    try:
        state = load_state()
    except json.JSONDecodeError as exc:
        return [f"invalid state JSON: {exc.msg}"]
    if not state:
        return ["missing state projection"]
    state_id = state.get("state_id")
    if not state_id:
        return ["legacy state has no state_id; mutate it explicitly to create its first checkpoint"]

    all_events, errors = read_event_log()
    events = [event for event in all_events if event.get("state_id") == state_id]
    if not events:
        errors.append(f"no events found for state_id {state_id}")
        return errors

    expected_revision = 1
    previous_event_id = None
    valid_events: list[dict[str, Any]] = []
    chain_errors: list[str] = []
    for event in events:
        revision = event.get("revision")
        if revision != expected_revision:
            chain_errors.append(
                f"revision mismatch: expected {expected_revision}, got {revision!r}"
            )
        if event.get("previous_event_id") != previous_event_id:
            chain_errors.append(f"broken previous_event_id at revision {revision!r}")
        projection = event.get("projection")
        if not isinstance(projection, dict):
            chain_errors.append(f"missing projection at revision {revision!r}")
        else:
            if projection.get("state_id") != state_id:
                chain_errors.append(f"projection state_id mismatch at revision {revision!r}")
            if projection.get("revision") != revision:
                chain_errors.append(f"projection revision mismatch at revision {revision!r}")
            if projection.get("last_event_id") != event.get("event_id"):
                chain_errors.append(f"projection event ID mismatch at revision {revision!r}")
            if event.get("state_sha256") != sha256_text(json_text(projection)):
                chain_errors.append(f"projection hash mismatch at revision {revision!r}")
        if chain_errors:
            break
        valid_events.append(event)
        previous_event_id = event.get("event_id")
        expected_revision += 1
    errors.extend(chain_errors)
    if not valid_events:
        return errors

    latest = valid_events[-1]
    state_errors: list[str] = []
    if state.get("revision") != latest.get("revision"):
        state_errors.append("state revision diverges from the event log")
    if state.get("last_event_id") != latest.get("event_id"):
        state_errors.append("state last_event_id diverges from the event log")
    if sha256_text(json_text(state)) != latest.get("state_sha256"):
        state_errors.append("state content hash diverges from the event log")

    if repair and not errors and state_errors:
        restored = json.loads(json.dumps(latest["projection"]))
        history(restored, "repair-state", f"restored revision {latest['revision']}")
        save_state(restored, allow_repair=True)
        return audit_state(repair=False)
    return errors + state_errors


def node_id_from_dir(node_dir: Path, leaf_root: Path) -> str:
    name = node_dir.name
    if name.startswith("root"):
        return name
    try:
        parts = node_dir.relative_to(leaf_root).parts
        return ".".join(parts)
    except ValueError:
        return name


def parent_of(node_id: str) -> str | None:
    if "." not in node_id:
        return None
    return node_id.rsplit(".", 1)[0]


def normalize_leaf_decision(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if normalized in LEAF_DECISIONS else None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _node_manifest(report: Path, leaf_root: Path) -> Path | None:
    for parent in report.parents:
        candidate = parent / "leaf_gate_input.json"
        if candidate.is_file():
            return candidate
        if parent == leaf_root.resolve():
            break
    return None


def _verify_leaf_delivery(report: Path) -> bool:
    output_dir = report.parent
    manifest_path = output_dir / "bundle_manifest.json"
    next_action_path = output_dir / "next_action.json"
    if not manifest_path.is_file() or not next_action_path.is_file():
        return False
    manifest = read_json(manifest_path, {})
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != 4:
        return False
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            return False
        path = (output_dir / str(item["path"])).resolve()
        try:
            path.relative_to(output_dir.resolve())
        except ValueError:
            return False
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            return False
    return manifest.get("bundle_sha256") == canonical_hash(files)


def scan_leaves(leaf_root: Path) -> list[dict[str, Any]]:
    if not leaf_root.exists():
        return []
    leaves: list[dict[str, Any]] = []
    for report in sorted(leaf_root.rglob("leaf_gate_report.json")):
        input_manifest_path = _node_manifest(report, leaf_root)
        if input_manifest_path is None or not _verify_leaf_delivery(report):
            continue
        try:
            leaf_report = json.loads(report.read_text(encoding="utf-8"))
            input_manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
            next_action = json.loads((report.parent / "next_action.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        decision = normalize_leaf_decision((leaf_report.get("decision") or {}).get("value"))
        if (
            leaf_report.get("artifact_schema_version") != "leaf-gate-report/v2"
            or (leaf_report.get("admission") or {}).get("state") != "ADMITTED"
            or decision != "STOP_LAYERING"
            or next_action.get("type") != "VIBECODE"
        ):
            continue
        node_dir = input_manifest_path.parent
        refs = input_manifest.get("current_artifacts") or {}
        if set(refs) != {"prd", "architecture", "testcases", "mocktest_report", "mocktest_evidence"}:
            continue
        resolved: dict[str, Path] = {}
        invalid = False
        for role, ref in refs.items():
            path = (node_dir / str(ref.get("path") or "")).resolve()
            try:
                path.relative_to(node_dir.resolve())
            except ValueError:
                invalid = True
                break
            if not path.is_file() or file_sha256(path) != ref.get("sha256"):
                invalid = True
                break
            resolved[role] = path
        if invalid:
            continue
        identity = leaf_report.get("identity") or {}
        node_id = identity.get("node_id")
        if not isinstance(node_id, str) or not node_id:
            continue
        feature = resolved["testcases"].with_name("testcases.feature")

        leaves.append(
            {
                "node_id": node_id,
                "path": rel(node_dir),
                "parent": identity.get("parent_node_id"),
                "decision": decision,
                "prd": rel(resolved["prd"]),
                "architecture": rel(resolved["architecture"]),
                "testcases": rel(resolved["testcases"]),
                "features": [rel(feature)] if feature.is_file() else [],
                "mocktest_report": rel(resolved["mocktest_report"]),
                "leaf_gate_report": rel(report),
                "next_action": rel(report.parent / "next_action.json"),
                "bundle_manifest": rel(report.parent / "bundle_manifest.json"),
                "missing": [],
                "wave": 1,
                "status": "DISCOVERED",
            }
        )
    return leaves


def template(name: str, fallback: str, values: dict[str, Any]) -> str:
    path = TEMPLATES_DIR / name
    text = path.read_text(encoding="utf-8") if path.exists() else fallback
    return text.format(**values)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def matrix_markdown(leaves: list[dict[str, Any]]) -> str:
    rows = [
        "| Wave | Node | Parent | Status | Missing |",
        "| --- | --- | --- | --- | --- |",
    ]
    for leaf in leaves:
        rows.append(
            f"| {leaf['wave']} | `{leaf['node_id']}` | `{leaf.get('parent') or 'root'}` | {leaf['status']} | {', '.join(leaf['missing']) or '-'} |"
        )
    if not leaves:
        rows.append("| - | - | - | NO_STOP_LAYERING_FOUND | - |")
    return "# Vibe Coding Execution Matrix\n\n" + "\n".join(rows) + "\n\nHuman gate: approve `matrix` before leaf task generation.\n"


def integration_map_markdown(leaves: list[dict[str, Any]]) -> str:
    groups: dict[str, list[str]] = {}
    for leaf in leaves:
        groups.setdefault(leaf.get("parent") or "root", []).append(leaf["node_id"])
    lines = ["# Integration Map", ""]
    for parent, children in sorted(groups.items()):
        lines.append(f"## `{parent}`")
        for child in sorted(children):
            lines.append(f"- `{child}`")
        lines.append("")
    if not groups:
        lines.append("No admitted `STOP_LAYERING` nodes found.")
    return "\n".join(lines)


def contract_index_markdown(leaves: list[dict[str, Any]]) -> str:
    lines = ["# Global Contract Index", "", "| Node | Architecture | Testcases |", "| --- | --- | --- |"]
    for leaf in leaves:
        architecture = f"`{leaf['architecture']}`" if leaf.get("architecture") else "-"
        testcases = f"`{leaf['testcases']}`" if leaf.get("testcases") else "-"
        lines.append(f"| `{leaf['node_id']}` | {architecture} | {testcases} |")
    if not leaves:
        lines.append("| - | - | - |")
    return "\n".join(lines)


def cmd_init(args: argparse.Namespace) -> int:
    state = default_state(args.leaf_root, args.target_repo, args.mode)
    history(state, "init", f"leaf_root={args.leaf_root}")
    save_state(state)
    print(f"Initialized {rel(STATE_PATH)}")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    state = load_state()
    leaf_root = Path(args.leaf_root or state.get("config", {}).get("leaf_root", "workspace/nodes"))
    if not leaf_root.is_absolute():
        leaf_root = ROOT / leaf_root
    leaves = scan_leaves(leaf_root)
    report = ["# Vibe Coding Doctor Report", "", f"- leaf_root: `{rel(leaf_root)}`", f"- coding_ready_count: {len(leaves)}", ""]
    for leaf in leaves:
        report.append(f"## `{leaf['node_id']}`")
        report.append(f"- status: {leaf['status']}")
        report.append(f"- path: `{leaf['path']}`")
        report.append(f"- missing: {', '.join(leaf['missing']) or '-'}")
        report.append("")
    if not leaves:
        report.append("No admitted canonical `STOP_LAYERING` nodes were found.")
    write_text(VIBECODE_DIR / "doctor-report.md", "\n".join(report))
    print(f"Wrote {rel(VIBECODE_DIR / 'doctor-report.md')}")
    return EXIT_OK if leaves else EXIT_BLOCKED


def cmd_generate_matrix(args: argparse.Namespace) -> int:
    state = load_state() or default_state(args.leaf_root or "workspace/nodes", ".", "single")
    leaf_root = Path(args.leaf_root or state.get("config", {}).get("leaf_root", "workspace/nodes"))
    if not leaf_root.is_absolute():
        leaf_root = ROOT / leaf_root
    leaves = scan_leaves(leaf_root)
    state.setdefault("config", {})["leaf_root"] = rel(leaf_root)
    state["leaves"] = leaves
    if leaves:
        state["stage"] = STAGE_MATRIX_PENDING_APPROVAL
        state["blocked_reason"] = None
    else:
        state["stage"] = STAGE_BLOCKED
        state["blocked_reason"] = "No STOP_LAYERING nodes found. Run the layered dev flow and Leaf Gate first."
    history(state, "generate-matrix", f"leaves={len(leaves)}")
    save_state(state)
    write_text(VIBECODE_DIR / "execution-matrix.md", matrix_markdown(leaves))
    write_text(VIBECODE_DIR / "integration-map.md", integration_map_markdown(leaves))
    write_text(VIBECODE_DIR / "global-contract-index.md", contract_index_markdown(leaves))
    print("Generated execution matrix, integration map, and contract index.")
    return EXIT_OK if leaves else EXIT_BLOCKED


def cmd_approve(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("No state. Run init first.", file=sys.stderr)
        return EXIT_ERROR
    if args.gate not in HUMAN_GATES:
        print(f"Unknown gate: {args.gate}", file=sys.stderr)
        return EXIT_ERROR
    state.setdefault("gates", {})[args.gate] = "passed"
    history(state, "approve", f"{args.gate}: {args.note or ''}".strip())
    save_state(state)
    print(f"Approved gate: {args.gate}")
    return EXIT_OK


def leaf_values(leaf: dict[str, Any]) -> dict[str, str]:
    node = leaf["node_id"]
    return {
        "node_id": node,
        "parent": leaf.get("parent") or "root",
        "leaf_path": leaf.get("path") or "",
        "prd": leaf.get("prd") or "",
        "architecture": leaf.get("architecture") or "",
        "testcases": leaf.get("testcases") or "",
        "mocktest_report": leaf.get("mocktest_report") or "",
        "leaf_gate_report": leaf.get("leaf_gate_report") or "",
        "next_action": leaf.get("next_action") or "",
        "bundle_manifest": leaf.get("bundle_manifest") or "",
        "features": "\n".join(f"- `{item}`" for item in leaf.get("features", [])) or "-",
        "backfill_dir": f"vibecode/backfill/{leaf.get('parent') or 'root'}",
    }


def cmd_generate_leaf_tasks(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("No state. Run init and generate-matrix first.", file=sys.stderr)
        return EXIT_ERROR
    if state.get("gates", {}).get("matrix") != "passed":
        print("Human gate required: approve matrix before generating leaf tasks.", file=sys.stderr)
        return EXIT_HUMAN_GATE
    leaves = state.get("leaves", [])
    if not leaves:
        print("No leaves in state. Run generate-matrix first.", file=sys.stderr)
        return EXIT_BLOCKED

    for leaf in leaves:
        values = leaf_values(leaf)
        leaf_dir = VIBECODE_DIR / "leaves" / leaf["node_id"]
        write_text(
            leaf_dir / "vibecode-task.md",
            template("vibecode-task.md", DEFAULT_VIBECODE_TASK, values),
        )
        write_text(
            leaf_dir / "allowed-context.md",
            template("allowed-context.md", DEFAULT_ALLOWED_CONTEXT, values),
        )
        write_text(
            leaf_dir / "forbidden-changes.md",
            template("forbidden-changes.md", DEFAULT_FORBIDDEN_CHANGES, values),
        )
        write_text(
            leaf_dir / "contract-checklist.md",
            template("contract-checklist.md", DEFAULT_CONTRACT_CHECKLIST, values),
        )
        write_text(
            leaf_dir / "implementation-checklist.md",
            template("implementation-checklist.md", DEFAULT_IMPLEMENTATION_CHECKLIST, values),
        )
        write_text(
            leaf_dir / "verification-checklist.md",
            template("verification-checklist.md", DEFAULT_VERIFICATION_CHECKLIST, values),
        )
        write_text(
            leaf_dir / "backfill-target.md",
            template("backfill-target.md", DEFAULT_BACKFILL_TARGET, values),
        )
    state["stage"] = STAGE_LEAF_IMPLEMENTATION
    state["active_leaf"] = leaves[0]["node_id"]
    state["active_parent"] = leaves[0].get("parent")
    history(state, "generate-leaf-tasks", f"count={len(leaves)}")
    save_state(state)
    print(f"Generated task packs for {len(leaves)} leaves.")
    return EXIT_OK


def stage_prompt(state: dict[str, Any]) -> tuple[int, str]:
    stage = state.get("stage", STAGE_INIT)
    if stage == STAGE_INIT:
        return EXIT_OK, "Run `python vibecode/scripts/vibecode.py doctor`, then `python vibecode/scripts/vibecode.py generate-matrix`."
    if stage == STAGE_BLOCKED:
        return EXIT_BLOCKED, f"Blocked: {state.get('blocked_reason') or 'unknown'}"
    if stage == STAGE_MATRIX_PENDING_APPROVAL:
        if state.get("gates", {}).get("matrix") == "passed":
            return EXIT_OK, "Run `python vibecode/scripts/vibecode.py advance-state`, then generate leaf tasks."
        return EXIT_HUMAN_GATE, "Human gate: review `vibecode/execution-matrix.md`, then approve with `python vibecode/scripts/vibecode.py approve --gate matrix --note \"approved\"`."
    if stage == STAGE_LEAF_TASKS_READY:
        return EXIT_OK, "Run `python vibecode/scripts/vibecode.py generate-leaf-tasks`."
    if stage == STAGE_LEAF_IMPLEMENTATION:
        active = state.get("active_leaf")
        return EXIT_OK, f"Leaf Owner: execute `vibecode/leaves/{active}/vibecode-task.md`, obey allowed/forbidden context, then produce the completion package."
    if stage == STAGE_LEAF_COMPLETION_REVIEW:
        return EXIT_HUMAN_GATE, "Human gate: review active leaf completion package, then approve `leaf_completion` or request fixes."
    if stage == STAGE_BACKFILL:
        return EXIT_OK, "Integration Owner: run contract diff, create backfill plan, wire real child into parent integration layer, and write backfill reports."
    if stage == STAGE_PARENT_COMPATIBILITY:
        return EXIT_OK, "Run parent compatibility checks and write `compatibility-check-report.md`."
    if stage == STAGE_FINAL_ACCEPTANCE:
        return EXIT_HUMAN_GATE, "Human gate: review `vibecode/final-report.md`, then approve `final` if ready."
    if stage == STAGE_DONE:
        return EXIT_OK, "Workflow done."
    return EXIT_ERROR, f"Unknown stage: {stage}"


def cmd_next_step(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        text = "No `vibecode/state.json`. Run `python vibecode/scripts/vibecode.py init --leaf-root workspace/nodes --target-repo .`."
        code = EXIT_OK
    else:
        code, text = stage_prompt(state)
    if args.write_prompt:
        write_text(Path(args.write_prompt), text)
    print(text)
    return code


def leaf_task_dir(state: dict[str, Any]) -> Path | None:
    active = state.get("active_leaf")
    return VIBECODE_DIR / "leaves" / active if active else None


def has_fail_marker(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    return any(marker in text for marker in ["fail", "failed", "contract_change_required", "unresolved high risk"])


def cmd_verify_stage(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("No state. Run init first.", file=sys.stderr)
        return EXIT_ERROR
    stage = state.get("stage")
    errors: list[str] = []
    if stage == STAGE_MATRIX_PENDING_APPROVAL:
        for name in ["execution-matrix.md", "integration-map.md", "global-contract-index.md"]:
            if not (VIBECODE_DIR / name).exists():
                errors.append(f"missing vibecode/{name}")
    elif stage == STAGE_LEAF_IMPLEMENTATION:
        task_dir = leaf_task_dir(state)
        if not task_dir:
            errors.append("missing active_leaf")
        else:
            for name in COMPLETION_FILES:
                path = task_dir / name
                if not path.exists():
                    errors.append(f"missing {rel(path)}")
            for name in ["test-results.md", "contract-diff.md", "risk-resolution.md"]:
                path = task_dir / name
                if has_fail_marker(path):
                    errors.append(f"failure marker in {rel(path)}")
    elif stage == STAGE_BACKFILL:
        parent = state.get("active_parent") or "root"
        backfill_dir = VIBECODE_DIR / "backfill" / parent
        for name in ["backfill-plan.md", "contract-diff-summary.md", "integration-wiring-report.md", "compatibility-check-report.md", "backfill-report.md"]:
            if not (backfill_dir / name).exists():
                errors.append(f"missing {rel(backfill_dir / name)}")
        if has_fail_marker(backfill_dir / "compatibility-check-report.md"):
            errors.append("parent compatibility report contains failure marker")
    elif stage == STAGE_FINAL_ACCEPTANCE:
        if not (VIBECODE_DIR / "final-report.md").exists():
            errors.append("missing vibecode/final-report.md")
    elif stage in {STAGE_INIT, STAGE_LEAF_TASKS_READY, STAGE_LEAF_COMPLETION_REVIEW, STAGE_PARENT_COMPATIBILITY, STAGE_DONE}:
        pass
    elif stage == STAGE_BLOCKED:
        errors.append(state.get("blocked_reason") or "workflow blocked")
    else:
        errors.append(f"unknown stage: {stage}")

    if errors:
        print("Stage verification failed:")
        for error in errors:
            print(f"- {error}")
        return EXIT_BLOCKED
    print(f"Stage verification passed: {stage}")
    return EXIT_OK


def cmd_advance_state(args: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("No state. Run init first.", file=sys.stderr)
        return EXIT_ERROR
    stage = state.get("stage")
    gates = state.get("gates", {})
    if stage == STAGE_MATRIX_PENDING_APPROVAL:
        if gates.get("matrix") != "passed":
            print("Human gate required: matrix approval.", file=sys.stderr)
            return EXIT_HUMAN_GATE
        state["stage"] = STAGE_LEAF_TASKS_READY
    elif stage == STAGE_LEAF_IMPLEMENTATION:
        check = cmd_verify_stage(argparse.Namespace())
        if check != EXIT_OK:
            return check
        state["stage"] = STAGE_LEAF_COMPLETION_REVIEW
    elif stage == STAGE_LEAF_COMPLETION_REVIEW:
        if gates.get("leaf_completion") != "passed":
            print("Human gate required: leaf completion approval.", file=sys.stderr)
            return EXIT_HUMAN_GATE
        state["stage"] = STAGE_BACKFILL
    elif stage == STAGE_BACKFILL:
        check = cmd_verify_stage(argparse.Namespace())
        if check != EXIT_OK:
            return check
        state["stage"] = STAGE_PARENT_COMPATIBILITY
    elif stage == STAGE_PARENT_COMPATIBILITY:
        state["stage"] = STAGE_FINAL_ACCEPTANCE
    elif stage == STAGE_FINAL_ACCEPTANCE:
        if gates.get("final") != "passed":
            print("Human gate required: final approval.", file=sys.stderr)
            return EXIT_HUMAN_GATE
        state["stage"] = STAGE_DONE
    else:
        print(f"No automatic transition for stage: {stage}", file=sys.stderr)
        return EXIT_BLOCKED
    history(state, "advance-state", f"{stage}->{state['stage']}")
    save_state(state)
    print(f"Advanced: {stage} -> {state['stage']}")
    return EXIT_OK


def parse_context_paths(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    found = re.findall(r"`([^`]+)`", text)
    return [item.replace("\\", "/").strip("/") for item in found if item and not item.startswith("python ")]


def cmd_guard_paths(args: argparse.Namespace) -> int:
    state = load_state()
    if not state or state.get("stage") != STAGE_LEAF_IMPLEMENTATION or not state.get("active_leaf"):
        print("No active leaf path guard.")
        return EXIT_OK
    task_dir = VIBECODE_DIR / "leaves" / state["active_leaf"]
    allowed = parse_context_paths(task_dir / "allowed-context.md")
    allowed.append(rel(task_dir))
    blocked: list[str] = []
    for raw in args.paths:
        normalized = raw.replace("\\", "/").strip("/")
        if not any(normalized == item or normalized.startswith(item.rstrip("/") + "/") for item in allowed):
            blocked.append(raw)
    if blocked:
        print("Path guard blocked files outside active leaf allowed context:")
        for item in blocked:
            print(f"- {item}")
        return EXIT_BLOCKED
    print("Path guard passed.")
    return EXIT_OK


def collect_path_values(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"path", "file_path", "target_file", "filename"} and isinstance(child, str):
                paths.append(child)
            elif key in {"paths", "files"} and isinstance(child, list):
                paths.extend(str(item) for item in child if isinstance(item, str))
            else:
                paths.extend(collect_path_values(child))
    elif isinstance(value, list):
        for child in value:
            paths.extend(collect_path_values(child))
    return paths


def cmd_hook_guard(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    paths = collect_path_values(payload)
    if not paths:
        print("No file paths found in hook payload.")
        return EXIT_OK
    return cmd_guard_paths(argparse.Namespace(paths=paths))


def normalized_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        clean = re.sub(r"\s+", " ", line.strip().lower())
        if clean and not clean.startswith("#") and clean not in {"---"}:
            lines.append(clean)
    return set(lines)


def legacy_text_contract_diff(parent: Path, child: Path, output: Path) -> int:
    parent_lines = normalized_lines(parent)
    child_lines = normalized_lines(child)
    if not parent_lines or not child_lines:
        status = "CONTRACT_CHANGE_REQUIRED"
        reason = "parent or child contract is empty or missing"
    elif parent_lines == child_lines:
        status = "MATCH"
        reason = "normalized contract lines match"
    elif parent_lines.issubset(child_lines):
        status = "ADDITIVE_ONLY"
        reason = "child includes all parent lines and adds extra details"
    elif parent_lines & child_lines:
        status = "ADAPTER_NEEDED"
        reason = "contracts overlap but do not match exactly"
    else:
        status = "LEAF_FIX_REQUIRED"
        reason = "child contract does not cover parent expectations"
    missing = sorted(parent_lines - child_lines)
    extra = sorted(child_lines - parent_lines)
    report = [
        "# Contract Diff",
        "",
        f"- status: `{status}`",
        f"- reason: {reason}",
        f"- parent: `{rel(parent)}`",
        f"- child: `{rel(child)}`",
        "",
        "## Missing From Child",
        "",
        "\n".join(f"- {line}" for line in missing) or "-",
        "",
        "## Additional In Child",
        "",
        "\n".join(f"- {line}" for line in extra) or "-",
    ]
    write_text(output, "\n".join(report))
    print(status)
    return EXIT_HUMAN_GATE if status == "CONTRACT_CHANGE_REQUIRED" else EXIT_OK


def cmd_contract_diff(args: argparse.Namespace) -> int:
    parent = Path(args.parent)
    child = Path(args.child)
    markdown_output = Path(args.output) if args.output else VIBECODE_DIR / "contract-diff.md"
    if args.legacy_text:
        print("WARNING: --legacy-text is non-authoritative compatibility mode.", file=sys.stderr)
        return legacy_text_contract_diff(parent, child, markdown_output)

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from vibecode.contracts import compare_contracts, write_reports

    validation_errors = []
    values = []
    for label, path in (("parent", parent), ("child", child)):
        try:
            values.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            values.append(None)
            validation_errors.append(f"{label}: {exc}")
    result = compare_contracts(values[0], values[1])
    if validation_errors:
        result["validation_errors"] = sorted(
            set(result["validation_errors"] + validation_errors)
        )
        result["status"] = "ERROR"
        result["outcome"] = "CONTRACT_CHANGE_REQUIRED"
    json_output = (
        Path(args.json_output)
        if args.json_output
        else VIBECODE_DIR / "contract-diff-report.json"
    )
    write_reports(result, json_output, markdown_output)
    print(result["outcome"])
    if result["status"] == "PASS":
        return EXIT_OK
    if result["status"] == "ERROR":
        return EXIT_ERROR
    if result["outcome"] == "CONTRACT_CHANGE_REQUIRED":
        return EXIT_HUMAN_GATE
    return EXIT_BLOCKED


def cmd_collect_reports(args: argparse.Namespace) -> int:
    state = load_state()
    leaves = state.get("leaves", []) if state else []
    lines = ["# Vibe Coding Final Report", "", f"- generated_at: {now()}", ""]
    lines.append("## Leaves")
    for leaf in leaves:
        leaf_dir = VIBECODE_DIR / "leaves" / leaf["node_id"]
        lines.append(f"- `{leaf['node_id']}`: `{rel(leaf_dir / 'completion-report.md')}`")
    if not leaves:
        lines.append("- No leaves recorded.")
    lines.append("")
    lines.append("## Backfill Reports")
    reports = sorted((VIBECODE_DIR / "backfill").glob("*/backfill-report.md"))
    for report in reports:
        lines.append(f"- `{rel(report)}`")
    if not reports:
        lines.append("- No backfill reports recorded.")
    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append("Pending human final approval.")
    write_text(VIBECODE_DIR / "final-report.md", "\n".join(lines))
    if state:
        state["stage"] = STAGE_FINAL_ACCEPTANCE
        history(state, "collect-reports", "final-report.md")
        save_state(state)
    print(f"Wrote {rel(VIBECODE_DIR / 'final-report.md')}")
    return EXIT_OK


def cmd_audit_state(args: argparse.Namespace) -> int:
    errors = audit_state(repair=args.repair)
    if errors:
        print("State audit failed:")
        for error in errors:
            print(f"- {error}")
        return EXIT_BLOCKED
    print("State audit passed.")
    return EXIT_OK


def cmd_self_test(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "workspace" / "nodes" / "root.demo"
        base.mkdir(parents=True)
        sources = {
            "prd": ("prd.json", "prd/v3"),
            "architecture": ("architecture.json", "architecture/v2"),
            "testcases": ("testcases.json", "testcases/v2"),
            "mocktest_report": ("mocktest_report.json", "mocktest-report/v2"),
            "mocktest_evidence": ("leaf_gate_evidence.json", "mocktest-leaf-evidence/v2"),
        }
        refs = {}
        for role, (name, version) in sources.items():
            write_json(base / name, {"artifact_id": role, "artifact_schema_version": version})
            refs[role] = {"path": name, "sha256": file_sha256(base / name)}
        write_text(base / "testcases.feature", "Feature: Demo\n")
        write_json(base / "leaf_gate_input.json", {"current_artifacts": refs})
        output = base / "leaf-gate"
        output.mkdir()
        write_json(output / "leaf_gate_report.json", {
            "artifact_schema_version": "leaf-gate-report/v2",
            "identity": {"node_id": "root.demo", "parent_node_id": "root"},
            "admission": {"state": "ADMITTED"},
            "decision": {"value": "STOP_LAYERING"},
            "next_action": {"type": "VIBECODE"},
        })
        write_text(output / "leaf_gate_report.md", "# Leaf Gate Report\n")
        write_json(output / "next_action.json", {"type": "VIBECODE"})
        write_json(output / "execution_log.json", {"events": []})
        files = [
            {"path": name, "sha256": file_sha256(output / name)}
            for name in ("leaf_gate_report.json", "leaf_gate_report.md", "next_action.json", "execution_log.json")
        ]
        write_json(output / "bundle_manifest.json", {"files": files, "bundle_sha256": canonical_hash(files)})
        leaves = scan_leaves(Path(tmp) / "workspace" / "nodes")
        assert len(leaves) == 1, leaves
        assert leaves[0]["status"] == "DISCOVERED", leaves[0]
        assert normalize_leaf_decision("STOP_LAYERING") == "STOP_LAYERING"
        assert normalize_leaf_decision("LEAF_READY") is None
    print("self-test passed")
    return EXIT_OK


def cmd_run_workflow(args: argparse.Namespace) -> int:
    """Run the new root workflow without changing the legacy state machine."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from vibecode.root_workflow import (
        EXIT_CONFIG,
        EXIT_RUNTIME,
        ConfigurationError,
        RootWorkflow,
        WorkflowInterrupted,
        command_adapter,
    )

    try:
        config_path = Path(args.config).resolve()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get("commands", {}), dict):
            raise ConfigurationError("project config must be an object with a commands object")
        model_parameters = json.loads(args.model_parameters)
        if not isinstance(model_parameters, dict):
            raise ConfigurationError("--model-parameters must decode to an object")
        input_path = Path(args.requirement or args.root_prd).resolve()
        mode = args.experiment_mode
        branch_mode = args.branch_mode
        if mode in {"sequential", "parallel"}:
            branch_mode, mode = mode, "full_recursive"
        workflow = RootWorkflow(
            output_root=Path(args.output_dir),
            run_id=args.run_id,
            project_id=args.project_id,
            root_node_id=args.root_node_id,
            input_path=input_path,
            input_kind="requirement" if args.requirement else "prd",
            config=config,
            adapter=command_adapter(config.get("commands", {}), cwd=config.get("cwd")),
            mode=mode,
            branch_mode=branch_mode,
            max_depth=args.max_depth,
            retry_limit=args.retry_limit,
            model=args.model,
            model_parameters=model_parameters,
            random_seed=args.random_seed,
            resume=args.resume,
            dry_run=args.dry_run,
        )
        return workflow.run()
    except WorkflowInterrupted:
        print("Workflow interrupted; rerun with --resume.", file=sys.stderr)
        return EXIT_RUNTIME
    except (OSError, json.JSONDecodeError, ConfigurationError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except Exception as exc:
        print(f"Unhandled workflow error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME


DEFAULT_VIBECODE_TASK = """# Vibe Code Task: {node_id}

Role: Leaf Owner
Parent: `{parent}`
Leaf source: `{leaf_path}`

## Inputs

- PRD: `{prd}`
- Architecture: `{architecture}`
- Testcases: `{testcases}`
- Mocktest report: `{mocktest_report}`
- Leaf Gate report: `{leaf_gate_report}`
- Next action: `{next_action}`
- Bundle manifest: `{bundle_manifest}`

## Feature Files

{features}

## Task

Implement only this leaf. Start with the public contract skeleton, then implement the internal behavior required by the feature files.

## Completion

Write:

- `completion-report.md`
- `contract-diff.md`
- `test-results.md`
- `risk-resolution.md`
- `child-completion-package.md`
"""

DEFAULT_ALLOWED_CONTEXT = """# Allowed Context: {node_id}

The Leaf Owner may read and edit only paths needed for this leaf.

## Source Artifacts

- `{leaf_path}`
- `{prd}`
- `{architecture}`
- `{testcases}`
- `{mocktest_report}`
- `{leaf_gate_report}`
- `{next_action}`
- `{bundle_manifest}`

## Generated Task Directory

- `vibecode/leaves/{node_id}`
"""

DEFAULT_FORBIDDEN_CHANGES = """# Forbidden Changes: {node_id}

Do not modify:

- parent wiring outside an approved backfill plan
- sibling implementations
- shared contracts or root-level DTO/event schemas
- unrelated business logic
- deployment, release, or global config files unless the task explicitly requires them
"""

DEFAULT_CONTRACT_CHECKLIST = """# Contract Checklist: {node_id}

- [ ] Public API/callable entrypoint matches parent expectation.
- [ ] DTO/schema fields match names, types, requiredness, and enum values.
- [ ] Error mapping is explicit.
- [ ] Events, state transitions, side effects, timeouts, retries, and idempotency are documented where applicable.
- [ ] Any mismatch is recorded in `contract-diff.md`.
"""

DEFAULT_IMPLEMENTATION_CHECKLIST = """# Implementation Checklist: {node_id}

- [ ] Build contract skeleton first.
- [ ] Add fake/mock dependencies where needed.
- [ ] Implement only leaf-owned behavior.
- [ ] Avoid parent wiring and sibling internals.
- [ ] Keep extra behavior internal unless explicitly approved.
"""

DEFAULT_VERIFICATION_CHECKLIST = """# Verification Checklist: {node_id}

- [ ] Run leaf-owned tests.
- [ ] Run provider contract tests.
- [ ] Run feature scenario checks.
- [ ] Check risk mitigations.
- [ ] Record commands and results in `test-results.md`.
"""

DEFAULT_BACKFILL_TARGET = """# Backfill Target: {node_id}

Parent: `{parent}`
Backfill report directory: `{backfill_dir}`

Integration Owner must run contract diff before replacing the parent mock/fake child with the real child.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Layered vibe coding workflow helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--leaf-root", default="workspace/nodes")
    p.add_argument("--target-repo", default=".")
    p.add_argument("--mode", default="single", choices=["single", "multi"])
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("doctor")
    p.add_argument("--leaf-root")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("generate-matrix")
    p.add_argument("--leaf-root")
    p.set_defaults(func=cmd_generate_matrix)

    p = sub.add_parser("approve")
    p.add_argument("--gate", required=True)
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("generate-leaf-tasks")
    p.set_defaults(func=cmd_generate_leaf_tasks)

    p = sub.add_parser("next-step")
    p.add_argument("--write-prompt")
    p.set_defaults(func=cmd_next_step)

    p = sub.add_parser("verify-stage")
    p.set_defaults(func=cmd_verify_stage)

    p = sub.add_parser("advance-state")
    p.set_defaults(func=cmd_advance_state)

    p = sub.add_parser("guard-paths")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_guard_paths)

    p = sub.add_parser("hook-guard")
    p.set_defaults(func=cmd_hook_guard)

    p = sub.add_parser("contract-diff")
    p.add_argument("--parent", required=True)
    p.add_argument("--child", required=True)
    p.add_argument("--output")
    p.add_argument("--json-output")
    p.add_argument("--legacy-text", action="store_true")
    p.set_defaults(func=cmd_contract_diff)

    p = sub.add_parser("collect-reports")
    p.set_defaults(func=cmd_collect_reports)

    p = sub.add_parser("audit-state")
    p.add_argument("--repair", action="store_true")
    p.set_defaults(func=cmd_audit_state)

    p = sub.add_parser("self-test")
    p.set_defaults(func=cmd_self_test)

    p = sub.add_parser(
        "run-workflow",
        help="run the recoverable root workflow (does not mutate legacy state.json)",
    )
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--requirement", help="path to a raw requirement artifact")
    source.add_argument("--root-prd", help="path to an existing structured root PRD")
    p.add_argument("--config", required=True, help="JSON project/module-adapter config")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--root-node-id", default="root")
    p.add_argument("--model")
    p.add_argument("--model-parameters", default="{}", help="JSON object")
    p.add_argument("--random-seed", type=int, default=0)
    p.add_argument("--max-depth", type=int, default=8)
    p.add_argument("--retry-limit", type=int, default=0)
    p.add_argument(
        "--experiment-mode",
        default="full_recursive",
        choices=["full_recursive", "non_recursive", "no_mock", "no_leaf_gate", "sequential", "parallel"],
    )
    p.add_argument("--branch-mode", default="parallel", choices=["parallel", "sequential"])
    p.add_argument("--resume", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_run_workflow)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
