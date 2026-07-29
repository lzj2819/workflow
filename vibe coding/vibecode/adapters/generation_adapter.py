"""CLI boundary for model-backed PRD, Architecture, and Gherkin generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibecode.executors.generation_executor import execute_generation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VeriLayer fresh-generation adapter")
    parser.add_argument("--module", required=True, choices=("prd", "architecture", "gherkin"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--parent-node-id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    args = parser.parse_args(argv)
    result = execute_generation(
        module=args.module, input_path=Path(args.input), output_dir=Path(args.output_dir),
        run_id=args.run_id, project_id=args.project_id, node_id=args.node_id,
        parent_node_id=args.parent_node_id, model=args.model, timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
