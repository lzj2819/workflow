"""Validate the frozen Day 2 production module configuration.

This command does not run modules or create experiment results.  It only
checks that the declared production command surface is complete and portable.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


MODULES = {"prd", "architecture", "gherkin", "mocktest", "leaf_gate", "coding", "backfill", "integration"}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def validate_config(config: dict[str, object]) -> list[str]:
    errors: list[str] = []
    commands = config.get("commands")
    if not isinstance(commands, dict) or set(commands) != MODULES:
        return ["commands must contain exactly the eight production modules"]
    for module, command in commands.items():
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            errors.append(f"{module}: command must be a non-empty string list")
            continue
        joined = " ".join(command).lower()
        if "tests/fixtures" in joined or "fixture" in joined:
            errors.append(f"{module}: production command must not reference a fixture")
        if any(Path(part).is_absolute() or WINDOWS_ABSOLUTE.match(part) for part in command):
            errors.append(f"{module}: production command must not contain an absolute path")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Day 2 production experiment configuration")
    parser.add_argument("--config", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.validate_only:
        parser.error("Day 2 supports --validate-only only; it does not execute experiments")
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 3
    errors = validate_config(config)
    if errors:
        print("ERROR: " + "; ".join(errors))
        return 3
    print("PASS: Day 2 production configuration is complete, relative, and fixture-free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
