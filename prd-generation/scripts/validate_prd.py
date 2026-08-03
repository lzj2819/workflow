"""Portable canonical PRD and consumer-profile validator."""
import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")

from prd_flow.consumer_profiles import CONSUMERS, validate_consumer_profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a canonical prd.json artifact")
    parser.add_argument("artifact", help="Path to prd.json")
    parser.add_argument(
        "--consumer",
        choices=sorted(CONSUMERS),
        default="canonical",
        help="Apply an immediate downstream consumer profile",
    )
    args = parser.parse_args(argv)
    path = Path(args.artifact)
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read canonical PRD: {exc}")
        return 1
    if not isinstance(model, dict):
        print("ERROR: canonical PRD must be a JSON object")
        return 1
    errors = validate_consumer_profile(model, args.consumer)
    if errors:
        print(f"FAIL: {args.consumer} profile rejected {path}")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"PASS: {args.consumer} profile accepted {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
