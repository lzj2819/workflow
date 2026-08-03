"""Aggregate per-batch validate-arch outputs into a single final report.

Uses report_enhancements.py to append component heatmap and architecture
modification mapping to the final report.

Usage:
    python aggregate_batch_results.py \
        E:\\path\\to\\batch-001 \
        E:\\path\\to\\batch-002 \
        --output E:\\path\\to\\validation-report.md
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_subagent_skill import apply_artifact_retention


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing batch artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing batch artifact: {path}")
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def merge_batches(batch_dirs: list[Path], work_dir: Path) -> dict[str, Path]:
    merged_plan_with_val: dict[str, Any] = {
        "feature_path": "",
        "arch_path": "",
        "arch_input_path": "",
        "test_cases": [],
        "component_cards": {},
        "component_prompts": {},
        "plans": [],
    }
    merged_hops: dict[str, list[dict[str, Any]]] = {}
    merged_compat: dict[str, Any] = {"per_scenario": {}, "global_findings": []}
    merged_val_results: list[dict[str, Any]] = []
    merged_call_log: list[dict[str, Any]] = []

    seen_findings: set[str] = set()

    for batch_dir in batch_dirs:
        plan_with_val = load_json(batch_dir / "plan_with_val.json")
        hops = load_json(batch_dir / "hops.json")
        compat = load_json(batch_dir / "compat.json")
        val_results = load_json(batch_dir / "val_results.json")
        call_log = load_jsonl(batch_dir / "subagent_calls.jsonl")

        # Plan-level metadata (all batches share the same feature/arch).
        if not merged_plan_with_val["feature_path"]:
            merged_plan_with_val["feature_path"] = plan_with_val.get("feature_path", "")
            merged_plan_with_val["arch_path"] = plan_with_val.get("arch_path", "")
            merged_plan_with_val["arch_input_path"] = plan_with_val.get("arch_input_path", "")
            merged_plan_with_val["component_cards"] = plan_with_val.get("component_cards", {})
            merged_plan_with_val["component_prompts"] = plan_with_val.get("component_prompts", {})

        merged_plan_with_val["test_cases"].extend(plan_with_val.get("test_cases", []))
        merged_plan_with_val["plans"].extend(plan_with_val.get("plans", []))

        merged_hops.update(hops)

        merged_compat["per_scenario"].update(compat.get("per_scenario", {}))
        for finding in compat.get("global_findings", []):
            key = f"{finding.get('severity')}:{finding.get('kind')}:{finding.get('detail')}"
            if key not in seen_findings:
                seen_findings.add(key)
                merged_compat["global_findings"].append(finding)

        merged_val_results.extend(val_results)
        merged_call_log.extend(call_log)

    work_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "plan_with_val": work_dir / "merged_plan_with_val.json",
        "hops": work_dir / "merged_hops.json",
        "compat": work_dir / "merged_compat.json",
        "val_results": work_dir / "merged_val_results.json",
        "call_log": work_dir / "merged_subagent_calls.jsonl",
        "strict_audit": work_dir / "merged_strict_audit.json",
    }

    paths["plan_with_val"].write_text(
        json.dumps(merged_plan_with_val, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["hops"].write_text(
        json.dumps(merged_hops, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["compat"].write_text(
        json.dumps(merged_compat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["val_results"].write_text(
        json.dumps(merged_val_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths["call_log"].write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in merged_call_log) + "\n",
        encoding="utf-8",
    )

    return paths


def compute_summary(val_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(val_results)
    passed = sum(1 for r in val_results if r.get("result", {}).get("overall") == "PASS")
    failed = sum(1 for r in val_results if r.get("result", {}).get("overall") == "FAIL")
    warnings = sum(1 for r in val_results if r.get("result", {}).get("overall") == "WARNING")
    missing = sum(1 for r in val_results if r.get("result", {}).get("overall") == "MISSING")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "missing": missing,
        "pass_rate": passed / total if total else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate validate-arch batch outputs")
    parser.add_argument("batch_dirs", nargs="+", help="Batch output directories")
    parser.add_argument("--output", "-o", required=True, help="Final validation report path")
    parser.add_argument(
        "--work-dir",
        help="Directory for merged intermediate files (default: <run-dir>/.aggregate-work)",
    )
    parser.add_argument(
        "--run-dir",
        help="Managed .work run root containing all batch directories.",
    )
    parser.add_argument(
        "--artifact-retention",
        choices=("report", "audit", "full"),
        help="PASS-run retention; default is report with --run-dir, otherwise full.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print summary, do not write full report",
    )
    args = parser.parse_args()

    batch_dirs = [Path(d) for d in args.batch_dirs]
    if args.work_dir:
        work_dir = Path(args.work_dir)
    elif args.run_dir:
        work_dir = Path(args.run_dir) / ".aggregate-work"
    else:
        parser.error("--work-dir is required when --run-dir is omitted")
    out_path = Path(args.output)
    retention = args.artifact_retention or ("report" if args.run_dir else "full")
    if retention != "full" and not args.run_dir:
        parser.error("artifact cleanup requires --run-dir")

    print(f"Aggregating {len(batch_dirs)} batch(es) ...")
    paths = merge_batches(batch_dirs, work_dir)

    val_results = json.loads(paths["val_results"].read_text(encoding="utf-8"))

    if not args.summary_only:
        audit_cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "run_subagent_skill.py"),
            "validate-run-artifacts",
            "--prompts",
            str(paths["plan_with_val"]),
            "--hops",
            str(paths["hops"]),
            "--val-results",
            str(paths["val_results"]),
            "--call-log",
            str(paths["call_log"]),
            "--require-call-log",
            "--output",
            str(paths["strict_audit"]),
        ]
        print("Auditing merged strict artifacts ...")
        subprocess.run(audit_cmd, check=True)

        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent / "run_subagent_skill.py"),
            "report",
            "--prompts",
            str(paths["plan_with_val"]),
            "--val-results",
            str(paths["val_results"]),
            "--compat",
            str(paths["compat"]),
            "--hops",
            str(paths["hops"]),
            "--strict",
            "--strict-audit",
            str(paths["strict_audit"]),
            "--artifact-dir",
            str(work_dir),
            "--output",
            str(out_path),
        ]
        if retention == "report":
            cmd.append("--omit-artifact-refs")
        print("Generating final report ...")
        subprocess.run(cmd, check=True)

    summary = compute_summary(val_results)
    print(f"总场景数: {summary['total']}")
    print(f"通过: {summary['passed']}")
    print(f"失败: {summary['failed']}")
    print(f"警告: {summary['warnings']}")
    print(f"缺失: {summary['missing']}")
    print(f"通过率: {summary['pass_rate']:.2%}")
    if not args.summary_only:
        print(f"报告: {out_path}")
        if args.run_dir:
            retention_result = apply_artifact_retention(args.run_dir, retention, "PASS")
            print(f"产物保留: {retention_result}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
