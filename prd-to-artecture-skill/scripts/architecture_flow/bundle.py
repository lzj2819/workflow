"""Atomic writer for the fixed canonical Architecture bundle."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .canonical import canonical_json_text, render_canonical_architecture
from .consumer_profiles import validate_consumer_profile


FIXED_BUNDLE = (
    "architecture.json",
    "architecture.md",
    "architecture-manifest.yaml",
    "validation_report.json",
    "execution_log.json",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_json_schema(model: dict[str, Any], schema_path: Path) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is required for canonical Architecture validation"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"schema:{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(model), key=lambda item: list(item.absolute_path))
    ]


def _common(model: dict[str, Any], artifact_type: str, artifact_id: str) -> dict[str, Any]:
    return {
        "schema_version": model["schema_version"],
        "artifact_schema_version": f"{artifact_type}/v1",
        "run_id": model["run_id"],
        "project_id": model["project_id"],
        "node_id": model["node_id"],
        "parent_node_id": model["parent_node_id"],
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "created_at": model["created_at"],
        "generator": "prd-to-architecture-skill",
        "status": model["status"],
        "input_artifacts": model["input_artifacts"],
        "requirement_ids": model["requirement_ids"],
    }


def _change_request_markdown(model: dict[str, Any]) -> str:
    lines = [
        "# Parent Change Request",
        "",
        f"- Architecture artifact: `{model['artifact_id']}`",
        f"- Target node: `{model['node_id']}`",
        f"- Parent node: `{model['parent_node_id']}`",
        "- Status: `waiting_parent`",
        "",
    ]
    for request in model["payload"]["change_requests"]:
        lines.extend(
            [
                f"## {request['id']}",
                "",
                f"- Trigger requirement: `{request['trigger_requirement_id']}`",
                f"- Affected parent field: `{request['affected_parent_field']}`",
                f"- Current rule: {request['current_rule'] or 'None'}",
                f"- Proposed change: {request['proposed_change'] or 'None'}",
                f"- Impact: {request['impact'] or 'None'}",
                f"- Blocked decisions: {', '.join(request['blocked_decision_ids']) or 'None'}",
                "",
            ]
        )
    return "\n".join(lines)


def _write_staged_files(
    stage: Path,
    model: dict[str, Any],
    validation_errors: list[str],
) -> None:
    (stage / "architecture.json").write_text(canonical_json_text(model), encoding="utf-8")
    (stage / "architecture.md").write_text(render_canonical_architecture(model), encoding="utf-8")
    evaluated_profiles = ["canonical"]
    if model["status"] == "PASS":
        evaluated_profiles.extend(("decompose", "mocktest", "leaf", "vibe_adapter"))
    else:
        evaluated_profiles.append("parent_immutability")
    validation = {
        **_common(
            model,
            "architecture_validation",
            f"ARCH-VALIDATION-{model['node_id']}",
        ),
        "valid": not validation_errors,
        "errors": validation_errors,
        "profiles": evaluated_profiles,
        "content_sha256": model["content_sha256"],
    }
    (stage / "validation_report.json").write_text(
        canonical_json_text(validation), encoding="utf-8"
    )
    events = [
        "inputs_validated",
        "canonical_model_built",
        "semantic_validation_passed",
    ]
    events.append(
        "consumer_profiles_passed"
        if model["status"] == "PASS"
        else "blocked_parent_change_recorded"
    )
    events.append("bundle_staged")
    execution = {
        **_common(
            model,
            "architecture_execution_log",
            f"ARCH-EXECUTION-{model['node_id']}",
        ),
        "operation": model["operation"],
        "architecture_mode": model["architecture_mode"],
        "events": events,
        "duration_ms": 0,
        "content_sha256": model["content_sha256"],
    }
    (stage / "execution_log.json").write_text(
        canonical_json_text(execution), encoding="utf-8"
    )
    if model["payload"]["change_requests"]:
        (stage / "parent-change-request.md").write_text(
            _change_request_markdown(model), encoding="utf-8"
        )
    inventory = [
        "architecture.json",
        "architecture.md",
        "validation_report.json",
        "execution_log.json",
    ]
    if (stage / "parent-change-request.md").is_file():
        inventory.append("parent-change-request.md")
    hashes = {name: file_sha256(stage / name) for name in sorted(inventory)}
    manifest = {
        **_common(
            model,
            "architecture_manifest",
            f"ARCH-MANIFEST-{model['node_id']}",
        ),
        "package": {
            "level": f"L{model['depth']}",
            "current_node_name": model["payload"]["design_context"]["summary"] or model["node_id"],
            "target_node_id": model["node_id"],
            "responsibility": model["payload"]["design_context"]["responsibility"],
            "exclusions": model["payload"]["design_context"]["exclusions"],
            "architecture_mode": model["architecture_mode"],
            "status": model["architecture_status"],
        },
        "inputs": {
            "source_prd_id": model["source_prd_id"],
            "parent_architecture": (
                model["payload"]["parent_binding"]["parent_artifact_id"]
                if model["payload"]["parent_binding"]
                else None
            ),
        },
        "artifacts": ["architecture.md"],
        "artifact_inventory": sorted(inventory),
        "artifact_hashes": hashes,
        "content_sha256": model["content_sha256"],
    }
    # JSON is valid YAML 1.2 and avoids introducing a second serializer dependency.
    (stage / "architecture-manifest.yaml").write_text(
        canonical_json_text(manifest), encoding="utf-8"
    )


def _verify_stage(stage: Path, model: dict[str, Any]) -> list[str]:
    errors = []
    expected = set(FIXED_BUNDLE)
    if model["payload"]["change_requests"]:
        expected.add("parent-change-request.md")
    actual = {path.name for path in stage.iterdir() if path.is_file()}
    if actual != expected:
        errors.append(f"bundle inventory mismatch: expected={sorted(expected)} actual={sorted(actual)}")
    manifest = json.loads((stage / "architecture-manifest.yaml").read_text(encoding="utf-8"))
    for name, expected_hash in manifest.get("artifact_hashes", {}).items():
        path = stage / name
        if not path.is_file() or file_sha256(path) != expected_hash:
            errors.append(f"manifest hash mismatch: {name}")
    if (stage / "architecture.md").read_text(encoding="utf-8") != render_canonical_architecture(model):
        errors.append("architecture.md differs from deterministic renderer")
    return errors


def write_bundle(
    model: dict[str, Any],
    output_dir: Path,
    *,
    schema_path: Path,
    parent_architecture: dict[str, Any] | None = None,
) -> list[str]:
    """Validate, stage, verify, and atomically publish one complete bundle."""
    errors = validate_json_schema(model, schema_path)
    profiles = ["canonical"]
    if model.get("status") == "PASS":
        profiles.extend(("decompose", "mocktest", "leaf", "vibe_adapter"))
    elif not (
        model.get("architecture_mode") == "decompose"
        and model.get("status") == "FAIL"
        and model.get("payload", {}).get("change_requests")
    ):
        errors.append("non-PASS bundle is allowed only for a blocked decompose parent change request")
    for profile in profiles:
        errors.extend(
            validate_consumer_profile(
                model,
                profile,
                parent_architecture=parent_architecture,
            )
        )
    errors = list(dict.fromkeys(errors))
    if errors:
        return errors

    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and model.get("operation") != "revise":
        return ["output_dir already exists; use operation=revise for an explicit replacement"]
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=parent))
    backup: Path | None = None
    try:
        _write_staged_files(stage, model, [])
        stage_errors = _verify_stage(stage, model)
        if stage_errors:
            return stage_errors
        if output_dir.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=parent))
            backup.rmdir()
            os.replace(output_dir, backup)
        os.replace(stage, output_dir)
        if backup and backup.exists():
            shutil.rmtree(backup)
        return []
    except Exception:
        if backup and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
