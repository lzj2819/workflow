"""Subagent-mode helper for the validate-arch skill.

This script is invoked by the current Codex session when running in subagent
mode. It handles the deterministic parts of the validate-arch workflow
(loading, prompt preparation, report rendering) while the LLM-heavy simulator
and validator reasoning is dispatched to Codex subagents.

There is no direct-LLM fallback: every component hop and every validator
judgment must be executed by an independent Codex subagent. Use
`simulate-step-prompt` to build the prompt for a single hop, spawn a subagent
with that prompt, and chain hops in the current session.

Usage:

  # 1. 准备：组件卡片 + 各场景逐跳执行计划
  python run_subagent_skill.py prepare --feature X.feature --arch arch.md --output plan.json

  # 2. 会话按 plan.json 的 hops 逐跳派组件 subagent，产出 {test_case_id: [HopResult...]} 写入 hops.json
  #    （使用 simulate-step-prompt 为每跳生成 prompt，再由当前会话派独立 subagent）

  # 3. 确定性接口检查（interface_compat 第 6 维）
  python run_subagent_skill.py contract-check --prompts plan.json --hops hops.json --output compat.json

  # 4. 生成 validator prompts（由 hops 重建 trace）
  python run_subagent_skill.py fill-validator-prompts --prompts plan.json --hops hops.json --output plan_with_val.json

  # 5. 会话按场景派 validator subagent，结果写 val-results.json

  # 6. 生成报告（合并 interface_compat + 数据流流转段 + 全局发现）
  python run_subagent_skill.py report --prompts plan_with_val.json --val-results val-results.json --compat compat.json --hops hops.json --output report.md
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

# Make project source importable regardless of CWD.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[
    2
]  # .agents/skills/validate-arch -> .agents/skills -> .agents -> repo-root
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(SCRIPT_DIR))

from mock_framework.config import load_config
from mock_framework.improvement.report_renderer import ReportRenderer
from mock_framework.loader import Loader
from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc
from mock_framework.models.simulator import (
    ExecutionTrace,
    TraceStep,
    SideEffect,
    StateTransitionRecord,
)
from mock_framework.models.validator import ValidationResult
from mock_framework.mocktest_protocol import (
    ArtifactRecord,
    FormalInputManifest,
    NormalizedArchitecture,
    NormalizedTestcases,
    exit_code_for_report,
    formal_protocol_metadata,
    load_formal_input_manifest,
    publish_strict_run,
    resolve_formal_sources,
    write_schemas,
)
from mock_framework.simulator.interface_checker import (
    check_contract_coverage,
    check_orphans,
    check_scenario,
    resolve_contract_binding,
    validate_state_transitions,
)
from mock_framework.skills.validate_arch import ValidateArchSkill
from mock_framework.validator.agent_core import ValidatorAgentCore
from mock_framework.validator.report_assembler import ReportAssembler

import report_enhancements

TRACE_SCHEMA_VERSION = "validate-arch-trace-v2"
PROMPT_SCHEMA_VERSION = "validate-arch-prompt-v3"


def _resolve_input_arguments(
    args: argparse.Namespace,
) -> tuple[str, str, FormalInputManifest | None, str | None]:
    manifest_path = getattr(args, "input_manifest", None)
    if manifest_path:
        if getattr(args, "feature", None) or getattr(args, "arch", None):
            raise ValueError("--input-manifest cannot be combined with --feature/--arch")
        manifest, resolved_manifest = load_formal_input_manifest(manifest_path)
        arch_path, feature_path = resolve_formal_sources(manifest, resolved_manifest)
        return feature_path, arch_path, manifest, str(resolved_manifest)
    if not getattr(args, "feature", None) or not getattr(args, "arch", None):
        raise ValueError("provide --input-manifest or both --feature and --arch")
    return str(args.feature), str(args.arch), None, None


def _feature_files(path: str | Path) -> list[Path]:
    target = Path(path)
    files = sorted(target.glob("*.feature")) if target.is_dir() else [target]
    if not files:
        raise ValueError(f"no .feature files found: {target}")
    return files


def _sha256_path(path: str | Path) -> str:
    target = Path(path)
    if target.is_file():
        return hashlib.sha256(target.read_bytes()).hexdigest()
    digest = hashlib.sha256()
    for item in sorted((p for p in target.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        digest.update(item.relative_to(target).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_run_manifest(
    feature_path: str,
    arch_path: str,
    effective_arch_path: str,
    config_path: str | None = None,
) -> dict[str, Any]:
    inputs = {
        "feature": {
            "path": str(Path(feature_path).resolve()),
            "sha256": _sha256_path(feature_path),
        },
        "architecture": {
            "path": str(Path(arch_path).resolve()),
            "sha256": _sha256_path(arch_path),
        },
        "effective_architecture": {
            "path": str(Path(effective_arch_path).resolve()),
            "sha256": _sha256_path(effective_arch_path),
        },
    }
    if config_path and Path(config_path).exists():
        inputs["config"] = {
            "path": str(Path(config_path).resolve()),
            "sha256": _sha256_path(config_path),
        }
    package_manifest = Path(arch_path) / "architecture-manifest.yaml"
    if package_manifest.is_file():
        inputs["package_manifest"] = {
            "path": str(package_manifest.resolve()),
            "sha256": _sha256_path(package_manifest),
        }
    canonical = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": "validate-arch-run-v1",
        "run_id": hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16],
        "inputs": inputs,
    }


def run_manifest_errors(prompts_data: dict[str, Any]) -> list[str]:
    manifest = prompts_data.get("run_manifest")
    if not manifest:
        return []
    errors: list[str] = []
    if manifest.get("schema_version") != "validate-arch-run-v1":
        errors.append("run manifest schema mismatch")
    for name, item in (manifest.get("inputs") or {}).items():
        path = Path(str(item.get("path") or ""))
        if not path.exists():
            errors.append(f"run manifest input missing: {name}")
            continue
        actual = _sha256_path(path)
        if actual != item.get("sha256"):
            errors.append(f"run manifest hash mismatch: {name}")
    return errors


def build_scenario_cache_key(
    tc_summary: dict[str, Any],
    plan_item: dict[str, Any],
    run_manifest: dict[str, Any],
    model_context: dict[str, Any],
    architecture_dependency: dict[str, Any] | None = None,
) -> str:
    """Hash every input that can change one scenario's hops or judgment."""
    effective_arch = (run_manifest.get("inputs") or {}).get("effective_architecture") or {}
    payload = {
        "trace_schema": TRACE_SCHEMA_VERSION,
        "prompt_schema": PROMPT_SCHEMA_VERSION,
        "feature_case": tc_summary,
        "execution_plan": {
            key: value
            for key, value in plan_item.items()
            if key not in {"validator_prompt", "deterministic_verdicts", "cache_provenance"}
        },
        "architecture_dependency": architecture_dependency,
        "architecture_sha256": (
            "" if architecture_dependency is not None else effective_arch.get("sha256", "")
        ),
        "models": model_context,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_scenario_architecture_dependency(
    entry_component: str,
    component_cards: dict[str, dict[str, Any]],
    data_flow_summary: list[dict[str, Any]],
    arch_doc: ArchDoc,
) -> dict[str, Any]:
    """Return the parsed architecture slice reachable from one scenario entry."""
    reachable = {entry_component} if entry_component in component_cards else set(component_cards)
    changed = True
    while changed:
        changed = False
        for edge in data_flow_summary:
            source = str(edge.get("from") or "")
            target = str(edge.get("to") or "")
            if source in reachable and target in component_cards and target not in reachable:
                reachable.add(target)
                changed = True
    relevant_edges = [
        edge
        for edge in data_flow_summary
        if edge.get("from") in reachable or edge.get("to") in reachable
    ]
    return {
        "components": {name: component_cards[name] for name in sorted(reachable)},
        "data_flow": relevant_edges,
        "state_machine": arch_doc.state_machine.model_dump(mode="json"),
        "entity_owners": arch_doc.entity_owners,
        "nfrs": [nfr.model_dump(mode="json") for nfr in arch_doc.nfrs],
    }


def assign_strict_equivalence_groups(
    test_case_summaries: list[dict[str, Any]], plans: list[dict[str, Any]]
) -> dict[str, Any]:
    """Group only Outline rows whose concrete execution evidence is identical."""
    tc_by_id = {tc["test_case_id"]: tc for tc in test_case_summaries}
    groups: dict[str, list[dict[str, Any]]] = {}
    for plan in plans:
        tc = tc_by_id.get(plan["test_case_id"], {})
        gherkin = tc.get("gherkin") or {}
        if not gherkin.get("parameters"):
            continue
        payload = {
            # Parameters and IDs are excluded only because every concrete step below
            # must already be byte-identical; changed parameter effects therefore
            # cannot be hidden from the proof.
            "feature": gherkin.get("feature"),
            "scenario": gherkin.get("scenario"),
            "steps": gherkin.get("steps", []),
            "tags": tc.get("tags", []),
            "technical_mapping": tc.get("technical_mapping", {}),
            "expectations": tc.get("expectations", {}),
            "execution_plan": {
                key: value
                for key, value in plan.items()
                if key
                not in {
                    "test_case_id",
                    "scenario_name",
                    "cache_key",
                    "cache_provenance",
                    "validator_prompt",
                    "deterministic_verdicts",
                    "equivalence",
                }
            },
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        groups.setdefault(key, []).append(plan)

    reusable_groups = 0
    reusable_rows = 0
    for key, members in groups.items():
        if len(members) < 2:
            continue
        reusable_groups += 1
        representative = members[0]["test_case_id"]
        for member in members:
            member["equivalence"] = {
                "mode": "strict",
                "key": key,
                "representative": representative,
                "is_representative": member["test_case_id"] == representative,
                "proof": "identical concrete Gherkin steps, mappings, expectations, tags, and execution plan",
            }
        reusable_rows += len(members) - 1
    return {
        "mode": "strict",
        "groups": reusable_groups,
        "reusable_rows": reusable_rows,
        "fallback_rows": len(plans) - reusable_rows,
    }


def _parse_arch_doc(arch_path: str) -> ArchDoc:
    """Read and parse an architecture document."""
    from mock_framework.loader.arch_doc_parser import ArchDocParser

    return ArchDocParser().parse(arch_path)


_PACKAGE_COMPONENT_TERMS = {
    "输入": "input",
    "窗口": "window",
    "字段": "field",
    "规范化": "normalizer",
    "标准化": "normalizer",
    "去重": "deduplicator",
    "约束": "constraint",
    "求值": "assessor",
    "评估": "assessor",
    "结果": "result",
    "装配": "assembler",
    "诊断": "diagnostic",
    "边界": "boundary",
    "解析": "resolver",
    "外呼": "outbound",
    "执行": "executor",
    "历史": "history",
    "适配": "adapter",
    "推荐": "recommendation",
    "编排": "orchestration",
    "配置": "configuration",
    "治理": "governance",
    "画像": "profile",
    "智能": "intelligence",
    "隐私": "privacy",
    "生命周期": "lifecycle",
}


def _markdown_table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _resolve_package_component_label(label: str, component_ids: list[str]) -> str:
    """Map a human-readable recursive-package label to one authoritative child_id."""
    cleaned = re.sub(r"[`（(].*?[）)]", "", label).strip(" `")
    direct = {component_id.lower(): component_id for component_id in component_ids}
    if cleaned.lower() in direct:
        return direct[cleaned.lower()]

    terms = set(re.findall(r"[a-z0-9]+", cleaned.lower()))
    terms.update(
        english for chinese, english in _PACKAGE_COMPONENT_TERMS.items() if chinese in cleaned
    )
    if not terms:
        return cleaned
    scored = sorted(
        (
            len(terms & set(re.findall(r"[a-z0-9]+", component_id.lower()))),
            component_id,
        )
        for component_id in component_ids
    )
    if scored and scored[-1][0] > 0 and (len(scored) == 1 or scored[-1][0] > scored[-2][0]):
        return scored[-1][1]
    return cleaned


def _canonical_flow_endpoint(label: Any, component_ids: list[str]) -> str:
    """Resolve a Mermaid short label without rewriting external collaborators."""
    value = str(label or "").strip()
    if value in component_ids:
        return value
    resolved = _resolve_package_component_label(value, component_ids)
    return resolved if resolved in component_ids else value


def _normalize_recursive_package_markdown(content: str) -> str:
    """Normalize equivalent L1/L2 package table vocabulary in the run-scoped copy."""
    if "validate-arch-package:" not in content:
        return content

    lines = content.splitlines()
    component_ids: list[str] = []
    in_registry = False
    for line in lines:
        cells = _markdown_table_cells(line)
        lowered = {cell.lower() for cell in cells}
        if "child_id" in lowered:
            in_registry = True
            continue
        if in_registry and not cells:
            in_registry = False
        if in_registry and cells and not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            child_id = cells[0].strip(" `")
            if re.fullmatch(r"[a-z0-9][a-z0-9-]+", child_id, re.I):
                component_ids.append(child_id)
    if not component_ids:
        return content

    marker = re.search(r"validate-arch-package:\s*(\{.*?\})\s*-->", content)
    try:
        package = json.loads(marker.group(1)) if marker else {}
    except json.JSONDecodeError:
        package = {}
    package_names = {
        str(package.get("target_node_id") or "").lower(),
        str(package.get("current_node_name") or "").lower(),
    }

    normalized: list[str] = []
    table_kind = ""
    for line in lines:
        cells = _markdown_table_cells(line)
        lowered = [cell.lower() for cell in cells]
        if cells and "child_id" in lowered:
            table_kind = "registry"
            cells = ["分配需求" if cell == "需求" else cell for cell in cells]
            normalized.append("| " + " | ".join(cells) + " |")
            continue
        if cells and (
            (cells[0] == "契约" and "L2 实现映射" in cells)
            or (cells[0].lower() == "父契约" and "当前实现映射" in cells)
        ):
            table_kind = "parent"
            normalized.append(
                "| 父契约 | 角色 | 不可变字段/语义 | 当前实现子节点 | 失败、幂等与版本 |"
            )
            continue
        if cells and cells[0].lower() == "内部契约 id":
            table_kind = "internal"
            normalized.append("| 契约 ID | 所有者 → 消费者 | 触发与 schema | 错误、幂等与兼容性 |")
            continue
        if not cells:
            table_kind = ""
            normalized.append(line)
            continue
        if table_kind and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            count = 4 if table_kind in {"parent", "internal"} else len(cells)
            normalized.append("|" + "|".join("---" for _ in range(count)) + "|")
            continue
        if table_kind == "parent" and len(cells) >= 4:
            contract_id, role, schema, implementation = cells[:4]
            errors = cells[4] if len(cells) >= 5 else ""
            chain = []
            for part in re.split(r"[；;。]|(?:→|->)", implementation):
                component = _resolve_package_component_label(part, component_ids)
                if component in component_ids and component not in chain:
                    chain.append(component)
            if chain:
                implementation = " → ".join(chain)
            role_match = re.search(
                r"(?:提供方\s*[:：]?\s*)?`?([^`；;]+?)`?\s*提供方\s*[；;]\s*"
                r"(?:消费者\s*[:：]?\s*)?`?([^`；;]+?)`?\s*消费方",
                role,
            )
            if role_match:
                provider = role_match.group(1).strip()
                consumer = role_match.group(2).strip()
                provider = (
                    chain[0] if chain else _resolve_package_component_label(provider, component_ids)
                )
                role = f"{provider} → {consumer}"
            schema = re.sub(r"\brequired\s*[:：]", "输入：", schema, flags=re.I)
            schema = re.sub(r"\bproduced\s*[:：]", "输出：", schema, flags=re.I)
            normalized.append(
                "| " + " | ".join([contract_id, role, schema, implementation, errors]) + " |"
            )
            continue
        if table_kind == "internal" and len(cells) >= 5:
            contract_id, ownership, trigger_input, output, errors = cells[:5]
            pair = re.split(r"\s*(?:→|->)\s*", ownership, maxsplit=1)
            provider = _resolve_package_component_label(pair[0], component_ids)
            consumers = [
                _resolve_package_component_label(item, component_ids)
                for item in re.split(r"[、/,，]", pair[1] if len(pair) > 1 else "")
                if item.strip()
            ]
            ownership = f"{provider} → {', '.join(consumers)}"
            schema = f"输入：{trigger_input}；输出：{output}"
            normalized.append("| " + " | ".join([contract_id, ownership, schema, errors]) + " |")
            continue
        normalized.append(line)

    # YAML contract blocks are authoritative architecture evidence, but the
    # parser consumes the same evidence in a machine-readable Markdown table.
    # Add an equivalent table only to the run-scoped effective copy.
    yaml_contract_rows: list[str] = []
    for match in re.finditer(
        r"(?ms)^###\s+`([^`]+)`\s*\n\s*```yaml\s*\n(.*?)\n\s*```",
        content,
    ):
        try:
            contract = yaml.safe_load(match.group(2)) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(contract, dict) or not contract.get("contract_id"):
            continue
        contract_id = str(contract.get("contract_id") or match.group(1)).strip()
        owner = _resolve_package_component_label(str(contract.get("owner") or ""), component_ids)
        consumer_values = contract.get("consumer") or ""
        if isinstance(consumer_values, list):
            consumers = [str(item).strip() for item in consumer_values if str(item).strip()]
        else:
            consumers = [str(consumer_values).strip()] if str(consumer_values).strip() else []
        consumer = ", ".join(
            _resolve_package_component_label(item, component_ids) for item in consumers
        )
        required = contract.get("required_fields") or []
        produced = contract.get("produced_fields") or []
        errors = contract.get("errors") or []
        compatibility = str(contract.get("compatibility") or "").strip()
        required_text = ", ".join(str(item).strip() for item in required)
        produced_text = ", ".join(str(item).strip() for item in produced)
        error_text = ", ".join(str(item).strip() for item in errors)
        if compatibility:
            error_text = f"{error_text}；{compatibility}" if error_text else compatibility
        schema = (
            f"输入：`{required_text}`；输出：`{produced_text}`；"
            f"触发：{str(contract.get('trigger') or '').strip()}"
        )
        yaml_contract_rows.append(
            "| " + " | ".join([contract_id, f"{owner} → {consumer}", schema, error_text]) + " |"
        )
    if yaml_contract_rows:
        new_rows = [
            row
            for row in yaml_contract_rows
            if "## validate-arch normalized internal contracts" not in normalized
        ]
        if new_rows:
            normalized.extend(
                [
                    "",
                    "## validate-arch normalized internal contracts",
                    "",
                    "| 契约 ID | 所有者 → 消费者 | 触发与 schema | 错误、幂等与兼容性 |",
                    "|---|---|---|---|",
                    *new_rows,
                ]
            )

    # Resolve Mermaid aliases to authoritative child IDs before ArchDocParser
    # extracts sequence edges. External actors remain unchanged.
    aliases: dict[str, str] = {}
    for line in normalized:
        participant = re.search(r"\bparticipant\s+(\w+)\s+as\s+(.+)$", line.strip())
        if participant:
            resolved = _resolve_package_component_label(participant.group(2), component_ids)
            if resolved in component_ids:
                aliases[participant.group(1)] = resolved
        node = re.search(r"\b(\w+)\s*\[\s*[\"']([^\"']+)[\"']\s*\]", line)
        if node:
            resolved = _resolve_package_component_label(node.group(2), component_ids)
            if resolved in component_ids:
                aliases[node.group(1)] = resolved
    if aliases:
        edge_pattern = re.compile(r"(?P<left>\w+)\s*(?P<arrow>-{1,2}>>?)\s*(?P<right>\w+)")
        normalized = [
            edge_pattern.sub(
                lambda match: (
                    f"{aliases.get(match.group('left'), match.group('left'))}"
                    f"{match.group('arrow')}"
                    f"{aliases.get(match.group('right'), match.group('right'))}"
                ),
                line,
            )
            for line in normalized
        ]
    return "\n".join(normalized) + ("\n" if content.endswith("\n") else "")


def _normalize_recursive_package_input(path: str) -> bool:
    target = Path(path)
    content = target.read_text(encoding="utf-8")
    normalized = _normalize_recursive_package_markdown(content)
    if normalized == content:
        return False
    target.write_text(normalized, encoding="utf-8")
    return True


def _create_prepare_llm_client(config: Any) -> Any:
    """为 prepare 阶段创建 LLMClient。"""
    from mock_framework.simulator.llm_client import LLMClientFactory

    provider_cfg = config.llm.simulator
    api_key = config.llm.api_key
    if api_key.startswith("${") and api_key.endswith("}"):
        import os

        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")
    return LLMClientFactory.create(
        provider=provider_cfg.provider,
        api_key=api_key,
        model=provider_cfg.model,
        token_budget=provider_cfg.token_budget,
        base_url=config.llm.base_url,
        timeout_seconds=provider_cfg.timeout_seconds,
        max_retries=provider_cfg.max_retries,
        retry_backoff_seconds=provider_cfg.retry_backoff_seconds,
    )


def _parse_entry_component_response(response: Any) -> dict[str, Any] | None:
    """解析 LLM 返回的入口组件推断结果，支持 dict、raw JSON 和 markdown 代码块。"""
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
    return None


# Local entry rules used by strict subagent flow instead of API-assisted entry inference.
_ENTRY_COMPONENT_RULES: list[dict[str, list[str]]] = [
    {
        "aliases": ["Solution Generation", "Solution Generation BC", "External LLM"],
        "keywords": [
            "完整解析",
            "完整解答",
            "最终答案",
            "full solution",
            "complete solution",
            "final answer",
            "llm",
            "大模型",
        ],
    },
    {
        "aliases": ["Problem Intake", "Problem Intake BC"],
        "keywords": [
            "提交",
            "上传",
            "识别",
            "解析题目",
            "题目",
            "图片",
            "submit",
            "upload",
            "ocr",
            "problem image",
            "math problem",
        ],
    },
    {
        "aliases": ["Tutoring Session", "Tutoring Session BC", "Guidance Session"],
        "keywords": [
            "引导",
            "提示",
            "会话",
            "下一步",
            "披露",
            "答疑",
            "guide",
            "hint",
            "next step",
            "tutor",
        ],
    },
    {
        "aliases": ["Hint Generation", "Hint Generation BC", "Knowledge Base"],
        "keywords": ["知识点", "公式", "提示生成", "formula", "knowledge", "hint generation"],
    },
    {
        "aliases": ["Data Retention & Compliance", "Data Retention & Compliance BC"],
        "keywords": ["保留", "合规", "删除", "审计", "隐私", "retention", "compliance", "privacy"],
    },
    {
        "aliases": ["Progress Tracking", "Progress Tracking BC"],
        "keywords": ["记录", "学习", "错题", "进度", "progress", "learning record"],
    },
    {
        "aliases": ["Anti-Abuse", "Anti-Abuse BC"],
        "keywords": ["限流", "审核", "拦截", "滥用", "rate limit", "abuse"],
    },
    {
        "aliases": ["Error Diagnosis", "Error Diagnosis BC"],
        "keywords": ["诊断", "错误", "薄弱点", "diagnosis", "mistake", "weakness"],
    },
    {
        "aliases": ["User Identity", "User Identity BC", "User Center"],
        "keywords": ["登录", "验证码", "账号", "身份", "用户", "login", "account", "identity"],
    },
]


def _normalize_component_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _component_name_matches(name: str, alias: str) -> bool:
    norm_name = _normalize_component_name(name)
    norm_alias = _normalize_component_name(alias)
    if norm_name == norm_alias:
        return True
    if norm_name.endswith("bc") and norm_name[:-2] == norm_alias:
        return True
    if norm_alias.endswith("bc") and norm_alias[:-2] == norm_name:
        return True
    # 空归一名（如纯中文名被剥离为空）不应子串匹配任意别名
    if not norm_name or not norm_alias:
        return False
    return norm_alias in norm_name or norm_name in norm_alias


def _resolve_component_alias(components: list[Any], aliases: list[str]) -> str | None:
    for alias in aliases:
        for c in components:
            if _component_name_matches(c.name, alias):
                return c.name
    return None


_ENTRY_STOP_WORDS = {
    "and",
    "component",
    "data",
    "for",
    "from",
    "handle",
    "service",
    "system",
    "the",
    "user",
    "via",
    "with",
}


def _entry_terms(value: Any) -> list[str]:
    """Extract stable architecture terms without assuming a business domain."""
    text = str(value or "").lower()
    chunks = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text)
    return [term for term in chunks if len(term) >= 2 and term not in _ENTRY_STOP_WORDS]


def _entry_signal_score(text: str, value: Any) -> int:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return 0
    normalized_candidate = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", candidate)
    normalized_text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.lower())
    score = 8 if len(normalized_candidate) >= 3 and normalized_candidate in normalized_text else 0
    score += sum(2 for term in set(_entry_terms(candidate)) if term in text.lower())
    return score


def _entry_semantic_score(text: str, value: Any) -> int:
    """Combine exact tokens with bounded Chinese phrase overlap."""
    return _entry_signal_score(text, value) + min(_chinese_phrase_score(text, value), 24)


_CONTRACT_FIELD_TERMS = {
    "allowed": "允许",
    "asin": "ASIN",
    "attributes": "属性",
    "authorization": "授权",
    "candidate": "候选",
    "configuration": "配置",
    "constraint": "约束规则",
    "discarded": "丢弃",
    "evidence": "证据",
    "event": "事件",
    "gate": "门禁",
    "history": "历史",
    "lifecycle": "生命周期",
    "log": "日志",
    "price": "价格",
    "profile": "画像",
    "result": "结果",
    "search": "检索",
    "state": "状态",
    "sync": "同步",
    "taxonomy": "词表",
    "version": "版本",
    "written": "写入",
}


def _contract_field_signal(value: Any) -> str:
    if isinstance(value, list):
        raw = " ".join(str(item) for item in value)
    else:
        raw = str(value or "")
    lower = raw.lower()
    translated = " ".join(
        chinese for english, chinese in _CONTRACT_FIELD_TERMS.items() if english in lower
    )
    return f"{raw} {translated}".strip()


def _select_entry_contract_action(
    card: dict[str, Any], text: str, fallback_action: str = "handle"
) -> str:
    """Choose the architecture contract that best explains the scenario entry."""
    candidates: list[tuple[int, int, str, bool]] = []
    component = str(card.get("name") or "")
    for interface in card.get("inbound_interfaces", []) + card.get("outbound_interfaces", []):
        contract = interface.get("contract") or {}
        contract_id = str(contract.get("contract_id") or interface.get("name") or "")
        if not contract_id:
            continue
        values = [
            interface.get("name", ""),
            _contract_field_signal(contract_id),
            contract.get("schema", ""),
            contract.get("errors", ""),
            contract.get("side_effects", ""),
        ]
        score = sum(_entry_semantic_score(text, value) for value in values)
        provider_owned = str(contract.get("provider") or "") == component
        non_self = int(str(contract.get("consumer") or "") != component)
        candidates.append((score, non_self, contract_id, provider_owned))
    if not candidates:
        return fallback_action
    owned = [item for item in candidates if item[3]]
    if owned:
        candidates = owned
    candidates.sort(reverse=True)
    if candidates[0][0] > 0 and (len(candidates) == 1 or candidates[0][0] > candidates[1][0]):
        return candidates[0][2]
    externally_visible = [item for item in candidates if item[1] == 1]
    if len(externally_visible) == 1:
        return externally_visible[0][2]
    return fallback_action


def _provider_contract_semantic_score(card: dict[str, Any], text: str) -> int:
    """Return the strongest scenario match among contracts owned by this component."""
    component = str(card.get("name") or "")
    scores: list[int] = []
    for interface in card.get("inbound_interfaces", []) + card.get("outbound_interfaces", []):
        contract = interface.get("contract") or {}
        if str(contract.get("provider") or "") != component:
            continue
        scores.append(
            sum(
                _entry_semantic_score(text, contract.get(key, ""))
                for key in (
                    "contract_id",
                    "errors",
                    "side_effects",
                )
            )
        )
    return max(scores, default=0)


def _external_entry_contract_score(card: dict[str, Any], text: str) -> int:
    """Score a component's user/UI-facing provider contracts."""
    component = str(card.get("name") or "")
    score = 0
    for interface in card.get("inbound_interfaces", []) + card.get("outbound_interfaces", []):
        contract = interface.get("contract") or {}
        if str(contract.get("provider") or "") != component:
            continue
        consumer = str(contract.get("consumer") or "").lower()
        if any(marker in consumer for marker in ("用户", "界面", " ui", "app", "client")):
            score = max(score, 1 + _entry_semantic_score(text, contract.get("schema", "")))
    return score


def _has_contract_failure_context(text: str) -> bool:
    return any(
        marker in text.lower()
        for marker in (
            "异常",
            "错误",
            "失败",
            "超时",
            "不可用",
            "状态为",
            "撤回",
            "删除",
            "日志",
            "门禁",
        )
    )


def _extract_chinese_phrases(text: str, max_len: int = 6) -> set[str]:
    """Extract overlapping Chinese phrases for fuzzy semantic matching."""
    text = str(text or "")
    blocks = re.findall(r"[一-鿿]{2,}", text)
    phrases: set[str] = set()
    for block in blocks:
        for length in range(2, min(max_len, len(block)) + 1):
            for i in range(len(block) - length + 1):
                phrases.add(block[i : i + length])
    return phrases


def _chinese_phrase_score(text: str, candidate: Any) -> int:
    """Score Chinese phrase overlap between scenario text and component signal."""
    candidate_text = str(candidate or "")
    text_phrases = _extract_chinese_phrases(text)
    candidate_phrases = _extract_chinese_phrases(candidate_text)
    if not text_phrases or not candidate_phrases:
        return 0
    generic = {
        "一个",
        "当前",
        "用户",
        "系统",
        "请求",
        "数据",
        "字段",
        "结果",
        "状态",
        "版本",
        "输入",
        "输出",
        "执行",
        "检查",
        "处理",
        "返回",
        "通过",
        "失败",
        "有效",
        "完整",
    }
    matches = {
        match
        for match in text_phrases & candidate_phrases
        if len(match) >= 3 or match not in generic
    }
    maximal = {
        match
        for match in matches
        if not any(match != other and match in other for other in matches)
    }
    return sum(min(len(match), 6) * 2 for match in maximal)


def _is_sequential_workflow(text: str) -> bool:
    """Detect end-to-end workflow scenarios that should start at the chain root."""
    markers = (
        "sequential_workflow",
        "端到端",
        "完整流程",
        "主成功路径",
        "用户提交",
        "并发负载",
        "负载测试",
    )
    lower = text.lower()
    return any(marker in lower for marker in markers)


def _find_dataflow_roots(
    components: list[Any], data_flow_summary: list[dict[str, Any]]
) -> list[str]:
    """Return components with no inbound edges from other known components."""
    component_names = {c.name for c in components}
    inbound = {
        step.get("to")
        for step in data_flow_summary
        if step.get("to") in component_names and step.get("from") in component_names
    }
    # Prefer components that receive external (non-component) input.
    external_inbound = {
        step.get("to")
        for step in data_flow_summary
        if step.get("to") in component_names and step.get("from") not in component_names
    }
    if external_inbound:
        return [c.name for c in components if c.name in external_inbound]
    roots = [c.name for c in components if c.name not in inbound]
    return roots


def _local_entry_component(
    text: str,
    component_cards: dict[str, dict[str, Any]],
    data_flow_summary: list[dict[str, Any]],
    components: list[Any],
) -> dict[str, Any]:
    """Infer an entry from the supplied architecture, without an external LLM."""
    text_lower = text.lower()
    component_names = {c.name for c in components}
    when_line = next(
        (
            line.strip().split(" ", 1)[1]
            for line in text.splitlines()
            if line.strip().lower().startswith("when ") and " " in line.strip()
        ),
        "",
    )
    weighted_text = f"{text_lower}\n{when_line.lower()}\n{when_line.lower()}"
    scenario_requirements = {
        match.upper() for match in re.findall(r"(?:REQ|NFR)-D\d{3}", weighted_text, re.IGNORECASE)
    }

    # Exact data-flow message match is the strongest local signal.
    for step in data_flow_summary:
        target = step.get("to", "")
        message = str(step.get("message") or "")
        action = str(step.get("action") or "")
        if target in component_names and any(
            signal and signal.lower() in text_lower for signal in (message, action)
        ):
            return {
                "entry_component": target,
                "entry_action": action or "handle",
                "confidence": "high",
                "reason": f"架构 data_flow 匹配: {message or action}",
            }

    scored: list[tuple[int, str, str, str]] = []
    for component in components:
        card = component_cards.get(component.name, {})
        signals: list[tuple[str, Any]] = [
            ("component", component.name),
            ("responsibility", getattr(component, "responsibility", "")),
        ]
        for entity, detail in (card.get("owned_entities") or {}).items():
            signals.append(("owned_entity", entity))
            signals.append(("owned_entity.detail", detail))
        for interface in card.get("inbound_interfaces", []) + card.get("outbound_interfaces", []):
            signals.append(("interface", interface.get("name", "")))
            contract = interface.get("contract") or {}
            provider = str(contract.get("provider") or "").strip()
            if provider and provider != component.name:
                continue
            for key in (
                "contract_id",
                "trigger",
                "action",
                "event",
                "operation",
                "errors",
                "side_effects",
            ):
                signals.append((f"contract.{key}", contract.get(key, "")))
            if provider == component.name:
                signals.append(
                    (
                        "contract.response",
                        _contract_field_signal(
                            contract.get("response") or contract.get("produced")
                        ),
                    )
                )
        for step in data_flow_summary:
            if step.get("to") == component.name:
                signals.extend(
                    [
                        ("data_flow.action", step.get("action", "")),
                        ("data_flow.message", step.get("message", "")),
                    ]
                )

        best_kind, best_value, best_score = "", "", 0
        for kind, value in signals:
            signal_score = _entry_semantic_score(weighted_text, value)
            if signal_score > best_score:
                best_kind, best_value, best_score = kind, str(value or ""), signal_score
        chinese_score = _chinese_phrase_score(
            weighted_text, getattr(component, "responsibility", "")
        )
        responsibility = str(getattr(component, "responsibility", ""))
        owned_requirements = responsibility.split("Supports:", 1)[0]
        component_requirements = {
            match.upper()
            for match in re.findall(r"(?:REQ|NFR)-D\d{3}", owned_requirements, re.IGNORECASE)
        }
        has_public_contract = any(
            (interface.get("contract") or {}).get("contract_type") == "module_contract"
            for interface in card.get("inbound_interfaces", [])
            + card.get("outbound_interfaces", [])
        )
        if (
            scenario_requirements
            and not scenario_requirements.intersection(component_requirements)
            and not _is_sequential_workflow(weighted_text)
            and not (has_public_contract and chinese_score >= 4)
        ):
            continue
        requirement_score = 40 if scenario_requirements & component_requirements else 0
        total = best_score + requirement_score + chinese_score
        if total:
            action = "handle"
            for step in data_flow_summary:
                if step.get("to") == component.name and _entry_signal_score(
                    weighted_text, step.get("message") or step.get("action")
                ):
                    action = str(step.get("action") or "handle")
                    break
            action = _select_entry_contract_action(card, weighted_text, action)
            scored.append((total, component.name, action, f"{best_kind}: {best_value}"))

    scored.sort(reverse=True)
    if scored:
        top_score, top_component, top_action, top_reason = scored[0]
        # End-to-end workflow scenarios should start at the data-flow root
        # even if requirement allocation points to a downstream component.
        if _is_sequential_workflow(weighted_text):
            roots = _find_dataflow_roots(components, data_flow_summary)
            root_scores = {item[1]: item for item in scored if item[1] in roots}
            if root_scores:
                external_scores = {
                    name: _external_entry_contract_score(
                        component_cards.get(name, {}), weighted_text
                    )
                    for name in root_scores
                }
                best_external = max(external_scores.values(), default=0)
                external_winners = [
                    name
                    for name, score in external_scores.items()
                    if score == best_external and score > 0
                ]
                if len(external_winners) == 1:
                    selected = root_scores[external_winners[0]]
                else:
                    selected = max(root_scores.values(), key=lambda item: item[0])
                return {
                    "entry_component": selected[1],
                    "entry_action": selected[2],
                    "confidence": "high" if selected[0] >= 8 else "medium",
                    "reason": f"端到端流程选择数据流起点: {selected[3]}",
                }
        tied = [item[1] for item in scored if item[0] == top_score]
        if len(tied) == 1:
            return {
                "entry_component": top_component,
                "entry_action": top_action,
                "confidence": "high" if top_score >= 8 else "medium",
                "reason": f"架构信号匹配: {top_reason}",
            }
        if _has_contract_failure_context(weighted_text):
            contract_scores = {
                component: _provider_contract_semantic_score(
                    component_cards.get(component, {}), weighted_text
                )
                for component in tied
            }
            best_contract_score = max(contract_scores.values(), default=0)
            contract_winners = [
                component
                for component, score in contract_scores.items()
                if score == best_contract_score and score > 0
            ]
            if len(contract_winners) == 1:
                selected = next(item for item in scored if item[1] == contract_winners[0])
                return {
                    "entry_component": selected[1],
                    "entry_action": selected[2],
                    "confidence": "high" if best_contract_score >= 8 else "medium",
                    "reason": "架构提供方契约错误语义打破入口并列",
                }
        external_scores = {
            component: _external_entry_contract_score(
                component_cards.get(component, {}), weighted_text
            )
            for component in tied
        }
        best_external_score = max(external_scores.values(), default=0)
        external_winners = [
            component
            for component, score in external_scores.items()
            if score == best_external_score and score > 0
        ]
        if len(external_winners) == 1:
            selected = next(item for item in scored if item[1] == external_winners[0])
            return {
                "entry_component": selected[1],
                "entry_action": selected[2],
                "confidence": "medium",
                "reason": "用户/界面动作选择架构声明的外部入口契约",
            }
        # A public module contract is the architecture-defined entry boundary
        # when several internal children share one requirement allocation.
        public_boundary = [
            item[1]
            for item in scored
            if item[0] == top_score
            and any(
                (interface.get("contract") or {}).get("contract_type") == "module_contract"
                and (interface.get("contract") or {}).get("consumer") not in component_names
                for interface in (component_cards.get(item[1], {}).get("outbound_interfaces", []))
            )
        ]
        if len(public_boundary) == 1:
            selected = next(item for item in scored if item[1] == public_boundary[0])
            return {
                "entry_component": selected[1],
                "entry_action": selected[2],
                "confidence": "high" if selected[0] >= 8 else "medium",
                "reason": f"架构公共入口边界匹配: {selected[3]}",
            }
        roots = [
            name
            for name in tied
            if not any(
                step.get("from") in tied and step.get("to") == name for step in data_flow_summary
            )
        ]
        if len(roots) == 1:
            selected = next(item for item in scored if item[1] == roots[0])
            return {
                "entry_component": selected[1],
                "entry_action": selected[2],
                "confidence": "high" if selected[0] >= 8 else "medium",
                "reason": f"架构数据流起点匹配: {selected[3]}",
            }
        if _is_sequential_workflow(weighted_text) and roots:
            selected = next(item for item in scored if item[1] == roots[0])
            return {
                "entry_component": selected[1],
                "entry_action": selected[2],
                "confidence": "medium",
                "reason": f"端到端流程，选择数据流起点: {selected[3]}",
            }
        # A real tie is unresolved. Choosing by sort order silently assigns
        # scenarios to the wrong module and makes the gate nondeterministic.
        return {
            "entry_component": "",
            "entry_action": "",
            "confidence": "low",
            "reason": f"入口组件存在歧义，并列候选: {', '.join(sorted(tied))}",
        }

    if _is_sequential_workflow(weighted_text):
        roots = _find_dataflow_roots(components, data_flow_summary)
        if roots:
            root = roots[0]
            card = component_cards.get(root, {})
            return {
                "entry_component": root,
                "entry_action": _select_entry_contract_action(card, weighted_text),
                "confidence": "medium",
                "reason": "端到端流程，选择数据流起点作为入口",
            }

    public_boundary = [
        component
        for component in components
        if any(
            (interface.get("contract") or {}).get("contract_type") == "module_contract"
            and (interface.get("contract") or {}).get("consumer") not in component_names
            for interface in component_cards.get(component.name, {}).get("outbound_interfaces", [])
        )
    ]
    if len(public_boundary) == 1:
        component = public_boundary[0]
        card = component_cards.get(component.name, {})
        return {
            "entry_component": component.name,
            "entry_action": _select_entry_contract_action(card, weighted_text),
            "confidence": "medium",
            "reason": "架构公共模块契约边界作为入口",
        }

    # Compatibility only: legacy aliases may help old architecture fixtures, but
    # they cannot select a component that is absent from the supplied architecture.
    for rule in _ENTRY_COMPONENT_RULES:
        if any(kw.lower() in text_lower for kw in rule["keywords"]):
            component = _resolve_component_alias(components, rule["aliases"])
            if component:
                return {
                    "entry_component": component,
                    "entry_action": "handle",
                    "confidence": "medium",
                    "reason": f"本地关键词匹配: {rule['keywords']}",
                }

    # Last resort: return the highest-scored candidate even when confidence is low,
    # so callers can see a recommendation instead of a blank entry.
    if scored:
        return {
            "entry_component": scored[0][1],
            "entry_action": scored[0][2],
            "confidence": "low",
            "reason": f"推荐入口候选（无强信号）: {scored[0][3]}",
        }

    return {
        "entry_component": "",
        "entry_action": "",
        "confidence": "low",
        "reason": "未从架构组件、接口或 data_flow 匹配到唯一入口",
    }


def _infer_entry_component(
    scenario_text: str,
    component_cards: dict[str, dict[str, Any]],
    data_flow_summary: list[dict[str, Any]],
    llm_client: Any,
    components: list[Any],
) -> dict[str, Any]:
    """推断场景入口组件。默认走本地规则；传入 llm_client 时才调用 LLM。"""
    if llm_client is None:
        return _local_entry_component(scenario_text, component_cards, data_flow_summary, components)

    try:
        prompt = _build_entry_component_prompt(scenario_text, component_cards, data_flow_summary)
        response = llm_client.complete(prompt)
        parsed = _parse_entry_component_response(response)
    except Exception as e:
        get_logger("loader.step_mapper").warning(f"Entry component LLM inference failed: {e}")
        return _local_entry_component(scenario_text, component_cards, data_flow_summary, components)

    if not parsed:
        return _local_entry_component(scenario_text, component_cards, data_flow_summary, components)

    entry = parsed.get("entry_component", "")
    component_names = {c.name for c in components}
    if entry not in component_names:
        return _local_entry_component(scenario_text, component_cards, data_flow_summary, components)

    return {
        "entry_component": entry,
        "entry_action": parsed.get("entry_action", "handle"),
        "confidence": parsed.get("confidence", "medium"),
        "reason": parsed.get("reason", ""),
    }


def _fallback_entry_component(text: str, components: list[Any]) -> dict[str, Any]:
    """当 LLM 入口推断失败时，使用关键词启发式 fallback。"""
    cards = {
        c.name: {
            "responsibility": getattr(c, "responsibility", ""),
            "inbound_interfaces": [],
            "outbound_interfaces": [],
        }
        for c in components
    }
    return _local_entry_component(text, cards, [], components)


def _should_continue_chain(hop: dict[str, Any]) -> bool:
    """判断当前 hop 是否还有下一跳。"""
    next_hop = hop.get("next_hop")
    return isinstance(next_hop, dict) and bool(next_hop.get("component"))


def _detect_loop(next_component: str, next_action: str, visited: set[tuple[str, str]]) -> bool:
    """检测 (component, action) 是否已访问过。"""
    return (next_component, next_action) in visited


def _update_shared_state(shared_state: dict[str, Any], hop: dict[str, Any]) -> None:
    """根据 hop 的 state_change 更新共享状态（in-place）。"""
    state_change = hop.get("state_change")
    if isinstance(state_change, dict) and state_change.get("entity"):
        shared_state[state_change["entity"]] = state_change.get("to_state", "")


def _build_entry_component_prompt(
    scenario_text: str,
    component_cards: dict[str, dict[str, Any]],
    data_flow_summary: list[dict[str, Any]],
) -> str:
    """构造入口组件推断 LLM prompt。"""
    cards_json = json.dumps(
        [
            {"name": name, "responsibility": card.get("responsibility", "")}
            for name, card in component_cards.items()
        ],
        ensure_ascii=False,
        indent=2,
    )
    flow_json = json.dumps(data_flow_summary, ensure_ascii=False, indent=2)
    return (
        "你是架构验证框架的场景入口推断助手。\n\n"
        "## 场景描述\n"
        f"{scenario_text}\n\n"
        "## 可用组件\n"
        f"```json\n{cards_json}\n```\n\n"
        "## 架构数据流\n"
        f"```json\n{flow_json}\n```\n\n"
        "## 任务\n"
        "请判断该场景的入口组件是哪一个。入口组件是指：当这个场景被执行时，用户或外部系统的第一个动作会落到哪个组件上。\n\n"
        "## 输出要求\n"
        "仅返回 raw JSON，不要 markdown 代码块：\n"
        "```json\n"
        "{\n"
        '  "entry_component": "<组件名，必须来自可用组件列表>",\n'
        '  "entry_action": "<动作名>",\n'
        '  "confidence": "high|medium|low",\n'
        '  "reason": "<一句话理由>"\n'
        "}\n"
        "```\n\n"
        "## 规则\n"
        "- 入口组件是指：当这个场景被执行时，用户或外部系统的第一个动作会落到哪个组件上。\n"
        "- 如果场景包含多个 When 步骤，入口组件应处理第一个 When（通常是系统侧动作），而不是后面的学生/外部 UI 动作。\n"
        "- 只依据本次提供的组件责任、接口和数据流判断，不假设固定业务领域。\n"
        "- 如果无法唯一确定，entry_component 留空且 confidence 设为 low。"
    )


def _arch_summary(arch_doc: ArchDoc) -> dict[str, Any]:
    """Build a JSON-serializable architecture summary for prompts."""
    return {
        "components": [
            {
                "name": c.name,
                "responsibility": c.responsibility,
                "tech_stack": c.tech_stack,
            }
            for c in arch_doc.components
        ],
        "data_flow": [
            {
                "from": step.from_component,
                "to": step.to_component,
                "action": step.action,
                "message": step.message,
            }
            for step in arch_doc.data_flow.sequence
        ],
        "state_machine": {
            "states": arch_doc.state_machine.states,
            "transitions": [
                {
                    "from": t.from_state,
                    "to": t.to_state,
                    "trigger": t.trigger,
                }
                for t in arch_doc.state_machine.transitions
            ],
        },
        "nfrs": [
            {
                "id": nfr.id,
                "metric": nfr.metric,
                "threshold": nfr.threshold,
                "unit": nfr.unit,
            }
            for nfr in arch_doc.nfrs
        ],
        "constraints": [
            {"type": c.type, "description": c.description, "target": c.target, "value": c.value}
            for c in arch_doc.constraints
        ],
        "interfaces": [
            {
                "name": i.name,
                "direction": i.direction,
                "protocol": i.protocol,
                "description": i.description,
            }
            for i in arch_doc.interfaces
        ],
    }


def _classify_component(
    name: str,
    responsibility: str | None = None,
    dispatch_kind: str | None = None,
) -> tuple[str, bool]:
    """Return declared dispatch semantics for a parsed architecture component.

    Responsibility text describes behavior, so it is intentionally not used to
    decide whether a component is dispatchable.  For example, a queue component
    can own a ``worker_job`` without itself being a runtime worker container.
    """
    text = f"{name} {responsibility or ''}".lower()
    declared = str(dispatch_kind or "").strip().lower()
    if declared in {"container", "datastore", "external", "heading"}:
        return declared, False
    if declared == "component":
        return "component", True
    name_text = name.lower()
    if name.startswith("Module "):
        return "heading", False
    if name.endswith(" BC") or "bounded context" in name_text:
        return "bounded_context", True
    if any(k in name_text for k in ("database", "db", "cache", "redis", "storage", "postgres")):
        return "datastore", False
    if any(k in name_text for k in ("web app", "api application", "container")):
        return "container", False
    return "component", True


def _test_case_summary(tc: Any) -> dict[str, Any]:
    """Build a JSON-serializable test-case summary for prompts."""
    return {
        "test_case_id": tc.test_case_id,
        "scenario_name": tc.source_scenario,
        "source_feature": tc.source_feature,
        "source_scenario": tc.source_scenario,
        "tags": tc.tags,
        "gherkin": tc.gherkin,
        "technical_mapping": {
            phase: [
                {
                    "step_index": m.step_index,
                    "text": m.text,
                    "mapping_type": m.mapping_type,
                    "target": m.target,
                    "assertion": m.assertion,
                    "confidence": m.confidence,
                }
                for m in mappings
            ]
            for phase, mappings in tc.technical_mapping.items()
        },
        "expectations": {
            "status_code": tc.expectations.status_code,
            "response_schema": tc.expectations.response_schema,
            "touched_components": tc.expectations.touched_components,
            "side_effects": tc.expectations.side_effects,
            "performance": tc.expectations.performance,
        },
    }


def _requirements_from_test_cases(test_cases: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for case in test_cases:
        found.update(
            match.upper()
            for match in re.findall(
                r"(?:REQ|FR|NFR)-[A-Za-z0-9_.-]+",
                json.dumps(case, ensure_ascii=False),
                flags=re.I,
            )
        )
    return sorted(found)


def _refresh_run_manifest_id(run_manifest: dict[str, Any]) -> None:
    canonical = json.dumps(
        run_manifest["inputs"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    run_manifest["run_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _attach_identity_manifest(
    output_data: dict[str, Any], run_manifest: dict[str, Any], manifest_path: str | None
) -> None:
    if not manifest_path:
        return
    path = Path(manifest_path).resolve()
    data = _read_json(path, None)
    if not isinstance(data, dict):
        raise ValueError(f"identity manifest must be a JSON object: {path}")
    output_data["protocol_metadata"] = data
    run_manifest.setdefault("inputs", {})["identity_manifest"] = {
        "path": str(path),
        "sha256": _sha256_path(path),
    }
    _refresh_run_manifest_id(run_manifest)


def _write_normalized_inputs(
    output_path: Path,
    output_data: dict[str, Any],
    run_manifest: dict[str, Any],
    arch_path: str,
    feature_path: str,
    arch_doc: ArchDoc,
    test_case_summaries: list[dict[str, Any]],
) -> None:
    """Write canonical JSON views without replacing the Markdown/Gherkin loaders."""
    protocol = output_data.get("protocol_metadata", {})
    identity = protocol.get("identity", {})
    normalized_run_id = str(protocol.get("run_id") or run_manifest["run_id"])
    created_at = datetime.now(timezone.utc).isoformat()
    requirement_ids = _requirements_from_test_cases(test_case_summaries)
    arch_source = ArtifactRecord(
        artifact_id=str(identity.get("architecture_artifact_id") or "architecture-source"),
        artifact_type="architecture_source",
        path=arch_path,
        sha256=_sha256_path(arch_path),
        schema_version="architecture-source/v1",
    )
    testcase_source = ArtifactRecord(
        artifact_id=str(identity.get("testcase_artifact_id") or "testcases-source"),
        artifact_type="testcases_source",
        path=feature_path,
        sha256=_sha256_path(feature_path),
        schema_version="testcases-source/v1",
    )
    normalized_arch = NormalizedArchitecture(
        run_id=normalized_run_id,
        project_id=str(identity.get("project_id") or ""),
        node_id=str(identity.get("node_id") or ""),
        source_prd_id=str(identity.get("source_prd_id") or ""),
        artifact_id=str(identity.get("architecture_artifact_id") or "architecture-normalized"),
        created_at=created_at,
        source=arch_source,
        requirement_ids=requirement_ids,
        architecture=arch_doc.model_dump(mode="json"),
    )
    normalized_tests = NormalizedTestcases(
        run_id=normalized_run_id,
        project_id=str(identity.get("project_id") or ""),
        node_id=str(identity.get("node_id") or ""),
        source_prd_id=str(identity.get("source_prd_id") or ""),
        artifact_id=str(identity.get("testcase_artifact_id") or "testcases-normalized"),
        created_at=created_at,
        source=testcase_source,
        requirement_ids=requirement_ids,
        testcases=test_case_summaries,
    )
    run_inputs_dir = output_path.parent / "inputs"
    run_inputs_dir.mkdir(parents=True, exist_ok=True)
    (run_inputs_dir / "architecture.normalized.json").write_text(
        normalized_arch.model_dump_json(indent=2), encoding="utf-8"
    )
    (run_inputs_dir / "testcases.normalized.json").write_text(
        normalized_tests.model_dump_json(indent=2), encoding="utf-8"
    )


def _scenario_text_from_summary(tc_summary: dict[str, Any]) -> str:
    gherkin = tc_summary.get("gherkin") or {}
    return (
        f"Feature: {gherkin.get('feature', '')}\n"
        f"Scenario: {gherkin.get('scenario', '')}\n"
        f"Tags: {' '.join(tc_summary.get('tags', []))}\n"
        + "\n".join(
            f"{step.get('keyword', '')} {step.get('text', '')}" for step in gherkin.get("steps", [])
        )
    )


def _requirement_group_keys(tags: list[str]) -> set[str]:
    """Return stable REQ/NFR tags without assuming a domain numbering scheme."""
    keys: set[str] = set()
    for tag in tags:
        normalized = str(tag or "").strip().lstrip("@").upper()
        if re.fullmatch(r"(?:REQ|NFR|TC)[-_][A-Z0-9-]+", normalized):
            keys.add(normalized)
    return keys


def _entry_action_for_binding(action: str, binding: dict[str, Any]) -> str:
    if (
        binding.get("status") == "resolved"
        and binding.get("binding_kind") != "component_scope"
        and binding.get("contract_id")
    ):
        return str(binding["contract_id"])
    return action or "handle"


def _bind_entry_plan(
    plan: dict[str, Any],
    card: dict[str, Any] | None,
    *,
    when_text: str,
) -> None:
    reliable_component = bool(plan.get("entry_component")) and plan.get("entry_confidence") in {
        "high",
        "medium",
    }
    binding = resolve_contract_binding(
        card,
        action=str(plan.get("entry_action") or ""),
        input_message={"when": when_text},
        allow_component_scope=reliable_component,
    )
    plan["entry_action"] = _entry_action_for_binding(str(plan.get("entry_action") or ""), binding)
    plan["entry_contract_id"] = binding.get("contract_id", "")
    plan["entry_contract_status"] = binding.get("status", "unresolved")
    plan["entry_contract_reason"] = binding.get("reason", "")
    plan["entry_binding_kind"] = binding.get("binding_kind", "")
    plan["entry_contract_candidates"] = binding.get("candidates", [])


def _apply_requirement_entry_consensus(
    plans: list[dict[str, Any]],
    test_cases: list[Any],
    cards: dict[str, dict[str, Any]],
) -> None:
    """Repair weak entries only when sibling scenarios establish one clear owner."""
    summaries: dict[str, dict[str, Any]] = {}
    for tc in test_cases:
        summary = _test_case_summary(tc)
        summaries[summary["test_case_id"]] = summary

    grouped: dict[str, list[dict[str, Any]]] = {}
    for plan in plans:
        tc = summaries.get(str(plan.get("test_case_id")), {})
        for key in _requirement_group_keys(tc.get("tags", [])):
            grouped.setdefault(key, []).append(plan)

    for key, members in grouped.items():
        strong_counts: dict[str, int] = {}
        for plan in members:
            component = str(plan.get("entry_component") or "")
            if component and plan.get("entry_confidence") in {"high", "medium"}:
                strong_counts[component] = strong_counts.get(component, 0) + 1
        if not strong_counts:
            continue
        ranked = sorted(strong_counts.items(), key=lambda item: (-item[1], item[0]))
        winner, winner_count = ranked[0]
        runner_count = ranked[1][1] if len(ranked) > 1 else 0
        strong_total = sum(strong_counts.values())
        decisive = (runner_count == 0 and winner_count >= 1) or (
            winner_count >= 2
            and winner_count >= runner_count * 2
            and winner_count / strong_total >= 0.70
        )
        if not decisive:
            continue

        for plan in members:
            if plan.get("entry_component") and plan.get("entry_confidence") != "low":
                continue
            tc = summaries.get(str(plan.get("test_case_id")), {})
            scenario_text = _scenario_text_from_summary(tc)
            fallback = str(plan.get("entry_action") or "handle")
            plan["entry_component"] = winner
            plan["entry_action"] = _select_entry_contract_action(
                cards.get(winner, {}), scenario_text, fallback
            )
            plan["entry_confidence"] = "medium"
            plan["entry_reason"] = (
                f"需求组 {key} 的可靠入口共识: {winner} " f"({winner_count}/{strong_total})"
            )
            when_text = next(
                (
                    str(step.get("text", ""))
                    for step in (tc.get("gherkin") or {}).get("steps", [])
                    if str(step.get("keyword", "")).lower() == "when"
                ),
                "",
            )
            _bind_entry_plan(plan, cards.get(winner), when_text=when_text)


def _match_component_names(text: str, component_names: set[str]) -> list[str]:
    """从一段（可能含散文的）文本中提取出现的已知组件名。

    consumer 字段常写作“协调 Privacy & Lifecycle、Profile Intelligence 和 Amazon ACL”，
    直接按分隔符拆分会混入散文，故改为对已知组件名做子串匹配。较长名字优先，避免短名误包含。
    """
    if not text:
        return []
    matched: list[str] = []
    # 按长度降序匹配，防止 “Amazon” 误命中含 “Amazon ACL” / “Amazon 历史” 的片段
    for name in sorted(component_names, key=len, reverse=True):
        if name and name in text and name not in matched:
            matched.append(name)
    return matched


def _filter_module_components(components: list[Any]) -> list[Any]:
    """过滤掉 flowchart/heading 兜底产生的非模块噪声组件（外部 actor、数据聚合体等）。

    若存在职责为权威描述（来自模块清单表）的组件，则只保留这些；否则保留全部
    （兼容仅用 BC 图表达组件的文档）。
    """
    authoritative = [c for c in components if _is_authoritative_resp(c)]
    return authoritative if authoritative else list(components)


def _is_authoritative_resp(component: Any) -> bool:
    resp = getattr(component, "responsibility", "") or ""
    return resp and not resp.startswith(("Bounded Context:", "Module:", "BC:"))


def build_component_cards(arch_doc: ArchDoc) -> dict[str, dict[str, Any]]:
    """由 ArchDoc 生成每个组件的卡片（从 data_flow + 接口 Provider/Consumer 推导进/出接口）。"""
    # 仅保留权威模块组件，过滤 flowchart 噪声（外部 actor / 数据聚合体）
    module_components = _filter_module_components(arch_doc.components)
    # 从 data_flow 推导每个组件的上下游拓扑
    inbound_map: dict[str, set[str]] = {}
    outbound_map: dict[str, set[str]] = {}
    component_ids = [component.name for component in module_components]
    for step in arch_doc.data_flow.sequence:
        source = _canonical_flow_endpoint(step.from_component, component_ids)
        target = _canonical_flow_endpoint(step.to_component, component_ids)
        outbound_map.setdefault(source, set()).add(target)
        inbound_map.setdefault(target, set()).add(source)

    # 显式接口作为补充，尝试按名称前缀归属（如 "POST /api/v1/questions" 出现在 Problem Intake 章节）
    global_inbound: list[dict[str, Any]] = []
    global_outbound: list[dict[str, Any]] = []
    # 按接口契约的 Provider/Consumer 归属：provider 出站、consumer 入站，
    # 同时把 consumer 纳入 provider 的 legal_next_hop、provider 纳入 consumer 的上游。
    # consumer 文本可能混有散文（“协调 A、B 和 C”），故用已知组件名集合做子串匹配提取真实模块名。
    component_name_set = {comp.name for comp in module_components}
    provider_outbound: dict[str, list[dict[str, Any]]] = {}
    consumer_inbound: dict[str, list[dict[str, Any]]] = {}
    for itf in arch_doc.interfaces:
        entry = {"name": itf.name, "protocol": itf.protocol, "contract": itf.contract}
        contract = itf.contract or {}
        provider = (contract.get("provider") or "").strip()
        consumer = (contract.get("consumer") or "").strip()
        consumer_names = _match_component_names(consumer, component_name_set)
        if "内部子节点" in consumer:
            consumer_names.update(name for name in component_name_set if name != provider)
        if provider:
            provider_outbound.setdefault(provider, []).append(entry)
            for cons in consumer_names:
                outbound_map.setdefault(provider, set()).add(cons)
                inbound_map.setdefault(cons, set()).add(provider)
        for cons in consumer_names:
            consumer_inbound.setdefault(cons, []).append(entry)
        if itf.direction == "inbound":
            global_inbound.append(entry)
        else:
            global_outbound.append(entry)

    cards: dict[str, dict[str, Any]] = {}
    for c in module_components:
        component_kind, strict_agent_component = _classify_component(
            c.name,
            getattr(c, "responsibility", ""),
            getattr(c, "dispatch_kind", None),
        )
        # legal_next_hop 只包含实际存在的组件名，过滤掉外部系统/聚合体等噪声端点
        outbound_names = sorted(
            n for n in outbound_map.get(c.name, set()) if n in component_name_set
        )
        inbound_names = sorted(n for n in inbound_map.get(c.name, set()) if n in component_name_set)
        outbound_interfaces = [
            {"name": name, "protocol": "data_flow", "contract": {}} for name in outbound_names
        ]
        inbound_interfaces = [
            {"name": name, "protocol": "data_flow", "contract": {}} for name in inbound_names
        ]
        # 优先用 Provider/Consumer 归属的显式接口（含 required/response 字段）
        outbound_interfaces.extend(provider_outbound.get(c.name, []))
        inbound_interfaces.extend(consumer_inbound.get(c.name, []))
        # 兜底：显式接口的名字包含组件名则归属到该组件
        for entry in global_outbound:
            if c.name.lower() in entry["name"].lower():
                outbound_interfaces.append(entry)
        for entry in global_inbound:
            if c.name.lower() in entry["name"].lower():
                inbound_interfaces.append(entry)

        # 把与该组件相关的架构约束（错误码/业务规则/NFR）收集到卡片里，
        # 让组件 Agent 在输出时能主动遵守 guard 条件。
        relevant_constraints = [
            {
                "type": con.type,
                "description": con.description,
                "target": con.target,
                "value": con.value,
            }
            for con in arch_doc.constraints
            if c.name.lower() in (con.target or "").lower()
            or c.name.lower() in (con.description or "").lower()
        ]

        cards[c.name] = {
            "name": c.name,
            "component_kind": component_kind,
            "strict_agent_component": strict_agent_component,
            "responsibility": c.responsibility,
            "owned_entities": {
                entity: arch_doc.entity_details.get(entity, "")
                for entity, owner in arch_doc.entity_owners.items()
                if owner == c.name
            },
            "tech_stack": c.tech_stack,
            "inbound_interfaces": inbound_interfaces,
            "outbound_interfaces": outbound_interfaces,
            "state_machine_subset": {
                "states": arch_doc.state_machine.states,
                "transitions": [
                    {"from": t.from_state, "to": t.to_state, "trigger": t.trigger}
                    for t in arch_doc.state_machine.transitions
                ],
            },
            "relevant_nfrs": [
                {"id": n.id, "metric": n.metric, "threshold": n.threshold, "unit": n.unit}
                for n in arch_doc.nfrs
            ],
            "relevant_constraints": relevant_constraints,
        }
    return cards


def build_execution_plan(
    test_case_id: str,
    scenario_name: str,
    touched_components: list[str],
    arch: ArchDoc,
    cards: dict[str, dict[str, Any]],
    then_expectations: list[dict[str, Any]] | None = None,
    trigger_message: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """按 data_flow 顺序、过滤到 touched_components，生成逐跳执行计划（向后兼容）。"""
    touched = set(touched_components)
    hops: list[dict[str, Any]] = []
    for step in arch.data_flow.sequence:
        if step.from_component in touched and step.to_component in touched:
            hops.append(
                {
                    "from": step.from_component,
                    "to": step.to_component,
                    "action": step.action,
                    "message_hint": step.message,
                }
            )
    return {
        "test_case_id": test_case_id,
        "scenario_name": scenario_name,
        "touched_components": list(touched_components),
        "hops": hops,
        "trigger_message": trigger_message or {},
        "then_expectations": then_expectations or [],
    }


def build_component_agent_prompt(
    card: dict[str, Any],
    data_flow_summary: list[dict[str, Any]] | None = None,
    all_component_names: list[str] | None = None,
    contract_binding: dict[str, Any] | None = None,
) -> str:
    """组件 agent 的静态 prompt 模板；运行时由会话注入入消息/action/状态。"""
    data_flow_summary = data_flow_summary or []
    comp_name = card.get("name", "")

    # Only keep edges that involve this component to shorten the prompt.
    relevant_flow = [
        step
        for step in data_flow_summary
        if step.get("from") == comp_name or step.get("to") == comp_name
    ]

    outbound_names = [
        itf["name"]
        for itf in card.get("outbound_interfaces", [])
        if itf.get("protocol") == "data_flow"
    ]
    known_components = set(all_component_names or [])
    legal_next_hops = (
        [name for name in outbound_names if name in known_components]
        if known_components
        else outbound_names
    )
    external_terminal_targets = sorted(
        {
            str(step.get("to"))
            for step in relevant_flow
            if step.get("from") == comp_name
            and step.get("to")
            and known_components
            and step.get("to") not in known_components
        }
    )

    prompt_card = dict(card)
    if contract_binding is not None:
        if contract_binding.get("status") == "resolved":
            flow_targets = {
                str(step.get("to"))
                for step in relevant_flow
                if step.get("from") == comp_name and step.get("to")
            }
            relevant_outbound = []
            for interface in card.get("outbound_interfaces", []):
                contract = interface.get("contract") or {}
                consumers = {
                    item.strip()
                    for item in re.split(r"[,，、;；\n]+", str(contract.get("consumer") or ""))
                    if item.strip()
                }
                if interface.get("name") in flow_targets or consumers.intersection(flow_targets):
                    relevant_outbound.append(interface)
            prompt_card["inbound_interfaces"] = []
            prompt_card["outbound_interfaces"] = relevant_outbound
            prompt_card["selected_contract"] = {
                "contract_id": contract_binding.get("contract_id", ""),
                "interface_name": contract_binding.get("interface_name", ""),
                "protocol": contract_binding.get("protocol", ""),
                "binding_role": contract_binding.get("binding_role", "unknown"),
                "contract": contract_binding.get("contract", {}),
            }

    # 收集当前绑定契约字段；旧调用未提供 binding 时保持兼容。
    inbound_required_lines: list[str] = []
    if contract_binding is not None and contract_binding.get("status") == "resolved":
        role = contract_binding.get("binding_role", "provider")
        fields = (
            contract_binding.get("accepted_fields", [])
            if role == "consumer"
            else contract_binding.get("required_fields", [])
        )
        inbound_required_lines = [
            f"- {contract_binding.get('contract_id', '')}: {field}" for field in fields
        ]
    elif contract_binding is None:
        for itf in card.get("inbound_interfaces", []):
            contract = itf.get("contract") or {}
            for field in contract.get("required", []):
                inbound_required_lines.append(f"- 来自 {itf['name']}: {field}")
    outbound_expected_lines: list[str] = []
    if contract_binding is not None and contract_binding.get("status") == "resolved":
        fields = (
            contract_binding.get("response_fields", [])
            if contract_binding.get("binding_role") != "consumer"
            else []
        )
        if fields:
            outbound_expected_lines.append(f"- {contract_binding.get('contract_id', '')}: {fields}")
    elif contract_binding is None:
        for itf in card.get("outbound_interfaces", []):
            contract = itf.get("contract") or {}
            fields = contract.get("response") or contract.get("required") or []
            if fields:
                outbound_expected_lines.append(f"- 到 {itf['name']}: {fields}")

    inbound_required_section = (
        "\n".join(inbound_required_lines)
        if inbound_required_lines
        else "（data_flow 推导的接口暂无显式 required 字段）"
    )
    outbound_expected_section = (
        "\n".join(outbound_expected_lines)
        if outbound_expected_lines
        else "（data_flow 推导的接口暂无显式 response 字段）"
    )

    constraints = card.get("relevant_constraints", [])
    constraints_section = (
        "\n".join(f"- [{c.get('type', 'rule')}] {c.get('description', '')}" for c in constraints)
        if constraints
        else "（无）"
    )

    schema = (
        '{"hop_index":0,"component":"","action":"","input_message":{},'
        '"output_message":{},"status":"PASS|ERROR|WARNING","latency_ms":0,'
        '"side_effects":[{"type":"write|read|delete|append","target":"","data":{}}],'
        '"state_change":{"entity":"","from_state":"","to_state":"","trigger":""}|null,'
        '"self_check":{"consumed_input_ok":true,"produced_fields":[],'
        '"missing_required_inputs":[],"undefined_next_call":null,'
        '"then_verification":{"assertion":"","satisfied":true,"evidence":""}|null},'
        '"next_hop":{"component":"","action":"","contract_id":"","reason":""}|null}'
    )

    return (
        f"你是组件【{comp_name}】。只扮演本组件，按 input_message/action/shared_state "
        "产出一个 HopResult；不要模拟其他组件或整条链路。\n\n"
        f"COMPONENT_CARD\n```json\n{json.dumps(prompt_card, ensure_ascii=False, separators=(',', ':'))}\n```\n\n"
        "CONTRACT_BINDING\n"
        f"```json\n{json.dumps(contract_binding or {'status': 'legacy-unbound'}, ensure_ascii=False, separators=(',', ':'))}\n```\n\n"
        "CONSTRAINTS\n"
        f"- legal_next_hop: {json.dumps(legal_next_hops, ensure_ascii=False, separators=(',', ':'))}\n"
        f"- external_terminal_targets: {json.dumps(external_terminal_targets, ensure_ascii=False, separators=(',', ':'))}\n"
        f"- relevant_flow: {json.dumps(relevant_flow, ensure_ascii=False, separators=(',', ':'))}\n"
        "next_hop.component 必须在 legal_next_hop 内；调用内部下游时填写其 contract_id；"
        "向 external_terminal_targets 返回结果时 next_hop 必须设 null，且不得填写 undefined_next_call。\n\n"
        "FIELDS\n"
        "inbound_required:\n" + inbound_required_section + "\n"
        "outbound_expected:\n" + outbound_expected_section + "\n"
        "guards:\n" + constraints_section + "\n\n"
        "OUTPUT raw JSON only, no markdown. Required shape:\n"
        f"{schema}\n\n"
        "Rules: phase given=建立前置状态, when=执行业务动作, then=验证断言；"
        "缺 inbound required 时 status=WARNING 并列入 missing_required_inputs；"
        "未定义下游写 undefined_next_call；produced_fields 只列 output_message 顶层业务字段；"
        "phase=then 或 next_hop=null 时必须填 then_verification；"
        "拒绝/上限/错误必须在 output_message 给出原因/错误码/状态；"
        "state_change.from_state 取 shared_state，to_state/trigger 写动作后的真实迁移。"
    )


def assemble_trace_from_hops(test_case_id: str, hops: list[dict[str, Any]]) -> ExecutionTrace:
    """把逐跳 HopResult 组装成 ExecutionTrace（input/output 终于被填满）。"""
    steps: list[TraceStep] = []
    side_effects: list[SideEffect] = []
    transitions: list[StateTransitionRecord] = []
    then_verifications: list[dict[str, Any]] = []
    t_ms = 0
    for i, h in enumerate(hops):
        nxt = hops[i + 1]["component"] if i + 1 < len(hops) else None
        latency = int(h.get("latency_ms", 0) or 0)
        self_check = h.get("self_check") if isinstance(h.get("self_check"), dict) else {}
        if h.get("synthetic"):
            self_check = dict(self_check)
            self_check["synthetic"] = True
        if h.get("contract_binding"):
            self_check = dict(self_check)
            self_check["contract_binding"] = h["contract_binding"]
        steps.append(
            TraceStep(
                step_number=i + 1,
                phase=h.get("phase", "when"),
                component=h["component"],
                action=str(h.get("action", "unknown")),
                target=nxt,
                method=h.get("method"),
                parameters=h.get("parameters"),
                input=h.get("input_message") or {},
                output=h.get("output_message") or {},
                self_check=self_check,
                next_hop=h.get("next_hop"),
                status=h.get("status"),
                timestamp_ms=t_ms,
                latency_ms=latency,
            )
        )
        t_ms += latency
        for se in h.get("side_effects", []) or []:
            side_effects.append(
                SideEffect(
                    type=se.get("type", "write"),
                    target=se.get("target", ""),
                    data=se.get("data", {}),
                )
            )
        sc = h.get("state_change")
        if isinstance(sc, dict) and "entity" in sc and "from_state" in sc and "to_state" in sc:
            transitions.append(
                StateTransitionRecord(
                    entity=sc["entity"],
                    from_state=sc["from_state"],
                    to_state=sc["to_state"],
                    trigger=sc.get("trigger", ""),
                )
            )
        tv = self_check.get("then_verification")
        if isinstance(tv, dict) and tv.get("assertion"):
            then_verifications.append(
                {
                    "component": h.get("component"),
                    "assertion": tv.get("assertion"),
                    "satisfied": tv.get("satisfied", False),
                    "evidence": tv.get("evidence", ""),
                }
            )
    return ExecutionTrace(
        trace_id=f"TRACE-{test_case_id}",
        test_case_id=test_case_id,
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=None,
        total_latency_ms=t_ms,
        steps=steps,
        side_effects=side_effects,
        state_transitions=transitions,
        then_verifications=then_verifications,
    )


def compute_contract_check(
    component_cards: dict[str, dict[str, Any]],
    plans: list[dict[str, Any]],
    hops_by_tc: dict[str, list[dict[str, Any]]],
    state_machine: Any | None = None,
    entity_owners: dict[str, str] | None = None,
) -> dict[str, Any]:
    """对每场景跑 interface_checker + 状态机校验，并算全局孤儿组件。"""
    per_scenario: dict[str, Any] = {}
    all_reached: set[str] = set()
    for plan in plans:
        tc_id = plan["test_case_id"]
        hops = hops_by_tc.get(tc_id, [])
        all_reached |= {h["component"] for h in hops}
        res = check_scenario(
            hops,
            component_cards,
            plan.get("then_expectations", []),
            emit_missing_contract=False,
        )
        state_findings = validate_state_transitions(
            hops, component_cards, state_machine, entity_owners
        )
        findings = res.findings + state_findings
        # 若状态校验发现 FAIL，提升该场景 interface_compat 为 FAIL
        status = res.status
        if any(f.severity == "FAIL" for f in state_findings):
            status = "FAIL"
        per_scenario[tc_id] = {
            "status": status,
            "detail": "; ".join(f.detail for f in findings) or res.detail,
            "findings": [
                {"kind": f.kind, "severity": f.severity, "detail": f.detail} for f in findings
            ],
        }
    strict_component_cards = {
        name: card
        for name, card in component_cards.items()
        if card.get("strict_agent_component", True)
    }
    orphans = check_orphans(all_reached, strict_component_cards)
    coverage = check_contract_coverage(strict_component_cards, all_reached)
    return {
        "per_scenario": per_scenario,
        "global_findings": [
            {"kind": f.kind, "severity": f.severity, "detail": f.detail}
            for f in [*orphans, *coverage]
        ],
    }


def cmd_contract_check(args: argparse.Namespace) -> int:
    """读 prompts.json + hops（按 tc 聚合）→ 写 interface_compat 结果。"""
    prompts_data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    manifest_errors = run_manifest_errors(prompts_data)
    if manifest_errors:
        print("ERROR: " + "; ".join(manifest_errors), file=sys.stderr)
        return 1
    hops_by_tc = json.loads(Path(args.hops).read_text(encoding="utf-8"))
    arch_doc = _parse_arch_doc(prompts_data["arch_input_path"])
    out = compute_contract_check(
        component_cards=prompts_data["component_cards"],
        plans=prompts_data["plans"],
        hops_by_tc=hops_by_tc,
        state_machine=arch_doc.state_machine,
        entity_owners=arch_doc.entity_owners,
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Contract-check written to: {args.output}")
    return 0


def build_validator_prompt(trace: ExecutionTrace, tc: Any, arch_doc: ArchDoc) -> str:
    """Build a validator prompt for a subagent.

    Reuses the existing ValidatorAgentCore prompt builder for consistency.
    """
    # ValidatorAgentCore expects an LLM client; pass a dummy one since we only
    # need the prompt text.
    core = ValidatorAgentCore(llm_client=None, token_budget=1_000_000)  # type: ignore[arg-type]
    return cast(str, core._build_prompt(trace, tc, arch_doc))


def _gherkin_phase_coverage(tc_summary: dict[str, Any]) -> dict[str, Any]:
    """Return Gherkin phase coverage from source steps, independent of component hops."""
    current_phase = ""
    phase_order: list[str] = []
    for step in tc_summary.get("gherkin", {}).get("steps", []):
        keyword = str(step.get("keyword", "")).strip().lower()
        if keyword in ("given", "when", "then"):
            current_phase = keyword
        elif keyword in ("and", "but") and current_phase:
            keyword = current_phase
        else:
            current_phase = keyword
        phase = current_phase or keyword
        if phase in ("given", "when", "then") and phase not in phase_order:
            phase_order.append(phase)
    present = {phase: phase in phase_order for phase in ("given", "when", "then")}
    order_positions = [
        phase_order.index(phase) for phase in ("given", "when", "then") if phase in phase_order
    ]
    return {
        **present,
        "ordered": order_positions == sorted(order_positions),
        "phase_order": phase_order,
        "missing": [phase for phase, ok in present.items() if not ok],
    }


def _compact_self_check(self_check: dict[str, Any]) -> dict[str, Any]:
    """Keep validator-relevant self-check evidence without repeating full contracts."""
    compact = {
        key: self_check[key]
        for key in (
            "synthetic",
            "produced_fields",
            "missing_required_inputs",
            "undefined_next_call",
            "artifact_error",
            "parse_error",
        )
        if key in self_check and self_check[key] not in (None, "", [], {})
    }
    binding = self_check.get("contract_binding")
    if isinstance(binding, dict):
        compact["contract_binding"] = {
            key: binding.get(key)
            for key in (
                "status",
                "contract_id",
                "binding_kind",
                "architecture_declared",
                "required_fields",
                "response_fields",
                "candidates",
                "reason",
            )
            if binding.get(key) not in (None, "", [], {})
        }
    return compact


def _evidence_field_exists(value: Any, field: str) -> bool:
    current = value
    for part in [p for p in re.split(r"\.|\[|\]", field) if p]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            if isinstance(value, dict) and "payload" in value and value["payload"] is not value:
                return _evidence_field_exists(value["payload"], field)
            return False
    return True


def build_deterministic_verdicts(
    trace: ExecutionTrace, tc_summary: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Precompute exact checks so the validator spends tokens on semantics only."""
    coverage = _gherkin_phase_coverage(tc_summary)
    structure_ok = (
        all(coverage[phase] for phase in ("given", "when", "then")) and coverage["ordered"]
    )
    artifact_errors: list[str] = []
    binding_errors: list[str] = []
    field_errors: list[str] = []
    binding_checked = 0
    field_checked = 0
    for step in trace.steps:
        self_check = step.self_check if isinstance(step.self_check, dict) else {}
        if self_check.get("artifact_error") or step.status == "ARTIFACT_ERROR":
            artifact_errors.append(
                f"hop {step.step_number}: {self_check.get('artifact_error', 'artifact_error')}"
            )
        if self_check.get("synthetic") or step.action == "setup_context":
            continue
        binding = self_check.get("contract_binding")
        if isinstance(binding, dict):
            binding_checked += 1
            if binding.get("status") != "resolved":
                binding_errors.append(
                    f"hop {step.step_number}: binding={binding.get('status', 'missing')}"
                )
        else:
            binding_errors.append(f"hop {step.step_number}: binding=missing")
        missing_required = self_check.get("missing_required_inputs") or []
        if missing_required:
            field_errors.append(
                f"hop {step.step_number}: missing required {', '.join(map(str, missing_required))}"
            )
        produced = self_check.get("produced_fields") or []
        for field in produced:
            field_checked += 1
            if not _evidence_field_exists(step.output, str(field)):
                field_errors.append(f"hop {step.step_number}: produced field absent: {field}")

    performance = (tc_summary.get("expectations") or {}).get("performance") or {}
    threshold = performance.get("max_total_latency_ms")
    if threshold is None:
        threshold = performance.get("max_latency_ms")
    performance_status = "NOT_APPLICABLE"
    performance_detail = "no deterministic single-trace latency threshold"
    if isinstance(threshold, (int, float)):
        performance_status = "PASS" if trace.total_latency_ms <= threshold else "FAIL"
        performance_detail = f"total={trace.total_latency_ms}ms, threshold={threshold}ms"

    binding_status = (
        "PASS"
        if binding_checked and not binding_errors
        else ("FAIL" if binding_errors else "NOT_APPLICABLE")
    )
    fields_status = (
        "PASS"
        if field_checked and not field_errors
        else ("FAIL" if field_errors else "NOT_APPLICABLE")
    )
    return {
        "structure": {
            "status": "PASS" if structure_ok else "FAIL",
            "detail": f"phase_order={coverage['phase_order']}, missing={coverage['missing']}",
        },
        "artifact_integrity": {
            "status": "FAIL" if artifact_errors else "PASS",
            "detail": artifact_errors or ["no artifact errors"],
        },
        "contract_binding": {
            "status": binding_status,
            "detail": binding_errors or [f"resolved bindings={binding_checked}"],
        },
        "produced_field_presence": {
            "status": fields_status,
            "detail": field_errors or [f"verified produced fields={field_checked}"],
        },
        "performance_threshold": {
            "status": performance_status,
            "detail": performance_detail,
        },
    }


def build_compact_trace_v2(trace: ExecutionTrace, tc_summary: dict[str, Any]) -> dict[str, Any]:
    """Build validator-facing trace evidence without conflating hops with Gherkin phases."""
    component_hops: list[dict[str, Any]] = []
    artifact_warnings: list[dict[str, Any]] = []
    for step in trace.steps:
        self_check = step.self_check if isinstance(step.self_check, dict) else {}
        is_synthetic = bool(self_check.get("synthetic")) or step.action == "setup_context"
        hop = {
            "step_number": step.step_number,
            "execution_phase": step.phase,
            "synthetic": is_synthetic,
            "component": step.component,
            "action": step.action,
            "target": step.target,
            "status": step.status,
            "event_in": step.input.get("event") if isinstance(step.input, dict) else None,
            "event_out": step.output.get("event") if isinstance(step.output, dict) else None,
            "output_summary": step.output,
            "self_check": _compact_self_check(self_check),
            "next_hop": step.next_hop,
        }
        component_hops.append(hop)
        if self_check.get("artifact_error") or step.status == "ARTIFACT_ERROR":
            artifact_warnings.append(
                {
                    "step_number": step.step_number,
                    "component": step.component,
                    "kind": self_check.get("artifact_error", "artifact_error"),
                    "detail": self_check.get("parse_error", ""),
                }
            )
    real_hops = [h for h in component_hops if not h.get("synthetic")]
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "trace_id": trace.trace_id,
        "test_case_id": trace.test_case_id,
        "total_latency_ms": trace.total_latency_ms,
        "deterministic_verdicts": build_deterministic_verdicts(trace, tc_summary),
        "gherkin_phase_coverage": _gherkin_phase_coverage(tc_summary),
        "component_execution": {
            "hops": component_hops,
            "real_hop_count": len(real_hops),
            "synthetic_hop_count": len(component_hops) - len(real_hops),
        },
        "side_effects": [
            {"type": se.type, "target": se.target, "data": se.data} for se in trace.side_effects
        ],
        "state_transitions": [
            {
                "entity": st.entity,
                "from_state": st.from_state,
                "to_state": st.to_state,
                "trigger": st.trigger,
            }
            for st in trace.state_transitions
        ],
        "then_verifications": trace.then_verifications,
        "artifact_warnings": artifact_warnings,
    }


def build_compact_validator_prompt(
    trace: ExecutionTrace,
    tc_summary: dict[str, Any],
    component_cards: dict[str, dict[str, Any]],
) -> str:
    """Build a smaller validator prompt that keeps audit files as source of truth.

    The full hops remain in hops.json for strict audit/reporting. This prompt
    sends the validator only the evidence needed for five-dimension judgment.
    """
    touched = {step.component for step in trace.steps}
    bindings_by_component: dict[str, list[dict[str, Any]]] = {}
    for step in trace.steps:
        self_check = step.self_check if isinstance(step.self_check, dict) else {}
        binding = self_check.get("contract_binding")
        if not isinstance(binding, dict):
            continue
        compact_binding = _compact_self_check({"contract_binding": binding}).get(
            "contract_binding", {}
        )
        existing = bindings_by_component.setdefault(step.component, [])
        if compact_binding and compact_binding not in existing:
            existing.append(compact_binding)
    relevant_components = [
        {
            "name": name,
            "responsibility": card.get("responsibility", ""),
            "selected_contract_ids": [
                binding.get("contract_id")
                for binding in bindings_by_component.get(name, [])
                if binding.get("contract_id")
            ],
        }
        for name, card in component_cards.items()
        if name in touched
    ]
    compact_trace = build_compact_trace_v2(trace, tc_summary)
    gherkin = {
        "scenario": tc_summary.get("gherkin", {}).get("scenario"),
        "steps": tc_summary.get("gherkin", {}).get("steps", []),
        "expectations": tc_summary.get("expectations", {}),
    }
    return (
        "Validator Agent. Return one raw JSON object, no markdown.\n"
        "Rules: judge only supplied evidence; raw hops remain in audit files; "
        "trace.deterministic_verdicts PASS/FAIL results are authoritative: copy structure, "
        "copy performance_threshold when applicable, and never PASS contract when binding or field presence FAIL; "
        "structure uses trace.gherkin_phase_coverage, not hop phase labels; "
        "flow checks component order and declared next_hop/interface fit; "
        "state checks transition ownership; contract checks produced fields and "
        "then_verifications; artifact_warnings are validate_arch trace_artifact issues, "
        "not architecture gaps; performance checks latency/NFRs. "
        "overall=FAIL if any dimension FAIL, WARNING if no FAIL but any WARNING, "
        "PASS if all pass, MISSING only for insufficient evidence.\n"
        "JSON keys: structure, flow, state, contract, performance "
        "as {status:PASS|FAIL|WARNING|MISSING, detail:string}; "
        "overall:PASS|FAIL|WARNING|MISSING; "
        "failure_analysis only on FAIL with dimension/problem/severity/impact/"
        "suggestion/scope/issue_kind/fix_owner; "
        "warning_analysis only on WARNING with dimension/problem/suggestion/"
        "scope/issue_kind/fix_owner.\n\n"
        "COMPONENTS\n"
        f"```json\n{json.dumps(relevant_components, ensure_ascii=False, separators=(',', ':'))}\n```\n\n"
        "GHERKIN\n"
        f"```json\n{json.dumps(gherkin, ensure_ascii=False, separators=(',', ':'))}\n```\n\n"
        "TRACE\n"
        f"```json\n{json.dumps(compact_trace, ensure_ascii=False, separators=(',', ':'))}\n```"
    )


def merge_interface_compat(val_output: dict[str, Any], compat: dict[str, Any]) -> dict[str, Any]:
    """把确定性接口检查结果并入 validator 输出，必要时把 overall 拉到 FAIL/WARNING。"""
    merged = dict(val_output)
    merged["interface_compat"] = {"status": compat["status"], "detail": compat["detail"]}
    if compat["status"] == "FAIL":
        merged["overall"] = "FAIL"
        # interface_compat 是确定性权威信号，但保留 validator 已有的失败分析（如果更具体）。
        # 根据 detail 判断 scope：字段级缺失归 module，接口/数据流缺失归 top_level。
        detail_lower = compat.get("detail", "").lower()
        scope = "module" if ("字段" in detail_lower or "field" in detail_lower) else "top_level"
        merged.setdefault(
            "failure_analysis",
            {
                "dimension": "interface_compat",
                "problem": compat["detail"],
                "severity": "high",
                "impact": "组件间契约不符，按当前设计无法串通",
                "suggestion": "补全上游输出字段或修正接口契约/数据流定义",
                "scope": scope,
            },
        )
    elif compat["status"] == "WARNING" and merged.get("overall") == "PASS":
        # 只标记 overall 为 WARNING，但不生成 warning_analysis，
        # 因为 "缺少 inbound 契约" 等属于 checker 噪音，不应作为架构建议。
        merged["overall"] = "WARNING"
    return merged


def _markdown_json(value: Any) -> str:
    """把对象序列化为 JSON 并转义 Markdown 表格/行内特殊字符。"""
    text = json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", "")


def render_dataflow_section(
    plans: list[dict[str, Any]], hops_by_tc: dict[str, list[dict[str, Any]]]
) -> str:
    """渲染「数据流流转」Markdown 段。"""
    lines = ["## 数据流流转", ""]
    for plan in plans:
        tc_id = plan["test_case_id"]
        lines.append(f"### {tc_id} - {plan['scenario_name']}")
        for h in hops_by_tc.get(tc_id, []):
            ins = _markdown_json(h.get("input_message", {}))
            outs = _markdown_json(h.get("output_message", {}))
            lines.append(
                f"- **{h['component']}** [{h.get('status', '?')}, {h.get('latency_ms', 0)}ms]: "
                f"{ins} → {outs}"
            )
        lines.append("")
    return "\n".join(lines)


def cmd_prepare(args: argparse.Namespace) -> int:
    """Generate simulator and validator prompts for each test case."""
    skill = ValidateArchSkill()
    try:
        feature_arg, arch_arg, formal_manifest, formal_manifest_path = _resolve_input_arguments(
            args
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 5 if "schema" in str(exc).lower() or "match" in str(exc).lower() else 3
    feature_path = skill._resolve_path(feature_arg)
    arch_path = skill._resolve_path(arch_arg)

    if not Path(feature_path).exists():
        print(f"ERROR: feature file not found: {feature_path}", file=sys.stderr)
        return 3
    if not Path(arch_path).exists():
        print(f"ERROR: architecture document not found: {arch_path}", file=sys.stderr)
        return 3
    if not args.output and not getattr(args, "output_dir", None):
        print("ERROR: --output or --output-dir is required", file=sys.stderr)
        return 1

    output_path = (
        Path(args.output).resolve()
        if args.output
        else Path(args.output_dir).resolve() / "plan.json"
    )
    if not args.output and args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    run_inputs_dir = output_path.parent / "inputs"

    # Aggregate directory of arch docs into a run-scoped file if needed.
    arch_input_path = arch_path
    if Path(arch_path).is_dir():
        arch_input_path = skill._aggregate_arch_docs(arch_path, run_inputs_dir)
        print(f"Aggregated arch docs to: {arch_input_path}")

    # Preprocess to scope validation to the current layer only.
    arch_input_path = skill._preprocess_for_current_layer(arch_input_path, run_inputs_dir)
    if _normalize_recursive_package_input(arch_input_path):
        print(f"Normalized recursive package vocabulary: {arch_input_path}")
    arch_input_path = str(Path(arch_input_path).resolve())
    print(f"Preprocessed arch doc: {arch_input_path}")
    run_manifest = build_run_manifest(
        feature_path, arch_path, arch_input_path, getattr(args, "config", None)
    )

    # Load test cases and architecture model.
    config = load_config(args.config)
    prepare_llm_client = None
    loader = Loader(config.loader)
    feature_files = _feature_files(feature_path)
    loaded = loader.load(str(feature_files[0]), arch_input_path)
    if len(feature_files) > 1:
        merged_test_cases = []
        for index, feature_file in enumerate(feature_files, start=1):
            current = loaded if index == 1 else loader.load(str(feature_file), arch_input_path)
            prefix = re.sub(r"[^A-Za-z0-9_-]+", "-", feature_file.stem).strip("-")
            merged_test_cases.extend(
                case.model_copy(
                    update={"test_case_id": f"F{index:03d}-{prefix}-{case.test_case_id}"}
                )
                for case in current.test_cases
            )
        loaded.test_cases = merged_test_cases
    test_case_ids = [case.test_case_id for case in loaded.test_cases]
    if len(test_case_ids) != len(set(test_case_ids)):
        print("ERROR: duplicate test_case_id across Feature files", file=sys.stderr)
        return 5

    # Filter to requested scenario range / IDs.
    selected = _select_test_cases(loaded.test_cases, args)
    if selected is None:
        return 1
    loaded.test_cases = selected
    if not loaded.test_cases:
        print("ERROR: no test cases matched the requested scenario selection", file=sys.stderr)
        return 1

    arch_doc = _parse_arch_doc(arch_input_path)

    cards = build_component_cards(arch_doc)
    # 入口推断只考虑权威模块组件，避免外部 actor / 数据聚合体等噪声被选为入口
    module_components = _filter_module_components(arch_doc.components)
    plans: list[dict[str, Any]] = []
    all_component_names = [c.name for c in module_components]
    component_ids = [component.name for component in module_components]
    data_flow_summary = [
        {
            "from": _canonical_flow_endpoint(step.from_component, component_ids),
            "to": _canonical_flow_endpoint(step.to_component, component_ids),
            "action": step.action,
            "message": step.message,
        }
        for step in arch_doc.data_flow.sequence
    ]
    component_prompts = {}
    if not getattr(args, "slim_prompts", False):
        component_prompts = {
            name: build_component_agent_prompt(card, data_flow_summary, all_component_names)
            for name, card in cards.items()
        }

    for tc in loaded.test_cases:
        scenario_text = (
            f"Feature: {tc.gherkin.get('feature', '')}\nScenario: {tc.gherkin.get('scenario', '')}\n"
            + f"Tags: {' '.join(tc.tags)}\n"
            + "\n".join(f"{s['keyword']} {s['text']}" for s in tc.gherkin.get("steps", []))
        )
        entry = _infer_entry_component(
            scenario_text=scenario_text,
            component_cards=cards,
            data_flow_summary=data_flow_summary,
            llm_client=prepare_llm_client,
            components=module_components,
        )
        tc_summary = _test_case_summary(tc)
        interactions = _interaction_sequence(tc_summary)
        when_text = str(interactions[0].get("when", ""))
        for interaction in interactions:
            interaction_text = (
                f"Feature: {tc.gherkin.get('feature', '')}\n"
                f"Scenario: {tc.gherkin.get('scenario', '')}\n"
                + "\n".join(f"Given {text}" for text in interaction["given"])
                + f"\nWhen {interaction['when']}"
            )
            interaction_entry = _infer_entry_component(
                scenario_text=interaction_text,
                component_cards=cards,
                data_flow_summary=data_flow_summary,
                llm_client=prepare_llm_client,
                components=module_components,
            )
            interaction.update(interaction_entry)
            interaction["trigger_message"] = {
                "when": interaction["when"],
                "action_hint": None,
            }
            _bind_entry_plan(
                interaction,
                cards.get(interaction_entry["entry_component"]),
                when_text=interaction["when"],
            )

        then_maps = tc.technical_mapping.get("then_steps", [])
        # Technical mapping targets are dicts and often empty; derive clean
        # assertion strings directly from Gherkin Then/And steps for the
        # then-phase hop that will run after the main chain.
        then_assertions = _then_assertions_from_gherkin(tc_summary)
        when_maps = tc.technical_mapping.get("when_steps", [])
        trigger_message: dict[str, Any] = interactions[0]["trigger_message"]
        if when_maps and isinstance(when_maps[0].assertion, dict):
            trigger_message["action_hint"] = when_maps[0].assertion.get("type")

        plan_item = {
            "test_case_id": tc.test_case_id,
            "scenario_name": tc.source_scenario,
            "entry_component": entry["entry_component"],
            "entry_action": entry["entry_action"],
            "entry_confidence": entry["confidence"],
            "entry_reason": entry["reason"],
            "trigger_message": trigger_message,
            "then_expectations": [
                {
                    "component": (
                        m.target.get("component", "")
                        if isinstance(m.target, dict)
                        else str(m.target)
                    ),
                    "assertion": m.assertion,
                }
                for m in then_maps
                if (m.target.get("component") if isinstance(m.target, dict) else m.target)
            ],
            "then_assertions": then_assertions,
            "interaction_sequence": interactions,
        }
        _bind_entry_plan(
            plan_item,
            cards.get(entry["entry_component"]),
            when_text=when_text,
        )
        # The primary fields are retained for backwards-compatible consumers;
        # the complete sequence is the source of truth for strict execution.
        interactions[0].update(
            {
                key: plan_item.get(key)
                for key in (
                    "entry_component",
                    "entry_action",
                    "entry_confidence",
                    "entry_reason",
                    "entry_contract_id",
                    "entry_contract_status",
                    "entry_contract_reason",
                    "entry_binding_kind",
                    "entry_contract_candidates",
                )
            }
        )
        plans.append(plan_item)

    _apply_requirement_entry_consensus(plans, loaded.test_cases, cards)
    for plan_item in plans:
        interactions = plan_item.get("interaction_sequence") or []
        if interactions:
            interactions[0].update(
                {
                    key: plan_item.get(key)
                    for key in (
                        "entry_component",
                        "entry_action",
                        "entry_confidence",
                        "entry_reason",
                        "entry_contract_id",
                        "entry_contract_status",
                        "entry_contract_reason",
                        "entry_binding_kind",
                        "entry_contract_candidates",
                    )
                }
            )

    # Allow users to bulk-override inferred entry components.
    try:
        entry_overrides = _load_entry_overrides(getattr(args, "entry_overrides", None))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for plan_item in plans:
        _apply_entry_overrides(plan_item, entry_overrides)
        if plan_item["test_case_id"] not in entry_overrides:
            continue
        tc = next(
            item for item in loaded.test_cases if item.test_case_id == plan_item["test_case_id"]
        )
        when_text = next(
            (
                str(step.get("text", ""))
                for step in tc.gherkin.get("steps", [])
                if str(step.get("keyword", "")).lower() == "when"
            ),
            "",
        )
        _bind_entry_plan(
            plan_item,
            cards.get(plan_item.get("entry_component", "")),
            when_text=when_text,
        )
        interactions = plan_item.get("interaction_sequence") or []
        if interactions:
            interactions[0].update(
                {
                    key: plan_item.get(key)
                    for key in (
                        "entry_component",
                        "entry_action",
                        "entry_confidence",
                        "entry_reason",
                        "entry_contract_id",
                        "entry_contract_status",
                        "entry_contract_reason",
                        "entry_binding_kind",
                        "entry_contract_candidates",
                    )
                }
            )

    test_case_summaries = [_test_case_summary(tc) for tc in loaded.test_cases]
    tc_summary_by_id = {tc["test_case_id"]: tc for tc in test_case_summaries}
    model_context = {
        "simulator": {
            "provider": config.llm.simulator.provider,
            "model": config.llm.simulator.model,
        },
        "validator": {
            "provider": config.llm.validator.provider,
            "model": config.llm.validator.model,
        },
    }
    for plan_item in plans:
        plan_item["cache_key"] = build_scenario_cache_key(
            tc_summary_by_id[plan_item["test_case_id"]],
            plan_item,
            run_manifest,
            model_context,
            build_scenario_architecture_dependency(
                plan_item.get("entry_component", ""), cards, data_flow_summary, arch_doc
            ),
        )
    equivalence_summary = (
        assign_strict_equivalence_groups(test_case_summaries, plans)
        if getattr(args, "strict_equivalence", False)
        else {"mode": "off", "groups": 0, "reusable_rows": 0, "fallback_rows": len(plans)}
    )

    output_data = {
        "feature_path": feature_path,
        "arch_path": arch_path,
        "arch_input_path": arch_input_path,
        "test_cases": test_case_summaries,
        "component_cards": cards,
        "component_prompt_mode": "dynamic" if getattr(args, "slim_prompts", False) else "embedded",
        "entry_inference": "local-architecture",
        "cache_schema_version": "validate-arch-cache-v1",
        "model_context": model_context,
        "equivalence_summary": equivalence_summary,
        "run_manifest": run_manifest,
        "plans": plans,
    }
    if formal_manifest:
        output_data["protocol_metadata"] = formal_protocol_metadata(formal_manifest)
        run_manifest["inputs"]["formal_input_manifest"] = {
            "path": str(formal_manifest_path),
            "sha256": _sha256_path(str(formal_manifest_path)),
            "schema_version": formal_manifest.schema_version,
        }
        _refresh_run_manifest_id(run_manifest)
    elif getattr(args, "identity_manifest", None):
        try:
            _attach_identity_manifest(output_data, run_manifest, args.identity_manifest)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 5
    if component_prompts:
        output_data["component_prompts"] = component_prompts

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_normalized_inputs(
        output_path,
        output_data,
        run_manifest,
        arch_path,
        feature_path,
        arch_doc,
        test_case_summaries,
    )
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path.parent / "run_manifest.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    eligible = [
        plan
        for plan in plans
        if not plan_item_semantic_errors(plan, tc_summary_by_id.get(plan["test_case_id"]))
    ]
    estimated_scenarios = max(0, len(eligible) - int(equivalence_summary.get("reusable_rows", 0)))
    est = estimated_scenarios * 3  # likely two component hops + one validator
    print(
        f"Prepared {len(plans)} scenario(s); strict 可执行={len(eligible)}, "
        f"语义门禁跳过={len(plans) - len(eligible)}, 预估 subagent 派发次数≈{est}"
    )
    return 0


def _synthetic_first_input(plan_item: dict[str, Any], tc_summary: dict[str, Any]) -> dict[str, Any]:
    """根据场景 Gherkin 构造首跳 input_message。"""
    steps = tc_summary.get("gherkin", {}).get("steps", [])
    given_text = next((s["text"] for s in steps if s["keyword"] == "Given"), "")
    when_text = next((s["text"] for s in steps if s["keyword"] == "When"), "")
    trigger = plan_item.get("trigger_message") or {}
    return {
        "event": plan_item.get("entry_action", "handle"),
        "given": given_text,
        "when": when_text,
        "original_trigger": trigger if isinstance(trigger, dict) else {},
    }


def _then_assertions_from_gherkin(tc_summary: dict[str, Any]) -> list[str]:
    """从 Gherkin 步骤提取 Then/And 断言文本。"""
    steps = tc_summary.get("gherkin", {}).get("steps", [])
    assertions: list[str] = []
    in_then = False
    for s in steps:
        kw = s["keyword"]
        if kw == "Then":
            in_then = True
            assertions.append(s["text"])
        elif kw == "And" and in_then:
            assertions.append(s["text"])
        elif kw in ("When", "Given"):
            in_then = False
    return assertions


def _scenario_number(tc: Any) -> int | None:
    """Extract the original Gherkin scenario number from a TestCase's source_scenario."""
    source = str(getattr(tc, "source_scenario", "") or "")
    match = re.search(r"\d+", source)
    return int(match.group()) if match else None


def _select_test_cases(test_cases: list[Any], args: argparse.Namespace) -> list[Any] | None:
    """Apply --start-scenario / --scenario-range / --scenario-ids filters.

    1-based scenario numbers are translated to SCENARIO-xxx IDs using the
    original Gherkin scenario order (Scenario Outline examples share the same
    source_scenario and are therefore kept together).
    """
    start = getattr(args, "start_scenario", None)
    range_str = getattr(args, "scenario_range", None)
    ids_str = getattr(args, "scenario_ids", None) or ""

    selected = list(test_cases)
    allowed_numbers: set[int] | None = None
    if start is not None or range_str:
        all_numbers = {_scenario_number(tc) for tc in test_cases}
        all_numbers.discard(None)
        allowed_numbers = set(all_numbers)
        if start is not None:
            try:
                s = int(start)
                allowed_numbers = {n for n in allowed_numbers if n is not None and n >= s}
            except ValueError:
                print(
                    f"ERROR: --start-scenario must be an integer: {start}",
                    file=sys.stderr,
                )
                return None
        if range_str:
            try:
                parts = range_str.split("-")
                low = int(parts[0])
                high = int(parts[1]) if len(parts) > 1 else low
                range_numbers = set(range(low, high + 1))
                if allowed_numbers is not None:
                    allowed_numbers &= range_numbers
                else:
                    allowed_numbers = range_numbers
            except (ValueError, IndexError):
                print(
                    f"ERROR: --scenario-range must be like 34-40: {range_str}",
                    file=sys.stderr,
                )
                return None
        selected = [tc for tc in selected if _scenario_number(tc) in (allowed_numbers or set())]
    if ids_str:
        allowed = {x.strip() for x in ids_str.split(",") if x.strip()}
        selected = [tc for tc in selected if tc.test_case_id in allowed]
    return selected


def _load_entry_overrides(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"entry overrides file not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def _apply_entry_overrides(plan_item: dict[str, Any], overrides: dict[str, Any]) -> None:
    tc_id = plan_item["test_case_id"]
    override = overrides.get(tc_id)
    if not override:
        return
    if isinstance(override, str):
        plan_item["entry_component"] = override
        plan_item["entry_confidence"] = "high"
        plan_item["entry_reason"] = f"用户通过 --entry-overrides 覆盖入口: {override}"
    elif isinstance(override, dict):
        if override.get("entry_component"):
            plan_item["entry_component"] = override["entry_component"]
        if override.get("entry_action"):
            plan_item["entry_action"] = override["entry_action"]
        plan_item["entry_confidence"] = override.get("entry_confidence", "high")
        plan_item["entry_reason"] = override.get(
            "entry_reason", "用户通过 --entry-overrides 覆盖入口"
        )


def _extract_json_from_response(response: Any) -> dict[str, Any]:
    """解析 LLM 返回，支持 dict、JSON 字符串、markdown 代码块。"""
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        text = response.lstrip("\ufeff").strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            last_error = str(exc)
        else:
            last_error = "parsed JSON is not an object"

        match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            fenced = match.group(1).strip()
            try:
                parsed = json.loads(fenced)
                if isinstance(parsed, dict):
                    return parsed
                last_error = "fenced JSON is not an object"
            except json.JSONDecodeError as exc:
                last_error = str(exc)

        balanced = _extract_balanced_json_object(text)
        if balanced:
            try:
                parsed = json.loads(balanced)
                if isinstance(parsed, dict):
                    return parsed
                last_error = "balanced JSON is not an object"
            except json.JSONDecodeError as exc:
                last_error = str(exc)
        return {"raw": response, "parse_error": last_error}
    return {
        "raw": str(response),
        "parse_error": f"unsupported response type {type(response).__name__}",
    }


def _extract_balanced_json_object(text: str) -> str | None:
    """Extract the first balanced top-level JSON object from mixed text."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _normalize_hop(
    raw: dict[str, Any],
    component: str,
    action: str,
    input_message: dict[str, Any],
    phase: str,
    hop_index: int,
) -> dict[str, Any]:
    """确保 hop 包含下游处理所需字段。"""
    hop = dict(raw)
    # 会话维护的字段优先于 LLM 返回值
    hop["hop_index"] = hop_index
    hop["component"] = component
    hop["action"] = action
    hop["input_message"] = input_message
    hop.setdefault("output_message", {})
    hop.setdefault("status", "PASS")
    hop.setdefault("latency_ms", 0)
    hop.setdefault("side_effects", [])
    hop.setdefault("state_change", None)
    hop["phase"] = phase
    hop.setdefault("self_check", {})
    if not isinstance(hop["self_check"], dict):
        hop["self_check"] = {}
    hop["self_check"].setdefault("consumed_input_ok", True)
    hop["self_check"].setdefault("produced_fields", [])
    hop["self_check"].setdefault("missing_required_inputs", [])
    hop["self_check"].setdefault("undefined_next_call", None)
    hop.setdefault("next_hop", None)
    _normalize_produced_fields(hop)
    return hop


def _normalize_produced_fields(hop: dict[str, Any]) -> None:
    """Make produced_fields deterministic from actual top-level output keys."""
    output = hop.get("output_message")
    actual = list(output.keys()) if isinstance(output, dict) else []
    self_check = hop.setdefault("self_check", {})
    declared = self_check.get("produced_fields")
    if not isinstance(declared, list):
        declared = []
    declared = [str(field) for field in declared if str(field)]
    if declared != actual:
        self_check["produced_fields_normalized_from"] = declared
    self_check["produced_fields"] = actual


def _resolve_next_hop(raw_next_hop: Any, valid_components: set[str]) -> dict[str, Any] | None:
    """校验并归一化 next_hop，返回的 component 必须是已知组件名。"""
    if not isinstance(raw_next_hop, dict):
        return None
    comp = raw_next_hop.get("component")
    if not isinstance(comp, str) or not comp:
        return None
    if comp in valid_components:
        result = {
            "component": comp,
            "action": raw_next_hop.get("action", "handle"),
            "reason": raw_next_hop.get("reason", ""),
        }
        if raw_next_hop.get("contract_id"):
            result["contract_id"] = raw_next_hop["contract_id"]
        return result
    # 尝试去掉空格/大小写等简单归一化
    normalized = comp.replace(" ", "").lower()
    for name in valid_components:
        if name.replace(" ", "").lower() == normalized:
            result = {
                "component": name,
                "action": raw_next_hop.get("action", "handle"),
                "reason": raw_next_hop.get("reason", ""),
            }
            if raw_next_hop.get("contract_id"):
                result["contract_id"] = raw_next_hop["contract_id"]
            return result
    return None


def _normalize_next_hop_contract(
    next_hop: dict[str, Any] | None,
    card: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Fill a uniquely determined internal contract_id for a legal next hop."""
    if not next_hop or next_hop.get("contract_id") or not card:
        return next_hop
    component = str(card.get("name") or "")
    target = str(next_hop.get("component") or "")
    matches: list[str] = []
    for interface in card.get("outbound_interfaces", []):
        contract = interface.get("contract") or {}
        if str(contract.get("provider") or "").strip() != component:
            continue
        consumers = {
            item.strip()
            for item in re.split(r"[,，、;；\n]+", str(contract.get("consumer") or ""))
            if item.strip()
        }
        chain = [str(item) for item in contract.get("implementation_chain") or []]
        connected_by_chain = any(
            left == component and right == target for left, right in zip(chain, chain[1:])
        )
        if target not in consumers and not connected_by_chain:
            continue
        contract_id = str(contract.get("contract_id") or interface.get("name") or "")
        if contract_id:
            matches.append(contract_id)
    unique_matches = sorted(set(matches))
    if len(unique_matches) == 1:
        normalized = dict(next_hop)
        normalized["contract_id"] = unique_matches[0]
        normalized["contract_id_normalized"] = True
        return normalized
    return next_hop


def _build_component_runtime_prompt(
    base_prompt: str,
    component: str,
    action: str,
    input_message: dict[str, Any],
    shared_state: dict[str, Any],
    phase: str,
    then_assertions: list[str] | None = None,
    header: str = "本跳运行时注入",
) -> str:
    """为单个组件 subagent 构造完整的运行时 prompt。"""
    runtime_injection = [
        f"## {header}",
        f"- component: {component}",
        f"- action: {action}",
        f"- phase: {phase}",
        f"- input_message: {json.dumps(input_message, ensure_ascii=False)}",
        f"- shared_state: {json.dumps(shared_state, ensure_ascii=False)}",
    ]
    if then_assertions:
        runtime_injection.append(
            "- then_expectations: " + json.dumps(then_assertions, ensure_ascii=False)
        )
        runtime_injection.append(
            "  如果本跳是场景最终输出（next_hop 为 null 或返回给学生/外部系统），"
            "请依据 then_expectations 检查 output_message，"
            "在 self_check.then_verification 中给出每条断言是否满足及证据。"
        )
    runtime_injection.append("\n请只返回 raw JSON，不要 markdown 代码块。")
    return base_prompt + "\n\n" + "\n".join(runtime_injection)


def cmd_simulate_step_prompt(args: argparse.Namespace) -> int:
    """为单跳组件 subagent 生成完整 prompt（从 stdin 读取请求 JSON）。

    请求格式示例：
    {
      "plan_path": "plan.json",
      "component": "Guidance Session",
      "action": "handle",
      "input_message": {...},
      "shared_state": {...},
      "phase": "when",
      "then_assertions": ["..."]   // 仅 then 阶段需要
    }
    """
    request_text = sys.stdin.read()
    if not request_text:
        print("ERROR: no request JSON on stdin", file=sys.stderr)
        return 1
    try:
        request = json.loads(request_text)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid request JSON: {e}", file=sys.stderr)
        return 1

    plan_path = request.get("plan_path")
    component = request.get("component")
    action = request.get("action", "handle")
    contract_id = request.get("contract_id", "")
    input_message = request.get("input_message", {})
    shared_state = request.get("shared_state", {})
    phase = request.get("phase", "when")
    then_assertions = request.get("then_assertions")

    if not plan_path or not component:
        print("ERROR: plan_path and component are required", file=sys.stderr)
        return 1

    prompts_data = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    manifest_errors = run_manifest_errors(prompts_data)
    if manifest_errors:
        print("ERROR: " + "; ".join(manifest_errors), file=sys.stderr)
        return 1
    component_cards = prompts_data.get("component_cards", {})
    card = component_cards.get(component)
    if card:
        binding = resolve_contract_binding(
            card,
            action=action,
            contract_id=contract_id,
            input_message=input_message,
        )
        arch_doc = _parse_arch_doc(prompts_data["arch_input_path"])
        data_flow_summary = [
            {
                "from": step.from_component,
                "to": step.to_component,
                "action": step.action,
                "message": step.message,
            }
            for step in arch_doc.data_flow.sequence
        ]
        all_component_names = list(component_cards.keys()) or [c.name for c in arch_doc.components]
        base_prompt = build_component_agent_prompt(
            card, data_flow_summary, all_component_names, contract_binding=binding
        )
    else:
        base_prompt = prompts_data.get("component_prompts", {}).get(component)
        if not base_prompt:
            print(f"ERROR: no prompt template or component card for: {component}", file=sys.stderr)
            return 1

    prompt = _build_component_runtime_prompt(
        base_prompt,
        component,
        action,
        input_message,
        shared_state,
        phase,
        then_assertions,
    )
    print(prompt)
    return 0


def _json_arg(value: str) -> dict[str, Any]:
    if not value:
        return {}
    p = Path(value)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(value)


def cmd_normalize_hop_response(args: argparse.Namespace) -> int:
    raw_text = sys.stdin.read()
    if not raw_text:
        print("ERROR: no subagent response on stdin", file=sys.stderr)
        return 1
    raw = _extract_json_from_response(raw_text)
    if "raw" in raw:
        error = {
            "artifact_error": "invalid_json_response",
            "parse_error": raw.get("parse_error", ""),
            "component": args.component,
            "action": args.action,
            "hop_index": args.hop_index,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.with_suffix(output.suffix + ".error.json").write_text(
            json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"ERROR: invalid JSON response for {args.component}", file=sys.stderr)
        return 2
    hop = _normalize_hop(
        raw=raw,
        component=args.component,
        action=args.action,
        input_message=_json_arg(args.input_message),
        phase=args.phase,
        hop_index=args.hop_index,
    )
    valid_components = {c for c in args.valid_components.split(",") if c}
    next_hop = _resolve_next_hop(hop.get("next_hop"), valid_components)
    hop["next_hop"] = next_hop
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(hop, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Normalized hop written to: {args.output}")
    return 0


def _sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cmd_fill_validator_prompts(args: argparse.Namespace) -> int:
    prompts_data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    manifest_errors = run_manifest_errors(prompts_data)
    if manifest_errors:
        print("ERROR: " + "; ".join(manifest_errors), file=sys.stderr)
        return 1
    hops_by_tc = json.loads(Path(args.hops).read_text(encoding="utf-8"))

    arch_doc = _parse_arch_doc(prompts_data["arch_input_path"])
    tc_by_id = {tc["test_case_id"]: tc for tc in prompts_data["test_cases"]}

    for plan_item in prompts_data["plans"]:
        tc_id = plan_item["test_case_id"]
        tc_summary = tc_by_id.get(tc_id)
        if tc_summary is None:
            print(f"ERROR: missing test case for {tc_id}", file=sys.stderr)
            return 1
        trace = assemble_trace_from_hops(tc_id, hops_by_tc.get(tc_id, []))
        plan_item["deterministic_verdicts"] = build_deterministic_verdicts(trace, tc_summary)
        if getattr(args, "compact_trace", False):
            plan_item["validator_prompt"] = build_compact_validator_prompt(
                trace, tc_summary, prompts_data.get("component_cards", {})
            )
        else:
            tc = _reconstruct_test_case(tc_summary)
            plan_item["validator_prompt"] = build_validator_prompt(trace, tc, arch_doc)

    prompts_data["_artifact_metadata"] = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_hashes": {
            "hops": _sha256_file(args.hops),
            "prompts": _sha256_file(args.prompts),
        },
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(prompts_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Filled validator prompts: {args.output}")
    return 0


_VALIDATOR_DIMENSIONS = ("structure", "flow", "state", "contract", "performance")
_VALIDATOR_STATUSES = {"PASS", "WARNING", "FAIL", "MISSING"}


def validator_payload_errors(payload: Any, *, require_dimensions: bool = True) -> list[str]:
    if not isinstance(payload, dict):
        return ["validator result must be an object"]
    errors: list[str] = []
    overall = payload.get("overall")
    if overall not in _VALIDATOR_STATUSES:
        errors.append(f"invalid validator overall status: {overall}")
    if overall == "MISSING":
        errors.append("validator overall=MISSING is not a completed judgment")
    if require_dimensions:
        for dimension in _VALIDATOR_DIMENSIONS:
            result = payload.get(dimension)
            if not isinstance(result, dict):
                errors.append(f"validator dimension missing: {dimension}")
                continue
            if result.get("status") not in _VALIDATOR_STATUSES:
                errors.append(f"invalid {dimension} status: {result.get('status')}")
            if not isinstance(result.get("detail"), str):
                errors.append(f"validator {dimension}.detail must be a string")
    return errors


def plan_item_semantic_errors(
    plan_item: dict[str, Any], tc_summary: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    if not plan_item.get("entry_component"):
        errors.append("entry component is unresolved")
    if plan_item.get("entry_confidence") == "low":
        errors.append("entry component confidence is low")
    if plan_item.get("entry_contract_status") != "resolved":
        errors.append(f"entry contract is {plan_item.get('entry_contract_status', 'unresolved')}")
    interactions = plan_item.get("interaction_sequence") or []
    for index, interaction in enumerate(interactions):
        if not isinstance(interaction, dict):
            errors.append(f"interaction {index + 1} is malformed")
            continue
        if not interaction.get("entry_component"):
            errors.append(f"interaction {index + 1} entry component is unresolved")
        if interaction.get("entry_confidence") == "low":
            errors.append(f"interaction {index + 1} entry component confidence is low")
        if interaction.get("entry_contract_status") != "resolved":
            errors.append(
                f"interaction {index + 1} entry contract is "
                f"{interaction.get('entry_contract_status', 'unresolved')}"
            )
    if tc_summary and "parameters" in tc_summary.get("gherkin", {}):
        mapping = tc_summary.get("technical_mapping") or {}
        for phase in ("given_steps", "when_steps", "then_steps"):
            if not mapping.get(phase):
                errors.append(f"Scenario Outline mapping missing: {phase}")
    return errors


def strict_semantic_errors(
    prompts_data: dict[str, Any],
    hops_by_tc: dict[str, list[dict[str, Any]]],
) -> list[str]:
    errors = run_manifest_errors(prompts_data)
    plans = prompts_data.get("plans", [])
    # Compatibility: old saved artifacts predate semantic binding metadata.
    if not any("entry_contract_status" in plan for plan in plans):
        return errors
    tc_by_id = {tc.get("test_case_id"): tc for tc in prompts_data.get("test_cases", [])}
    for plan in plans:
        tc_id = str(plan.get("test_case_id", ""))
        for detail in plan_item_semantic_errors(plan, tc_by_id.get(tc_id)):
            errors.append(f"{tc_id}: {detail}")
        for i, hop in enumerate(hops_by_tc.get(tc_id, [])):
            if hop.get("unresolved_next_hop"):
                errors.append(f"{tc_id}: hop {i} declares an unresolved next_hop")
            if hop.get("truncated_at_max_hops"):
                errors.append(f"{tc_id}: hop {i} reached the configured max_hops limit")
            if hop.get("synthetic") or hop.get("action") == "setup_context":
                continue
            binding = hop.get("contract_binding")
            if not isinstance(binding, dict) or binding.get("status") != "resolved":
                status = binding.get("status") if isinstance(binding, dict) else "missing"
                errors.append(f"{tc_id}: hop {i} contract binding is {status}")
    return errors


def validate_strict_artifacts(
    prompts_data: dict[str, Any],
    hops_by_tc: dict[str, list[dict[str, Any]]],
    val_results: list[dict[str, Any]],
    call_log: list[dict[str, Any]] | None = None,
    require_call_log: bool = False,
    expected_input_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    plans = prompts_data.get("plans", [])
    component_cards = prompts_data.get("component_cards", {})
    valid_components = set(prompts_data.get("component_prompts", {}).keys())
    if not valid_components:
        valid_components = set(component_cards.keys())
    strict_components = {
        name for name, card in component_cards.items() if card.get("strict_agent_component", True)
    }
    if not strict_components:
        strict_components = valid_components

    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(strict_semantic_errors(prompts_data, hops_by_tc))
    metadata = prompts_data.get("_artifact_metadata", {})
    if metadata:
        schema_version = metadata.get("schema_version")
        if schema_version != TRACE_SCHEMA_VERSION:
            errors.append(
                f"artifact schema mismatch: expected {TRACE_SCHEMA_VERSION}, got {schema_version}"
            )
        if expected_input_hashes:
            recorded_hashes = metadata.get("input_hashes", {})
            for name, expected_hash in expected_input_hashes.items():
                if recorded_hashes.get(name) != expected_hash:
                    errors.append(
                        f"stale validator prompts: {name} hash does not match current artifact"
                    )
    scenario_ids = {p["test_case_id"] for p in plans}
    validator_ids = {v.get("test_case_id") for v in val_results}
    strict_validator_schema = any("entry_contract_status" in p for p in plans)
    validator_by_id = {v.get("test_case_id"): v.get("result") for v in val_results}
    call_log_verified = False
    component_calls: set[tuple[str, int, str]] = set()
    validator_calls: set[str] = set()

    if any(isinstance(plan.get("equivalence"), dict) for plan in plans):
        recomputed_plans = json.loads(json.dumps(plans, ensure_ascii=False))
        assign_strict_equivalence_groups(prompts_data.get("test_cases", []), recomputed_plans)
        recomputed_by_id = {
            plan.get("test_case_id"): plan.get("equivalence") for plan in recomputed_plans
        }
        for plan in plans:
            equivalence = plan.get("equivalence")
            if not isinstance(equivalence, dict):
                continue
            tc_id = str(plan.get("test_case_id", ""))
            expected = recomputed_by_id.get(tc_id) or {}
            if expected.get("key") != equivalence.get("key"):
                errors.append(f"{tc_id}: strict-equivalence proof key mismatch")
                continue
            representative = equivalence.get("representative")
            if representative != tc_id:
                if hops_by_tc.get(tc_id) != hops_by_tc.get(representative):
                    errors.append(f"{tc_id}: equivalent hops differ from representative")
                if validator_by_id.get(tc_id) != validator_by_id.get(representative):
                    errors.append(
                        f"{tc_id}: equivalent validator result differs from representative"
                    )

    for plan in plans:
        provenance = plan.get("cache_provenance")
        if not isinstance(provenance, dict) or not provenance.get("cache_hit"):
            continue
        tc_id = str(plan.get("test_case_id", ""))
        if provenance.get("cache_key") != plan.get("cache_key"):
            errors.append(f"{tc_id}: cache provenance key mismatch")
            continue
        source_audit = Path(str(provenance.get("source_run", ""))) / "strict_audit.json"
        if not source_audit.exists():
            errors.append(f"{tc_id}: cache source strict audit is missing")
            continue
        actual_hash = hashlib.sha256(source_audit.read_bytes()).hexdigest()
        if actual_hash != provenance.get("source_strict_audit_sha256"):
            errors.append(f"{tc_id}: cache source strict audit hash mismatch")
            continue
        try:
            source_status = json.loads(source_audit.read_text(encoding="utf-8-sig")).get("status")
        except (json.JSONDecodeError, OSError):
            source_status = None
        if source_status != "PASS":
            errors.append(f"{tc_id}: cache source strict audit is not PASS")

    if call_log is None:
        if require_call_log:
            errors.append("missing subagent call log")
        else:
            warnings.append("subagent call log not provided; audit checks artifacts only")
    else:
        call_log_verified = True
        for entry in call_log:
            role = entry.get("role")
            tc_id = str(entry.get("test_case_id", ""))
            if role == "component":
                try:
                    hop_index = int(entry.get("hop_index", -1))
                except (TypeError, ValueError):
                    errors.append(f"{tc_id}: component call log has invalid hop_index")
                    continue
                component_calls.add((tc_id, hop_index, str(entry.get("component", ""))))
            elif role == "validator":
                validator_calls.add(tc_id)

    for plan in plans:
        tc_id = plan["test_case_id"]
        hops = hops_by_tc.get(tc_id, [])
        if not hops:
            errors.append(f"{tc_id}: missing hops")
            continue

        for i, hop in enumerate(hops):
            comp = hop.get("component")
            action = hop.get("action", "handle")
            is_synthetic = bool(hop.get("synthetic")) or action == "setup_context"
            if comp not in valid_components:
                errors.append(f"{tc_id}: hop {i} unknown component {comp}")
                continue
            if comp not in strict_components:
                errors.append(
                    f"{tc_id}: hop {i} component {comp} is not allowed as a strict component subagent"
                )
            output_message = hop.get("output_message", {})
            self_check = hop.get("self_check") if isinstance(hop.get("self_check"), dict) else {}
            if hop.get("artifact_error") or (
                isinstance(output_message, dict)
                and output_message.get("error") == "invalid_json_response"
            ):
                errors.append(f"{tc_id}: hop {i} contains invalid_json_response artifact error")
            if self_check.get("artifact_error"):
                errors.append(
                    f"{tc_id}: hop {i} contains trace artifact error: {self_check.get('artifact_error')}"
                )
            if (
                call_log is not None
                and not is_synthetic
                and (tc_id, i, str(comp)) not in component_calls
            ):
                errors.append(
                    f"{tc_id}: hop {i} component {comp} has no matching component subagent call log"
                )
            if not isinstance(output_message, dict):
                errors.append(f"{tc_id}: hop {i} output_message must be an object")
            if not isinstance(hop.get("self_check", {}), dict):
                errors.append(f"{tc_id}: hop {i} self_check must be an object")

            resolved = _resolve_next_hop(hop.get("next_hop"), valid_components)
            if resolved and i + 1 < len(hops):
                nxt = hops[i + 1]
                if nxt.get("component") != resolved["component"]:
                    errors.append(
                        f"{tc_id}: hop {i} next_hop.component={resolved['component']} but next hop is {nxt.get('component')}"
                    )
                if str(nxt.get("action", "handle")) != str(resolved.get("action", "handle")):
                    warnings.append(
                        f"{tc_id}: hop {i} next_hop.action={resolved.get('action')} but next hop action is {nxt.get('action')}"
                    )
            elif resolved and i + 1 >= len(hops):
                errors.append(f"{tc_id}: hop {i} declares next_hop but chain stops")
            elif hop.get("next_hop") not in (None, {}):
                errors.append(f"{tc_id}: hop {i} has invalid next_hop {hop.get('next_hop')}")

        if tc_id not in validator_ids:
            errors.append(f"{tc_id}: missing validator result")
        else:
            for detail in validator_payload_errors(
                validator_by_id.get(tc_id),
                require_dimensions=strict_validator_schema,
            ):
                errors.append(f"{tc_id}: {detail}")
            result = validator_by_id.get(tc_id)
            deterministic = plan.get("deterministic_verdicts") or {}
            if isinstance(result, dict):
                structure_status = (deterministic.get("structure") or {}).get("status")
                if (
                    structure_status in ("PASS", "FAIL")
                    and (result.get("structure") or {}).get("status") != structure_status
                ):
                    errors.append(
                        f"{tc_id}: validator structure contradicts deterministic {structure_status}"
                    )
                performance_status = (deterministic.get("performance_threshold") or {}).get(
                    "status"
                )
                if (
                    performance_status in ("PASS", "FAIL")
                    and (result.get("performance") or {}).get("status") != performance_status
                ):
                    errors.append(
                        f"{tc_id}: validator performance contradicts deterministic {performance_status}"
                    )
                contract_blockers = (
                    (deterministic.get("contract_binding") or {}).get("status"),
                    (deterministic.get("produced_field_presence") or {}).get("status"),
                )
                if (
                    "FAIL" in contract_blockers
                    and (result.get("contract") or {}).get("status") != "FAIL"
                ):
                    errors.append(f"{tc_id}: validator contract ignores deterministic FAIL")
        if call_log is not None and tc_id not in validator_calls:
            errors.append(f"{tc_id}: missing validator subagent call log")

    extra_validators = sorted(v for v in validator_ids if v and v not in scenario_ids)
    for tc_id in extra_validators:
        warnings.append(f"{tc_id}: validator result has no matching plan")

    return {
        "status": "PASS" if not errors else "FAIL",
        "execution_mode": "interactive-strict",
        "strict_component_subagents": True,
        "call_log_verified": call_log_verified,
        "scenario_count": len(plans),
        "hop_count": sum(len(hops_by_tc.get(p["test_case_id"], [])) for p in plans),
        "validator_count": len(validator_ids),
        "errors": errors,
        "warnings": warnings,
    }


def _read_call_log(path: str | None) -> list[dict[str, Any]] | None:
    if not path:
        return None
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def cmd_validate_run_artifacts(args: argparse.Namespace) -> int:
    prompts_data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    hops_by_tc = json.loads(Path(args.hops).read_text(encoding="utf-8"))
    val_results = json.loads(Path(args.val_results).read_text(encoding="utf-8"))
    audit = validate_strict_artifacts(
        prompts_data,
        hops_by_tc,
        val_results,
        call_log=_read_call_log(args.call_log),
        require_call_log=args.require_call_log,
        expected_input_hashes={"hops": _sha256_file(args.hops)},
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Strict audit written to: {args.output} ({audit['status']})")
    return 0 if audit["status"] == "PASS" else 1


def render_strict_audit_section(audit: dict[str, Any]) -> str:
    lines = [
        "## Strict Subagent Audit",
        "",
        f"- execution_mode: {audit.get('execution_mode', '')}",
        f"- strict_component_subagents: {audit.get('strict_component_subagents', False)}",
        f"- call_log_verified: {audit.get('call_log_verified', False)}",
        f"- status: {audit.get('status', 'MISSING')}",
        f"- scenarios: {audit.get('scenario_count', 0)}",
        f"- hops: {audit.get('hop_count', 0)}",
        f"- validators: {audit.get('validator_count', 0)}",
    ]
    if audit.get("errors"):
        lines.append("- errors: " + "; ".join(audit["errors"]))
    if audit.get("warnings"):
        lines.append("- warnings: " + "; ".join(audit["warnings"]))
    return "\n".join(lines)


def _reconstruct_test_case(tc_summary: dict[str, Any]) -> Any:
    """Reconstruct a TestCase-like object from its JSON summary."""
    from mock_framework.models.loader import TestCase, Expectations, TechnicalMapping

    def _make_mapping(m: dict[str, Any]) -> TechnicalMapping:
        return TechnicalMapping(
            step_index=m["step_index"],
            text=m["text"],
            mapping_type=m["mapping_type"],
            target=m["target"],
            assertion=m.get("assertion"),
            confidence=m.get("confidence", "medium"),
        )

    technical_mapping = {
        phase: [_make_mapping(m) for m in mappings]
        for phase, mappings in tc_summary["technical_mapping"].items()
    }

    exp = tc_summary["expectations"]
    return TestCase(
        test_case_id=tc_summary["test_case_id"],
        source_feature=tc_summary["source_feature"],
        source_scenario=tc_summary["source_scenario"],
        tags=tc_summary["tags"],
        gherkin=tc_summary["gherkin"],
        technical_mapping=technical_mapping,
        expectations=Expectations(
            status_code=exp["status_code"],
            response_schema=exp["response_schema"],
            touched_components=exp["touched_components"],
            side_effects=exp["side_effects"],
            performance=exp["performance"],
        ),
    )


def _read_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def cmd_report(args: argparse.Namespace) -> int:
    prompts_data = _read_json_file(args.prompts)
    val_results = _read_json_file(args.val_results)
    compat = _read_json_file(args.compat)
    hops_by_tc = _read_json_file(args.hops)
    strict_audit: dict[str, Any] | None = None
    if args.strict or args.strict_audit:
        if not args.strict_audit:
            print("ERROR: --strict requires --strict-audit", file=sys.stderr)
            return 1
        strict_audit = _read_json_file(args.strict_audit)
        if args.strict and strict_audit.get("status") != "PASS":
            print(
                "ERROR: strict audit did not pass; refusing to generate strict report",
                file=sys.stderr,
            )
            return 1

    feature_path = prompts_data["feature_path"]
    arch_path = prompts_data["arch_path"]
    component_names = list(prompts_data.get("component_prompts", {}).keys())
    if not component_names:
        component_names = list(prompts_data.get("component_cards", {}).keys())

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if getattr(args, "audience", "architecture") == "architecture":
        evidence_refs: list[str] | None = None
        if getattr(args, "omit_artifact_refs", False):
            evidence_refs = []
        elif getattr(args, "artifact_dir", None):
            artifact_dir = Path(args.artifact_dir).resolve()
            evidence_refs = [
                str(artifact_dir / "strict_audit.json"),
                str(artifact_dir / "compat.json"),
                str(artifact_dir / "hops.json"),
            ]
            if getattr(args, "diagnostics", False):
                evidence_refs.insert(
                    0,
                    str(output_path.with_name(f"{output_path.stem}-diagnostics.md").resolve()),
                )
        report_md = report_enhancements.render_architecture_report(
            feature_path=feature_path,
            arch_path=arch_path,
            hops_by_tc=hops_by_tc,
            val_results=val_results,
            compat=compat,
            component_names=component_names,
            strict_audit=strict_audit,
            evidence_refs=evidence_refs,
        )
        output_path.write_text(report_md, encoding="utf-8")
        print(f"Report written to: {args.output}")
        if getattr(args, "diagnostics", False):
            diagnostics_md = report_enhancements.render_diagnostics_report(
                feature_path=feature_path,
                arch_path=arch_path,
                val_results=val_results,
                compat=compat,
                component_names=component_names,
                strict_audit=strict_audit,
            )
            diagnostics_path = output_path.with_name(f"{output_path.stem}-diagnostics.md")
            diagnostics_path.write_text(diagnostics_md, encoding="utf-8")
            print(f"Diagnostics written to: {diagnostics_path}")
        return 0

    assembler = ReportAssembler()
    val_by_id = {item["test_case_id"]: item for item in val_results}

    validation_results: list[ValidationResult] = []
    for tc_summary in prompts_data["test_cases"]:
        tc_id = tc_summary["test_case_id"]
        val_item = val_by_id.get(tc_id)
        if val_item is None:
            print(f"ERROR: missing validator result for {tc_id}", file=sys.stderr)
            return 1
        compat_sc = compat["per_scenario"].get(tc_id, {"status": "MISSING", "detail": ""})
        merged = merge_interface_compat(val_item["result"], compat_sc)
        validation_results.append(
            assembler.assemble_result(
                test_case_id=tc_id, scenario_name=tc_summary["scenario_name"], agent_output=merged
            )
        )

    report_id = (
        f"VAL-{validation_results[0].test_case_id}"
        if validation_results
        else f"VAL-{Path(feature_path).stem}"
    )
    report = assembler.build_report(
        report_id=report_id,
        architecture_doc=arch_path,
        gherkin_source=feature_path,
        results=validation_results,
    )
    report_md = ReportRenderer().render(report)

    # 追加数据流流转段 + 全局发现
    report_md += "\n\n" + render_dataflow_section(prompts_data["plans"], hops_by_tc)
    if compat.get("global_findings"):
        report_md += "\n## 全局发现\n\n"
        for f in compat["global_findings"]:
            report_md += f"- [{f['severity']}] {f['kind']}: {f['detail']}\n"

    if strict_audit:
        report_md += "\n\n" + render_strict_audit_section(strict_audit)

    report_md += report_enhancements.build_enhancement_sections(
        hops_by_tc, val_results, compat, component_names, audience="full"
    )

    output_path.write_text(report_md, encoding="utf-8")
    print(f"Report written to: {args.output}")
    return 0


# ---------- run-strict one-shot orchestration ----------

_HOP_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "output_message": {"type": "object"},
        "status": {"type": "string"},
        "latency_ms": {"type": "integer"},
        "side_effects": {"type": "array"},
        "state_change": {"anyOf": [{"type": "object"}, {"type": "null"}]},
        "self_check": {"type": "object"},
        "next_hop": {"anyOf": [{"type": "object"}, {"type": "null"}]},
    },
    "required": ["output_message", "status", "self_check", "next_hop"],
    "additionalProperties": True,
}

_VALIDATOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "structure": {"type": "object"},
        "flow": {"type": "object"},
        "state": {"type": "object"},
        "contract": {"type": "object"},
        "performance": {"type": "object"},
        "overall": {"enum": ["PASS", "FAIL", "WARNING", "MISSING"]},
    },
    "required": ["structure", "flow", "state", "contract", "performance", "overall"],
    "additionalProperties": True,
}


def _run_subagent_skill(
    args: list[str],
    stdin: str | None = None,
    stdout_path: Path | None = None,
    timeout: int = 300,
) -> str:
    """Invoke another run_subagent_skill.py subcommand as a subprocess."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(Path(__file__).resolve()), *args]
    proc = subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=timeout,
    )
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"run_subagent_skill {' '.join(args)} failed rc={proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc.stdout


def _codex_subagent(
    prompt: str,
    raw_path: Path,
    role: str,
    schema_path: Path | None = None,
    timeout: int = 300,
) -> str:
    """Spawn a single codex subagent and return the raw response text."""
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    codex_bin = os.environ.get("MOCK_FRAMEWORK_CODEX_BIN")
    if not codex_bin:
        bundled_bin = Path.home() / ".codex" / ".sandbox-bin" / "codex.exe"
        if bundled_bin.is_file():
            codex_bin = str(bundled_bin)
        else:
            codex_bin = shutil.which("codex") or "codex"
    cmd = [
        codex_bin,
        "exec",
        "-C",
        str(PROJECT_ROOT),
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--ephemeral",
        "--output-last-message",
        str(raw_path),
    ]
    # The Codex Responses API enforces strict JSON Schema objects and rejects
    # the intentionally permissive schemas used by this workflow
    # (``additionalProperties`` must be false at every object node).  The
    # prompt already specifies the exact raw JSON shape and the caller runs
    # structural validation/retry after parsing, so do not pass the schema to
    # ``codex exec``.  Keep ``schema_path`` in the function signature and
    # write the schema artifact for traceability/backward compatibility.
    cmd.append("-")
    wrapped = (
        "You are an independent validate-arch subagent for this single invocation.\n"
        "Do not use tools. Do not read or write files. Return only raw JSON.\n\n" + prompt
    )
    proc = subprocess.run(
        cmd,
        input=wrapped,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )
    transcript = raw_path.with_suffix(raw_path.suffix + ".codex.log")
    transcript.write_text(
        "COMMAND: " + " ".join(cmd) + "\n\nSTDOUT:\n" + proc.stdout + "\n\nSTDERR:\n" + proc.stderr,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"codex {role} subagent failed rc={proc.returncode}; see {transcript}")
    if not raw_path.exists():
        raise RuntimeError(f"codex {role} subagent did not write {raw_path}")
    return raw_path.read_text(encoding="utf-8").strip()


def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _auto_run_dir(feature_path: str | Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    feature_stem = Path(feature_path).stem
    return PROJECT_ROOT / ".work" / "validate-arch" / "runs" / f"{feature_stem}-strict-{stamp}"


def _delivery_report_path(
    feature_path: str | Path,
    run_dir: str | Path,
    report_dir: str | Path | None,
) -> Path:
    run_path = Path(run_dir)
    if report_dir:
        return Path(report_dir).resolve() / f"{run_path.name}-validation-report.md"
    return run_path / f"{Path(feature_path).stem}-validation-report.md"


def _effective_artifact_retention(args: argparse.Namespace) -> str:
    configured = getattr(args, "artifact_retention", None)
    if configured:
        return str(configured)
    return "report" if getattr(args, "report_dir", None) else "full"


def _is_managed_work_dir(path: Path) -> bool:
    managed_root = (PROJECT_ROOT / ".work" / "validate-arch").resolve()
    try:
        path.resolve().relative_to(managed_root)
    except ValueError:
        return False
    return True


def apply_artifact_retention(run_dir: str | Path, retention: str, audit_status: str) -> str:
    """Apply PASS-only retention without deleting user-selected report directories."""
    path = Path(run_dir).resolve()
    if audit_status != "PASS":
        return "preserved-failed-audit"
    if retention == "full":
        return "preserved-full"
    if retention == "audit":
        if not _is_managed_work_dir(path):
            return "preserved-unsafe-cleanup-path"
        for scenarios_dir in sorted(path.rglob("scenarios"), reverse=True):
            if scenarios_dir.is_dir():
                shutil.rmtree(scenarios_dir, ignore_errors=True)
        for candidate in path.rglob("artifact_errors.jsonl"):
            candidate.unlink()
        return "preserved-audit"
    if retention == "report":
        if not _is_managed_work_dir(path):
            return "preserved-unsafe-cleanup-path"
        shutil.rmtree(path)
        return "removed-report-only-workdir"
    raise ValueError(f"Unsupported artifact retention: {retention}")


def cleanup_empty_run_shells(report_dir: str | Path) -> list[str]:
    """Remove direct child run shells that contain no validation artifacts."""
    root = Path(report_dir).resolve()
    if not root.exists():
        return []
    removed: list[str] = []
    allowed_logs = {"run-strict.stdout.log", "run-strict.stderr.log"}
    for child in root.iterdir():
        if not child.is_dir() or child.parent != root:
            continue
        if "strict" not in child.name.lower() and "diagnostic" not in child.name.lower():
            continue
        files = [item for item in child.rglob("*") if item.is_file()]
        dirs = [item for item in child.rglob("*") if item.is_dir()]
        is_empty_dir = not files and not dirs
        is_zero_log_shell = (
            not dirs
            and bool(files)
            and {item.name for item in files}.issubset(allowed_logs)
            and all(item.stat().st_size == 0 for item in files)
        )
        if is_empty_dir or is_zero_log_shell:
            shutil.rmtree(child)
            removed.append(str(child))
    return removed


def _first_step_text(tc: dict[str, Any], keyword: str) -> str:
    for step in tc.get("gherkin", {}).get("steps", []):
        if step.get("keyword") == keyword:
            return step.get("text", "")
    return ""


def _synthetic_setup_hop(
    component: str, action: str, input_message: dict[str, Any]
) -> dict[str, Any]:
    return {
        "hop_index": 0,
        "component": component,
        "action": "setup_context",
        "phase": "given",
        "synthetic": True,
        "input_message": input_message,
        "output_message": {
            "given_context": input_message.get("given", ""),
            "when": input_message.get("when", ""),
            "original_trigger": input_message.get("original_trigger", {}),
        },
        "status": "PASS",
        "latency_ms": 0,
        "self_check": {
            "consumed_input_ok": True,
            "produced_fields": ["given_context"],
            "missing_required_inputs": [],
            "undefined_next_call": None,
            "then_verification": None,
        },
        "next_hop": {
            "component": component,
            "action": action,
            "reason": "Given context established",
        },
        "state_change": None,
        "side_effects": [],
    }


def _error_hop(
    component: str,
    action: str,
    input_message: dict[str, Any],
    phase: str,
    hop_index: int,
    message: str,
) -> dict[str, Any]:
    return {
        "hop_index": hop_index,
        "component": component,
        "action": action,
        "phase": phase,
        "input_message": input_message,
        "output_message": {"error": message},
        "status": "ERROR",
        "latency_ms": 0,
        "self_check": {
            "consumed_input_ok": False,
            "produced_fields": ["error"],
            "missing_required_inputs": [],
            "undefined_next_call": message,
            "then_verification": None,
        },
        "next_hop": None,
        "state_change": None,
        "side_effects": [],
    }


def _missing_validator_result(message: str) -> dict[str, Any]:
    return {
        "structure": {"status": "MISSING", "detail": message},
        "flow": {"status": "MISSING", "detail": message},
        "state": {"status": "MISSING", "detail": message},
        "contract": {"status": "MISSING", "detail": message},
        "performance": {"status": "MISSING", "detail": message},
        "overall": "MISSING",
    }


def _interaction_sequence(tc_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a Gherkin scenario into ordered user/system interactions.

    A ``When`` starts an interaction.  Its following ``Then``/``And`` steps
    remain attached to that interaction until the next Given/When.  This keeps
    multi-operation scenarios executable without inventing separate scenarios.
    """
    given: list[str] = []
    interactions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    active = ""
    for raw in tc_summary.get("gherkin", {}).get("steps", []):
        keyword = str(raw.get("keyword", "")).strip().lower()
        text = str(raw.get("text", "")).strip()
        if not text:
            continue
        if keyword == "given":
            given.append(text)
            current = None
            active = "given"
        elif keyword == "when":
            current = {
                "interaction_index": len(interactions),
                "given": list(given),
                "when": text,
                "when_steps": [text],
                "then_assertions": [],
            }
            interactions.append(current)
            active = "when"
        elif keyword == "then":
            if current is not None:
                current["then_assertions"].append(text)
            active = "then"
        elif keyword == "and":
            if active == "given":
                given.append(text)
            elif active == "when" and current is not None:
                current["when_steps"].append(text)
                current["when"] = " AND ".join(current["when_steps"])
            elif active == "then" and current is not None:
                current["then_assertions"].append(text)
    if interactions:
        return interactions
    # Preserve the semantic gate behavior for malformed/non-action scenarios:
    # no implicit component is invented, but downstream code has one stable row.
    return [
        {
            "interaction_index": 0,
            "given": given,
            "when": "",
            "when_steps": [],
            "then_assertions": [],
        }
    ]


def _strict_equivalence_copy(
    item: dict[str, Any], completed: dict[str, Any]
) -> tuple[str, Any] | None:
    """Copy a completed representative only when prepare proved strict equivalence."""
    equivalence = item.get("equivalence") or {}
    representative = equivalence.get("representative")
    tc_id = item.get("test_case_id")
    if not representative or representative == tc_id or representative not in completed:
        return None
    copied = json.loads(json.dumps(completed[representative], ensure_ascii=False))
    return str(representative), copied


def _simulate_components_strict(
    plan_path: Path,
    output_dir: Path,
    max_hops: int,
    subagent_runner: str,
    subagent_timeout: int,
) -> None:
    """Run the component subagent loop for every scenario in the plan."""
    plan = _read_json(plan_path)
    valid_components = set(plan.get("component_cards", {}).keys())
    tc_by_id = {tc["test_case_id"]: tc for tc in plan.get("test_cases", [])}
    hops_by_tc: dict[str, list[dict[str, Any]]] = {}
    call_log_path = output_dir / "subagent_calls.jsonl"
    if call_log_path.exists():
        call_log_path.unlink()
    hop_schema_path = output_dir / "hop_output_schema.json"
    _write_json(hop_schema_path, _HOP_OUTPUT_SCHEMA)

    for item in plan.get("plans", []):
        tc_id = item["test_case_id"]
        tc = tc_by_id.get(tc_id)
        if tc is None:
            continue
        equivalent = _strict_equivalence_copy(item, hops_by_tc)
        if equivalent:
            representative, hops = equivalent
            hops_by_tc[tc_id] = hops
            for hop_index, hop in enumerate(hops):
                if hop.get("synthetic") or hop.get("action") == "setup_context":
                    continue
                _append_jsonl(
                    call_log_path,
                    {
                        "role": "component",
                        "test_case_id": tc_id,
                        "hop_index": hop_index,
                        "component": hop.get("component", ""),
                        "action": hop.get("action", ""),
                        "equivalence_hit": True,
                        "equivalence_key": (item.get("equivalence") or {}).get("key"),
                        "representative": representative,
                    },
                )
            _write_json(output_dir / "hops.json", hops_by_tc)
            print(f"[{tc_id}] reused strict-equivalent hops from {representative}", flush=True)
            continue
        semantic_errors = plan_item_semantic_errors(item, tc)
        if semantic_errors:
            print(f"[{tc_id}] skipped: {semantic_errors}", flush=True)
            continue

        interactions = item.get("interaction_sequence") or [
            {
                "entry_component": item["entry_component"],
                "entry_action": item.get("entry_action") or "handle",
                "entry_contract_id": item.get("entry_contract_id", ""),
                "then_assertions": item.get("then_assertions", []),
            }
        ]
        interaction_index = 0
        interaction = interactions[interaction_index]
        component = interaction.get("entry_component", item["entry_component"])
        action = interaction.get("entry_action") or "handle"
        contract_id = interaction.get("entry_contract_id", "")
        input_message: dict[str, Any] = {
            "event": action,
            "given": _first_step_text(tc, "Given"),
            "when": interaction.get("when", _first_step_text(tc, "When")),
            "original_trigger": interaction.get("trigger_message") or item.get("trigger_message") or {},
            "interaction_index": interaction_index,
            "interaction_count": len(interactions),
        }
        shared_state: dict[str, Any] = {}
        visited: set[tuple[str, str]] = set()
        hops = [_synthetic_setup_hop(component, action, input_message)]
        hops[0]["interaction_index"] = interaction_index

        for hop_index in range(1, max_hops + 1):
            request = {
                "plan_path": str(plan_path.resolve()),
                "component": component,
                "action": action,
                "contract_id": contract_id,
                "input_message": input_message,
                "shared_state": shared_state,
                "phase": "when",
                "then_assertions": interaction.get("then_assertions", []),
            }
            prompt_path = output_dir / f"hop_prompt_{tc_id}_{hop_index:02d}.txt"
            input_path = output_dir / f"hop_input_{tc_id}_{hop_index:02d}.json"
            result_path = output_dir / f"hop_result_{tc_id}_{hop_index:02d}.json"
            _write_json(input_path, input_message)
            _run_subagent_skill(
                ["simulate-step-prompt"],
                stdin=json.dumps(request, ensure_ascii=False),
                stdout_path=prompt_path,
            )
            prompt = prompt_path.read_text(encoding="utf-8")

            normalized: dict[str, Any] | None = None
            last_error = ""
            for attempt in range(1, 4):
                raw_path = (
                    output_dir / f"raw_hop_response_{tc_id}_{hop_index:02d}_attempt{attempt}.txt"
                )
                _append_jsonl(
                    call_log_path,
                    {
                        "role": "component",
                        "test_case_id": tc_id,
                        "hop_index": hop_index,
                        "component": component,
                        "action": action,
                        "attempt": attempt,
                        "prompt_file": str(prompt_path),
                        "raw_response_file": str(raw_path),
                    },
                )
                try:
                    if subagent_runner == "codex":
                        raw = _codex_subagent(
                            prompt, raw_path, "component", hop_schema_path, subagent_timeout
                        )
                    else:
                        raise RuntimeError(f"unsupported subagent runner: {subagent_runner}")
                    _run_subagent_skill(
                        [
                            "normalize-hop-response",
                            "--component",
                            component,
                            "--action",
                            action,
                            "--input-message",
                            str(input_path),
                            "--phase",
                            "when",
                            "--hop-index",
                            str(hop_index),
                            "--valid-components",
                            ",".join(sorted(valid_components)),
                            "--output",
                            str(result_path),
                        ],
                        stdin=raw,
                    )
                    normalized = _read_json(result_path)
                    normalized["contract_binding"] = resolve_contract_binding(
                        plan.get("component_cards", {}).get(component),
                        action=action,
                        contract_id=contract_id,
                        input_message=input_message,
                    )
                    raw_next_hop = normalized.get("next_hop")
                    normalized["next_hop"] = _normalize_next_hop_contract(
                        _resolve_next_hop(raw_next_hop, valid_components),
                        plan.get("component_cards", {}).get(component),
                    )
                    if isinstance(raw_next_hop, dict) and raw_next_hop and not normalized["next_hop"]:
                        normalized["unresolved_next_hop"] = raw_next_hop
                    normalized["interaction_index"] = interaction_index
                    _write_json(result_path, normalized)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    time.sleep(1)

            if normalized is None:
                normalized = _error_hop(
                    component,
                    action,
                    input_message,
                    "when",
                    hop_index,
                    last_error or "subagent did not return valid JSON",
                )
                _write_json(result_path, normalized)

            hops.append(normalized)

            state_change = normalized.get("state_change")
            if isinstance(state_change, dict) and state_change.get("entity"):
                shared_state[str(state_change["entity"])] = state_change.get("to_state")

            next_hop = _resolve_next_hop(normalized.get("next_hop"), valid_components)
            if not next_hop:
                if normalized.get("unresolved_next_hop"):
                    break
                interaction_index += 1
                if interaction_index < len(interactions):
                    interaction = interactions[interaction_index]
                    component = interaction.get("entry_component", "")
                    action = interaction.get("entry_action") or "handle"
                    contract_id = interaction.get("entry_contract_id", "")
                    input_message = {
                        "event": action,
                        "given": interaction.get("given", []),
                        "when": interaction.get("when", ""),
                        "original_trigger": interaction.get("trigger_message") or {},
                        "interaction_index": interaction_index,
                        "interaction_count": len(interactions),
                    }
                    setup = _synthetic_setup_hop(component, action, input_message)
                    setup["interaction_index"] = interaction_index
                    hops.append(setup)
                    continue
                break
            pair = (next_hop["component"], next_hop.get("action", "handle"))
            if pair in visited:
                normalized.setdefault("self_check", {})[
                    "undefined_next_call"
                ] = f"cycle detected for {pair[0]}.{pair[1]}"
                normalized["next_hop"] = None
                break
            visited.add((component, action))
            component = next_hop["component"]
            action = next_hop.get("action", "handle")
            contract_id = next_hop.get("contract_id", "")
            input_message = normalized.get("output_message") or {}
        else:
            hops[-1].setdefault("self_check", {})["undefined_next_call"] = "max hop limit reached"
            hops[-1]["next_hop"] = None

        if len(hops) > 1:
            for h in hops[1:]:
                h["phase"] = "when"
            hops[-1]["phase"] = "then"

        hops_by_tc[tc_id] = hops
        _write_json(output_dir / "hops.json", hops_by_tc)
        print(f"[{tc_id}] simulated {len(hops)} hop(s)", flush=True)


def _run_validators_strict(
    plan_with_val_path: Path,
    output_dir: Path,
    subagent_runner: str,
    subagent_timeout: int,
) -> None:
    """Run one validator subagent per scenario using the pre-filled validator prompt."""
    plan = _read_json(plan_with_val_path)
    val_results: list[dict[str, Any]] = []
    results_by_tc: dict[str, dict[str, Any]] = {}
    call_log_path = output_dir / "subagent_calls.jsonl"
    val_schema_path = output_dir / "validator_output_schema.json"
    _write_json(val_schema_path, _VALIDATOR_OUTPUT_SCHEMA)

    for item in plan.get("plans", []):
        tc_id = item["test_case_id"]
        equivalent = _strict_equivalence_copy(item, results_by_tc)
        if equivalent:
            representative, result = equivalent
            _append_jsonl(
                call_log_path,
                {
                    "role": "validator",
                    "test_case_id": tc_id,
                    "equivalence_hit": True,
                    "equivalence_key": (item.get("equivalence") or {}).get("key"),
                    "representative": representative,
                },
            )
            results_by_tc[tc_id] = result
            val_results.append({"test_case_id": tc_id, "result": result})
            _write_json(output_dir / "val_results.json", val_results)
            print(f"[{tc_id}] reused strict-equivalent validator from {representative}", flush=True)
            continue
        prompt = item.get("validator_prompt", "")
        if not prompt:
            print(f"[{tc_id}] no validator prompt, skipping", flush=True)
            continue

        raw_path = output_dir / f"raw_validator_response_{tc_id}.txt"
        result: dict[str, Any] | None = None
        last_error = ""
        for attempt in range(1, 4):
            try:
                if subagent_runner == "codex":
                    raw = _codex_subagent(
                        prompt, raw_path, "validator", val_schema_path, subagent_timeout
                    )
                else:
                    raise RuntimeError(f"unsupported subagent runner: {subagent_runner}")
                parsed = json.loads(raw)
                errors = validator_payload_errors(parsed, require_dimensions=True)
                if errors:
                    last_error = "; ".join(errors)
                    continue
                result = parsed
                break
            except Exception as exc:
                last_error = str(exc)
                time.sleep(1)

        if result is None:
            result = _missing_validator_result(
                last_error or "validator subagent did not return valid JSON"
            )

        _append_jsonl(
            call_log_path,
            {
                "role": "validator",
                "test_case_id": tc_id,
                "attempt": attempt,
                "raw_response_file": str(raw_path),
            },
        )
        results_by_tc[tc_id] = result
        val_results.append({"test_case_id": tc_id, "result": result})
        _write_json(output_dir / "val_results.json", val_results)
        print(f"[{tc_id}] validator: {result.get('overall')}", flush=True)


def cmd_run_strict(args: argparse.Namespace) -> int:
    """One-shot strict subagent validation: prepare → simulate → validate → report."""
    try:
        feature_arg, arch_arg, _, _ = _resolve_input_arguments(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 5 if "schema" in str(exc).lower() or "match" in str(exc).lower() else 3
    feature_path = str(Path(feature_arg).resolve())
    arch_path = str(Path(arch_arg).resolve())
    if not Path(feature_path).exists():
        print(f"ERROR: feature file not found: {feature_path}", file=sys.stderr)
        return 3
    if not Path(arch_path).exists():
        print(f"ERROR: architecture document not found: {arch_path}", file=sys.stderr)
        return 3

    output_dir = Path(args.output_dir).resolve() if args.output_dir else _auto_run_dir(feature_path)
    retention = _effective_artifact_retention(args)
    report_path = _delivery_report_path(
        feature_path,
        output_dir,
        getattr(args, "report_dir", None),
    )
    if retention == "report" and report_path.resolve().is_relative_to(output_dir.resolve()):
        print(
            "ERROR: artifact-retention=report requires --report-dir outside the run workspace",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "report_dir", None):
        removed_shells = cleanup_empty_run_shells(args.report_dir)
        if removed_shells:
            print(
                f"[run-strict] removed {len(removed_shells)} empty startup run shell(s)",
                flush=True,
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "driver_state.json",
        {"started_at": datetime.now(timezone.utc).isoformat(), "cache_hits": []},
    )
    if getattr(args, "ground_truth", None):
        shutil.copyfile(args.ground_truth, output_dir / "ground_truth.json")
    plan_path = output_dir / "plan.json"

    # 1. Prepare
    prepare_args = []
    if args.config:
        # ``--config`` is a global argparse option and must precede the
        # subcommand.  Appending it after ``prepare`` makes the one-shot
        # ``run-strict`` entry point fail before any run artifacts are written.
        prepare_args.extend(["--config", args.config])
    prepare_args.extend(["prepare", "--output", str(plan_path), "--slim-prompts"])
    if getattr(args, "input_manifest", None):
        prepare_args.extend(["--input-manifest", args.input_manifest])
    else:
        prepare_args.extend(["--feature", feature_path, "--arch", arch_path])
    if args.scenario_ids:
        prepare_args.extend(["--scenario-ids", args.scenario_ids])
    if getattr(args, "start_scenario", None) is not None:
        prepare_args.extend(["--start-scenario", str(args.start_scenario)])
    if getattr(args, "scenario_range", None):
        prepare_args.extend(["--scenario-range", args.scenario_range])
    if getattr(args, "entry_overrides", None):
        prepare_args.extend(["--entry-overrides", args.entry_overrides])
    if getattr(args, "identity_manifest", None):
        prepare_args.extend(["--identity-manifest", args.identity_manifest])
    if getattr(args, "strict_equivalence", False):
        prepare_args.append("--strict-equivalence")
    print(f"[run-strict] preparing plan: {plan_path}", flush=True)
    _run_subagent_skill(prepare_args)

    # Keep every downstream diagnostic stage runnable when the semantic gate
    # skips every scenario before the first component hop.
    _write_json(output_dir / "hops.json", {})
    _write_json(output_dir / "val_results.json", [])
    (output_dir / "subagent_calls.jsonl").write_text("", encoding="utf-8")

    max_hops = getattr(args, "max_hops", 20)
    subagent_runner = getattr(args, "subagent_runner", "codex")
    subagent_timeout = getattr(args, "subagent_timeout", 300)

    # 2. Component subagent simulation
    print("[run-strict] simulating components...", flush=True)
    _simulate_components_strict(plan_path, output_dir, max_hops, subagent_runner, subagent_timeout)

    # 3. Deterministic contract check
    compat_path = output_dir / "compat.json"
    print(f"[run-strict] contract-check: {compat_path}", flush=True)
    _run_subagent_skill(
        [
            "contract-check",
            "--prompts",
            str(plan_path),
            "--hops",
            str(output_dir / "hops.json"),
            "--output",
            str(compat_path),
        ]
    )

    # 4. Fill validator prompts
    plan_with_val_path = output_dir / "plan_with_val.json"
    fill_args = [
        "fill-validator-prompts",
        "--prompts",
        str(plan_path),
        "--hops",
        str(output_dir / "hops.json"),
        "--output",
        str(plan_with_val_path),
    ]
    if getattr(args, "compact_trace", False):
        fill_args.append("--compact-trace")
    print(f"[run-strict] filling validator prompts: {plan_with_val_path}", flush=True)
    _run_subagent_skill(fill_args)

    # 5. Validator subagents
    print("[run-strict] running validators...", flush=True)
    _run_validators_strict(plan_with_val_path, output_dir, subagent_runner, subagent_timeout)

    # 6. Strict audit
    audit_path = output_dir / "strict_audit.json"
    print(f"[run-strict] auditing artifacts: {audit_path}", flush=True)
    audit_error = ""
    try:
        _run_subagent_skill(
            [
                "validate-run-artifacts",
                "--prompts",
                str(plan_with_val_path),
                "--hops",
                str(output_dir / "hops.json"),
                "--val-results",
                str(output_dir / "val_results.json"),
                "--call-log",
                str(output_dir / "subagent_calls.jsonl"),
                "--require-call-log",
                "--output",
                str(audit_path),
            ]
        )
    except RuntimeError as exc:
        audit_error = str(exc)
        if not audit_path.exists():
            raise
    audit = _read_json(audit_path, {})
    status = audit.get("status", "UNKNOWN")

    # 7. Report
    report_args = [
        "report",
        "--prompts",
        str(plan_with_val_path),
        "--val-results",
        str(output_dir / "val_results.json"),
        "--compat",
        str(compat_path),
        "--hops",
        str(output_dir / "hops.json"),
        "--output",
        str(report_path),
        "--strict-audit",
        str(audit_path),
        "--audience",
        args.audience,
        "--artifact-dir",
        str(output_dir),
    ]
    if status == "PASS":
        report_args.append("--strict")
        if retention == "report":
            report_args.append("--omit-artifact-refs")
    if getattr(args, "diagnostics", False):
        report_args.append("--diagnostics")
    print(f"[run-strict] rendering report: {report_path}", flush=True)
    _run_subagent_skill(report_args)

    if audit_error:
        print(
            "[run-strict] strict audit failed; diagnostic report was still generated",
            file=sys.stderr,
            flush=True,
        )
    summary_path = output_dir / "run_summary.json"
    _write_json(
        summary_path,
        {
            "audit_status": status,
            "report": str(report_path),
            "run_dir": str(output_dir),
            "artifact_retention": retention,
        },
    )
    formal_output_dir = (
        output_dir / "formal"
        if report_path.resolve().is_relative_to(output_dir.resolve())
        else report_path.parent / output_dir.name
    )
    identity = {
        key: getattr(args, key, "")
        for key in (
            "project_id",
            "node_id",
            "parent_node_id",
            "branch_id",
            "architecture_artifact_id",
            "testcase_artifact_id",
            "source_prd_id",
        )
        if getattr(args, key, "")
    }
    formal_report = publish_strict_run(
        output_dir,
        formal_output_dir,
        expected_identity=identity,
        run_id=getattr(args, "run_id", None),
        random_seed=getattr(args, "random_seed", None),
        model_context={
            "simulator_model": getattr(args, "simulator_model", ""),
            "validator_model": getattr(args, "validator_model", ""),
        },
        include_source_refs=retention != "report",
    )
    summary = _read_json(summary_path, {})
    summary["mocktest_status"] = formal_report.status
    summary["formal_output_dir"] = str(formal_output_dir)
    _write_json(summary_path, summary)
    retention_result = apply_artifact_retention(output_dir, retention, status)
    print(
        f"[run-strict] finished. audit={status} report={report_path} "
        f"retention={retention_result}",
        flush=True,
    )
    return exit_code_for_report(formal_report)


def cmd_publish_artifacts(args: argparse.Namespace) -> int:
    identity = {
        key: getattr(args, key, "") for key in RUN_IDENTITY_FIELDS if getattr(args, key, "")
    }
    report = publish_strict_run(
        args.run_dir,
        args.output_dir,
        expected_identity=identity,
        run_id=args.run_id,
        random_seed=args.random_seed,
        model_context={
            "simulator_model": args.simulator_model,
            "validator_model": args.validator_model,
        },
        include_source_refs=not args.self_contained,
    )
    print(report.model_dump_json(indent=2), flush=True)
    return exit_code_for_report(report)


RUN_IDENTITY_FIELDS = (
    "project_id",
    "node_id",
    "parent_node_id",
    "branch_id",
    "architecture_artifact_id",
    "testcase_artifact_id",
    "source_prd_id",
)


def add_protocol_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", help="Unique execution ID; default is a generated UUID")
    parser.add_argument("--random-seed", type=int)
    parser.add_argument("--simulator-model", default="")
    parser.add_argument("--validator-model", default="")
    parser.add_argument(
        "--self-contained",
        action="store_true",
        help="Omit references to source run files that will not be delivered",
    )
    for key in RUN_IDENTITY_FIELDS:
        parser.add_argument("--" + key.replace("_", "-"), default="")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_subagent_skill",
        description="Subagent-mode helper for the validate-arch skill.",
    )
    parser.add_argument(
        "--config",
        default="config/default.yaml",
        help="Path to mock_framework config file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Generate subagent prompts")
    prepare_parser.add_argument("--feature", "-f")
    prepare_parser.add_argument("--arch", "-a")
    prepare_parser.add_argument("--input-manifest")
    prepare_parser.add_argument(
        "--output", "-o", help="Path to write plan.json (default: <output-dir>/plan.json)"
    )
    prepare_parser.add_argument(
        "--output-dir",
        help="Directory for run artifacts; plan.json is written here unless --output is given",
    )
    prepare_parser.add_argument(
        "--scenario-ids",
        default="",
        help="Comma-separated list of test_case_ids to include (default: all)",
    )
    prepare_parser.add_argument(
        "--start-scenario",
        type=int,
        help="1-based index of the first scenario to include (translated to SCENARIO-xxx ID)",
    )
    prepare_parser.add_argument(
        "--scenario-range",
        help='Inclusive scenario range like "34-40" (1-based, translated to SCENARIO-xxx IDs)',
    )
    prepare_parser.add_argument(
        "--entry-overrides",
        help="JSON file mapping test_case_id to entry_component (or dict with entry_component/action)",
    )
    prepare_parser.add_argument(
        "--slim-prompts",
        action="store_true",
        help=(
            "Do not embed all component prompt templates in plan.json; "
            "simulate-step-prompt will generate the requested component prompt on demand."
        ),
    )
    prepare_parser.add_argument(
        "--strict-equivalence",
        action="store_true",
        help=(
            "Reuse only Scenario Outline rows with byte-identical concrete steps, "
            "mappings, expectations, tags, and execution plans."
        ),
    )

    subparsers.add_parser(
        "simulate-step-prompt",
        help="Print the full prompt for a single component subagent hop (reads request JSON from stdin)",
    )

    normalize_parser = subparsers.add_parser(
        "normalize-hop-response",
        help="Normalize one raw component subagent response from stdin into a HopResult JSON file",
    )
    normalize_parser.add_argument("--component", required=True)
    normalize_parser.add_argument("--action", default="handle")
    normalize_parser.add_argument("--input-message", default="{}")
    normalize_parser.add_argument("--phase", default="when")
    normalize_parser.add_argument("--hop-index", type=int, default=0)
    normalize_parser.add_argument("--valid-components", required=True)
    normalize_parser.add_argument("--output", "-o", required=True)

    fill_parser = subparsers.add_parser(
        "fill-validator-prompts",
        help="Fill validator prompts after simulator results are ready",
    )
    fill_parser.add_argument("--prompts", "-p", required=True)
    fill_parser.add_argument("--hops", required=True)
    fill_parser.add_argument("--output", "-o", required=True)
    fill_parser.add_argument(
        "--compact-trace",
        action="store_true",
        help="Generate a smaller validator prompt from a compact trace summary.",
    )

    audit_parser = subparsers.add_parser(
        "validate-run-artifacts",
        help="Audit strict per-hop component subagent artifacts before report generation",
    )
    audit_parser.add_argument("--prompts", "-p", required=True)
    audit_parser.add_argument("--hops", required=True)
    audit_parser.add_argument("--val-results", "-v", required=True)
    audit_parser.add_argument(
        "--call-log", help="JSONL/JSON list of component and validator subagent calls"
    )
    audit_parser.add_argument(
        "--require-call-log",
        action="store_true",
        help="Fail if --call-log is missing or incomplete",
    )
    audit_parser.add_argument("--output", "-o", required=True)

    report_parser = subparsers.add_parser("report", help="Generate final report")
    report_parser.add_argument("--prompts", "-p", required=True)
    report_parser.add_argument("--val-results", "-v", required=True)
    report_parser.add_argument("--compat", required=True)
    report_parser.add_argument("--hops", required=True)
    report_parser.add_argument("--output", "-o", required=True)
    report_parser.add_argument(
        "--audience",
        choices=("full", "architecture"),
        default="architecture",
        help=(
            "Report audience. 'architecture' (default) emits only the architecture-designer "
            "delivery report; 'full' preserves the original detailed per-scenario validation report."
        ),
    )
    report_parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Also write an internal diagnostics report next to the main report (off by default).",
    )
    prepare_parser.add_argument(
        "--identity-manifest",
        help=(
            "JSON object with identity plus architecture/testcase identities; "
            "its hash becomes part of the input fingerprint"
        ),
    )
    report_parser.add_argument(
        "--artifact-dir",
        help="Run artifact directory used to render valid evidence references in the report.",
    )
    report_parser.add_argument(
        "--omit-artifact-refs",
        action="store_true",
        help="Omit sibling artifact references from a self-contained report-only delivery.",
    )
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Require a PASS strict audit before writing the report",
    )
    report_parser.add_argument("--strict-audit", help="Path to validate-run-artifacts output")

    cc_parser = subparsers.add_parser(
        "contract-check", help="Deterministic interface compatibility check"
    )
    cc_parser.add_argument("--prompts", "-p", required=True)
    cc_parser.add_argument("--hops", required=True, help="JSON: {test_case_id: [HopResult...]}")
    cc_parser.add_argument("--output", "-o", required=True)

    run_strict_parser = subparsers.add_parser(
        "run-strict",
        help="One-shot strict subagent validation (prepare → simulate → validate → report)",
    )
    run_strict_parser.add_argument("--feature", "-f")
    run_strict_parser.add_argument("--arch", "-a")
    run_strict_parser.add_argument("--input-manifest")
    run_strict_parser.add_argument(
        "--ground-truth", help="Optional defect-injection Ground Truth JSON"
    )
    run_strict_parser.add_argument(
        "--output-dir",
        "-o",
        help="Run workspace for intermediate artifacts (default: .work/validate-arch/runs/<auto-name>)",
    )
    run_strict_parser.add_argument(
        "--report-dir",
        help="Delivery directory for the auto-named final report; enables report-only retention by default.",
    )
    run_strict_parser.add_argument(
        "--artifact-retention",
        choices=("report", "audit", "full"),
        help=(
            "PASS-run retention: report removes managed .work run files, audit drops per-call "
            "debug files, full keeps everything. Default: report with --report-dir, otherwise full."
        ),
    )
    run_strict_parser.add_argument(
        "--scenario-ids",
        default="",
        help="Comma-separated list of test_case_ids to include",
    )
    run_strict_parser.add_argument(
        "--start-scenario",
        type=int,
        help="1-based index of the first scenario to include",
    )
    run_strict_parser.add_argument(
        "--scenario-range",
        help='Inclusive scenario range like "34-40"',
    )
    run_strict_parser.add_argument(
        "--entry-overrides",
        help="JSON file mapping test_case_id to entry_component (or dict with entry_component/action)",
    )
    run_strict_parser.add_argument(
        "--slim-prompts",
        action="store_true",
        help="Use dynamic per-hop component prompts (recommended).",
    )
    run_strict_parser.add_argument(
        "--strict-equivalence",
        action="store_true",
        help="Reuse byte-identical Scenario Outline rows within this run.",
    )
    run_strict_parser.add_argument("--identity-manifest")
    run_strict_parser.add_argument(
        "--compact-trace",
        action="store_true",
        help="Generate smaller validator prompts from compact trace summaries.",
    )
    run_strict_parser.add_argument(
        "--max-hops",
        type=int,
        default=20,
        help="Maximum component hops per scenario (default: 20)",
    )
    run_strict_parser.add_argument(
        "--subagent-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for each component/validator subagent (default: 300)",
    )
    run_strict_parser.add_argument(
        "--subagent-runner",
        default="codex",
        choices=("codex",),
        help="Subagent runner backend (default: codex)",
    )
    run_strict_parser.add_argument(
        "--audience",
        choices=("full", "architecture"),
        default="architecture",
        help="Report audience (default: architecture)",
    )
    run_strict_parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Also write an internal diagnostics report next to the main report.",
    )
    add_protocol_arguments(run_strict_parser)

    publish_parser = subparsers.add_parser(
        "publish-artifacts",
        help="Publish versioned Mocktest/Leaf Gate artifacts from a strict run directory",
    )
    publish_parser.add_argument("--run-dir", required=True)
    publish_parser.add_argument("--output-dir", required=True)
    add_protocol_arguments(publish_parser)

    schemas_parser = subparsers.add_parser("export-schemas", help="Export protocol JSON Schemas")
    schemas_parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    if args.command == "prepare":
        return cmd_prepare(args)
    if args.command == "simulate-step-prompt":
        return cmd_simulate_step_prompt(args)
    if args.command == "normalize-hop-response":
        return cmd_normalize_hop_response(args)
    if args.command == "fill-validator-prompts":
        return cmd_fill_validator_prompts(args)
    if args.command == "validate-run-artifacts":
        return cmd_validate_run_artifacts(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "contract-check":
        return cmd_contract_check(args)
    if args.command == "run-strict":
        return cmd_run_strict(args)
    if args.command == "publish-artifacts":
        return cmd_publish_artifacts(args)
    if args.command == "export-schemas":
        write_schemas(args.output_dir)
        return 0

    parser.print_help()
    return 1


def _configure_utf8_stdio() -> None:
    """Reconfigure stdio to UTF-8 on Windows and other restricted terminals."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


if __name__ == "__main__":
    _configure_utf8_stdio()
    sys.exit(main())
