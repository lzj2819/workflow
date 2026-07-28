"""Interactive driver for validate-arch strict subagent simulation.

This script coordinates per-hop component subagent execution. It generates
prompt files, waits for result files, normalizes them, and advances chains.
When all scenarios finish it writes hops.json and subagent_calls.jsonl.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
TMP = Path(
    os.environ.get(
        "VALIDATE_ARCH_WORK_DIR",
        str(PROJECT_ROOT / ".work" / "validate-arch" / "interactive"),
    )
)
PLAN_PATH = TMP / "plan_locked.json"
STATE_PATH = TMP / "sim_state.json"
PROMPT_DIR = TMP / "hop_prompts"
RESULT_DIR = TMP / "hop_results"
HOPS_PATH = TMP / "hops.json"
CALL_LOG_PATH = TMP / "subagent_calls.jsonl"
MAX_HOPS = 20

sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(TMP))
sys.path.insert(0, str(SCRIPT_DIR))

from run_subagent_skill import (
    _extract_json_from_response,
    _normalize_hop,
    _resolve_next_hop,
)


def run_simulate_step_prompt(request: dict) -> str:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "run_subagent_skill.py"), "simulate-step-prompt"],
        input=json.dumps(request, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"simulate-step-prompt failed: {proc.stderr}")
    return proc.stdout


def load_plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"hops_by_tc": {}, "call_log": [], "ready_requests": []}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_initial_request(plan_item: dict, tc_summary: dict) -> dict:
    steps = tc_summary.get("gherkin", {}).get("steps", [])
    given_text = next((s["text"] for s in steps if s["keyword"] == "Given"), "")
    when_text = next((s["text"] for s in steps if s["keyword"] == "When"), "")
    trigger = plan_item.get("trigger_message") or {}
    input_message = {
        "event": plan_item.get("entry_action", "handle"),
        "given": given_text,
        "when": when_text,
        "original_trigger": trigger if isinstance(trigger, dict) else {},
    }
    return {
        "plan_path": str(PLAN_PATH.resolve()),
        "component": plan_item["entry_component"],
        "action": plan_item["entry_action"],
        "input_message": input_message,
        "shared_state": {},
        "phase": "when",
        "then_assertions": plan_item.get("then_assertions", []),
    }


def build_next_request(prev_hop: dict, plan: dict) -> dict | None:
    next_hop = _resolve_next_hop(prev_hop.get("next_hop"), set(plan["component_cards"].keys()))
    if not next_hop:
        return None
    output_message = prev_hop.get("output_message", {})
    shared_state = {}
    state_change = prev_hop.get("state_change")
    if isinstance(state_change, dict) and state_change.get("entity"):
        shared_state[state_change["entity"]] = state_change.get("to_state", "")
    return {
        "plan_path": str(PLAN_PATH.resolve()),
        "component": next_hop["component"],
        "action": next_hop.get("action", "handle"),
        "input_message": output_message if isinstance(output_message, dict) else {"payload": output_message},
        "shared_state": shared_state,
        "phase": "when",
        "then_assertions": [],
    }


def normalize_hop_result(raw: dict, request: dict, hop_index: int) -> dict:
    parsed = _extract_json_from_response(raw)
    if "parse_error" in parsed:
        return {
            "hop_index": hop_index,
            "component": request["component"],
            "action": request["action"],
            "input_message": request["input_message"],
            "output_message": {"error": "invalid_json_response", "raw": raw.get("raw") if isinstance(raw, dict) else str(raw)},
            "status": "ARTIFACT_ERROR",
            "latency_ms": 0,
            "side_effects": [],
            "state_change": None,
            "phase": request.get("phase", "when"),
            "self_check": {
                "consumed_input_ok": True,
                "produced_fields": [],
                "missing_required_inputs": [],
                "undefined_next_call": None,
                "artifact_error": "invalid_json_response",
                "parse_error": parsed.get("parse_error", ""),
            },
            "next_hop": None,
        }
    return _normalize_hop(parsed, request["component"], request["action"], request["input_message"], request.get("phase", "when"), hop_index)


def main():
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    plan = load_plan()
    state = load_state()
    test_cases = {tc["test_case_id"]: tc for tc in plan["test_cases"]}
    valid_components = set(plan["component_cards"].keys())

    for plan_item in plan["plans"]:
        tc_id = plan_item["test_case_id"]
        if tc_id not in state["hops_by_tc"]:
            state["hops_by_tc"][tc_id] = []
            req = build_initial_request(plan_item, test_cases[tc_id])
            state["ready_requests"].append({"tc_id": tc_id, "hop_index": 0, "request": req})

    still_waiting = []
    for item in state["ready_requests"]:
        tc_id = item["tc_id"]
        hop_index = item["hop_index"]
        result_path = RESULT_DIR / f"{tc_id}_{hop_index}.json"
        prompt_path = PROMPT_DIR / f"{tc_id}_{hop_index}.txt"
        if not prompt_path.exists():
            prompt = run_simulate_step_prompt(item["request"])
            prompt_path.write_text(prompt, encoding="utf-8")

        if result_path.exists():
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            hop = normalize_hop_result(raw, item["request"], hop_index)
            state["hops_by_tc"][tc_id].append(hop)
            state["call_log"].append({
                "role": "component",
                "test_case_id": tc_id,
                "hop_index": hop_index,
                "component": item["request"]["component"],
                "action": item["request"]["action"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if hop_index + 1 < MAX_HOPS:
                next_req = build_next_request(hop, plan)
                if next_req and _resolve_next_hop(hop.get("next_hop"), valid_components):
                    still_waiting.append({"tc_id": tc_id, "hop_index": hop_index + 1, "request": next_req})
                else:
                    print(f"[{tc_id}] chain ends at hop {hop_index} ({item['request']['component']})")
            else:
                print(f"[{tc_id}] max hops reached at {hop_index}")
        else:
            still_waiting.append(item)

    state["ready_requests"] = still_waiting
    save_state(state)

    if not still_waiting:
        HOPS_PATH.write_text(json.dumps(state["hops_by_tc"], ensure_ascii=False, indent=2), encoding="utf-8")
        CALL_LOG_PATH.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in state["call_log"]), encoding="utf-8")
        print("\nAll scenarios simulated.")
        print(f"Wrote {HOPS_PATH}")
        print(f"Wrote {CALL_LOG_PATH}")
        return 0

    print("\nPending component subagent calls:\n")
    for item in still_waiting:
        tc_id = item["tc_id"]
        hop_index = item["hop_index"]
        comp = item["request"]["component"]
        prompt_path = PROMPT_DIR / f"{tc_id}_{hop_index}.txt"
        result_path = RESULT_DIR / f"{tc_id}_{hop_index}.json"
        print(f"- {tc_id} hop {hop_index}: component={comp}")
        print(f"  prompt: {prompt_path}")
        print(f"  result: {result_path}")
    print("\nSpawn an independent Codex subagent for each pending prompt, then write the raw JSON HopResult to the result path.")
    return 0


if __name__ == "__main__":
    main()
