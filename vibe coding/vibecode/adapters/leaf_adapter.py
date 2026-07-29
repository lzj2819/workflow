"""Translate root-workflow artifacts to the formal Leaf Gate input package."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecode.artifact_contract import content_sha256


LeafRunner = Callable[[Path, Path, Path], int]
_REQ = re.compile(r"\bREQ-[A-Za-z0-9-]+\b")


def _load_bundle(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    records = value.get("records") if isinstance(value, dict) else None
    if not isinstance(records, list):
        raise ValueError("leaf input must be a root-workflow records bundle")
    return [record for record in records if isinstance(record, dict)]


def _one(records: list[dict[str, Any]], generator: str) -> dict[str, Any]:
    matches = [record for record in records if record.get("generator") == generator]
    if len(matches) != 1:
        raise ValueError(f"leaf input must contain exactly one {generator} record")
    return matches[0]


def _requirements(record: dict[str, Any], content: str) -> list[str]:
    explicit = record.get("requirement_ids")
    values = explicit if isinstance(explicit, list) else []
    found = [item for item in values if isinstance(item, str) and item]
    return sorted(set(found or _REQ.findall(content) or ["REQ-ROOT"]))


def _common(*, artifact_type: str, run_id: str, project_id: str, node_id: str,
            parent_node_id: str | None, requirement_ids: list[str], status: str = "PASS") -> dict[str, Any]:
    return {
        "schema_version": "1.0", "run_id": run_id, "project_id": project_id,
        "node_id": node_id, "parent_node_id": parent_node_id,
        "artifact_id": f"{run_id}:{node_id}:leaf-input:{artifact_type}",
        "artifact_type": artifact_type, "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": "verilayer_leaf_adapter", "status": status,
        "input_artifacts": [], "requirement_ids": requirement_ids,
    }


def _run_leaf(script: Path, node_dir: Path, output: Path) -> int:
    completed = subprocess.run([sys.executable, str(script), str(node_dir), "--output", str(output)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return completed.returncode


def _depth_settings(record: dict[str, Any], prd_text: str, default_max_depth: int) -> tuple[int, int]:
    """Read depth from the original public requirement when generation omits it."""
    candidates: list[dict[str, Any]] = []
    try:
        value = json.loads(prd_text)
        if isinstance(value, dict):
            candidates.append(value)
    except json.JSONDecodeError:
        pass
    for raw in record.get("input_artifacts", []):
        path = Path(raw) if isinstance(raw, str) else None
        if path and path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    candidates.append(value)
            except (OSError, json.JSONDecodeError):
                continue
    for value in candidates:
        depth, maximum = value.get("depth"), value.get("max_depth")
        if isinstance(depth, int) and depth >= 0:
            if isinstance(maximum, int) and maximum >= depth:
                return depth, maximum
            return depth, default_max_depth
    return 0, default_max_depth


def _write_formal_input(*, records: list[dict[str, Any]], package: Path, run_id: str,
                        project_id: str, node_id: str, parent_node_id: str | None,
                        max_depth: int, max_requirements: int) -> list[str]:
    prd_record, arch_record = _one(records, "prd"), _one(records, "architecture")
    gherkin_record, mock_record = _one(records, "gherkin"), _one(records, "mocktest")
    prd_path = Path(prd_record.get("primary_artifact", "")); arch_path = Path(arch_record.get("primary_artifact", ""))
    feature_path = Path(gherkin_record.get("primary_artifact", "")); report_path = Path(mock_record.get("primary_artifact", ""))
    for label, path in (("prd", prd_path), ("architecture", arch_path), ("gherkin", feature_path), ("mocktest", report_path)):
        if not path.is_file():
            raise ValueError(f"{label} primary artifact is missing")
    prd_text = prd_path.read_text(encoding="utf-8", errors="replace")
    requirements = _requirements(prd_record, prd_text)
    depth, max_depth = _depth_settings(prd_record, prd_text, max_depth)
    package.mkdir(parents=True, exist_ok=True)
    (package / "leaf-gate.config.json").write_text(
        json.dumps({"thresholds": {"max_requirements": max_requirements,
                                    "max_recursion_depth": max_depth}}, indent=2) + "\n",
        encoding="utf-8",
    )
    (package / "prd.json").write_text(json.dumps({
        **_common(artifact_type="prd", run_id=run_id, project_id=project_id, node_id=node_id,
                  parent_node_id=parent_node_id, requirement_ids=requirements),
        "requirements": requirements, "node_history": [], "depth": depth, "max_depth": max_depth,
        "source_artifact": str(prd_path),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (package / "architecture.json").write_text(json.dumps({
        **_common(artifact_type="architecture", run_id=run_id, project_id=project_id, node_id=node_id,
                  parent_node_id=parent_node_id, requirement_ids=requirements),
        # A one-to-one responsibility view avoids inventing a free-form parse of
        # Markdown while keeping a root multi-requirement decision reproducible.
        "components": [{"id": f"component-{req}"} for req in requirements],
        "interfaces": [], "dependencies": [], "depth": 1, "risks": [],
        "source_artifact": str(arch_path),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    feature_text = feature_path.read_text(encoding="utf-8", errors="replace")
    feature_reqs = sorted(set(_REQ.findall(feature_text)))
    covered = [req for req in requirements if req in feature_reqs]
    (package / "testcases.json").write_text(json.dumps({
        **_common(artifact_type="testcases", run_id=run_id, project_id=project_id, node_id=node_id,
                  parent_node_id=parent_node_id, requirement_ids=requirements),
        "testcases": [{"id": f"scenario-{req}", "requirement_ids": [req], "status": "PASS"} for req in covered],
        "source_artifact": str(feature_path),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    semantic = report.get("validation_status") or report.get("status")
    (package / "mocktest_report.json").write_text(json.dumps({
        **_common(artifact_type="mocktest_report", run_id=run_id, project_id=project_id, node_id=node_id,
                  parent_node_id=parent_node_id, requirement_ids=requirements, status=str(semantic or "ERROR")),
        "execution_status": report.get("execution_status"), "validation_status": semantic,
        "strict_audit_status": mock_record.get("strict_audit_status"),
        "defects": report.get("defects", []), "source_artifact": str(report_path),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return requirements


def _children(raw: Any, *, parent_depth: int, max_depth: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    converted = []
    for child in raw:
        if not isinstance(child, dict):
            raise ValueError("formal Leaf child must be an object")
        child_id = child.get("node_id") or child.get("child_node_id")
        if not isinstance(child_id, str) or not child_id:
            raise ValueError("formal Leaf child lacks node_id/child_node_id")
        requirements = child.get("requirement_ids")
        if not isinstance(requirements, list) or not all(isinstance(item, str) and item for item in requirements):
            raise ValueError("formal Leaf child requirement_ids are invalid")
        converted.append({
            "node_id": child_id, "name": child.get("name", child_id),
            "responsibility": child.get("responsibility", ""), "requirement_ids": requirements,
            "decomposition_rationale": child.get("decomposition_rationale", ""),
            "expected_interfaces": child.get("expected_interfaces", []), "priority": child.get("priority", 0),
            "requirement": {"requirement_ids": requirements, "depth": parent_depth + 1, "max_depth": max_depth,
                            "parent_artifact_refs": child.get("expected_interfaces", [])},
        })
    return converted


def execute_adapter(*, input_path: Path, output_dir: Path, run_id: str, project_id: str,
                    node_id: str, parent_node_id: str | None, max_depth: int = 2,
                    max_requirements: int = 1,
                    script: Path | None = None, leaf_runner: LeafRunner = _run_leaf) -> dict[str, Any]:
    if max_depth < 1 or max_requirements < 1:
        raise ValueError("max_depth and max_requirements must be positive")
    records = _load_bundle(input_path)
    output_dir = output_dir.resolve(); package = output_dir / "formal-input"
    requirements = _write_formal_input(records=records, package=package, run_id=run_id, project_id=project_id,
                                       node_id=node_id, parent_node_id=parent_node_id, max_depth=max_depth,
                                       max_requirements=max_requirements)
    source_prd = json.loads((package / "prd.json").read_text(encoding="utf-8"))
    runner_script = script or Path(__file__).resolve().parents[3] / "leaf-gate" / "scripts" / "run_leaf_gate.py"
    decision_path = output_dir / "leaf_gate_decision.json"
    exit_code = leaf_runner(runner_script, package, decision_path)
    if not decision_path.is_file():
        return {"status": "ERROR", "output_artifacts": [], "error_type": "LEAF_REPORT_MISSING",
                "error_message": f"Leaf Gate exited {exit_code} without a decision report"}
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    status = decision.get("status", "ERROR")
    children = _children(decision.get("proposed_children"), parent_depth=source_prd["depth"], max_depth=source_prd["max_depth"])
    error = None if status in {"CONTINUE_LAYERING", "STOP_LAYERING"} else {
        "category": "business" if exit_code == 2 else "tool", "code": "LEAF_GATE_FAILED",
        "message": decision.get("rationale", [{}])[0].get("message", "Leaf Gate did not decide"),
    }
    result = {
        "schema_version": "verilayer-artifact/v0.2", "run_id": run_id, "project_id": project_id,
        "node_id": node_id, "parent_node_id": parent_node_id, "artifact_id": f"{run_id}:{node_id}:leaf_gate:result",
        "artifact_type": "leaf", "status": status, "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"executor": "formal_leaf_gate", "script": "leaf-gate/scripts/run_leaf_gate.py"},
        "input_artifacts": [str(input_path)], "requirement_ids": requirements,
        "content_path": "leaf_gate_decision.json", "content_sha256": content_sha256(decision_path),
        "output_artifacts": ["leaf_gate_decision.json"], "decision": decision.get("decision", status),
        "proposed_children": children, "evidence_complete": True, "formal_exit_code": exit_code,
        "error": error, "error_type": error["code"] if error else None,
        "error_message": error["message"] if error else None,
    }
    (output_dir / "module-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriLayer formal Leaf Gate adapter")
    parser.add_argument("--input", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True); parser.add_argument("--project-id", required=True)
    parser.add_argument("--node-id", required=True); parser.add_argument("--parent-node-id")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-requirements", type=int, default=1)
    args = parser.parse_args(argv)
    result = execute_adapter(input_path=Path(args.input), output_dir=Path(args.output_dir), run_id=args.run_id,
                             project_id=args.project_id, node_id=args.node_id,
                             parent_node_id=None if args.parent_node_id in {None, "", "None", "null"} else args.parent_node_id,
                             max_depth=args.max_depth, max_requirements=args.max_requirements)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
