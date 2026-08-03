"""Public Mocktest v2 CLI.

LLM-heavy strict dispatch remains owned by the Codex skill driver.  This CLI
provides deterministic input inspection, workspace initialization, schema
export, and publication without exposing the retired legacy Pipeline.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from mock_framework.canonical_contract import (
    initialize_workspace,
    load_canonical_pair,
    publish_canonical_bundle,
    resolve_testcases_authority,
)


def _inspect(args: argparse.Namespace) -> int:
    try:
        authority, projection = resolve_testcases_authority(args.testcases)
        loaded = load_canonical_pair(
            args.architecture,
            authority,
            feature_projection_path=projection,
        )
        initialize_workspace(
            args.output_dir,
            loaded.normalized_input,
            loaded.extraction_report,
            run_id=args.run_id,
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 5
    print(
        json.dumps(
            {
                "status": loaded.extraction_report["status"],
                "run_dir": str(Path(args.output_dir).resolve()),
                "blocked_testcase_ids": loaded.extraction_report["blocked_testcase_ids"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if loaded.extraction_report["status"] == "PASS" else 2


def _publish(args: argparse.Namespace) -> int:
    try:
        publish_canonical_bundle(args.run_dir, args.output_dir)
        report = json.loads(
            (Path(args.output_dir) / "mocktest_report.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4
    status = report["states"]["overall"]
    print(json.dumps({"overall": status, "output_dir": str(Path(args.output_dir).resolve())}))
    return 0 if status == "PASS" else (2 if status in {"FAIL", "WARNING", "BLOCKED"} else 4)


def _export_schemas(args: argparse.Namespace) -> int:
    source = Path(__file__).resolve().parents[2] / "schemas"
    target = Path(args.output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.schema.json"), key=lambda item: item.name):
        shutil.copyfile(path, target / path.name)
    print(json.dumps({"status": "PASS", "schema_count": len(list(source.glob("*.schema.json")))}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mocktest v2 deterministic contract CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect-input", help="Validate v2 inputs and initialize a run")
    inspect.add_argument("--architecture", required=True)
    inspect.add_argument(
        "--testcases", required=True, help="testcases.json or verified sibling .feature"
    )
    inspect.add_argument("--output-dir", required=True)
    inspect.add_argument("--run-id")
    publish = subparsers.add_parser("publish", help="Publish a retained strict workspace")
    publish.add_argument("--run-dir", required=True)
    publish.add_argument("--output-dir", required=True)
    schemas = subparsers.add_parser("export-schemas", help="Copy the checked-in v2 schema registry")
    schemas.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "inspect-input":
        return _inspect(args)
    if args.command == "publish":
        return _publish(args)
    if args.command == "export-schemas":
        return _export_schemas(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
