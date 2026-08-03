"""Main-session strict validate-arch driver.

This is the interactive execution strategy for the canonical Mocktest v2
input/result contract. The parent session prepares one normalized plan,
spawns each component/validator subagent directly, and publishes through the
same canonical bundle writer used by the one-shot runner. Migration-private
filenames remain internal evidence only.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import os
import subprocess
import sys
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RUNNER = SCRIPT_DIR / "run_subagent_skill.py"

sys.path.insert(0, str(SCRIPT_DIR))
from run_subagent_skill import (  # noqa: E402
    _delivery_report_path,
    _extract_json_from_response,
    _normalize_next_hop_contract,
    _normalize_produced_fields,
    _resolve_next_hop,
    _resolve_input_arguments,
    apply_artifact_retention,
    cleanup_empty_run_shells,
    plan_item_semantic_errors,
    resolve_contract_binding,
    strict_semantic_errors,
    validator_payload_errors,
)
from mock_framework.canonical_contract import publish_canonical_bundle  # noqa: E402


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def run_lock(output_dir: Path, timeout_seconds: float = 60.0):
    """Serialize mutations to one strict-run workspace.

    Subagents may finish simultaneously, while hops/state/call logs are shared
    JSON artifacts.  An atomic lock prevents lost updates and torn JSONL rows;
    an abandoned lock is recoverable after a bounded stale interval.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / ".driver.lock"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            break
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > timeout_seconds
            except FileNotFoundError:
                continue
            if stale:
                lock_path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError(f"timed out waiting for strict run lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def serialized_run(fn: Any) -> Any:
    @functools.wraps(fn)
    def wrapped(args: argparse.Namespace) -> Any:
        with run_lock(Path(args.output_dir)):
            return fn(args)

    return wrapped


def artifact_attempt_key(kind: str, test_case_id: str, hop_index: int | None = None) -> str:
    suffix = f":{hop_index}" if hop_index is not None else ""
    return f"{kind}:{test_case_id}{suffix}"


def recover_artifact_attempt(out: Path, key: str) -> None:
    """Record that a later successful attempt supersedes an earlier failure."""
    append_jsonl(
        out / "artifact_errors.jsonl",
        {"event": "artifact_recovered", "attempt_key": key},
    )


def run_py(args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(RUNNER), *args]
    proc = subprocess.run(
        cmd,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT,
        env=env,
    )
    if proc.returncode != 0:
        sys.stdout.buffer.write(proc.stdout)
        sys.stderr.buffer.write(proc.stderr)
        raise RuntimeError(f"command failed: {' '.join(cmd)}")
    return proc


def first_step_text(tc_summary: dict[str, Any], keyword: str) -> str:
    for step in tc_summary.get("gherkin", {}).get("steps", []):
        if str(step.get("keyword", "")).lower() == keyword.lower():
            return str(step.get("text", ""))
    return ""


def interaction_sequence(plan_item: dict[str, Any], tc_summary: dict[str, Any]) -> list[dict[str, Any]]:
    sequence = plan_item.get("interaction_sequence")
    if isinstance(sequence, list) and sequence:
        return [item for item in sequence if isinstance(item, dict)]
    return [
        {
            "interaction_index": 0,
            "given": [first_step_text(tc_summary, "Given")],
            "when": first_step_text(tc_summary, "When"),
            "then_assertions": plan_item.get("then_assertions", []),
            "entry_component": plan_item.get("entry_component", ""),
            "entry_action": plan_item.get("entry_action", "handle"),
            "entry_contract_id": plan_item.get("entry_contract_id", ""),
            "trigger_message": plan_item.get("trigger_message") or {},
        }
    ]


def initial_message(
    plan_item: dict[str, Any], tc_summary: dict[str, Any], interaction_index: int = 0
) -> dict[str, Any]:
    interaction = interaction_sequence(plan_item, tc_summary)[interaction_index]
    return {
        "event": interaction.get("entry_action", plan_item.get("entry_action", "handle")),
        "given": interaction.get("given", [first_step_text(tc_summary, "Given")]),
        "when": interaction.get("when", first_step_text(tc_summary, "When")),
        "original_trigger": interaction.get("trigger_message") or plan_item.get("trigger_message") or {},
        "interaction_index": interaction_index,
        "interaction_count": len(interaction_sequence(plan_item, tc_summary)),
    }


def synthetic_hop(
    component: str,
    action: str,
    msg: dict[str, Any],
    contract_id: str = "",
    interaction_index: int = 0,
) -> dict[str, Any]:
    return {
        "hop_index": 0,
        "component": component,
        "action": "setup_context",
        "phase": "given",
        "input_message": msg,
        "output_message": {
            "given_context": msg.get("given", ""),
            "when": msg.get("when", ""),
            "event": msg.get("event", action),
        },
        "status": "PASS",
        "latency_ms": 0,
        "side_effects": [],
        "state_change": None,
        "self_check": {
            "consumed_input_ok": True,
            "produced_fields": ["given_context", "when", "event"],
            "missing_required_inputs": [],
            "undefined_next_call": None,
            "then_verification": None,
            "synthetic": True,
        },
        "next_hop": {
            "component": component,
            "action": action,
            "contract_id": contract_id,
            "reason": "Given context established",
        },
        "synthetic": True,
        "interaction_index": interaction_index,
    }


def relabel(hops: list[dict[str, Any]]) -> None:
    for hop in hops:
        if hop.get("synthetic"):
            hop["phase"] = "given"
        else:
            hop["phase"] = "when"


def update_shared_state(shared_state: dict[str, Any], hop: dict[str, Any]) -> None:
    sc = hop.get("state_change")
    if isinstance(sc, dict) and sc.get("entity"):
        shared_state[str(sc["entity"])] = sc.get("to_state")
    for effect in hop.get("side_effects") or []:
        if isinstance(effect, dict) and effect.get("type") == "append":
            target = str(effect.get("target", "append_log"))
            existing = shared_state.get(target)
            if not isinstance(existing, list):
                shared_state[target] = [] if existing is None else [existing]
            shared_state[target].append(effect.get("data"))


def build_shared_state(hops: list[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for hop in hops:
        update_shared_state(state, hop)
    return state


def plan_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return list(plan.get("plans", []))


def scenario_dir(out: Path, tc_id: str) -> Path:
    return out / "scenarios" / tc_id


def reuse_validated_scenarios(out: Path, source: Path) -> list[str]:
    """Copy only exact-key scenarios from a previously strict-PASS run."""
    if not source.exists() or source.resolve() == out.resolve():
        return []
    audit_path = source / "strict_audit.json"
    audit = read_json(audit_path, {})
    if audit.get("status") != "PASS":
        return []
    old_plan_path = source / "plan_with_val.json"
    if not old_plan_path.exists():
        old_plan_path = source / "plan.json"
    old_plan = read_json(old_plan_path, {})
    new_plan = read_json(out / "plan.json", {})
    if old_plan.get("cache_schema_version") != "validate-arch-cache-v1":
        return []
    old_by_key = {
        item.get("cache_key"): item for item in old_plan.get("plans", []) if item.get("cache_key")
    }
    old_hops = read_json(source / "hops.json", {})
    old_vals = {
        item.get("test_case_id"): item for item in read_json(source / "val_results.json", [])
    }
    reused_hops: dict[str, Any] = {}
    reused_vals: list[dict[str, Any]] = []
    hits: list[str] = []
    provenance: list[dict[str, Any]] = []
    source_audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    for item in new_plan.get("plans", []):
        cache_key = item.get("cache_key")
        old_item = old_by_key.get(cache_key)
        if not old_item:
            continue
        old_tc_id = old_item.get("test_case_id")
        tc_id = item.get("test_case_id")
        hops = old_hops.get(old_tc_id)
        val = old_vals.get(old_tc_id)
        if not isinstance(hops, list) or not hops or not isinstance(val, dict):
            continue
        if validator_payload_errors(val.get("result"), require_dimensions=True):
            continue
        reused_hops[tc_id] = hops
        reused_vals.append({"test_case_id": tc_id, "result": val["result"]})
        item["cache_provenance"] = {
            "cache_hit": True,
            "source_run": str(source.resolve()),
            "source_test_case_id": old_tc_id,
            "cache_key": cache_key,
            "source_strict_audit_sha256": source_audit_hash,
        }
        hits.append(tc_id)
        provenance.append(item["cache_provenance"] | {"test_case_id": tc_id})
        for hop_index, hop in enumerate(hops):
            if hop.get("synthetic") or hop.get("action") == "setup_context":
                continue
            append_jsonl(
                out / "subagent_calls.jsonl",
                {
                    "role": "component",
                    "test_case_id": tc_id,
                    "hop_index": hop_index,
                    "component": hop.get("component", ""),
                    "action": hop.get("action", ""),
                    "cache_hit": True,
                    "cache_key": cache_key,
                    "source_run": str(source.resolve()),
                },
            )
        append_jsonl(
            out / "subagent_calls.jsonl",
            {
                "role": "validator",
                "test_case_id": tc_id,
                "cache_hit": True,
                "cache_key": cache_key,
                "source_run": str(source.resolve()),
            },
        )
    if hits:
        write_json(out / "plan.json", new_plan)
        write_json(out / "hops.json", reused_hops)
        write_json(out / "val_results.json", reused_vals)
    write_json(
        out / "cache_provenance.json",
        {
            "schema_version": "validate-arch-cache-v1",
            "source_run": str(source.resolve()),
            "hits": provenance,
        },
    )
    return hits


def reuse_ready_equivalent_hops(
    out: Path,
    plan: dict[str, Any],
    hops_by_tc: dict[str, list[dict[str, Any]]],
    state: dict[str, Any],
) -> None:
    done = set(state.get("component_done", []))
    changed = False
    for item in plan_items(plan):
        tc_id = item["test_case_id"]
        equivalence = item.get("equivalence") or {}
        representative = equivalence.get("representative")
        if not representative or representative == tc_id or tc_id in done:
            continue
        if representative not in done or representative not in hops_by_tc:
            continue
        hops = json.loads(json.dumps(hops_by_tc[representative], ensure_ascii=False))
        hops_by_tc[tc_id] = hops
        done.add(tc_id)
        changed = True
        for hop_index, hop in enumerate(hops):
            if hop.get("synthetic") or hop.get("action") == "setup_context":
                continue
            append_jsonl(
                out / "subagent_calls.jsonl",
                {
                    "role": "component",
                    "test_case_id": tc_id,
                    "hop_index": hop_index,
                    "component": hop.get("component", ""),
                    "action": hop.get("action", ""),
                    "equivalence_hit": True,
                    "equivalence_key": equivalence.get("key"),
                    "representative": representative,
                },
            )
    if changed:
        state["component_done"] = sorted(done)
        write_json(out / "hops.json", hops_by_tc)
        write_json(out / "driver_state.json", state)


def reuse_ready_equivalent_validators(
    out: Path, plan: dict[str, Any], state: dict[str, Any]
) -> None:
    vals = read_json(out / "val_results.json", [])
    val_by_id = {item.get("test_case_id"): item for item in vals}
    done = set(state.get("validator_done", []))
    changed = False
    for item in plan_items(plan):
        tc_id = item["test_case_id"]
        equivalence = item.get("equivalence") or {}
        representative = equivalence.get("representative")
        if not representative or representative == tc_id or tc_id in done:
            continue
        representative_val = val_by_id.get(representative)
        if not representative_val:
            continue
        copied = {
            "test_case_id": tc_id,
            "result": json.loads(json.dumps(representative_val["result"], ensure_ascii=False)),
        }
        vals.append(copied)
        val_by_id[tc_id] = copied
        done.add(tc_id)
        changed = True
        append_jsonl(
            out / "subagent_calls.jsonl",
            {
                "role": "validator",
                "test_case_id": tc_id,
                "equivalence_hit": True,
                "equivalence_key": equivalence.get("key"),
                "representative": representative,
            },
        )
    if changed:
        state["validator_done"] = sorted(done)
        write_json(out / "val_results.json", vals)
        write_json(out / "driver_state.json", state)


@serialized_run
def init(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    try:
        feature_path, arch_path, _, _ = _resolve_input_arguments(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(5 if "schema" in str(exc).lower() or "match" in str(exc).lower() else 3)
    report_path = _delivery_report_path(feature_path, out, getattr(args, "report_dir", None))
    retention = args.artifact_retention or (
        "report" if getattr(args, "report_dir", None) else "full"
    )
    if retention == "report" and report_path.resolve().is_relative_to(out.resolve()):
        raise SystemExit(
            "artifact-retention=report requires --report-dir outside the run workspace"
        )
    if getattr(args, "report_dir", None):
        cleanup_empty_run_shells(args.report_dir)
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["prepare", "--slim-prompts", "--output", str(out / "plan.json")]
    if getattr(args, "input_manifest", None):
        cmd.extend(["--input-manifest", args.input_manifest])
    else:
        cmd.extend(["--feature", feature_path, "--arch", arch_path])
    if args.scenario_ids:
        cmd.extend(["--scenario-ids", args.scenario_ids])
    if args.strict_equivalence:
        cmd.append("--strict-equivalence")
    if getattr(args, "identity_manifest", None):
        cmd.extend(["--identity-manifest", args.identity_manifest])
    run_py(cmd)
    if getattr(args, "ground_truth", None):
        shutil.copyfile(args.ground_truth, out / "ground_truth.json")
    if not (out / "hops.json").exists():
        write_json(out / "hops.json", {})
    if not (out / "subagent_calls.jsonl").exists():
        (out / "subagent_calls.jsonl").write_text("", encoding="utf-8")
    cache_hits = reuse_validated_scenarios(out, Path(args.reuse_from)) if args.reuse_from else []
    state = {
        "phase": "components",
        "component_done": sorted(cache_hits),
        "validator_done": sorted(cache_hits),
        "cache_hits": sorted(cache_hits),
        "max_hops": args.max_hops,
        "report_path": str(report_path),
        "artifact_retention": retention,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "protocol_metadata": {
            key: getattr(args, key, "")
            for key in (
                "run_id",
                "project_id",
                "node_id",
                "parent_node_id",
                "branch_id",
                "architecture_artifact_id",
                "testcase_artifact_id",
                "source_prd_id",
                "random_seed",
                "simulator_model",
                "validator_model",
            )
            if getattr(args, key, None) not in (None, "")
        },
    }
    write_json(out / "driver_state.json", state)
    print(json.dumps({"status": "initialized", "output_dir": str(out)}, ensure_ascii=False))


@serialized_run
def next_components(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    plan = read_json(out / "plan.json", {})
    hops_by_tc = read_json(out / "hops.json", {})
    state = read_json(out / "driver_state.json", {})
    reuse_ready_equivalent_hops(out, plan, hops_by_tc, state)
    hops_by_tc = read_json(out / "hops.json", {})
    state = read_json(out / "driver_state.json", state)
    done = set(state.get("component_done", []))
    pending: list[dict[str, Any]] = []
    limit = int(args.limit)
    component_names = set(plan.get("component_cards", {}).keys()) or set(
        plan.get("component_prompts", {}).keys()
    )
    tc_by_id = {tc["test_case_id"]: tc for tc in plan.get("test_cases", [])}

    for item in plan_items(plan):
        if len(pending) >= limit:
            break
        tc_id = item["test_case_id"]
        if tc_id in done:
            continue
        equivalence = item.get("equivalence") or {}
        if equivalence.get("representative") not in (None, "", tc_id):
            # The representative is deliberately executed first; this row is
            # revisited and copied once its proof-equivalent evidence exists.
            continue
        semantic_errors = plan_item_semantic_errors(item, tc_by_id.get(tc_id))
        if semantic_errors:
            blocked = state.setdefault("semantic_blocked", {})
            blocked[tc_id] = semantic_errors
            done.add(tc_id)
            state["component_done"] = sorted(done)
            write_json(out / "driver_state.json", state)
            continue
        interactions = interaction_sequence(item, tc_by_id[tc_id])
        hops = list(hops_by_tc.get(tc_id, []))
        if not hops:
            msg = initial_message(item, tc_by_id[tc_id])
            first_interaction = interactions[0]
            hops = [
                synthetic_hop(
                    first_interaction.get("entry_component", item["entry_component"]),
                    first_interaction.get("entry_action", item.get("entry_action", "handle")),
                    msg,
                    first_interaction.get("entry_contract_id", item.get("entry_contract_id", "")),
                    0,
                )
            ]
            hops_by_tc[tc_id] = hops
            write_json(out / "hops.json", hops_by_tc)

        last = hops[-1]
        raw_next_hop = last.get("next_hop")
        next_hop = _resolve_next_hop(raw_next_hop, component_names)
        non_synthetic_count = len([h for h in hops if not h.get("synthetic")])
        if non_synthetic_count >= int(state.get("max_hops", 20)):
            last["truncated_at_max_hops"] = True
            last["next_hop"] = None
            relabel(hops)
            hops_by_tc[tc_id] = hops
            write_json(out / "hops.json", hops_by_tc)
            done.add(tc_id)
            state["component_done"] = sorted(done)
            write_json(out / "driver_state.json", state)
            continue
        if not next_hop and isinstance(raw_next_hop, dict) and raw_next_hop:
            # Never erase a claimed successor just because it could not be
            # resolved.  The semantic gate must report the architecture gap.
            last["unresolved_next_hop"] = raw_next_hop
            last["next_hop"] = None
        if not next_hop:
            interaction_index = int(last.get("interaction_index", 0))
            if last.get("unresolved_next_hop"):
                relabel(hops)
                hops_by_tc[tc_id] = hops
                write_json(out / "hops.json", hops_by_tc)
                done.add(tc_id)
                state["component_done"] = sorted(done)
                write_json(out / "driver_state.json", state)
                continue
            next_interaction_index = interaction_index + 1
            if next_interaction_index >= len(interactions):
                relabel(hops)
                hops_by_tc[tc_id] = hops
                write_json(out / "hops.json", hops_by_tc)
                done.add(tc_id)
                state["component_done"] = sorted(done)
                write_json(out / "driver_state.json", state)
                continue
            interaction = interactions[next_interaction_index]
            msg = initial_message(item, tc_by_id[tc_id], next_interaction_index)
            last = synthetic_hop(
                interaction.get("entry_component", ""),
                interaction.get("entry_action", "handle"),
                msg,
                interaction.get("entry_contract_id", ""),
                next_interaction_index,
            )
            hops.append(last)
            hops_by_tc[tc_id] = hops
            write_json(out / "hops.json", hops_by_tc)
            next_hop = _resolve_next_hop(last.get("next_hop"), component_names)
            if not next_hop:
                last["unresolved_next_hop"] = last.get("next_hop")
                last["next_hop"] = None
                relabel(hops)
                hops_by_tc[tc_id] = hops
                write_json(out / "hops.json", hops_by_tc)
                done.add(tc_id)
                state["component_done"] = sorted(done)
                write_json(out / "driver_state.json", state)
                continue

        hop_index = len(hops)
        comp = next_hop["component"]
        action = next_hop.get("action", "handle")
        input_msg = last.get("output_message", {})
        if last.get("synthetic"):
            input_msg = last.get("input_message", {})
        sd = scenario_dir(out, tc_id)
        sd.mkdir(parents=True, exist_ok=True)
        input_path = sd / f"hop_input_{hop_index:03d}.json"
        request_path = sd / f"hop_request_{hop_index:03d}.json"
        prompt_path = sd / f"hop_prompt_{hop_index:03d}.txt"
        raw_path = sd / f"raw_hop_response_{hop_index:03d}.txt"
        result_path = sd / f"hop_result_{hop_index:03d}.json"
        write_json(input_path, input_msg)
        request = {
            "plan_path": str(out / "plan.json"),
            "component": comp,
            "action": action,
            "contract_id": next_hop.get("contract_id", ""),
            "input_message": input_msg,
            "shared_state": build_shared_state(hops),
            "phase": "when",
            "then_assertions": interactions[int(last.get("interaction_index", 0))].get(
                "then_assertions", []
            ),
            "hop_index": hop_index,
            "interaction_index": int(last.get("interaction_index", 0)),
        }
        write_json(request_path, request)
        proc = run_py(["simulate-step-prompt"], stdin=request_path.read_bytes())
        prompt_path.write_bytes(proc.stdout)
        pending_item = {
            "kind": "component",
            "test_case_id": tc_id,
            "hop_index": hop_index,
            "component": comp,
            "action": action,
            "prompt_file": str(prompt_path),
            "raw_response_file": str(raw_path),
            "result_file": str(result_path),
            "input_file": str(input_path),
            "request_file": str(request_path),
            "interaction_index": int(last.get("interaction_index", 0)),
        }
        pending_file = sd / f"pending_component_{hop_index:03d}.json"
        pending_item["pending_file"] = str(pending_file)
        write_json(pending_file, pending_item)
        pending.append(pending_item)
    write_json(out / "pending_components.json", pending)
    print(
        json.dumps(
            {"pending": pending, "remaining": len(plan_items(plan)) - len(done)},
            ensure_ascii=False,
            indent=2,
        )
    )


@serialized_run
def consume_component(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    pending = read_json(Path(args.pending_file), {})
    raw_path = Path(pending["raw_response_file"])
    raw_text = raw_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    parsed = _extract_json_from_response(raw_text)
    if "raw" in parsed:
        error = {
            "artifact_error": "invalid_json_response",
            "parse_error": parsed.get("parse_error", ""),
            "test_case_id": pending["test_case_id"],
            "hop_index": int(pending["hop_index"]),
            "component": pending["component"],
            "action": pending["action"],
            "raw_response_file": str(raw_path),
            "attempt_key": artifact_attempt_key(
                "component", pending["test_case_id"], int(pending["hop_index"])
            ),
        }
        error_path = Path(pending["result_file"]).with_suffix(".error.json")
        write_json(error_path, error)
        append_jsonl(out / "artifact_errors.jsonl", error)
        state = read_json(out / "driver_state.json", {})
        needs = set(state.get("needs_reconsume", []))
        needs.add(pending["test_case_id"])
        state["needs_reconsume"] = sorted(needs)
        done = set(state.get("component_done", []))
        done.discard(pending["test_case_id"])
        state["component_done"] = sorted(done)
        write_json(out / "driver_state.json", state)
        append_jsonl(
            out / "subagent_calls.jsonl",
            {
                "role": "component",
                "test_case_id": pending["test_case_id"],
                "agent_id": args.agent_id,
                "hop_index": int(pending["hop_index"]),
                "component": pending["component"],
                "action": pending["action"],
                "prompt_file": pending["prompt_file"],
                "raw_response_file": pending["raw_response_file"],
                "artifact_error_file": str(error_path),
                "parse_status": "invalid_json_response",
            },
        )
        print(json.dumps({"artifact_error": error}, ensure_ascii=False))
        return
    plan = read_json(out / "plan.json", {})
    valid_components = set(plan.get("component_cards", {}).keys()) or set(
        plan.get("component_prompts", {}).keys()
    )
    hop = dict(parsed)
    hop["hop_index"] = int(pending["hop_index"])
    hop["component"] = pending["component"]
    hop["action"] = pending["action"]
    hop["input_message"] = read_json(Path(pending["input_file"]), {})
    request = read_json(Path(pending["request_file"]), {})
    card = plan.get("component_cards", {}).get(pending["component"])
    hop["contract_binding"] = resolve_contract_binding(
        card,
        action=pending["action"],
        contract_id=request.get("contract_id", ""),
        input_message=hop["input_message"],
    )
    hop.setdefault("output_message", {})
    hop.setdefault("status", "PASS")
    hop.setdefault("latency_ms", 0)
    hop.setdefault("side_effects", [])
    hop.setdefault("state_change", None)
    hop.setdefault("self_check", {})
    hop["self_check"].setdefault("consumed_input_ok", True)
    hop["self_check"].setdefault("produced_fields", [])
    hop["self_check"].setdefault("missing_required_inputs", [])
    hop["self_check"].setdefault("undefined_next_call", None)
    hop["self_check"].setdefault("then_verification", None)
    _normalize_produced_fields(hop)
    raw_next_hop = hop.get("next_hop")
    hop["next_hop"] = _normalize_next_hop_contract(
        _resolve_next_hop(raw_next_hop, valid_components),
        card,
    )
    if isinstance(raw_next_hop, dict) and raw_next_hop and not hop["next_hop"]:
        hop["unresolved_next_hop"] = raw_next_hop
    hop["phase"] = "when"
    hop["interaction_index"] = int(request.get("interaction_index", 0))
    write_json(Path(pending["result_file"]), hop)

    hops_by_tc = read_json(out / "hops.json", {})
    hops = list(hops_by_tc.get(pending["test_case_id"], []))
    # Replace if re-consuming the same hop, otherwise append.
    existing = [i for i, h in enumerate(hops) if h.get("hop_index") == hop["hop_index"]]
    if existing:
        hops[existing[0]] = hop
    else:
        hops.append(hop)
    state = read_json(out / "driver_state.json", {})
    done = set(state.get("component_done", []))
    needs = set(state.get("needs_reconsume", []))
    needs.discard(pending["test_case_id"])
    state["needs_reconsume"] = sorted(needs)
    # Terminal status is decided by next-components, which may need to start
    # another explicit Gherkin interaction after this chain completes.
    done.discard(pending["test_case_id"])
    state["component_done"] = sorted(done)
    write_json(out / "driver_state.json", state)
    hops_by_tc[pending["test_case_id"]] = hops
    write_json(out / "hops.json", hops_by_tc)
    recover_artifact_attempt(
        out,
        artifact_attempt_key("component", pending["test_case_id"], int(pending["hop_index"])),
    )
    append_jsonl(
        out / "subagent_calls.jsonl",
        {
            "role": "component",
            "test_case_id": pending["test_case_id"],
            "agent_id": args.agent_id,
            "hop_index": int(pending["hop_index"]),
            "component": pending["component"],
            "action": pending["action"],
            "prompt_file": pending["prompt_file"],
            "raw_response_file": pending["raw_response_file"],
            "normalized_result_file": pending["result_file"],
        },
    )
    print(
        json.dumps(
            {
                "consumed": pending["test_case_id"],
                "hop": hop["hop_index"],
                "status": hop.get("status"),
            },
            ensure_ascii=False,
        )
    )


@serialized_run
def prepare_validators(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    state = read_json(out / "driver_state.json", {})
    needs_reconsume = state.get("needs_reconsume", [])
    if needs_reconsume:
        raise RuntimeError(
            f"cannot prepare validators; scenarios need reconsume: {needs_reconsume}"
        )
    plan_data = read_json(out / "plan.json", {})
    hops_data = read_json(out / "hops.json", {})
    semantic_errors = strict_semantic_errors(plan_data, hops_data)
    if semantic_errors:
        write_json(out / "semantic_errors.json", semantic_errors)
        raise RuntimeError(
            "cannot prepare validators; strict semantic gates failed: "
            + "; ".join(semantic_errors[:10])
        )
    previous_semantic_errors = read_json(out / "semantic_errors.json", [])
    if previous_semantic_errors:
        append_jsonl(
            out / "semantic_gate_history.jsonl",
            {"event": "semantic_gate_recovered", "errors": previous_semantic_errors},
        )
    write_json(out / "semantic_errors.json", [])
    run_py(
        [
            "contract-check",
            "--prompts",
            str(out / "plan.json"),
            "--hops",
            str(out / "hops.json"),
            "--output",
            str(out / "compat.json"),
        ]
    )
    run_py(
        [
            "fill-validator-prompts",
            "--prompts",
            str(out / "plan.json"),
            "--hops",
            str(out / "hops.json"),
            "--compact-trace",
            "--output",
            str(out / "plan_with_val.json"),
        ]
    )
    plan = read_json(out / "plan_with_val.json", {})
    for item in plan.get("plans", []):
        tc_id = item["test_case_id"]
        sd = scenario_dir(out, tc_id)
        sd.mkdir(parents=True, exist_ok=True)
        (sd / f"validator_prompt_{tc_id}.txt").write_text(
            item.get("validator_prompt", ""), encoding="utf-8"
        )
    if not (out / "val_results.json").exists():
        write_json(out / "val_results.json", [])
    print(
        json.dumps(
            {"status": "validators_prepared", "count": len(plan.get("plans", []))},
            ensure_ascii=False,
        )
    )


@serialized_run
def next_validators(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    plan = read_json(out / "plan_with_val.json", {})
    state = read_json(out / "driver_state.json", {})
    reuse_ready_equivalent_validators(out, plan, state)
    state = read_json(out / "driver_state.json", state)
    done = set(state.get("validator_done", []))
    done.update(v.get("test_case_id") for v in read_json(out / "val_results.json", []))
    pending = []
    for item in plan.get("plans", []):
        if len(pending) >= int(args.limit):
            break
        tc_id = item["test_case_id"]
        if tc_id in done:
            continue
        sd = scenario_dir(out, tc_id)
        pending_item = {
            "kind": "validator",
            "test_case_id": tc_id,
            "prompt_file": str(sd / f"validator_prompt_{tc_id}.txt"),
            "raw_response_file": str(sd / f"validator_response_{tc_id}.txt"),
        }
        pending_file = sd / f"pending_validator_{tc_id}.json"
        pending_item["pending_file"] = str(pending_file)
        write_json(pending_file, pending_item)
        pending.append(pending_item)
    write_json(out / "pending_validators.json", pending)
    print(
        json.dumps(
            {"pending": pending, "remaining": len(plan.get("plans", [])) - len(done)},
            ensure_ascii=False,
            indent=2,
        )
    )


@serialized_run
def consume_validator(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    pending = read_json(Path(args.pending_file), {})
    raw_text = (
        Path(pending["raw_response_file"])
        .read_text(encoding="utf-8", errors="replace")
        .lstrip("\ufeff")
    )
    parsed = _extract_json_from_response(raw_text)
    payload_errors = (
        ["invalid validator JSON"]
        if "raw" in parsed
        else validator_payload_errors(parsed, require_dimensions=True)
    )
    if payload_errors:
        error = {
            "artifact_error": "invalid_validator_response",
            "errors": payload_errors,
            "test_case_id": pending["test_case_id"],
            "raw_response_file": pending["raw_response_file"],
            "attempt_key": artifact_attempt_key("validator", pending["test_case_id"]),
        }
        error_path = Path(pending["raw_response_file"]).with_suffix(".error.json")
        write_json(error_path, error)
        append_jsonl(out / "artifact_errors.jsonl", error)
        state = read_json(out / "driver_state.json", {})
        needs = set(state.get("validator_needs_reconsume", []))
        needs.add(pending["test_case_id"])
        state["validator_needs_reconsume"] = sorted(needs)
        done = set(state.get("validator_done", []))
        done.discard(pending["test_case_id"])
        state["validator_done"] = sorted(done)
        write_json(out / "driver_state.json", state)
        append_jsonl(
            out / "subagent_calls.jsonl",
            {
                "role": "validator",
                "test_case_id": pending["test_case_id"],
                "agent_id": args.agent_id,
                "prompt_file": pending["prompt_file"],
                "raw_response_file": pending["raw_response_file"],
                "artifact_error_file": str(error_path),
                "parse_status": "invalid_validator_response",
            },
        )
        print(json.dumps({"artifact_error": error}, ensure_ascii=False))
        return
    vals = read_json(out / "val_results.json", [])
    vals = [v for v in vals if v.get("test_case_id") != pending["test_case_id"]]
    vals.append({"test_case_id": pending["test_case_id"], "result": parsed})
    write_json(out / "val_results.json", vals)
    state = read_json(out / "driver_state.json", {})
    done = set(state.get("validator_done", []))
    done.add(pending["test_case_id"])
    state["validator_done"] = sorted(done)
    needs = set(state.get("validator_needs_reconsume", []))
    needs.discard(pending["test_case_id"])
    state["validator_needs_reconsume"] = sorted(needs)
    write_json(out / "driver_state.json", state)
    recover_artifact_attempt(out, artifact_attempt_key("validator", pending["test_case_id"]))
    append_jsonl(
        out / "subagent_calls.jsonl",
        {
            "role": "validator",
            "test_case_id": pending["test_case_id"],
            "agent_id": args.agent_id,
            "prompt_file": pending["prompt_file"],
            "raw_response_file": pending["raw_response_file"],
            "parse_status": "valid",
        },
    )
    print(
        json.dumps(
            {"consumed": pending["test_case_id"], "overall": parsed.get("overall")},
            ensure_ascii=False,
        )
    )


@serialized_run
def finalize(args: argparse.Namespace) -> None:
    out = Path(args.output_dir)
    state = read_json(out / "driver_state.json", {})
    audit_path = out / "strict_audit.json"
    audit_error = ""
    try:
        run_py(
            [
                "validate-run-artifacts",
                "--prompts",
                str(out / "plan_with_val.json"),
                "--hops",
                str(out / "hops.json"),
                "--val-results",
                str(out / "val_results.json"),
                "--call-log",
                str(out / "subagent_calls.jsonl"),
                "--require-call-log",
                "--output",
                str(audit_path),
            ]
        )
    except RuntimeError as exc:
        audit_error = str(exc)
        if not audit_path.exists():
            raise
    audit = read_json(audit_path, {})
    audit_status = audit.get("status", "UNKNOWN")
    report_path = Path(state.get("report_path") or (out / "validation-report.md"))
    retention = state.get("artifact_retention", "full")
    report_args = [
        "report",
        "--prompts",
        str(out / "plan_with_val.json"),
        "--val-results",
        str(out / "val_results.json"),
        "--compat",
        str(out / "compat.json"),
        "--hops",
        str(out / "hops.json"),
        "--strict-audit",
        str(audit_path),
        "--audience",
        "architecture",
        "--artifact-dir",
        str(out),
        "--output",
        str(report_path),
    ]
    if audit_status == "PASS":
        report_args.append("--strict")
        if retention == "report":
            report_args.append("--omit-artifact-refs")
    run_py(report_args)
    vals = read_json(out / "val_results.json", [])
    counts = {"PASS": 0, "FAIL": 0, "WARNING": 0, "MISSING": 0}
    for item in vals:
        key = item.get("result", {}).get("overall", "MISSING")
        counts[key if key in counts else "MISSING"] += 1
    write_json(
        out / "run_summary.json",
        {
            "count": len(vals),
            "overall_counts": counts,
            "audit_status": audit_status,
            "report": str(report_path),
            "run_dir": str(out),
            "artifact_retention": retention,
        },
    )
    metadata = state.get("protocol_metadata", {})
    formal_output_dir = (
        out / "formal"
        if report_path.resolve().is_relative_to(out.resolve())
        else report_path.parent / out.name
    )
    publish_args = [
        "publish-artifacts",
        "--run-dir",
        str(out),
        "--output-dir",
        str(formal_output_dir),
    ]
    if retention == "report":
        publish_args.append("--self-contained")
    for key, value in metadata.items():
        publish_args.extend(["--" + key.replace("_", "-"), str(value)])
    publish_error = ""
    canonical_input = read_json(out / "normalized_input.json", {})
    if canonical_input.get("artifact_schema_version") == "mocktest-normalized-input/v2":
        try:
            publish_canonical_bundle(out, formal_output_dir)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            publish_error = f"canonical v2 publication failed: {exc}"
    else:
        try:
            run_py(publish_args)
        except RuntimeError as exc:
            # A FAIL/ERROR legacy result intentionally exits non-zero.  The files
            # remain the source of truth and must still be delivered.
            publish_error = str(exc)
    formal_report = read_json(formal_output_dir / "mocktest_report.json", {})
    formal_status = (
        formal_report.get("states", {}).get("overall")
        if formal_report.get("artifact_schema_version") == "mocktest-report/v2"
        else formal_report.get("status", "ERROR")
    )
    summary = read_json(out / "run_summary.json", {})
    summary["formal_output_dir"] = str(formal_output_dir)
    write_json(out / "run_summary.json", summary)
    retention_result = apply_artifact_retention(out, retention, audit_status)
    result = {
        "status": "finalized" if audit_status == "PASS" else "diagnostic",
        "audit_status": audit_status,
        "count": len(vals),
        "overall_counts": counts,
        "report": str(report_path),
        "formal_output_dir": str(formal_output_dir),
        "mocktest_status": formal_status,
        "retention": retention_result,
    }
    if audit_error:
        result["audit_error"] = audit_error
    if publish_error:
        result["publish_result"] = publish_error
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if formal_status in {"FAIL", "WARNING", "BLOCKED"}:
        raise SystemExit(2)
    if formal_status == "ERROR" or audit_status != "PASS":
        error_text = " ".join(formal_report.get("errors", [])).lower()
        raise SystemExit(5 if "schema" in error_text or "identity" in error_text else 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("--feature")
    parser.add_argument("--arch")
    parser.add_argument("--scenario-ids", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-dir")
    parser.add_argument(
        "--artifact-retention",
        choices=("report", "audit", "full"),
        default=None,
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-hops", type=int, default=20)
    parser.add_argument("--pending-file")
    parser.add_argument("--agent-id", default="")
    parser.add_argument("--strict-equivalence", action="store_true")
    parser.add_argument("--identity-manifest")
    parser.add_argument("--input-manifest")
    parser.add_argument("--ground-truth")
    parser.add_argument("--run-id")
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--simulator-model", default="")
    parser.add_argument("--validator-model", default="")
    for key in (
        "project_id",
        "node_id",
        "parent_node_id",
        "branch_id",
        "architecture_artifact_id",
        "testcase_artifact_id",
        "source_prd_id",
    ):
        parser.add_argument("--" + key.replace("_", "-"), default="")
    parser.add_argument(
        "--reuse-from",
        default="",
        help="Reuse exact-key scenarios from a previous strict-PASS output directory.",
    )
    args = parser.parse_args()
    commands = {
        "init": init,
        "next-components": next_components,
        "consume-component": consume_component,
        "prepare-validators": prepare_validators,
        "next-validators": next_validators,
        "consume-validator": consume_validator,
        "finalize": finalize,
    }
    if args.command not in commands:
        raise SystemExit(f"unknown command: {args.command}")
    commands[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
