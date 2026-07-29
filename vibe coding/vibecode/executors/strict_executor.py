"""Run validate-arch strict work without conflating transport and semantics."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from vibecode.executors.model_runner import run_codex


ModelRunner = Callable[..., dict[str, Any]]
DriverCall = Callable[[list[str]], int]


def _subprocess_driver(python: str, driver: Path) -> DriverCall:
    def call(arguments: list[str]) -> int:
        completed = subprocess.run(
            [python, str(driver), *arguments], capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        return completed.returncode
    return call


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _respond(
    *, pending: dict[str, Any], output_dir: Path, model: str, runner: ModelRunner
) -> dict[str, Any]:
    prompt_file = Path(pending["prompt_file"])
    raw_file = Path(pending["raw_response_file"])
    relative = raw_file.resolve().relative_to(output_dir.resolve()).as_posix()
    prompt = prompt_file.read_text(encoding="utf-8", errors="replace")
    result = runner(
        prompt=(prompt + "\n\nWrite exactly one JSON response to `" + relative
                + "` in the current workspace. Do not modify any other file."),
        workspace=output_dir, model=model, timeout_seconds=600,
    )
    if result.get("status") != "PASS" or not raw_file.is_file():
        raise RuntimeError("strict response agent did not write its declared raw response")
    return result


def execute_strict(
    *, feature_path: Path, architecture_path: Path, output_dir: Path,
    python: str, driver: Path, model: str, run_id: str, project_id: str,
    node_id: str, parent_node_id: str | None, runner: ModelRunner = run_codex,
    driver_call: DriverCall | None = None,
) -> dict[str, Any]:
    """Execute every strict stage and return independent completeness/status fields."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    call = driver_call or _subprocess_driver(python, driver)
    common = ["--output-dir", str(output_dir)]
    init = ["init", "--feature", str(feature_path), "--arch", str(architecture_path), *common,
            "--run-id", run_id, "--project-id", project_id, "--node-id", node_id]
    if parent_node_id:
        init.extend(["--parent-node-id", parent_node_id])
    if call(init) != 0:
        return _result("ERROR", output_dir, "STRICT_INIT_FAILED", "strict init failed")

    model_events: list[dict[str, Any]] = []
    while True:
        if call(["next-components", *common, "--limit", "1"]) != 0:
            return _result("ERROR", output_dir, "STRICT_COMPONENT_QUEUE_FAILED", "cannot obtain component work")
        pending = _read_json(output_dir / "pending_components.json", [])
        if not pending:
            break
        item = pending[0]
        try:
            model_events.append(_respond(pending=item, output_dir=output_dir, model=model, runner=runner))
        except RuntimeError as exc:
            return _result("ERROR", output_dir, "STRICT_COMPONENT_RESPONSE_ERROR", str(exc), model_events)
        if call(["consume-component", *common, "--pending-file", item["pending_file"], "--agent-id", "codex-cli"]) != 0:
            return _result("ERROR", output_dir, "STRICT_COMPONENT_CONSUME_FAILED", "component response could not be consumed", model_events)

    if call(["prepare-validators", *common]) != 0:
        return _result("FAIL", output_dir, "STRICT_SEMANTIC_BLOCKED", "strict semantic gate blocked validators", model_events)
    while True:
        if call(["next-validators", *common, "--limit", "1"]) != 0:
            return _result("ERROR", output_dir, "STRICT_VALIDATOR_QUEUE_FAILED", "cannot obtain validator work", model_events)
        pending = _read_json(output_dir / "pending_validators.json", [])
        if not pending:
            break
        item = pending[0]
        try:
            model_events.append(_respond(pending=item, output_dir=output_dir, model=model, runner=runner))
        except RuntimeError as exc:
            return _result("ERROR", output_dir, "STRICT_VALIDATOR_RESPONSE_ERROR", str(exc), model_events)
        if call(["consume-validator", *common, "--pending-file", item["pending_file"], "--agent-id", "codex-cli"]) != 0:
            return _result("ERROR", output_dir, "STRICT_VALIDATOR_CONSUME_FAILED", "validator response could not be consumed", model_events)

    # A semantic FAIL deliberately returns exit 2. The formal report, not that
    # transport code, is authoritative for the semantic classification.
    finalize_exit = call(["finalize", *common])
    report = _read_json(output_dir / "formal/mocktest_report.json", {})
    audit = _read_json(output_dir / "strict_audit.json", {})
    execution_complete = report.get("execution_status") == "COMPLETED"
    semantic_status = report.get("validation_status") or report.get("status")
    audit_status = audit.get("status") or report.get("metrics", {}).get("strict_audit_status")
    if not report:
        return _result("ERROR", output_dir, "STRICT_FINALIZE_REPORT_MISSING", "finalize did not publish report", model_events)
    status = "PASS" if execution_complete and semantic_status == "PASS" and audit_status == "PASS" else "FAIL"
    if finalize_exit not in (0, 2):
        status = "ERROR"
    return {
        **_result(status, output_dir, None, None, model_events),
        "execution_complete": execution_complete, "semantic_status": semantic_status,
        "strict_audit_status": audit_status, "finalize_exit": finalize_exit,
        "report_path": "formal/mocktest_report.json",
    }


def _result(status: str, output_dir: Path, code: str | None, message: str | None,
            model_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "status": status, "output_artifacts": ["formal/mocktest_report.json"]
        if (output_dir / "formal/mocktest_report.json").is_file() else [],
        "model_events": model_events or [], "error_type": code, "error_message": message,
    }
