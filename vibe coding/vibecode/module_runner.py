"""Run and join current-attempt Architecture/Gherkin module adapters."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ModuleRunner = Callable[
    [str, Any, Path, Path, dict[str, Any]],
    dict[str, Any],
]


class JoinError(ValueError):
    """The design/test branch Join cannot safely start or complete."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command_module(
    module: str,
    command: list[str],
    input_path: Path,
    output_dir: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    values = {
        **context,
        "module": module,
        "input": str(input_path),
        "output_dir": str(output_dir),
    }
    rendered = [part.format_map(values) for part in command]
    try:
        completed = subprocess.run(
            rendered,
            cwd=context.get("cwd"),
            capture_output=True,
            text=True,
            timeout=context.get("timeout_seconds"),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error_result(module, context["input_hash"], type(exc).__name__, str(exc))
    if completed.returncode != 0:
        return _error_result(
            module,
            context["input_hash"],
            "NONZERO_EXIT",
            f"module exited with code {completed.returncode}",
        )
    result_path = output_dir / "module-result.json"
    if not result_path.is_file():
        return _error_result(
            module,
            context["input_hash"],
            "MISSING_RESULT",
            "module did not write module-result.json",
        )
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error_result(module, context["input_hash"], "INVALID_RESULT", str(exc))
    if not isinstance(result, dict):
        return _error_result(
            module, context["input_hash"], "INVALID_RESULT", "result must be an object"
        )
    return result


def execute_design_branches(
    prd_path: Path,
    attempt_dir: Path,
    architecture_spec: Any,
    gherkin_spec: Any,
    *,
    run_id: str,
    project_id: str,
    node_id: str,
    mode: str = "parallel",
    runner: ModuleRunner = run_command_module,
    runner_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in {"parallel", "sequential"}:
        raise JoinError(f"unsupported execution mode: {mode}")
    if not prd_path.is_file():
        raise JoinError(f"missing PRD input: {prd_path}")
    if attempt_dir.exists() and any(attempt_dir.iterdir()):
        raise JoinError(f"attempt directory contains stale artifacts: {attempt_dir}")
    attempt_dir.mkdir(parents=True, exist_ok=True)
    input_hash = file_sha256(prd_path)
    input_dir = attempt_dir / "input"
    input_dir.mkdir()
    input_snapshot = input_dir / "prd.json"
    shutil.copyfile(prd_path, input_snapshot)
    if file_sha256(input_snapshot) != input_hash:
        raise JoinError("PRD snapshot hash does not match source input")
    base_context = {
        **(runner_context or {}),
        "run_id": run_id,
        "project_id": project_id,
        "node_id": node_id,
        "input_hash": input_hash,
    }
    specifications = {
        "architecture": architecture_spec,
        "gherkin": gherkin_spec,
    }
    branch_dirs = {name: attempt_dir / name for name in specifications}
    for branch_dir in branch_dirs.values():
        branch_dir.mkdir()

    started = time.perf_counter()
    if mode == "parallel":
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="design-branch") as pool:
            futures = {
                name: pool.submit(
                    _run_one,
                    name,
                    specifications[name],
                    input_snapshot,
                    branch_dirs[name],
                    base_context,
                    runner,
                )
                for name in ("architecture", "gherkin")
            }
            results = {name: futures[name].result() for name in ("architecture", "gherkin")}
    else:
        results = {
            name: _run_one(
                name,
                specifications[name],
                input_snapshot,
                branch_dirs[name],
                base_context,
                runner,
            )
            for name in ("architecture", "gherkin")
        }
    wall_time_ms = round((time.perf_counter() - started) * 1000, 3)
    current_input_hash = file_sha256(input_snapshot)
    errors = [
        f"{name}: {result.get('error_message') or result.get('status')}"
        for name, result in results.items()
        if result.get("status") != "PASS"
    ]
    if current_input_hash != input_hash:
        errors.append("PRD input changed during branch execution")
    status = "PASS" if not errors else "ERROR"
    joined = {
        "schema_version": "1.0",
        "run_id": run_id,
        "project_id": project_id,
        "node_id": node_id,
        "mode": mode,
        "status": status,
        "mocktest_allowed": status == "PASS",
        "source_input_artifact": str(prd_path),
        "input_artifact": str(input_snapshot),
        "input_hash": input_hash,
        "wall_time_ms": wall_time_ms,
        "branches": results,
        "errors": errors,
    }
    _atomic_write_json(attempt_dir / "design-join.json", joined)
    return joined


def _run_one(
    module: str,
    specification: Any,
    input_path: Path,
    output_dir: Path,
    context: dict[str, Any],
    runner: ModuleRunner,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = runner(module, specification, input_path, output_dir, dict(context))
        result = _validate_result(module, result, output_dir, context["input_hash"])
    except Exception as exc:  # module boundaries must fail closed
        result = _error_result(module, context["input_hash"], type(exc).__name__, str(exc))
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    return {
        "schema_version": "1.0",
        "run_id": context["run_id"],
        "project_id": context["project_id"],
        "node_id": context["node_id"],
        "parent_node_id": context.get("parent_node_id"),
        "artifact_id": f"{context['run_id']}:{context['node_id']}:{module}:result",
        "artifact_type": "module_result",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": module,
        "input_artifacts": [str(input_path)],
        "requirement_ids": list(context.get("requirement_ids", [])),
        **result,
        "duration_ms": duration_ms,
    }


def _validate_result(
    module: str,
    result: dict[str, Any],
    output_dir: Path,
    input_hash: str,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise JoinError(f"{module} result must be an object")
    if result.get("module") != module:
        raise JoinError(f"{module} result identifies module {result.get('module')!r}")
    if result.get("input_hash") != input_hash:
        raise JoinError(f"{module} input hash does not match current PRD")
    if result.get("status") not in {"PASS", "FAIL", "ERROR"}:
        raise JoinError(f"{module} returned invalid status {result.get('status')!r}")
    if result["status"] != "PASS":
        return result
    artifacts = result.get("output_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise JoinError(f"{module} PASS result requires output_artifacts")
    output_root = output_dir.resolve()
    hashes: dict[str, str] = {}
    for raw_path in artifacts:
        if not isinstance(raw_path, str):
            raise JoinError(f"{module} output artifact path must be a string")
        artifact = Path(raw_path)
        if not artifact.is_absolute():
            artifact = output_dir / artifact
        resolved = artifact.resolve()
        try:
            resolved.relative_to(output_root)
        except ValueError as exc:
            raise JoinError(f"{module} output escapes branch directory: {raw_path}") from exc
        if not resolved.is_file():
            raise JoinError(f"{module} declared missing output: {raw_path}")
        hashes[resolved.relative_to(output_root).as_posix()] = file_sha256(resolved)
    return {**result, "output_hashes": hashes}


def _error_result(
    module: str, input_hash: str, error_type: str, error_message: str
) -> dict[str, Any]:
    return {
        "module": module,
        "status": "ERROR",
        "input_hash": input_hash,
        "output_artifacts": [],
        "error_type": error_type,
        "error_message": error_message,
    }


def _atomic_write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
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
