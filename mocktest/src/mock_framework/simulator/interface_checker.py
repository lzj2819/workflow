"""确定性的组件间接口兼容/连通性检查器。

输入是一次场景走链的 HopResult 列表 + 组件卡片 + 架构 then 期望，
输出 interface_compat 维度结果与全局发现。纯函数、无 LLM、可复现。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CompatFinding:
    """单条接口兼容性发现。"""

    kind: str  # missing_field | missing_contract | undefined_edge | unreachable_expectation | orphan_component
    severity: str  # FAIL | WARNING
    detail: str


@dataclass
class CompatResult:
    """单场景接口兼容性汇总。"""

    status: str  # PASS | FAIL | WARNING
    detail: str
    findings: list[CompatFinding] = field(default_factory=list)


def _contract_fields(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value:
        return [value]
    return []


def _contract_key(interface: dict[str, Any]) -> str:
    contract = interface.get("contract") or {}
    return str(contract.get("contract_id") or interface.get("name") or "")


def _binding_result(
    status: str,
    *,
    interface: Optional[dict[str, Any]] = None,
    candidates: Optional[list[str]] = None,
    reason: str,
    binding_role: str = "unknown",
) -> dict[str, Any]:
    interface = interface or {}
    contract = interface.get("contract") or {}
    contract_required = _contract_fields(contract.get("required"))
    response_fields = _contract_fields(contract.get("response") or contract.get("produced"))
    required_fields = contract_required if binding_role != "consumer" else []
    accepted_fields = response_fields if binding_role == "consumer" else contract_required
    return {
        "status": status,
        "contract_id": _contract_key(interface),
        "interface_name": str(interface.get("name") or ""),
        "protocol": str(interface.get("protocol") or ""),
        "binding_kind": str(contract.get("binding_kind") or "machine_contract"),
        "architecture_declared": contract.get("architecture_declared", True),
        "binding_role": binding_role,
        "required_fields": required_fields,
        "provider_required_fields": contract_required,
        "accepted_fields": accepted_fields,
        "response_fields": response_fields,
        "candidates": candidates or [],
        "reason": reason,
        "contract": contract if status == "resolved" else {},
    }


def _component_scope_binding(
    card: dict[str, Any],
    *,
    candidates: Optional[list[str]] = None,
    reason: str,
) -> dict[str, Any]:
    """Represent a trusted component entry with no unique public contract."""
    component = str(card.get("name") or "").strip()
    interface = {
        "name": f"component-scope://{component}",
        "protocol": "component_scope",
        "contract": {
            "contract_id": f"component-scope://{component}",
            "contract_type": "component_scope",
            "provider": component,
            "binding_kind": "component_scope",
            "architecture_declared": False,
        },
    }
    return _binding_result(
        "resolved",
        interface=interface,
        candidates=candidates,
        reason=reason,
        binding_role="provider",
    )


def _consumer_names(value: Any) -> set[str]:
    """Split a contract consumer declaration into exact component names."""
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = re.split(r"[,，、;；\n]+", str(value or ""))
    return {item.strip() for item in raw_items if item.strip()}


def _binding_role(interface: dict[str, Any], component: str) -> str:
    contract = interface.get("contract") or {}
    provider = str(contract.get("provider") or "").strip()
    consumer_text = str(contract.get("consumer") or "")
    if provider == component:
        return "provider"
    if component in _consumer_names(contract.get("consumer")) or "内部子节点" in consumer_text:
        return "consumer"
    return "unknown"


def resolve_contract_binding(
    card: Optional[dict[str, Any]],
    *,
    action: str = "",
    contract_id: str = "",
    input_message: Optional[dict[str, Any]] = None,
    allow_component_scope: bool = False,
) -> dict[str, Any]:
    """Resolve one contract owned or consumed by a component hop."""
    if not card:
        return _binding_result("unresolved", reason="component card missing")

    unique: dict[str, dict[str, Any]] = {}
    for interface in card.get("inbound_interfaces", []) + card.get("outbound_interfaces", []):
        contract = interface.get("contract") or {}
        key = _contract_key(interface)
        if key and contract:
            unique.setdefault(key, interface)

    component = str(card.get("name") or "")
    requested_id = str(contract_id or "").strip()
    if requested_id.startswith("component-scope://"):
        expected = f"component-scope://{component}"
        if requested_id == expected:
            return _component_scope_binding(
                card,
                reason="explicit component-scope entry binding",
            )
        return _binding_result(
            "unresolved",
            candidates=[expected],
            reason=f"component-scope binding does not match component: {requested_id}",
        )

    owned = [
        interface
        for interface in unique.values()
        if str((interface.get("contract") or {}).get("provider") or "").strip() == component
    ]
    candidates = owned or list(unique.values())
    candidate_ids = sorted(_contract_key(interface) for interface in candidates)
    all_candidate_ids = sorted(_contract_key(interface) for interface in unique.values())
    if not candidates:
        if allow_component_scope:
            return _component_scope_binding(
                card,
                reason="component entry resolved; no machine-readable contract declared",
            )
        return _binding_result(
            "unresolved", candidates=[], reason="no machine-readable contract candidate"
        )

    if requested_id:
        exact = [item for item in candidates if _contract_key(item) == requested_id]
        if len(exact) == 1:
            return _binding_result(
                "resolved",
                interface=exact[0],
                reason="explicit contract_id match",
                binding_role=_binding_role(exact[0], component),
            )
        inbound = [
            item
            for item in unique.values()
            if _contract_key(item) == requested_id and _binding_role(item, component) == "consumer"
        ]
        if len(inbound) == 1:
            return _binding_result(
                "resolved",
                interface=inbound[0],
                reason="explicit inbound contract_id match",
                binding_role="consumer",
            )
        return _binding_result(
            "unresolved",
            candidates=all_candidate_ids,
            reason=f"contract_id not connected to component: {requested_id}",
        )

    evidence = " ".join(
        [
            str(action or ""),
            str((input_message or {}).get("event") or ""),
            str((input_message or {}).get("when") or ""),
            str((input_message or {}).get("contract_id") or ""),
        ]
    ).lower()
    normalized_evidence = re.sub(r"[^a-z0-9]+", "", evidence)
    scored: list[tuple[int, dict[str, Any]]] = []
    for interface in candidates:
        key = _contract_key(interface).lower()
        normalized_key = re.sub(r"[^a-z0-9]+", "", key)
        score = 10 if normalized_key and normalized_key in normalized_evidence else 0
        score += sum(
            2 for token in re.findall(r"[a-z0-9]+", key) if len(token) >= 3 and token in evidence
        )
        if score:
            scored.append((score, interface))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score = scored[0][0]
        best = [interface for score, interface in scored if score == best_score]
        if len(best) == 1:
            return _binding_result(
                "resolved",
                interface=best[0],
                reason="action/message contract match",
                binding_role=_binding_role(best[0], component),
            )
        internal = [
            interface
            for interface in best
            if str(interface.get("protocol") or "") == "internal_port"
        ]
        if len(internal) == 1:
            return _binding_result(
                "resolved",
                interface=internal[0],
                reason="preferred internal contract among tied matches",
                binding_role=_binding_role(internal[0], component),
            )
        if allow_component_scope:
            return _component_scope_binding(
                card,
                candidates=sorted(_contract_key(item) for item in best),
                reason=(
                    "component entry resolved; multiple machine contracts match "
                    "the entry action, so validation starts at the component boundary"
                ),
            )
        return _binding_result(
            "ambiguous",
            candidates=sorted(_contract_key(item) for item in best),
            reason="multiple contracts match action/message",
        )

    if len(candidates) == 1:
        return _binding_result(
            "resolved",
            interface=candidates[0],
            reason="sole provider-owned contract",
            binding_role=_binding_role(candidates[0], component),
        )
    internal = [
        interface
        for interface in candidates
        if str(interface.get("protocol") or "") == "internal_port"
    ]
    if len(internal) == 1:
        return _binding_result(
            "resolved",
            interface=internal[0],
            reason="preferred internal contract among provider-owned candidates",
            binding_role=_binding_role(internal[0], component),
        )
    if allow_component_scope:
        return _component_scope_binding(
            card,
            candidates=candidate_ids,
            reason=(
                "component entry resolved; multiple machine contracts remain "
                "ambiguous, so validation starts at the component boundary"
            ),
        )
    return _binding_result(
        "ambiguous",
        candidates=candidate_ids,
        reason="multiple provider-owned contracts and no unique action match",
    )


def _resolve_dotted_field(output: dict[str, Any], field: str) -> bool:
    """检查嵌套 dict/list 中是否存在 dotted path。

    支持两种数组索引写法：
    - `generated_layers.0.layer_type`
    - `generated_layers[0].layer_type`

    如果顶层找不到且 output 包含 `payload`，会尝试到 `payload` 下查找
    （兼容部分组件把业务字段包在 payload 中的写法）。
    """
    return _resolve_dotted_field_impl(output, field) or (
        isinstance(output, dict)
        and "payload" in output
        and _resolve_dotted_field_impl(output["payload"], field)
    )


def _resolve_dotted_field_impl(obj: Any, field: str) -> bool:
    parts = _split_field_path(field)
    current: Any = obj
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return False
            current = current[part]
        elif isinstance(current, list):
            if not isinstance(part, int) or part < 0 or part >= len(current):
                return False
            current = current[part]
        else:
            return False
    return True


def _split_field_path(field: str) -> list[str | int]:
    """把字段路径拆成 dict key / list index 混合列表。"""
    parts: list[str | int] = []
    for raw in re.split(r"\.|\[|\]", field):
        raw = raw.strip()
        if not raw:
            continue
        if raw.isdigit():
            parts.append(int(raw))
        else:
            parts.append(raw)
    return parts


def _flatten_keys(obj: Any, prefix: str = "") -> set[str]:
    """把嵌套 dict/list 的 key 展平成 dotted path 集合。"""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            keys.add(path)
            keys |= _flatten_keys(v, path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            path = f"{prefix}[{i}]" if prefix else f"[{i}]"
            keys.add(path)
            keys |= _flatten_keys(item, path)
    return keys


# 这些前缀/字段属于 agent 自检元数据，不属于组件对外接口字段，
# 不应参与接口兼容性检查。
_INTERNAL_VERIFICATION_PREFIXES: tuple[str, ...] = (
    "assertions_checked",
    "assertion_results",
    "verification_results",
    "then_verifications",
    "verification_status",
    "metric_assertion_passed",
    "overall_assertion",
    "all_passed",
    "all_assertions_passed",
)


def _is_internal_verification_field(field: str) -> bool:
    """判断字段路径是否属于自检元数据，不应作为接口字段。"""
    first = field.split(".")[0].split("[")[0]
    return first.startswith(_INTERNAL_VERIFICATION_PREFIXES) or field in {
        "threshold",
        "actual_value",
        "expected",
    }


def _check_output_message_matches_produced_fields(hop: dict[str, Any]) -> list[CompatFinding]:
    """检查 self_check.produced_fields 是否真实出现在 output_message 中（支持 nested path）。"""
    findings: list[CompatFinding] = []
    produced = hop.get("self_check", {}).get("produced_fields") or []
    output = hop.get("output_message") or {}
    if not isinstance(output, dict):
        output = {}
    flattened = _flatten_keys(output)
    for field in produced:
        if _is_internal_verification_field(field):
            continue
        if _resolve_dotted_field(output, field) or field in flattened:
            continue
        findings.append(
            CompatFinding(
                kind="missing_field",
                severity="FAIL",
                detail=f"{hop['component']} 声称产出字段 {field}，但 output_message 中不存在",
            )
        )
    return findings


def validate_state_transitions(
    hops: list[dict[str, Any]],
    component_cards: dict[str, dict[str, Any]],
    state_machine: Any,
    entity_owners: Optional[dict[str, str]] = None,
) -> list[CompatFinding]:
    """集中式状态机权威校验。

    - 组件只能修改架构明确声明由其拥有的实体。
    - 转换必须出现在架构状态机定义中。
    - from_state 必须等于该实体当前状态（首跳允许从任意状态开始）。
    """
    findings: list[CompatFinding] = []
    if not state_machine or not getattr(state_machine, "transitions", None):
        return findings

    valid_transitions = {(t.from_state, t.to_state, t.trigger) for t in state_machine.transitions}
    entity_current_state: dict[str, str] = {}

    for hop in hops:
        sc = hop.get("state_change")
        if not isinstance(sc, dict) or not sc.get("entity"):
            continue
        entity = sc["entity"]
        from_state = sc.get("from_state", "")
        to_state = sc.get("to_state", "")
        trigger = sc.get("trigger", "")
        component = hop.get("component", "")

        # 1. 组件权威：只信任显式 ownership，不按名称包含关系猜测。
        owner = (entity_owners or {}).get(entity)
        if owner and owner != component:
            findings.append(
                CompatFinding(
                    kind="state_authority",
                    severity="FAIL",
                    detail=f"{component} 无权修改实体 {entity}（架构 owner={owner}）",
                )
            )
        elif not owner:
            findings.append(
                CompatFinding(
                    kind="state_authority_unresolved",
                    severity="WARNING",
                    detail=f"validate_arch 缺少实体 {entity} 的显式 owner，未执行权威判定",
                )
            )

        # 2. 转换合法
        if (from_state, to_state, trigger) not in valid_transitions:
            findings.append(
                CompatFinding(
                    kind="invalid_state_transition",
                    severity="FAIL",
                    detail=f"{component} 报告非法状态转换 ({from_state} -> {to_state}, trigger={trigger})",
                )
            )

        # 3. 状态连续
        if entity in entity_current_state and entity_current_state[entity] != from_state:
            findings.append(
                CompatFinding(
                    kind="state_continuity",
                    severity="FAIL",
                    detail=f"{entity} 状态不连续：期望 from_state={entity_current_state[entity]}，实际 {from_state}",
                )
            )

        entity_current_state[entity] = to_state

    return findings


def _check_then_content_assertions(
    hops: list[dict[str, Any]], then_expectations: list[dict[str, Any]]
) -> list[CompatFinding]:
    """轻量内容级 then 断言检查（不依赖 LLM）。"""
    findings: list[CompatFinding] = []
    then_hops_by_comp: dict[str, list[dict[str, Any]]] = {}
    for h in hops:
        if h.get("phase") == "then":
            then_hops_by_comp.setdefault(h["component"], []).append(h)

    for exp in then_expectations:
        assertion = exp.get("assertion", "")
        comp = exp.get("component", "")
        if not assertion or not comp:
            continue
        for h in then_hops_by_comp.get(comp, []):
            output = h.get("output_message") or {}
            content = str(output.get("content", output.get("message", output)))
            if "不包含完整答案" in assertion and any(
                kw in content for kw in ("完整答案", "答案是", "最终答案", "解为")
            ):
                findings.append(
                    CompatFinding(
                        kind="content_violation",
                        severity="FAIL",
                        detail=f"{comp} 的 then 断言要求不包含完整答案，但 output 疑似包含",
                    )
                )
            if "返回完整步骤解析" in assertion and not any(
                kw in content for kw in ("步骤", "解析", "Step", "solution")
            ):
                findings.append(
                    CompatFinding(
                        kind="content_violation",
                        severity="FAIL",
                        detail=f"{comp} 的 then 断言要求返回完整步骤解析，但 output 中未找到",
                    )
                )
    return findings


def check_scenario(
    hops: list[dict[str, Any]],
    component_cards: dict[str, dict[str, Any]],
    then_expectations: list[dict[str, Any]],
    *,
    emit_missing_contract: bool = True,
) -> CompatResult:
    """检查单场景走链的接口兼容性。

    hops 每项需含: component, output_message(dict), self_check.produced_fields(list),
    可选 inferred(bool), self_check.undefined_next_call(str|None), phase(str)。
    component_cards[name].inbound_interfaces[].contract.required 是下游必需字段。
    """
    findings: list[CompatFinding] = []
    reached = {h["component"] for h in hops}

    for hop in hops:
        binding = hop.get("contract_binding")
        if not isinstance(binding, dict) or binding.get("status") == "resolved":
            continue
        findings.append(
            CompatFinding(
                kind="ambiguous_contract_binding",
                severity="WARNING",
                detail=(
                    f"validate_arch 无法为 {hop.get('component', '')}/{hop.get('action', '')} "
                    f"绑定唯一契约：{binding.get('reason', '')} "
                    f"candidates={binding.get('candidates', [])}"
                ),
            )
        )

    # 相邻跳字段契约比对
    for up, down in zip(hops, hops[1:]):
        produced = set(up.get("self_check", {}).get("produced_fields", []))
        produced |= _flatten_keys(up.get("output_message") or {})
        down_card = component_cards.get(down["component"])
        binding = down.get("contract_binding")
        has_resolved_binding = False
        if isinstance(binding, dict):
            if binding.get("status") != "resolved":
                continue
            has_resolved_binding = True
            required = _contract_fields(binding.get("required_fields"))
        else:
            required = _required_inbound_fields(down_card)
        if down_card is not None and not required:
            if emit_missing_contract and not has_resolved_binding:
                findings.append(
                    CompatFinding(
                        kind="missing_contract",
                        severity="WARNING",
                        detail=f"{down['component']} 缺少 inbound required 字段契约，无法做强字段校验",
                    )
                )
            continue
        missing = [
            f
            for f in required
            if not _resolve_dotted_field(up.get("output_message") or {}, f) and f not in produced
        ]
        if missing:
            findings.append(
                CompatFinding(
                    kind="missing_field",
                    severity="FAIL",
                    detail=f"{down['component']} 入参缺字段 {missing}（上游 {up['component']} 未产出）",
                )
            )

    # produced_fields 与 output_message 一致性
    for h in hops:
        findings.extend(_check_output_message_matches_produced_fields(h))

    # 内容级 then 断言检查
    findings.extend(_check_then_content_assertions(hops, then_expectations))

    # 未定义边
    for h in hops:
        if h.get("inferred"):
            findings.append(
                CompatFinding(
                    kind="undefined_edge",
                    severity="WARNING",
                    detail=f"{h['component']} 走的是架构未定义的推断边",
                )
            )
        und = h.get("self_check", {}).get("undefined_next_call")
        if und:
            findings.append(
                CompatFinding(
                    kind="undefined_edge",
                    severity="FAIL",
                    detail=f"{h['component']} 试图调用架构未定义的 {und}",
                )
            )

    # 断流：then 期望组件未触达
    for exp in then_expectations:
        comp = exp.get("component")
        if comp and comp not in reached:
            findings.append(
                CompatFinding(
                    kind="unreachable_expectation",
                    severity="FAIL",
                    detail=f"then 期望的组件 {comp} 在走链中不可达",
                )
            )

    return _aggregate(findings)


def _normalize_component_name(name: str) -> str:
    """归一化组件名，用于忽略空格/大小写/后缀差异。"""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def check_orphans(
    all_reached: set[str], component_cards: dict[str, dict[str, Any]]
) -> list[CompatFinding]:
    """全局：架构里从未被任何场景触达的组件。"""
    findings: list[CompatFinding] = []
    reached_norm = {_normalize_component_name(n) for n in all_reached}
    seen: set[str] = set()
    for name in component_cards:
        norm = _normalize_component_name(name)
        if norm in reached_norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        findings.append(
            CompatFinding(
                kind="orphan_component",
                severity="WARNING",
                detail=f"组件 {name} 从未被任何场景触达（孤儿组件）",
            )
        )
    return findings


def check_contract_coverage(
    component_cards: dict[str, dict[str, Any]],
    components: set[str] | None = None,
) -> list[CompatFinding]:
    """全局：组件缺少 machine-readable inbound required 字段契约。"""
    findings: list[CompatFinding] = []
    seen: set[str] = set()
    names = sorted(components or set(component_cards.keys()))
    for name in names:
        card = component_cards.get(name)
        if not card or _required_inbound_fields(card):
            continue
        norm = _normalize_component_name(name)
        if norm in seen:
            continue
        seen.add(norm)
        findings.append(
            CompatFinding(
                kind="contract_coverage_gap",
                severity="WARNING",
                detail=f"{name} 缺少 machine-readable inbound required 字段契约，已按全局契约覆盖缺口记录",
            )
        )
    return findings


def _required_inbound_fields(card: Optional[dict[str, Any]]) -> list[str]:
    if not card:
        return []
    req: list[str] = []
    for itf in card.get("inbound_interfaces", []):
        contract = itf.get("contract") or {}
        req.extend(contract.get("required", []))
    return req


def _aggregate(findings: list[CompatFinding]) -> CompatResult:
    if any(f.severity == "FAIL" for f in findings):
        status = "FAIL"
    elif findings:
        status = "WARNING"
    else:
        status = "PASS"
    detail = "; ".join(f.detail for f in findings) or "所有相邻跳契约相容，触达组件可达"
    return CompatResult(status=status, detail=detail, findings=findings)


def demo() -> None:
    """最小自检：缺字段 → FAIL；全相容 → PASS；孤儿 → WARNING。"""
    cards: dict[str, dict[str, Any]] = {
        "A": {"inbound_interfaces": []},
        "B": {"inbound_interfaces": [{"contract": {"required": ["x"]}}]},
    }
    bad: CompatResult = check_scenario(
        [
            {"component": "A", "output_message": {}, "self_check": {"produced_fields": []}},
            {"component": "B", "output_message": {}, "self_check": {"produced_fields": []}},
        ],
        cards,
        [],
    )
    assert bad.status == "FAIL", bad
    good: CompatResult = check_scenario(
        [
            {
                "component": "A",
                "output_message": {"x": 1},
                "self_check": {"produced_fields": ["x"]},
            },
            {"component": "B", "output_message": {}, "self_check": {"produced_fields": []}},
        ],
        cards,
        [],
    )
    assert good.status == "PASS", good
    orphans: list[CompatFinding] = check_orphans({"A"}, cards)
    assert any(f.kind == "orphan_component" for f in orphans), orphans
    print("interface_checker demo OK")


if __name__ == "__main__":
    demo()
