"""Deterministic external adapter used by root-workflow CLI fixtures."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--scenario", default="single")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / f"{args.module}.json"
    prd_id = f"prd:{args.node_id}"
    payload = {"artifact_schema_version": "fixture/v1", "artifact_id": f"{args.module}:{args.node_id}",
               "run_id": "fixture-run", "project_id": "fixture", "node_id": args.node_id, "status": "PASS"}
    if args.module == "prd":
        payload.update({"artifact_schema_version": "prd/v3", "artifact_id": prd_id})
    elif args.module == "architecture":
        payload.update({"artifact_schema_version": "architecture/v2", "source_prd_id": prd_id,
                        "ready_for_downstream": True, "payload": {"contracts": [{"id": "fixture.api"}]}})
    elif args.module == "gherkin":
        payload.update({"artifact_schema_version": "testcases/v2", "source_prd": {"artifact_id": prd_id},
                        "blocked_items": [], "testcases": [{"tc_id": "TC-1"}]})
    elif args.module == "mocktest":
        payload.update({"artifact_schema_version": "mocktest-report/v2", "states": {"overall": "PASS"},
                        "coverage": {"total": 1, "evaluated": 1}, "findings": []})
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    artifacts = [str(artifact)]
    if args.module == "mocktest":
        evidence = output / "leaf_gate_evidence.json"
        evidence.write_text(json.dumps({"artifact_schema_version": "mocktest-leaf-evidence/v2", "status": "PASS"}), encoding="utf-8")
        artifacts.append(str(evidence))
    result = {"status": "PASS", "output_artifacts": artifacts, "token_usage": 1, "estimated_cost": 0.0}
    if args.scenario == "branch_failure" and args.module == "architecture":
        result = {"status": "ERROR", "output_artifacts": [], "error_type": "FIXTURE", "error_message": "injected branch failure"}
    elif args.scenario == "mock_defect" and args.module == "mocktest":
        result = {"status": "FAIL", "output_artifacts": [], "error_type": "DEFECT", "error_message": "injected architecture defect", "defect_count": 1}
    elif args.module == "architecture":
        result.update({"interfaces": ["fixture.api"], "blocking_issues": []})
    elif args.module == "leaf_gate":
        if args.scenario in {"recursive", "contract_conflict"} and args.node_id == "root":
            result.update({"decision": "CONTINUE_LAYERING", "admission_state": "ADMITTED", "bundle_verified": True,
                           "proposed_children": [{"child_node_id": "child-a", "parent_node_id": "root", "requirement_ids": ["R1"], "requirement": {"text": "child"}}]})
        else:
            result.update({"decision": "STOP_LAYERING", "admission_state": "ADMITTED", "bundle_verified": True})
    elif args.module == "coding":
        result["changed_paths"] = [f"nodes/{args.node_id}/implementation.py"]
    elif args.module == "backfill":
        conflict = args.scenario == "contract_conflict"
        difference = [{"type": "PARAMETER_TYPE_CHANGED", "interface_id": "fixture.api", "path": "parameters.id.type",
                       "breaking": True, "parent": "string", "child": "integer"}] if conflict else []
        result["contract_diff"] = {"schema_version": "1.0", "status": "FAIL" if conflict else "PASS",
                                   "outcome": "CONTRACT_CHANGE_REQUIRED" if conflict else "MATCH",
                                   "parent_contract_id": "parent", "child_contract_id": "child",
                                   "parent_hash": "a" * 64, "child_hash": "b" * 64,
                                   "breaking_count": int(conflict), "compatible_count": 0,
                                   "differences": difference, "validation_errors": []}
        result["checks"] = {name: ("FAIL" if conflict and name == "contract" else "PASS") for name in
                            ("contract", "provider_compatibility", "consumer_compatibility", "parent_integration", "feature_smoke", "regression")}
    (output / "module-result.json").write_text(json.dumps(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
