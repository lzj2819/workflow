"""CLI boundary for the real, isolated Coding Executor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibecode.executors.coding_executor import execute_coding


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VeriLayer isolated Coding Executor")
    parser.add_argument("--input", required=True, help="public coding-request JSON")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--parent-node-id")
    parser.add_argument("--max-repairs", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = execute_coding(
        request_path=Path(args.input),
        workspace_root=Path(args.workspace_root),
        output_dir=Path(args.output_dir),
        run_id=args.run_id,
        project_id=args.project_id,
        node_id=args.node_id,
        python=args.python,
        parent_node_id=args.parent_node_id,
        max_repairs=args.max_repairs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
