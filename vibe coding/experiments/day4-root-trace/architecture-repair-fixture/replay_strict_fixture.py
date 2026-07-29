"""Deterministically replay the Day 4 Architecture repair fixture.

This is isolated repair-loop evidence.  It drives the canonical strict driver
with fixed component and validator responses; it never calls a model and never
writes to the Day 4 a/b/c/d run directories.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FIXTURE_DIR.parents[2]))

from vibecode.executors.strict_executor import execute_strict


def _runner(*, prompt: str, workspace: Path, model: str, timeout_seconds: int) -> dict[str, str]:
    """Write a valid fixed raw response for the strict driver's requested file."""
    del model, timeout_seconds
    match = re.search(r"Write exactly one JSON response to `([^`]+)`", prompt)
    if match is None:
        raise RuntimeError("strict executor did not declare a raw response path")
    target = workspace / match.group(1)
    if "Validator Agent" in prompt:
        payload = {
            dimension: {"status": "PASS", "detail": "deterministic fixture evidence is complete"}
            for dimension in ("structure", "flow", "state", "contract", "performance")
        }
        payload["overall"] = "PASS"
    else:
        payload = {
            "output_message": {
                "status_code": 200,
                "status": "ok",
                "node_id": "root",
                "requirement_ids": ["REQ-D4-HEALTH", "REQ-D4-TRACE"],
                "request_id": None,
                "body": {"status": "ok"},
            },
            "status": "PASS",
            "latency_ms": 0,
            "side_effects": [{"type": "read", "target": "GET /health", "data": {}}],
            "state_change": None,
            "self_check": {
                "consumed_input_ok": True,
                "produced_fields": [],
                "missing_required_inputs": [],
                "undefined_next_call": None,
                "then_verification": {
                    "assertion": "all frozen health assertions",
                    "satisfied": True,
                    "evidence": "fixed HTTP 200 health response contains every frozen field",
                },
            },
            "next_hop": None,
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"status": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to reuse fixture output: {args.output_dir}")
    result = execute_strict(
        feature_path=FIXTURE_DIR / "testcases.feature",
        architecture_path=FIXTURE_DIR / "architecture.repaired.md",
        output_dir=args.output_dir,
        python=sys.executable,
        driver=args.driver,
        model="deterministic-fixture",
        run_id="day4-architecture-repair-fixture-20260729-replay-a",
        project_id="verilayer-day4",
        node_id="root",
        parent_node_id=None,
        runner=_runner,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
