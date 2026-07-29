"""Bounded model-backed generation for fresh root-workflow artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecode.artifact_contract import content_sha256
from vibecode.executors.evidence import write_json_evidence
from vibecode.executors.model_runner import run_codex


ModelRunner = Callable[..., dict[str, Any]]
_SPECS = {
    "prd": ("prd.json", "prd", "Create a JSON PRD with requirement_ids and explicit requirements."),
    "architecture": ("architecture.md", "architecture", "Create Markdown architecture with named components, entry contract, flows, error behavior, and explicit interfaces. For strict validation, include a `validate-arch-package` JSON comment; a `Component registry` table with `child_id`, `responsibility`, and `dispatch_kind` columns (use dispatch_kind `component`); and a second `组件职责` table with `Component` and `Responsibility` columns. The public entry's canonical child_id must be `public-api-service`; use `Public API Service` only as its human-readable display name. Add `Entry endpoint and request`, `Request flow`, and an actual Mermaid `sequenceDiagram` beginning `Client -> PublicAPIService:`. Add an `Internal contract mapping` table whose columns are exactly `contract_id`, `Owner → Consumer`, `触发与 schema`, and `Errors, idempotency, compatibility`. In every Owner/Consumer cell use only bare canonical child_ids separated by `→` (never `Provider:`, `Consumer:`, or prose). Every strict component must appear on at least one scenario-reachable flow; omit components not used by the Feature. Declare a machine-readable inbound public contract and a public response contract. For every contract, write fields as backtick lists immediately after `输入:` and `输出:` (for example, `输入: `event`; 输出: `status_code, body``). Then add a `Contract mapping` section with the same public endpoint's contract_id, Provider, Consumer, explicit inputs, outputs, and errors."),
    "gherkin": ("testcases.feature", "testcases", "Create executable Gherkin scenarios with REQ tags, concrete inputs, and observable assertions. For strict validation, every When step must say `the client sends METHOD /path to Public API Service`, where METHOD/path are explicit. Keep Given steps as client/request state only; do not name internal components in Given. Every scenario must have a concrete Then response assertion."),
}


def _requirement_ids(source: str) -> list[str]:
    found = sorted(set(re.findall(r"\bREQ-[A-Za-z0-9-]+\b", source)))
    return found or ["REQ-ROOT"]


def execute_generation(
    *, module: str, input_path: Path, output_dir: Path, run_id: str,
    project_id: str, node_id: str, parent_node_id: str | None,
    model: str, timeout_seconds: int = 600, runner: ModelRunner = run_codex,
) -> dict[str, Any]:
    """Generate exactly one public artifact in the supplied attempt directory."""
    if module not in _SPECS:
        raise ValueError("module must be prd, architecture, or gherkin")
    if not input_path.is_file():
        raise ValueError("input_path must identify a file")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target_name, artifact_type, instruction = _SPECS[module]
    source = input_path.read_text(encoding="utf-8", errors="replace")
    prompt = (
        f"You are generating one fresh VeriLayer {module} artifact.\n"
        f"{instruction}\n"
        f"Write exactly `{target_name}` in the current workspace; do not modify parent directories or hidden tests.\n"
        "Use only the public input below. Do not use Tutor artifacts, fixtures, or prior calibration outputs.\n\n"
        f"PUBLIC INPUT:\n{source}"
    )
    model_result = runner(prompt=prompt, workspace=output_dir, model=model, timeout_seconds=timeout_seconds)
    target = output_dir / target_name
    passed = model_result.get("status") == "PASS" and target.is_file()
    error = None if passed else {
        "category": "tool" if model_result.get("status") == "ERROR" else "business",
        "code": "GENERATION_FAILED" if model_result.get("status") != "PASS" else "EXPECTED_ARTIFACT_MISSING",
        "message": model_result.get("error_message") or f"{target_name} was not produced",
    }
    evidence = write_json_evidence(output_dir, "generation-evidence.json", {
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "target": target_name,
        "model": model_result,
    })
    result = {
        "schema_version": "verilayer-artifact/v0.2", "run_id": run_id,
        "project_id": project_id, "node_id": node_id, "parent_node_id": parent_node_id,
        "artifact_id": f"{run_id}:{node_id}:{module}:result", "artifact_type": artifact_type,
        "status": "PASS" if passed else "ERROR", "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"executor": "generation_executor", "model": model},
        "input_artifacts": [input_path.name], "requirement_ids": _requirement_ids(source),
        "content_path": target_name if passed else None,
        "content_sha256": content_sha256(target) if passed else None, "error": error,
        "module": module, "input_hash": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "output_artifacts": [target_name] if passed else [], "output_hashes": {target_name: content_sha256(target)} if passed else {},
        "evidence": evidence,
        "error_type": error["code"] if error else None, "error_message": error["message"] if error else None,
    }
    (output_dir / "module-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
