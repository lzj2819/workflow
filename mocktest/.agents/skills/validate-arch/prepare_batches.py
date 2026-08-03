"""Prepare batch definitions for multi-session true-subagent validation.

Reads a validate-arch plan.json and emits batches.json. Optionally writes a
sliced plan.json into each batch directory so batch workers can skip prepare:

    {
      "feature_path": "...",
      "arch_path": "...",
      "batches": [
        {
          "name": "batch-001",
          "scenario_ids": ["SCENARIO-001", "SCENARIO-002"],
          "plan_path": "out/batch-001/plan.json"
        },
        ...
      ]
    }

Partition strategies:
  --by-tag         : one batch per unique @REQ-XXX tag (default)
  --batch-size N   : fixed N scenarios per batch
"""

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def partition_by_tag(test_cases: list[dict]) -> list[tuple[str, list[str]]]:
    batches: dict[str, list[str]] = {}
    for tc in test_cases:
        tags = tc.get("tags", []) or []
        req_tags = [t for t in tags if t.startswith("@REQ-")]
        key = req_tags[0] if req_tags else "untagged"
        batches.setdefault(key, []).append(tc["test_case_id"])
    return [(name, ids) for name, ids in batches.items()]


def partition_by_size(test_cases: list[dict], size: int) -> list[tuple[str, list[str]]]:
    ids = [tc["test_case_id"] for tc in test_cases]
    result: list[tuple[str, list[str]]] = []
    for i in range(0, len(ids), size):
        result.append((f"batch-{i // size + 1:03d}", ids[i : i + size]))
    return result


def slice_plan(plan: dict, scenario_ids: list[str]) -> dict:
    allowed = set(scenario_ids)
    sliced = dict(plan)
    sliced["test_cases"] = [
        tc for tc in plan.get("test_cases", []) if tc.get("test_case_id") in allowed
    ]
    sliced["plans"] = [
        item for item in plan.get("plans", []) if item.get("test_case_id") in allowed
    ]
    return sliced


def main() -> int:
    parser = argparse.ArgumentParser(description="Partition validate-arch scenarios into batches")
    parser.add_argument("--plan", "-p", required=True, help="Path to plan.json")
    parser.add_argument("--output", "-o", required=True, help="Output batches.json path")
    parser.add_argument(
        "--write-plans-to",
        help="Optional batch root directory; writes <root>/<batch-name>/plan.json slices",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--by-tag", action="store_true", help="Partition by @REQ-XXX tag (default)")
    group.add_argument("--batch-size", type=int, help="Fixed batch size")
    args = parser.parse_args()

    plan = load_json(Path(args.plan))
    test_cases = plan.get("test_cases", [])

    if args.batch_size:
        batches = partition_by_size(test_cases, args.batch_size)
    else:
        batches = partition_by_tag(test_cases)

    batch_entries: list[dict] = []
    for name, ids in batches:
        entry = {"name": name, "scenario_ids": ids}
        if args.write_plans_to:
            batch_dir = Path(args.write_plans_to) / name
            batch_dir.mkdir(parents=True, exist_ok=True)
            plan_path = batch_dir / "plan.json"
            plan_path.write_text(
                json.dumps(slice_plan(plan, ids), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            entry["plan_path"] = str(plan_path)
        batch_entries.append(entry)

    out = {
        "feature_path": plan.get("feature_path", ""),
        "arch_path": plan.get("arch_path", ""),
        "batches": batch_entries,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(batches)} batch(es): {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
