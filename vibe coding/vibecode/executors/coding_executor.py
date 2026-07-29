"""Run a public-spec Coding task in an isolated workspace with bounded repair."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecode.artifact_contract import content_sha256
from vibecode.executors.evidence import write_json_evidence
from vibecode.executors.model_runner import run_codex
from vibecode.executors.pytest_runner import run_pytest
from vibecode.executors.workspace import prepare_workspace


ModelRunner = Callable[..., dict[str, Any]]


def _read_request(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {"requirement_ids", "public_prompt", "model"}
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"coding request missing: {', '.join(missing)}")
    if not isinstance(value["requirement_ids"], list) or not all(
        isinstance(item, str) and item for item in value["requirement_ids"]
    ):
        raise ValueError("requirement_ids must be a non-empty list of strings")
    if not isinstance(value["public_prompt"], str) or not value["public_prompt"].strip():
        raise ValueError("public_prompt must be a non-empty string")
    return value


def _tree_manifest(workspace: Path) -> list[dict[str, str]]:
    ignored = {".git", ".pytest_cache", "__pycache__"}
    items: list[dict[str, str]] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        relative = path.relative_to(workspace).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items.append({"path": relative, "sha256": digest})
    return items


def _copy_public_tests(request: dict[str, Any], request_path: Path, workspace: Path) -> None:
    """Copy only declared public tests; hidden inputs are never accepted here."""
    source_value = request.get("public_tests_dir")
    if source_value is None:
        return
    if not isinstance(source_value, str) or not source_value:
        raise ValueError("public_tests_dir must be a non-empty relative path")
    source = (request_path.parent / source_value).resolve()
    try:
        source.relative_to(request_path.parent.resolve())
    except ValueError as exc:
        raise ValueError("public_tests_dir escapes the request directory") from exc
    if not source.is_dir():
        raise ValueError("public_tests_dir must name an existing directory")
    destination = workspace / "tests"
    shutil.copytree(source, destination, dirs_exist_ok=True)


def execute_coding(
    *,
    request_path: Path,
    workspace_root: Path,
    output_dir: Path,
    run_id: str,
    project_id: str,
    node_id: str,
    python: str,
    parent_node_id: str | None = None,
    max_repairs: int = 2,
    runner: ModelRunner = run_codex,
) -> dict[str, Any]:
    """Execute only public task context; never copy hidden tests into the workspace."""
    if max_repairs < 0 or max_repairs > 2:
        raise ValueError("max_repairs must be between 0 and 2")
    request_path = request_path.resolve()
    request = _read_request(request_path)
    workspace = prepare_workspace(workspace_root, run_id, node_id)
    _copy_public_tests(request, request_path, workspace)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = request["public_prompt"].strip() + "\n\nWrite only inside the current workspace. Do not access hidden tests or parent directories."
    attempts: list[dict[str, Any]] = []
    for attempt in range(max_repairs + 1):
        if attempt:
            prior = attempts[-1]["pytest"]
            prompt = (
                request["public_prompt"].strip()
                + "\n\nRepair the current workspace using only this public pytest evidence:\n"
                + json.dumps(prior, ensure_ascii=False)
                + "\nDo not access hidden tests or parent directories."
            )
        model = runner(
            prompt=prompt,
            workspace=workspace,
            model=request["model"],
            timeout_seconds=int(request.get("model_timeout_seconds", 600)),
        )
        pytest_result = run_pytest(
            python=python,
            workspace=workspace,
            arguments=list(request.get("pytest_arguments", ["-q"])),
            timeout_seconds=int(request.get("pytest_timeout_seconds", 120)),
        )
        attempts.append({"attempt": attempt, "model": model, "pytest": pytest_result})
        if model.get("status") == "PASS" and pytest_result.get("status") == "PASS":
            break

    status = "PASS" if attempts[-1]["model"].get("status") == "PASS" and attempts[-1]["pytest"].get("status") == "PASS" else "FAIL"
    evidence = {
        "request_sha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "workspace": _tree_manifest(workspace),
        "attempts": attempts,
    }
    evidence_ref = write_json_evidence(output_dir, "coding-evidence.json", evidence)
    result = {
        "schema_version": "verilayer-artifact/v0.2",
        "run_id": run_id,
        "project_id": project_id,
        "node_id": node_id,
        "parent_node_id": parent_node_id,
        "artifact_id": f"{run_id}:{node_id}:coding:result",
        "artifact_type": "code",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"executor": "coding_executor", "model": request["model"]},
        "input_artifacts": [request_path.name],
        "requirement_ids": request["requirement_ids"],
        "content_path": "module-result.json",
        "content_sha256": "",
        "error": None,
        "workspace": str(workspace),
        "evidence": evidence_ref,
        "attempt_count": len(attempts),
        "pytest_status": attempts[-1]["pytest"].get("status"),
        "last_pytest": attempts[-1]["pytest"],
    }
    result_path = output_dir / "module-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["content_sha256"] = content_sha256(result_path)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
