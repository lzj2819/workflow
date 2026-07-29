"""Create a bounded public Coding request from a STOP_LAYERING root bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from vibecode.artifact_contract import content_sha256
from vibecode.executors.coding_executor import execute_coding


CodingRunner = Callable[..., dict[str, Any]]


def _records(bundle: Path) -> list[dict[str, Any]]:
    value = json.loads(bundle.read_text(encoding="utf-8"))
    records = value.get("records") if isinstance(value, dict) else None
    if not isinstance(records, list):
        raise ValueError("coding input must be a root-workflow records bundle")
    return [item for item in records if isinstance(item, dict)]


def _one(records: list[dict[str, Any]], generator: str) -> dict[str, Any]:
    matches = [item for item in records if item.get("generator") == generator]
    if len(matches) != 1:
        raise ValueError(f"coding input must contain exactly one {generator} record")
    return matches[0]


def _public_request(*, records: list[dict[str, Any]], output_dir: Path, node_id: str,
                    model: str) -> Path:
    prd, leaf = _one(records, "prd"), _one(records, "leaf_gate")
    if (leaf.get("decision") or leaf.get("status")) != "STOP_LAYERING":
        raise ValueError("Coding is only admissible after a formal STOP_LAYERING decision")
    requirements = prd.get("requirement_ids")
    if not isinstance(requirements, list) or not all(isinstance(item, str) and item for item in requirements):
        raise ValueError("leaf PRD has no valid requirement_ids")
    tests = output_dir / "public-tests"; tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_app.py").write_text(
        "from fastapi.testclient import TestClient\n\n"
        "def test_health_contract():\n"
        "    from app import app\n"
        "    response = TestClient(app).get('/health')\n"
        "    assert response.status_code == 200\n"
        "    body = response.json()\n"
        "    assert body['status'] == 'ok'\n"
        "    assert isinstance(body['node_id'], str)\n"
        "    assert isinstance(body['requirement_ids'], list)\n",
        encoding="utf-8",
    )
    request = {
        "requirement_ids": requirements, "model": model, "public_tests_dir": "public-tests",
        "pytest_arguments": ["-q", "tests/test_app.py"], "pytest_timeout_seconds": 120,
        "public_prompt": (
            "Implement one isolated, fresh FastAPI leaf in app.py. "
            "Expose GET /health returning JSON with status exactly 'ok', node_id exactly "
            f"{node_id!r}, and requirement_ids containing {requirements!r}. "
            "Use only the public requirements and test already in this workspace. "
            "Do not read parent directories, hidden tests, Tutor artifacts, or prior runs."
        ),
        "source_artifacts": [str(prd.get("primary_artifact", "")), str(leaf.get("primary_artifact", ""))],
    }
    path = output_dir / "coding-request.json"
    path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def execute_adapter(*, input_path: Path, output_dir: Path, run_id: str, project_id: str,
                    node_id: str, parent_node_id: str | None, model: str,
                    coding_runner: CodingRunner = execute_coding) -> dict[str, Any]:
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    request = _public_request(records=_records(input_path), output_dir=output_dir, node_id=node_id, model=model)
    result = coding_runner(request_path=request, workspace_root=output_dir / "workspaces", output_dir=output_dir,
                           run_id=run_id, project_id=project_id, node_id=node_id, python=sys.executable,
                           parent_node_id=parent_node_id, max_repairs=2)
    status = result.get("status", "ERROR")
    result["output_artifacts"] = ["module-result.json"]
    result["content_path"] = "module-result.json"
    result_path = output_dir / "module-result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["content_sha256"] = content_sha256(result_path)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["status"] = status
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriLayer root Coding adapter")
    parser.add_argument("--input", required=True); parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True); parser.add_argument("--project-id", required=True)
    parser.add_argument("--node-id", required=True); parser.add_argument("--parent-node-id")
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)
    result = execute_adapter(input_path=Path(args.input), output_dir=Path(args.output_dir), run_id=args.run_id,
                             project_id=args.project_id, node_id=args.node_id, parent_node_id=args.parent_node_id,
                             model=args.model)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Semantic code/test failures are structured results consumed by RootWorkflow.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
