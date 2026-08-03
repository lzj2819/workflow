#!/usr/bin/env python
"""CLI for Top-level and Decompose canonical Architecture generation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from architecture_flow.bundle import write_bundle  # noqa: E402
from architecture_flow.canonical import build_canonical_architecture  # noqa: E402
from architecture_flow.consumer_profiles import validate_prd_v3  # noqa: E402


EXIT_OK = 0
EXIT_INPUT = 1
EXIT_QUALITY = 2
EXIT_ENVIRONMENT = 3
EXIT_RUNTIME = 4
EXIT_SCHEMA = 5


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_ref(path: Path, model: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": str(model.get("artifact_id") or path.stem),
        "artifact_type": str(model.get("artifact_type") or path.stem),
        "artifact_schema_version": str(
            model.get("artifact_schema_version") or model.get("schema_version") or "unknown"
        ),
        "path": str(path.resolve()),
        "sha256": _sha256(path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate one canonical Architecture bundle")
    subparsers = parser.add_subparsers(dest="architecture_mode", required=True)
    for name in ("top-level", "decompose"):
        command = subparsers.add_parser(name)
        command.add_argument("--prd", required=True, type=Path, help="approved canonical PRD v3 JSON")
        command.add_argument("--design", required=True, type=Path, help="structured Architecture design draft JSON")
        command.add_argument("--output-dir", required=True, type=Path)
        command.add_argument("--operation", choices=("new", "revise", "migrate"), default="new")
        if name == "decompose":
            command.add_argument("--parent-architecture", required=True, type=Path)
            command.add_argument("--target-node-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        prd = _load_json(args.prd)
        draft = _load_json(args.design)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "errors": [str(exc)]}, ensure_ascii=False))
        return EXIT_INPUT
    prd_errors = validate_prd_v3(prd)
    if prd_errors:
        print(json.dumps({"status": "ERROR", "errors": prd_errors}, ensure_ascii=False, indent=2))
        return EXIT_SCHEMA

    parent = None
    input_artifacts = [_artifact_ref(args.prd, prd)]
    if args.architecture_mode == "decompose":
        try:
            parent = _load_json(args.parent_architecture)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(json.dumps({"status": "ERROR", "errors": [str(exc)]}, ensure_ascii=False))
            return EXIT_INPUT
        input_artifacts.append(_artifact_ref(args.parent_architecture, parent))
    try:
        model = build_canonical_architecture(
            draft,
            prd,
            architecture_mode=args.architecture_mode.replace("-", "_"),
            operation=args.operation,
            parent_architecture=parent,
            target_node_id=getattr(args, "target_node_id", None),
            input_artifacts=input_artifacts,
        )
        schema_path = SCRIPT_DIR.parent / "schemas" / "canonical-architecture.schema.json"
        errors = write_bundle(
            model,
            args.output_dir,
            schema_path=schema_path,
            parent_architecture=parent,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "errors": [str(exc)]}, ensure_ascii=False))
        return EXIT_RUNTIME
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return EXIT_QUALITY
    print(
        json.dumps(
            {
                "status": model["status"],
                "architecture_mode": model["architecture_mode"],
                "artifact_id": model["artifact_id"],
                "output_dir": str(args.output_dir.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return EXIT_OK if model["status"] == "PASS" else EXIT_QUALITY


if __name__ == "__main__":
    raise SystemExit(main())
