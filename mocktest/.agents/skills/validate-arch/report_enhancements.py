"""LEGACY report views isolated from the Mocktest v2 publisher.

Retained only for compatibility comparison; these helpers must not define the
canonical result, status, or bundle.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


DIMENSIONS = ("structure", "flow", "state", "contract", "performance", "interface_compat")

PROCESS_NOISE_PATTERNS = (
    "invalid_json_response",
    "invalid json from subagent",
    "invalid json",
    "consumed_input_ok=false",
    "raw payload",
    "raw hop",
    "compact trace",
    "no explicit when phase",
    "no separate when phase",
    "no distinct when phase",
    "given followed directly by then",
    "given step followed directly by a then",
    "emit explicit given/when/then",
    "phase labels",
    "extend the trace",
    "extend the simulator trace",
    "simulator trace",
    "run the when step",
    "execute an explicit when step",
    "execute a distinct when step",
    "execute the when step",
    "when phase",
    "验证流程",
    "模拟过程",
)

SCENARIO_INPUT_PATTERNS = (
    "provide the concrete selected_proficiency_level",
    "selected_proficiency_level is missing",
    "missing_selected_proficiency_level",
    "provide the complete solution content as input",
    "provided problem context",
    "scenario input",
    "test fixture",
    "input_message",
    "missing_required_inputs",
    "补充场景输入",
)

ARCHITECTURE_PATTERNS = (
    "not a legal downstream",
    "not a legal outbound",
    "legal downstream",
    "legal outbound",
    "undefined",
    "架构未定义",
    "合法下游",
    "outbound interface",
    "inbound interface",
    "interface",
    "接口",
    "契约",
    "required field",
    "required_fields",
    "data_flow",
    "数据流",
    "state machine",
    "transition",
    "状态",
    "流转",
    "owner",
    "population",
    "metric",
    "p95",
    "latency",
    "success rate",
    "success-rate",
    "指标",
    "成功率",
    "比例",
    "延迟",
    "retention",
    "deletion",
    "audit",
    "readability",
    "保留",
    "删除",
    "审计",
    "可读",
    "otp",
    "sms",
    "verification code",
    "验证码",
    "身份",
    "user identity bc",
    "data retention & compliance bc",
    "solution generation bc",
    "hint generation bc",
    "problem intake bc",
    "tutoring session bc",
    "entry component",
    "入口",
    "missing_problem_context",
    "problem context",
    "上下文",
    "complete_solution",
)

MODULE_DETAIL_PATTERNS = (
    "button display",
    "standard terminology",
    "follow-up",
    "layered_hint",
    "key calculation",
    "step by step",
    "人教",
    "隐私提示",
    "提示方向",
    "追问问题",
    "关键计算",
    "最终答案",
    "按钮显示",
)


def scenario_components(hops: list[dict[str, Any]]) -> list[str]:
    comps = []
    for h in hops:
        c = h.get("component")
        if c and c not in comps:
            comps.append(c)
        t = h.get("target")
        if isinstance(t, str) and t and t not in comps:
            comps.append(t)
    return comps


def components_in_text(text: str, component_names: list[str]) -> list[str]:
    found = []
    for name in component_names:
        if name in text and name not in found:
            found.append(name)
    return found


def _norm(text: Any) -> str:
    return str(text or "").lower()


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    lower = _norm(text)
    return any(pattern in lower for pattern in patterns)


def _merge_interface_compat(val_output: dict[str, Any], compat: dict[str, Any]) -> dict[str, Any]:
    """把确定性接口检查结果并入 validator 输出，与 run_subagent_skill 保持一致。"""
    merged = dict(val_output)
    merged["interface_compat"] = {"status": compat["status"], "detail": compat["detail"]}
    if compat["status"] == "FAIL":
        merged["overall"] = "FAIL"
        merged["failure_analysis"] = {
            "dimension": "interface_compat",
            "problem": compat["detail"],
            "severity": "high",
            "impact": "组件间契约不符，按当前设计无法串通",
            "suggestion": "补全上游输出字段或修正接口契约/数据流定义",
        }
    elif compat["status"] == "WARNING" and merged.get("overall") == "PASS":
        # 只标记 overall 为 WARNING，但不生成 warning_analysis，
        # 因为 "缺少 inbound 契约" 等需在架构报告中合并为一条文档契约建议。
        merged["overall"] = "WARNING"
    return merged


def _enrich_val_results(
    val_results: list[dict[str, Any]], compat: dict[str, Any]
) -> list[dict[str, Any]]:
    """返回已合并 interface_compat 的 val_results 副本。"""
    per_scenario = compat.get("per_scenario", {})
    enriched: list[dict[str, Any]] = []
    for val in val_results:
        tc_id = val.get("test_case_id")
        compat_sc = per_scenario.get(tc_id, {"status": "MISSING", "detail": ""})
        new_val = dict(val)
        new_val["result"] = _merge_interface_compat(dict(val.get("result", {})), compat_sc)
        enriched.append(new_val)
    return enriched


def classify_issue_kind(dim: str, detail: str, analysis_text: str = "") -> str:
    """Classify a validator issue for report routing.

    Returns one of:
    - architecture: actionable architecture document change.
    - module_detail: keep out of architecture report; revisit in child/module design.
    - scenario_input: feature fixture/input issue, not architecture.
    - validation_process: simulator/trace/reporting issue, not architecture.
    """
    text = f"{dim} {detail} {analysis_text}"
    lower = _norm(text)
    has_arch_hint = _contains_any(lower, ARCHITECTURE_PATTERNS)

    if dim == "structure":
        return "validation_process"
    if any(
        owner in lower
        for owner in (
            "fix_owner=workflow_or_input_provider",
            "fix_owner=input_provider",
            "fix_owner=scenario_fixture",
            "fix_owner=test_fixture",
            "fix_owner=upstream_contract_producer",
        )
    ):
        return "scenario_input"
    if any(
        owner in lower
        for owner in (
            "fix_owner=validation_process",
            "fix_owner=simulator",
            "fix_owner=reporter",
        )
    ):
        return "validation_process"
    if "fix_owner=architecture" in lower:
        return "architecture"
    if _contains_any(lower, PROCESS_NOISE_PATTERNS):
        # Keep genuine architecture failures when the same text explicitly names illegal
        # architecture routing or interface ownership; hide pure trace/phase noise.
        if "invalid json" in lower or not has_arch_hint:
            return "validation_process"
    if _contains_any(lower, SCENARIO_INPUT_PATTERNS) and not has_arch_hint:
        return "scenario_input"
    if dim == "interface_compat":
        if "缺少 inbound required 字段契约" in detail and not (
            "架构未定义" in detail or "入参缺字段" in detail or "声称产出字段" in detail
        ):
            return "validation_process"
        return "architecture"
    if has_arch_hint:
        return "architecture"
    if _contains_any(lower, MODULE_DETAIL_PATTERNS):
        return "module_detail"
    if dim in ("flow", "state", "performance"):
        return "architecture"
    return "module_detail"


def build_component_heatmap(
    hops_by_tc: dict[str, list[dict[str, Any]]],
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    component_names: list[str],
    *,
    architecture_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Build per-component failure/warning heatmap with dimension breakdown."""
    heatmap: dict[str, dict[str, Any]] = {
        name: {"total": 0, "fail": 0, "warning": 0, "missing": 0, "dims": {}}
        for name in component_names
    }

    enriched_vals = _enrich_val_results(val_results, compat)
    val_by_id = {r["test_case_id"]: r for r in enriched_vals}

    for tc_id, hops in hops_by_tc.items():
        comps = scenario_components(hops)
        val = val_by_id.get(tc_id)
        if not val:
            continue
        result = val.get("result", {})
        overall = result.get("overall", "MISSING")

        dim_hits: list[tuple[str, str, str]] = []
        for dim in DIMENSIONS:
            dim_result = result.get(dim, {})
            status = dim_result.get("status", "MISSING")
            if status not in ("FAIL", "WARNING"):
                continue
            detail = dim_result.get("detail", "")
            if architecture_only and classify_issue_kind(dim, detail) != "architecture":
                continue
            dim_hits.append((dim, status, detail))

        if architecture_only and not dim_hits:
            continue

        for c in comps:
            heatmap[c]["total"] += 1
            if overall == "FAIL":
                heatmap[c]["fail"] += 1
            elif overall == "WARNING":
                heatmap[c]["warning"] += 1
            elif overall == "MISSING":
                heatmap[c]["missing"] += 1

        for dim, status, detail in dim_hits:
            dim_comps = components_in_text(detail, component_names)
            if not dim_comps:
                dim_comps = comps
            for c in dim_comps:
                heatmap[c]["dims"].setdefault(dim, {"fail": 0, "warning": 0})
                heatmap[c]["dims"][dim]["fail" if status == "FAIL" else "warning"] += 1

    return {k: v for k, v in heatmap.items() if v["total"] > 0}


def _shorten(text: str, length: int = 120) -> str:
    text = str(text or "").replace("\n", " ").strip()
    if len(text) <= length:
        return text
    return text[: length - 1] + "..."


def _parse_interface_compat_detail(detail: str) -> list[tuple[str, str, str, str]]:
    """解析 interface_checker detail，返回 (target_section, action, content, reason) 列表。

    只把真正的接口字段缺失/不一致映射为架构文档修改点；
    "缺少 inbound required 字段契约" 会在架构报告中合并为一条整体建议。
    """
    items: list[tuple[str, str, str, str]] = []
    for segment in re.split(r"[;；]", detail):
        segment = segment.strip()
        if not segment:
            continue
        # 声称产出字段不存在
        m = re.search(r"^(.*?)\s+声称产出字段\s+(.+?)(?:[，,；;]|$)", segment)
        if m:
            comp = m.group(1).strip()
            field = m.group(2).strip().rstrip("，,；;")
            items.append(
                (
                    f"06-interface-contracts.md / {comp}.outbound_interfaces",
                    "add_or_correct_output_field",
                    field,
                    f"{comp} 声称产出字段 {field} 不存在",
                )
            )
            continue
        # 入参缺字段（上游未产出）
        m = re.search(r"^(.*?)\s+入参缺字段\s+(.+?)\s*（上游", segment)
        if m:
            comp = m.group(1).strip()
            fields = m.group(2).strip()
            items.append(
                (
                    f"06-interface-contracts.md / {comp}.inbound_interfaces",
                    "add_required_fields",
                    fields,
                    f"{comp} 入参缺字段 {fields}",
                )
            )
    return items


def _analysis_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _analysis_text(result: dict[str, Any]) -> str:
    records = _analysis_records(result.get("failure_analysis")) + _analysis_records(
        result.get("warning_analysis")
    )
    parts: list[str] = []
    for record in records:
        for key in ("problem", "impact", "suggestion", "scope", "issue_kind", "fix_owner"):
            value = record.get(key)
            if value:
                parts.append(f"{key}={value}")
    return " ".join(parts)


def _priority(status: str, detail: str) -> str:
    lower = _norm(detail)
    if status == "FAIL" and any(k in lower for k in ("not a legal", "架构未定义", "missing_problem_context")):
        return "high"
    if status == "FAIL":
        return "medium"
    return "medium"


def _architecture_action(
    dim: str, status: str, detail: str, component: str
) -> tuple[str, str, str, str, str]:
    """Return category, target section, action, reason, priority."""
    lower = _norm(detail)
    priority = _priority(status, detail)

    metric_ratio = re.search(r"\bratio\b", lower) is not None
    if any(k in lower for k in ("p95", "metric", "latency", "success rate", "success-rate", "指标", "成功率", "比例", "延迟")) or metric_ratio:
        return (
            "指标与可观测性契约",
            "interfaces / observability",
            f"为 {component} 涉及的指标补充 owner、统计口径、起止事件、数据来源、计算窗口、阈值和查询接口。",
            "验证显示指标计算或指标查询没有清晰的拥有者、统计口径、数据来源和合法调用接口。",
            priority,
        )

    if any(k in lower for k in ("retention", "deletion", "audit", "readability", "保留", "删除", "审计", "可读")):
        return (
            "数据保留与合规边界",
            "data / interfaces / deployment",
            f"明确 {component} 涉及的数据生命周期 owner、保留/删除规则、审计事件、查询接口与合法数据流。",
            "验证显示保留期可读性检查、删除任务和删除审计能力没有完整的接口边界与合法数据流。",
            priority,
        )

    if dim == "interface_compat" or any(k in lower for k in ("outbound interface", "inbound interface", "接口", "契约", "required field", "required_fields")):
        return (
            "组件接口字段契约",
            "interfaces",
            f"补充或修正 {component} 的 inbound/outbound 字段、契约 ID、事件/动作、错误码和 next_hop，并保证上游 produced_fields 覆盖下游 required_fields。",
            "验证显示组件间字段级输入输出契约不足，接口检查只能做弱校验或发现上游/下游字段不一致。",
            priority,
        )

    if dim == "state":
        return (
            "状态机与生命周期",
            "runtime / data",
            f"补充 {component} 相关状态机的前置状态、触发事件、成功/失败分支和可观测副作用。",
            "验证显示相关场景的状态前置条件、失败分支或副作用边界不完整。",
            priority,
        )

    return (
        "跨组件数据流",
        "runtime / interfaces",
        f"修正 {component} 所在流程的合法数据流和责任边界，明确入口组件、next_hop 条件、返回事件和终止条件。",
        "验证显示场景链路需要的跨组件调用未被当前架构声明为合法数据流。",
        priority,
    )


def _required_contract_components(compat: dict[str, Any]) -> tuple[list[str], int]:
    found: list[str] = []
    count = 0
    for item in compat.get("global_findings", []):
        if item.get("kind") != "contract_coverage_gap":
            continue
        detail = item.get("detail", "")
        comp = detail.split(" 缺少 ", 1)[0].strip()
        count += 1
        if comp and comp not in found:
            found.append(comp)
    for sc in compat.get("per_scenario", {}).values():
        detail = sc.get("detail", "")
        for match in re.finditer(r"([^;；]+?)\s+缺少 inbound required 字段契约", detail):
            comp = match.group(1).strip()
            count += 1
            if comp and comp not in found:
                found.append(comp)
    return found, count


def build_architecture_findings(
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    hops_by_tc: dict[str, list[dict[str, Any]]],
    component_names: list[str],
) -> list[dict[str, Any]]:
    """Build architecture-layer findings only."""
    findings: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    def add_finding(
        *,
        category: str,
        priority: str,
        target_section: str,
        action: str,
        reason: str,
        scenarios: list[str],
        components: list[str],
        dimension: str,
        evidence_detail: str,
    ) -> None:
        # A report card represents a semantic root cause, not one wording of one
        # scenario.  The first explicitly named component is the ownership scope;
        # wording, field lists, and scenario IDs are evidence attached to that root.
        owner = components[0] if components else "GLOBAL"
        key = f"{category}|{owner}"
        item = seen.get(key)
        if item is None:
            item = {
                "fingerprint": hashlib.sha256(key.encode("utf-8")).hexdigest()[:12],
                "owner_domain": "architecture",
                "category": category,
                "priority": priority,
                "target_section": target_section,
                "action": action,
                "reason": reason,
                "affected_scenarios": [],
                "components": [],
                "occurrences": 0,
                "evidence": [],
                "required_changes": [],
            }
            seen[key] = item
            findings.append(item)
        if action and action not in item["required_changes"]:
            item["required_changes"].append(action)
        evidence = {
            "test_case_id": scenarios[0] if scenarios else "GLOBAL",
            "dimension": dimension,
            "severity": priority,
            "detail": _shorten(evidence_detail, 260),
        }
        if evidence not in item["evidence"]:
            item["evidence"].append(evidence)
            item["occurrences"] += 1
        priority_rank = {"high": 3, "medium": 2, "low": 1}
        if priority_rank.get(priority, 0) > priority_rank.get(item["priority"], 0):
            item["priority"] = priority
        for sc in scenarios:
            if sc and sc not in item["affected_scenarios"]:
                item["affected_scenarios"].append(sc)
        for comp in components:
            if comp and comp not in item["components"]:
                item["components"].append(comp)

    required_contract_comps, required_contract_count = _required_contract_components(compat)
    if required_contract_comps and (required_contract_count >= 2 or len(required_contract_comps) >= 2):
        add_finding(
            category="组件接口字段契约",
            priority="medium",
            target_section="06-interface-contracts.md",
            action="为被多场景触达的 BC 补充机器可读的 inbound required_fields、outbound produced_fields、错误码和事件字段；至少覆盖 "
            + ", ".join(required_contract_comps)
            + "。",
            reason="当前接口检查只能给出弱校验 WARNING，说明架构文档缺少可被验证器稳定消费的字段级接口契约。",
            scenarios=["GLOBAL"],
            components=required_contract_comps,
            dimension="interface_compat",
            evidence_detail=f"{required_contract_count} contract coverage gaps",
        )

    for tc_id, sc_compat in compat.get("per_scenario", {}).items():
        status = sc_compat.get("status", "")
        detail = sc_compat.get("detail", "")
        if status not in ("FAIL", "WARNING") or not detail:
            continue
        parsed_details = _parse_interface_compat_detail(detail)
        for target_section, action, content, reason in parsed_details:
            add_finding(
                category="组件接口字段契约",
                priority=_priority(status, detail),
                target_section=target_section,
                action=f"{action}: {content}",
                reason=reason,
                scenarios=[tc_id],
                components=components_in_text(detail, component_names),
                dimension="interface_compat",
                evidence_detail=detail,
            )
        # Field-level parser output is already a more precise representation of
        # this evidence; do not add a second generic card for the same failure.
        if parsed_details:
            continue
        if classify_issue_kind("interface_compat", detail) != "architecture":
            continue
        comps = components_in_text(detail, component_names) or scenario_components(hops_by_tc.get(tc_id, []))
        component = comps[0] if comps else "system"
        category, target, action, reason, priority = _architecture_action(
            "interface_compat", status, detail, component
        )
        add_finding(
            category=category,
            priority=priority,
            target_section=target,
            action=action,
            reason=reason,
            scenarios=[tc_id],
            components=comps,
            dimension="interface_compat",
            evidence_detail=detail,
        )

    enriched_vals = _enrich_val_results(val_results, compat)
    for val in enriched_vals:
        tc_id = val.get("test_case_id", "")
        result = val.get("result", {})
        analysis_text = _analysis_text(result)
        default_comps = scenario_components(hops_by_tc.get(tc_id, []))
        for dim in DIMENSIONS:
            dim_result = result.get(dim, {})
            status = dim_result.get("status", "")
            if status not in ("FAIL", "WARNING"):
                continue
            detail = dim_result.get("detail", "")
            if classify_issue_kind(dim, detail, analysis_text) != "architecture":
                continue
            comps = components_in_text(detail + " " + analysis_text, component_names) or default_comps
            component = comps[0] if comps else "system"
            category, target, action, reason, priority = _architecture_action(
                dim, status, f"{detail} {analysis_text}", component
            )
            add_finding(
                category=category,
                priority=priority,
                target_section=target,
                action=action,
                reason=reason,
                scenarios=[tc_id],
                components=comps,
                dimension=dim,
                evidence_detail=f"{detail} {analysis_text}".strip(),
            )

    for item in findings:
        changes = item.pop("required_changes")
        if len(changes) > 1:
            item["action"] = changes[0] + f"（另合并 {len(changes) - 1} 条同根因字段/场景证据，详见 diagnostics。）"
    return findings


def build_diagnostics(
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    component_names: list[str],
) -> dict[str, list[dict[str, str]]]:
    """Return non-architecture issues for internal diagnostics."""
    diagnostics: dict[str, list[dict[str, str]]] = {
        "validation_process": [],
        "scenario_input": [],
        "module_detail": [],
        "raw_evidence": [],
    }
    enriched_vals = _enrich_val_results(val_results, compat)
    for val in enriched_vals:
        tc_id = val.get("test_case_id", "")
        result = val.get("result", {})
        analysis_text = _analysis_text(result)
        for dim in DIMENSIONS:
            dim_result = result.get(dim, {})
            status = dim_result.get("status", "")
            if status not in ("FAIL", "WARNING"):
                continue
            detail = dim_result.get("detail", "")
            kind = classify_issue_kind(dim, detail, analysis_text)
            diagnostics["raw_evidence"].append(
                {
                    "test_case_id": tc_id,
                    "dimension": dim,
                    "status": status,
                    "detail": _shorten(detail, 220),
                }
            )
            if kind in diagnostics:
                diagnostics[kind].append(
                    {
                        "test_case_id": tc_id,
                        "dimension": dim,
                        "status": status,
                        "detail": _shorten(detail, 220),
                    }
                )

    for tc_id, sc_compat in compat.get("per_scenario", {}).items():
        detail = sc_compat.get("detail", "")
        status = sc_compat.get("status", "")
        if status not in ("FAIL", "WARNING"):
            continue
        kind = classify_issue_kind("interface_compat", detail)
        diagnostics["raw_evidence"].append(
            {
                "test_case_id": tc_id,
                "dimension": "interface_compat",
                "status": status,
                "detail": _shorten(detail, 220),
            }
        )
        if kind in diagnostics:
            diagnostics[kind].append(
                {
                    "test_case_id": tc_id,
                    "dimension": "interface_compat",
                    "status": status,
                    "detail": _shorten(detail, 220),
                }
            )
    return diagnostics


def build_modifications(
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    hops_by_tc: dict[str, list[dict[str, Any]]],
    component_names: list[str],
) -> list[dict[str, Any]]:
    """Map only architecture/module-design findings to concrete document sections."""
    modifications: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_mod(
        target_section: str,
        action: str,
        content: str,
        reason: str,
        scenarios: list[str],
        scope: str,
    ) -> None:
        key = f"{target_section}|{action}|{content}"
        if key in seen:
            for mod in modifications:
                if mod["_key"] == key:
                    for sc in scenarios:
                        if sc not in mod["affected_scenarios"]:
                            mod["affected_scenarios"].append(sc)
                    return
        seen.add(key)
        modifications.append(
            {
                "_key": key,
                "target_section": target_section,
                "action": action,
                "content": content,
                "reason": reason,
                "affected_scenarios": scenarios,
                "scope": scope,
            }
        )

    # Preserve field-level interface modification output for full/debug reports.
    for tc_id, sc_compat in compat.get("per_scenario", {}).items():
        status = sc_compat.get("status", "")
        if status not in ("FAIL", "WARNING"):
            continue
        detail = sc_compat.get("detail", "")
        for target_section, action, content, reason in _parse_interface_compat_detail(detail):
            add_mod(target_section, action, content, reason, [tc_id], "module")

    for finding in build_architecture_findings(val_results, compat, hops_by_tc, component_names):
        add_mod(
            finding["target_section"],
            "update_architecture",
            finding["action"],
            finding["reason"],
            finding["affected_scenarios"],
            "top_level",
        )

    diagnostics = build_diagnostics(val_results, compat, component_names)
    for item in diagnostics.get("module_detail", []):
        add_mod(
            "模块详细设计阶段",
            "defer_to_module_design",
            item["detail"],
            f"{item['dimension']} {item['status']}: 属于组件内部行为细节，不进入顶层架构报告",
            [item["test_case_id"]],
            "module",
        )

    for mod in modifications:
        mod.pop("_key", None)
    return modifications


def format_heatmap_markdown(heatmap: dict[str, dict[str, Any]]) -> str:
    header = "| 组件 | 相关场景 | 失败 | 警告 | 缺失 | " + " | ".join(DIMENSIONS) + " |"
    sep = "|" + "|".join(["---"] * (5 + len(DIMENSIONS))) + "|"
    lines = ["## 组件问题热力", "", header, sep]

    for comp, data in sorted(
        heatmap.items(), key=lambda x: (x[1]["fail"], x[1]["warning"]), reverse=True
    ):
        cells = [
            comp,
            str(data["total"]),
            str(data["fail"]),
            str(data["warning"]),
            str(data["missing"]),
        ]
        for dim in DIMENSIONS:
            d = data["dims"].get(dim, {})
            f = d.get("fail", 0)
            w = d.get("warning", 0)
            cells.append(f"F{f}/W{w}" if f or w else "-")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _classify_mod_scope(mod: dict[str, Any], full_detail: str = "") -> str:
    """把修改建议按粒度分为顶层架构问题（top_level）或模块内部问题（module）。"""
    if mod.get("scope") in ("top_level", "module"):
        return mod["scope"]
    section = mod.get("target_section", "")
    text = f"{mod.get('reason', '')} {mod.get('content', '')} {full_detail}".lower()
    if section.endswith(".md") or " / " in section:
        return "top_level"
    if _contains_any(text, MODULE_DETAIL_PATTERNS):
        return "module"
    return "top_level"


def format_modifications_markdown(mods: list[dict[str, Any]], title: str | None = None) -> str:
    lines: list[str] = []
    if title:
        lines.append(f"## {title}")
        lines.append("")
    lines.extend(
        [
            "| 目标章节 | 操作 | 修改内容 | 原因 | 影响场景 |",
            "|---|---|---|---|---|",
        ]
    )
    for mod in mods:
        scenarios = ", ".join(mod["affected_scenarios"])
        content = mod["content"].replace("|", "\\|").replace("\n", " ")
        reason = mod["reason"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {mod['target_section']} | {mod['action']} | {content} | {reason} | {scenarios} |"
        )
    return "\n".join(lines)


def _strict_evidence_line(strict_audit: dict[str, Any] | None) -> str:
    if not strict_audit:
        return "未提供 strict audit。"
    summary = strict_audit.get("summary", {})
    scenario_count = summary.get("scenario_count", strict_audit.get("scenario_count", "?"))
    hop_count = summary.get("hop_count", strict_audit.get("hop_count", "?"))
    validator_count = summary.get("validator_count", strict_audit.get("validator_count", "?"))
    return (
        f"审计状态={strict_audit.get('status')}，覆盖场景={scenario_count}，"
        f"组件模拟跳数={hop_count}，validator 检查数={validator_count}"
    )


def _target_files_for_category(category: str, target_section: str) -> list[str]:
    if category == "上下文传递与完整解答契约":
        return [
            "05-data-model.md#3-tutoring-session-bc",
            "05-data-model.md#5-solution-generation-bc",
            "06-interface-contracts.md#17-请求完整解答",
            "06-interface-contracts.md#23-关键事件清单",
        ]
    if category == "场景入口与身份认证边界":
        return [
            "02-module-partitioning.md#module-总览",
            "03-runtime-architecture.md#31-主成功路径登录--上传--答疑--查看完整解答",
            "05-data-model.md#1-user-identity-bc",
            "06-interface-contracts.md#11-短信验证码发送",
            "06-interface-contracts.md#12-短信验证码校验",
        ]
    if category == "指标与可观测性契约":
        return [
            "06-interface-contracts.md#16-请求下一轮提示",
            "06-interface-contracts.md#17-请求完整解答",
            "08-deployment.md#与-qas-的映射",
        ]
    if category == "数据保留与合规边界":
        return [
            "03-runtime-architecture.md#33-生命周期与合规路径数据删除",
            "05-data-model.md#6-data-retention--compliance-bc",
            "06-interface-contracts.md#23-关键事件清单",
            "08-deployment.md#与-qas-的映射",
        ]
    if category == "组件接口字段契约":
        return [
            "06-interface-contracts.md#1-同步-api-契约",
            "06-interface-contracts.md#22-事件-schema-模板",
            "06-interface-contracts.md#23-关键事件清单",
        ]
    return [target_section]


def _contract_stub_for_category(category: str, components: list[str]) -> str:
    if category == "上下文传递与完整解答契约":
        return "\n".join(
            [
                "```yaml",
                "SolutionRequestContext:",
                "  required_fields:",
                "    - session_id",
                "    - problem_id",
                "    - problem_text_or_image_ref",
                "    - student_id",
                "    - student_level",
                "    - hint_round",
                "    - solution_request_reason",
                "  produced_fields:",
                "    - complete_solution_id",
                "    - step_by_step_derivation",
                "    - display_ready",
                "  preconditions:",
                "    - TutoringSession.status == active",
                "    - student explicitly requested full solution",
                "```",
            ]
        )
    if category == "场景入口与身份认证边界":
        return "\n".join(
            [
                "```yaml",
                "IdentityEntryMapping:",
                "  send_sms_code:",
                "    owner: User Identity BC",
                "    input: [phone_number, request_time, client_id]",
                "    output: [verification_token, expires_at, resend_after_seconds]",
                "  validate_sms_code:",
                "    owner: User Identity BC",
                "    input: [phone_number, code, verification_token, attempt_time]",
                "    output: [student_id, auth_session_id, status]",
                "  failure_policy:",
                "    max_failed_attempts: 5",
                "    resend_min_interval_seconds: 60",
                "```",
            ]
        )
    if category == "指标与可观测性契约":
        return "\n".join(
            [
                "```yaml",
                "MetricContract:",
                "  p95_first_hint_latency:",
                "    owner: Observability/AI Tutoring runtime",
                "    start_event: valid_problem_accepted",
                "    end_event: first_hint_returned",
                "    threshold: 15s",
                "  full_solution_p95_latency:",
                "    start_event: full_solution_requested",
                "    end_event: complete_solution_display_ready",
                "    threshold: 20s",
                "  deletion_success_rate:",
                "    owner: Data Retention & Compliance BC",
                "    threshold: 100%",
                "    evidence: deletion audit log",
                "```",
            ]
        )
    if category == "数据保留与合规边界":
        return "\n".join(
            [
                "```yaml",
                "RetentionBoundary:",
                "  resource_types: [problem_image, tutoring_session, hint_round, complete_solution]",
                "  expires_at: uploaded_at + 30d",
                "  check_readability(resource_id, at_time): readable | expired | deleted",
                "  deletion_job:",
                "    owner: Data Retention & Compliance BC",
                "    emits: [DataRetentionExpired, DataDeleted, DeletionFailed]",
                "  audit_fields: [resource_id, resource_type, deletion_time, status, retry_count]",
                "```",
            ]
        )
    listed = ", ".join(components) if components else "相关 BC"
    return "\n".join(
        [
            "```yaml",
            "ComponentInterfaceContract:",
            f"  components: [{listed}]",
            "  inbound:",
            "    required_fields: []  # fill per API/event",
            "    optional_fields: []",
            "  outbound:",
            "    produced_fields: []",
            "    error_codes: []",
            "    next_hop: []",
            "  validation_rule: every downstream required_field is produced upstream",
            "```",
        ]
    )


def _acceptance_criteria_for_category(category: str, scenarios: list[str]) -> list[str]:
    scenario_text = ", ".join(sc for sc in scenarios if sc != "GLOBAL") or "相关场景"
    if category == "上下文传递与完整解答契约":
        return [
            f"重新运行 validate-arch 后，{scenario_text} 不再因 `MISSING_PROBLEM_CONTEXT`、完整解答上下文缺失或完整解答 contract 失败。",
            "Solution Generation BC 的输入契约中能追溯到题目、会话、基础水平和解答请求原因。",
            "完整解答返回契约包含可展示状态和逐步推导内容字段。",
        ]
    if category == "场景入口与身份认证边界":
        return [
            f"重新运行 validate-arch 后，{scenario_text} 不再被路由到 Problem Intake BC 或 Tutoring Session BC 承接验证码职责。",
            "手机号登录、验证码校验、重发限制、连续错误失效均能映射到 User Identity BC。",
            "接口契约中声明验证码状态、失败次数、重发间隔和失效策略。",
        ]
    if category == "指标与可观测性契约":
        return [
            f"重新运行 validate-arch 后，{scenario_text} 不再因指标 owner、统计口径或查询接口缺失而失败。",
            "P95、交互比例、删除成功率均有 owner、数据来源、统计窗口、阈值和排除项。",
            "部署/可观测性文档能说明指标采集位置和告警责任。",
        ]
    if category == "数据保留与合规边界":
        return [
            f"重新运行 validate-arch 后，{scenario_text} 不再因保留期可读性、删除审计或合法数据流缺失而失败。",
            "Data Retention & Compliance BC 明确拥有保留策略、删除任务和审计日志。",
            "30 天前后可读性检查、删除事件和失败重试均有接口或事件契约。",
        ]
    return [
        f"重新运行 `contract-check` 后，{scenario_text} 不再出现相关 inbound required 字段弱校验或字段不一致问题。",
        "每个被触达 BC 均声明 inbound required_fields、outbound produced_fields、error_codes 和 next_hop。",
        "上游 produced_fields 能覆盖下游 required_fields。",
    ]


def _heading_slug(heading: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", heading.strip().lower(), flags=re.UNICODE)
    return slug.strip("-")


def _architecture_index(arch_path: str) -> list[dict[str, str]]:
    """Index only files/headings that are present in this run's architecture input."""
    root = Path(arch_path)
    paths = sorted(root.rglob("*.md")) if root.is_dir() else ([root] if root.is_file() else [])
    indexed: list[dict[str, str]] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        source_name = path.name
        saw_heading = False
        for line in lines:
            source_match = re.match(r"<!--\s*Source:\s*(.+?)\s*-->", line)
            if source_match:
                source_name = Path(source_match.group(1).strip()).name
                continue
            heading_match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
            if not heading_match:
                continue
            heading = heading_match.group(1).strip().strip("`")
            ref = source_name
            slug = _heading_slug(heading)
            if slug:
                ref += f"#{slug}"
            indexed.append({"file": source_name, "heading": heading, "ref": ref})
            saw_heading = True
        if not saw_heading:
            indexed.append({"file": source_name, "heading": "", "ref": source_name})
    # Aggregated inputs can repeat a heading; keep the first stable reference.
    return list({item["ref"]: item for item in indexed}.values())


def _target_files_for_finding(finding: dict[str, Any], arch_path: str) -> list[str]:
    index = _architecture_index(arch_path)
    if not index:
        return ["未定位（本次架构输入不可读取）"]
    hints = {
        "组件接口字段契约": ("interface", "contract", "api", "event", "接口", "契约", "事件"),
        "指标与可观测性契约": ("metric", "observ", "deploy", "指标", "可观测", "部署", "运维"),
        "数据保留与合规边界": ("data", "retention", "compliance", "数据", "保留", "合规", "隐私"),
        "状态机与生命周期": ("runtime", "state", "data", "运行", "状态", "数据", "生命周期"),
        "跨组件数据流": ("runtime", "flow", "component", "运行", "流程", "组件", "模块"),
    }.get(finding["category"], ())
    scored: list[tuple[int, str]] = []
    for item in index:
        text = f"{item['file']} {item['heading']}".lower()
        score = sum(1 for hint in hints if hint in text)
        if score:
            scored.append((score, item["ref"]))
    if scored:
        return [ref for _, ref in sorted(scored, key=lambda value: (-value[0], value[1]))[:4]]
    # An unresolved semantic target must still point at a real input file, never a
    # domain-specific file invented by the renderer.
    return sorted({item["file"] for item in index})[:1]


def _contract_stub_for_finding(finding: dict[str, Any]) -> str:
    components = finding.get("components", [])
    listed = ", ".join(components) if components else "TBD_FROM_ARCHITECTURE"
    return "\n".join(
        [
            "```yaml",
            "ArchitectureChange:",
            f"  category: {finding['category']}",
            f"  affected_components: [{listed}]",
            "  owner: TBD",
            "  contract_or_rule:",
            "    inputs: []",
            "    outputs: []",
            "    errors_or_branches: []",
            "  verification: rerun validate-arch for affected scenarios",
            "```",
        ]
    )


def _acceptance_criteria_for_finding(finding: dict[str, Any]) -> list[str]:
    scenarios = [sc for sc in finding.get("affected_scenarios", []) if sc != "GLOBAL"]
    scenario_text = ", ".join(scenarios) or "相关场景"
    return [
        f"重新运行 validate-arch 后，{scenario_text} 的同一根因不再出现。",
        "修改内容在实际架构文件中具有明确 owner、输入、输出、失败/分支规则和可验证证据。",
        "contract-check 与 strict audit 均通过，且未引入新的未解析 contract binding。",
    ]


def _confidence_for_finding(finding: dict[str, Any]) -> str:
    scenarios = [sc for sc in finding.get("affected_scenarios", []) if sc != "GLOBAL"]
    if finding.get("priority") == "high" and len(scenarios) >= 2:
        return "high"
    if finding.get("priority") == "high":
        return "medium"
    return "medium"


def _change_card_for_finding(
    finding: dict[str, Any],
    arch_path: str,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    category = finding["category"]
    scenarios = finding.get("affected_scenarios", [])
    components = finding.get("components", [])
    return {
        "finding_id": f"ARCH-{finding['fingerprint'].upper()}",
        "priority": finding["priority"],
        "category": category,
        "target_files": _target_files_for_finding(finding, arch_path),
        "current_gap": finding["reason"],
        "required_change": finding["action"],
        "contract_stub": _contract_stub_for_finding(finding),
        "affected_scenarios": scenarios,
        "occurrences": finding.get("occurrences", len(scenarios)),
        "acceptance_criteria": _acceptance_criteria_for_finding(finding),
        "evidence_ref": (
            evidence_refs
            if evidence_refs is not None
            else [
                "validation-report-diagnostics.md",
                "strict_audit.json",
                "compat.json",
                "hops.json",
            ]
        ),
        "confidence": _confidence_for_finding(finding),
    }


def render_architecture_report(
    *,
    feature_path: str,
    arch_path: str,
    hops_by_tc: dict[str, list[dict[str, Any]]],
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    component_names: list[str],
    strict_audit: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
) -> str:
    """Render the architecture-facing report only."""
    findings = build_architecture_findings(val_results, compat, hops_by_tc, component_names)
    scenario_ids = sorted({sc for f in findings for sc in f["affected_scenarios"] if sc != "GLOBAL"})
    components = sorted({c for f in findings for c in f.get("components", [])})
    priority_order = {"high": 0, "medium": 1, "low": 2}
    sorted_findings = sorted(findings, key=lambda f: (priority_order.get(f["priority"], 9), f["category"]))
    cards = [
        _change_card_for_finding(finding, arch_path, evidence_refs)
        for finding in sorted_findings
    ]

    lines: list[str] = [
        "# 架构设计修改报告",
        "",
        f"**架构文档**: {arch_path}",
        f"**Gherkin 源**: {feature_path}",
        f"**执行证据**: {_strict_evidence_line(strict_audit)}",
        "",
        "## 结论摘要",
        "",
        f"- 需要进入架构设计层处理的修改项: {len(findings)}",
        f"- 涉及场景: {', '.join(scenario_ids) if scenario_ids else '无'}",
        f"- 涉及组件: {', '.join(components) if components else '无'}",
        "",
    ]

    if cards:
        lines.extend(
            [
                "## 架构修改项总览",
                "",
                "| ID | 优先级 | 置信度 | 类别 | 合并证据数 | 目标文件/章节 | 影响场景 |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for card in cards:
            scenarios = ", ".join(card["affected_scenarios"])
            row = [
                card["finding_id"],
                card["priority"],
                card["confidence"],
                card["category"],
                card["occurrences"],
                "; ".join(card["target_files"]),
                scenarios,
            ]
            lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in row) + " |")
        lines.append("")
    else:
        lines.extend(["## 架构修改项", "", "未发现可归因到架构文档的修改项。", ""])

    if cards:
        lines.extend(["## Architecture Change Cards", ""])
        for card in cards:
            lines.extend(
                [
                    f"### {card['finding_id']} - {card['category']}",
                    "",
                    f"- **优先级**: {card['priority']}",
                    f"- **置信度**: {card['confidence']}",
                    f"- **合并证据数**: {card['occurrences']}",
                    f"- **影响场景**: {', '.join(card['affected_scenarios'])}",
                    "- **目标文件/章节**:",
                ]
            )
            for target in card["target_files"]:
                lines.append(f"  - `{target}`")
            lines.extend(
                [
                    f"- **当前缺口**: {card['current_gap']}",
                    f"- **必须修改**: {card['required_change']}",
                    "- **契约草案**:",
                    "",
                    card["contract_stub"],
                    "",
                    "- **验收标准**:",
                ]
            )
            for criterion in card["acceptance_criteria"]:
                lines.append(f"  - {criterion}")
            if card["evidence_ref"]:
                lines.extend(["- **证据引用**:"])
                for ref in card["evidence_ref"]:
                    lines.append(f"  - `{ref}`")
            lines.append("")

    heatmap = build_component_heatmap(
        hops_by_tc, val_results, compat, component_names, architecture_only=True
    )
    if heatmap:
        lines.append("## 架构影响组件概览")
        lines.append("")
        lines.append("| 组件 | 相关架构问题场景数 | 主要维度 |")
        lines.append("|---|---|---|")
        for comp, data in sorted(heatmap.items(), key=lambda x: x[1]["total"], reverse=True):
            dims = []
            for dim, counts in data["dims"].items():
                total = counts.get("fail", 0) + counts.get("warning", 0)
                if total:
                    dims.append(f"{dim}:{total}")
            lines.append(f"| {comp} | {data['total']} | {', '.join(dims)} |")
        lines.append("")

    return "\n".join(lines)


def render_diagnostics_report(
    *,
    feature_path: str,
    arch_path: str,
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    component_names: list[str],
    strict_audit: dict[str, Any] | None = None,
) -> str:
    diagnostics = build_diagnostics(val_results, compat, component_names)
    lines: list[str] = [
        "# validate-arch 内部诊断报告",
        "",
        f"**架构文档**: {arch_path}",
        f"**Gherkin 源**: {feature_path}",
        f"**执行证据**: {_strict_evidence_line(strict_audit)}",
        "",
        "本报告记录被架构层交付报告剔除的内容，用于改进模拟、validator prompt、场景输入或后续模块设计。",
        "",
    ]
    titles = {
        "validation_process": "验证流程问题",
        "scenario_input": "场景输入/夹具问题",
        "module_detail": "模块详细设计问题",
        "raw_evidence": "全部原始异常证据（未聚合）",
    }
    for kind, title in titles.items():
        items = diagnostics[kind]
        lines.extend([f"## {title}", ""])
        if not items:
            lines.extend(["无。", ""])
            continue
        lines.extend(["| 场景 | 维度 | 状态 | 详情 |", "|---|---|---|---|"])
        for item in items:
            lines.append(
                "| "
                + " | ".join(
                    str(item[k]).replace("|", "\\|").replace("\n", " ")
                    for k in ("test_case_id", "dimension", "status", "detail")
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines)


def build_enhancement_sections(
    hops_by_tc: dict[str, list[dict[str, Any]]],
    val_results: list[dict[str, Any]],
    compat: dict[str, Any],
    component_names: list[str],
    *,
    audience: str = "full",
) -> str:
    """Return Markdown string with heatmap and modification mapping, or empty string."""
    architecture_only = audience == "architecture"
    heatmap = build_component_heatmap(
        hops_by_tc, val_results, compat, component_names, architecture_only=architecture_only
    )
    modifications = build_modifications(val_results, compat, hops_by_tc, component_names)
    for mod in modifications:
        mod["scope"] = _classify_mod_scope(mod)

    sections: list[str] = []
    if heatmap:
        sections.append(format_heatmap_markdown(heatmap))

    top_mods = [m for m in modifications if m.get("scope") == "top_level"]
    module_mods = [m for m in modifications if m.get("scope") == "module" and not architecture_only]

    if top_mods:
        sections.append(
            format_modifications_markdown(top_mods, title="架构文档修改建议映射（最顶层）")
        )
    if module_mods:
        sections.append(
            format_modifications_markdown(module_mods, title="留待模块设计阶段验证的修改点")
        )

    if not sections:
        return ""
    return "\n\n" + "\n\n".join(sections) + "\n"
