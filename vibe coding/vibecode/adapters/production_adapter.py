"""CLI boundary used by the Day 2 production command configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibecode.adapters.common import PRODUCTION_MODULES, controlled_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VeriLayer Day 2 production adapter skeleton")
    parser.add_argument("--module", required=True, choices=PRODUCTION_MODULES)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default="day2-controlled-error")
    parser.add_argument("--project-id", default="verilayer")
    parser.add_argument("--node-id", default="root")
    parser.add_argument("--parent-node-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_path.is_file():
        result = {
            "module": args.module,
            "status": "ERROR",
            "input_hash": None,
            "output_artifacts": [],
            "output_hashes": {},
            "error_type": "INPUT_NOT_FOUND",
            "error_message": "adapter input does not exist",
        }
    else:
        repository_root = Path.cwd().resolve()
        try:
            input_reference = input_path.relative_to(repository_root).as_posix()
        except ValueError:
            result = {
                "module": args.module,
                "status": "ERROR",
                "input_hash": None,
                "output_artifacts": [],
                "output_hashes": {},
                "error_type": "INPUT_OUTSIDE_REPOSITORY",
                "error_message": "adapter input must be repository-relative",
            }
        else:
            result = controlled_error(
                module=args.module,
                input_path=input_path,
                input_reference=input_reference,
                run_id=args.run_id,
                project_id=args.project_id,
                node_id=args.node_id,
                parent_node_id=args.parent_node_id,
            )
    (output_dir / "module-result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # The command transport succeeded; `status=ERROR` is the controlled module outcome.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
