#!/usr/bin/env python
"""Validate a canonical Architecture artifact against one consumer profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from architecture_flow.bundle import validate_json_schema  # noqa: E402
from architecture_flow.consumer_profiles import CONSUMERS, validate_consumer_profile  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate canonical Architecture v2")
    parser.add_argument("architecture", type=Path)
    parser.add_argument("--consumer", choices=sorted(CONSUMERS), default="canonical")
    parser.add_argument("--parent-architecture", type=Path)
    args = parser.parse_args(argv)
    try:
        model = json.loads(args.architecture.read_text(encoding="utf-8-sig"))
        parent = (
            json.loads(args.parent_architecture.read_text(encoding="utf-8-sig"))
            if args.parent_architecture
            else None
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    schema = SCRIPT_DIR.parent / "schemas" / "canonical-architecture.schema.json"
    errors = validate_json_schema(model, schema)
    errors.extend(
        validate_consumer_profile(model, args.consumer, parent_architecture=parent)
    )
    errors = list(dict.fromkeys(errors))
    print(
        json.dumps(
            {"status": "PASS" if not errors else "FAIL", "consumer": args.consumer, "errors": errors},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
