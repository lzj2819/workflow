"""Root-workflow adapter for real validate-arch strict evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from vibecode.artifact_contract import content_sha256
from vibecode.executors.strict_executor import execute_strict


StrictRunner = Callable[..., dict[str, Any]]


def _select_artifact(bundle: Path, generator: str) -> Path:
    """Select one actual upstream root-workflow artifact, never a fixture."""
    value = json.loads(bundle.read_text(encoding="utf-8"))
    records = value.get("records") if isinstance(value, dict) else None
    if not isinstance(records, list):
        raise ValueError("strict input must be a root-workflow records bundle")
    matches = [record for record in records if isinstance(record, dict) and record.get("generator") == generator]
    if len(matches) != 1:
        raise ValueError(f"strict input must contain exactly one {generator} record")
    artifact = matches[0].get("primary_artifact")
    path = Path(artifact) if isinstance(artifact, str) else None
    if path is None or not path.is_file():
        raise ValueError(f"{generator} primary artifact is missing")
    return path.resolve()


def execute_adapter(*, input_path: Path, output_dir: Path, run_id: str, project_id: str,
                    node_id: str, parent_node_id: str | None, model: str, driver: Path,
                    strict_runner: StrictRunner = execute_strict) -> dict[str, Any]:
    """Write a v0.2 result while preserving semantic FAIL as a normal outcome."""
    architecture = _select_artifact(input_path, "architecture")
    feature = _select_artifact(input_path, "gherkin")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    strict = strict_runner(
        feature_path=feature, architecture_path=architecture, output_dir=output_dir,
        python=sys.executable, driver=driver, model=model, run_id=run_id,
        project_id=project_id, node_id=node_id, parent_node_id=parent_node_id,
    )
    report = output_dir / "formal" / "mocktest_report.json"
    status = strict.get("status", "ERROR")
    error = None if status == "PASS" else {
        "category": "tool" if status == "ERROR" else "business",
        "code": strict.get("error_type") or "STRICT_VALIDATION_FAILED",
        "message": strict.get("error_message") or "strict validation did not PASS",
    }
    result = {
        "schema_version": "verilayer-artifact/v0.2", "run_id": run_id,
        "project_id": project_id, "node_id": node_id, "parent_node_id": parent_node_id,
        "artifact_id": f"{run_id}:{node_id}:mocktest:result", "artifact_type": "mocktest_report",
        "status": status, "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": {"executor": "strict_executor", "model": model},
        "input_artifacts": [str(architecture), str(feature)], "requirement_ids": [],
        "content_path": "formal/mocktest_report.json" if report.is_file() else None,
        "content_sha256": content_sha256(report) if report.is_file() else None,
        "output_artifacts": ["formal/mocktest_report.json"] if report.is_file() else [],
        "error": error, "error_type": error["code"] if error else None,
        "error_message": error["message"] if error else None,
        "execution_complete": strict.get("execution_complete"),
        "semantic_status": strict.get("semantic_status"),
        "strict_audit_status": strict.get("strict_audit_status"),
        "finalize_exit": strict.get("finalize_exit"),
        "model_events": strict.get("model_events", []),
    }
    result_path = output_dir / "module-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VeriLayer real strict Mocktest adapter")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--parent-node-id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--driver", default=os.environ.get("VERILAYER_STRICT_DRIVER"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.driver:
        raise SystemExit("VERILAYER_STRICT_DRIVER or --driver is required for real strict execution")
    result = execute_adapter(
        input_path=Path(args.input), output_dir=Path(args.output_dir), run_id=args.run_id,
        project_id=args.project_id, node_id=args.node_id, parent_node_id=args.parent_node_id,
        model=args.model, driver=Path(args.driver),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # RootWorkflow reads the structured result. A semantic FAIL is deliberately
    # an exit-0 protocol result, not a transport error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
