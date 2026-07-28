"""Claude Code Skill — validate-arch"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml  # type: ignore[import-untyped]

from mock_framework.agents.skill_gateway import ClaudeCodeSkillGateway
from mock_framework.config import load_config
from mock_framework.loader import Loader
from mock_framework.logger import get_logger
from mock_framework.models.validator import ValidationReport
from mock_framework.pipeline import Pipeline
from mock_framework.simulator.llm_client import LLMClient, LLMClientFactory
from mock_framework.simulator.simulator import Simulator
from mock_framework.validator.validator import Validator

from .skill_llm_client import SkillLLMClient


@dataclass
class SkillArgs:
    """Skill 参数"""

    feature: str
    arch: str
    mode: str = "full"
    max_rounds: int = 3
    show_reasoning: bool = False


@dataclass
class SkillResult:
    """Skill 返回结果"""

    status: str
    report_path: Optional[str]
    suggestions_count: int
    message: str


def _resolve_api_key(value: str) -> str:
    """解析 API Key，支持 ${ENV_VAR} 环境变量语法."""
    match = re.match(r"^\$\{(.+)\}$", value)
    if match:
        return os.environ.get(match.group(1), value)
    return value


class ValidateArchSkill:
    """
    Claude Code Skill 入口。

    被 Claude Code 调用时，直接利用当前会话上下文：
    - 读取工作区文件
    - 使用 Loader 解析 Gherkin 与架构文档
    - 通过核心 Simulator + Validator 完成模拟与验证
    - 复用 Pipeline 的改进建议生成
    - 结果直接展示在对话中
    """

    def __init__(self) -> None:
        self.logger = get_logger("skill.validate_arch")
        self.config = load_config()

    def _is_claude_code_environment(self) -> bool:
        """检测是否在支持 Skill IPC 的 Claude Code 环境中运行。

        多因子检测：
        1. MOCK_FRAMEWORK_FORCE_SKILL_IPC=1 强制启用 Skill IPC
        2. MOCK_FRAMEWORK_FORCE_API=1 强制禁用 Skill IPC
        3. CLAUDE_CODE_CHILD_SESSION=1 表示 VS Code 扩展子会话，stdout markers
           不会被当前 Claude 会话捕获，因此不走 Skill IPC
        4. CLAUDE_CODE / CLAUDECODE 环境变量 == "1"
        5. .claude 目录存在于当前工作目录
        6. CLAUDE_SESSION 环境变量存在

        可通过设置 MOCK_FRAMEWORK_FORCE_API=1 强制使用 API 模式，
        或 MOCK_FRAMEWORK_FORCE_SKILL_IPC=1 强制使用 Skill IPC 模式。
        """
        if os.environ.get("MOCK_FRAMEWORK_FORCE_API") == "1":
            return False
        if os.environ.get("MOCK_FRAMEWORK_FORCE_SKILL_IPC") == "1":
            return True
        if os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1":
            return False
        if os.environ.get("CLAUDE_CODE") == "1":
            return True
        if os.environ.get("CLAUDECODE") == "1":
            return True
        if Path(".claude").exists():
            return True
        if os.environ.get("CLAUDE_SESSION") is not None:
            return True
        return False

    async def execute(self, args: SkillArgs) -> SkillResult:
        """
        Skill 执行入口。

        与 CLI 模式的区别：
        - 不通过外部 LLM API 调用，而是通过当前 Claude 会话
        - 可以直接修改工作区文件
        - 结果直接展示在对话中
        """
        self.logger.info("Skill execute: feature=%s arch=%s", args.feature, args.arch)

        # Resolve paths
        feature_path = self._resolve_path(args.feature)
        arch_path = self._resolve_path(args.arch)

        # Validate files exist
        if not Path(feature_path).exists():
            return SkillResult(
                status="ERROR",
                report_path=None,
                suggestions_count=0,
                message=f"Feature file not found: {feature_path}",
            )
        if not Path(arch_path).exists():
            return SkillResult(
                status="ERROR",
                report_path=None,
                suggestions_count=0,
                message=f"Arch doc not found: {arch_path}",
            )

        # 如果 arch 是目录，聚合所有 .md 文件到临时文件
        arch_input_path = arch_path
        if Path(arch_path).is_dir():
            arch_input_path = self._aggregate_arch_docs(arch_path)
            self.logger.info("Arch path is directory, aggregated to: %s", arch_input_path)

        # 预处理：仅验证当前层，屏蔽下一层引用
        arch_input_path = self._preprocess_for_current_layer(arch_input_path)
        self.logger.info(
            "Arch doc preprocessed for current-layer-only validation: %s", arch_input_path
        )

        # 在 executor 线程中运行同步的 Pipeline，避免 LLMClient 同步接口与异步 gateway 的事件循环冲突
        loop = asyncio.get_running_loop()
        report: ValidationReport = await loop.run_in_executor(
            None,
            self._run_pipeline,
            feature_path,
            arch_input_path,
        )

        # Write report
        report_path = self._write_report(report, feature_path, arch_path)

        # 收集建议数量
        suggestions_count = len(report.recommendations)

        # 注意：本阶段移除自动修改循环，max_rounds 保留但忽略
        if args.mode == "full" and args.max_rounds > 1:
            self.logger.info(
                "max_rounds=%d is ignored in Skill mode; auto-modify loop removed in this refactor.",
                args.max_rounds,
            )

        # Build message
        passed = report.summary.get("passed", 0)
        failed = report.summary.get("failed", 0)
        warnings = report.summary.get("warnings", 0)
        missing = report.summary.get("missing", 0)
        total = report.summary.get("total_test_cases", 0)

        if failed == 0 and warnings == 0 and missing == 0:
            message = f"✅ All {total} test case(s) passed."
        else:
            message = (
                f"❌ Validation completed: {passed}/{total} passed, "
                f"{failed} failed, {warnings} warnings, {missing} missing. "
                f"See {report_path}"
            )

        status = "PASS" if failed == 0 and missing == 0 else "FAIL"
        return SkillResult(
            status=status,
            report_path=report_path,
            suggestions_count=suggestions_count,
            message=message,
        )

    def _run_pipeline(self, feature_path: str, arch_input_path: str) -> ValidationReport:
        """同步方法：构建并运行核心 Pipeline."""
        loader = Loader(self.config.loader)

        if self._is_claude_code_environment():
            gateway = ClaudeCodeSkillGateway()
            sim_llm: LLMClient = SkillLLMClient(
                gateway=gateway,
                agent_type="simulator",
            )
            val_llm: LLMClient = SkillLLMClient(
                gateway=gateway,
                agent_type="validator",
            )
        else:
            api_key = _resolve_api_key(self.config.llm.api_key)
            base_url = self.config.llm.base_url
            sim_cfg = self.config.llm.simulator
            val_cfg = self.config.llm.validator
            sim_llm = LLMClientFactory.create(
                provider=sim_cfg.provider,
                api_key=api_key,
                model=sim_cfg.model,
                token_budget=sim_cfg.token_budget,
                base_url=base_url,
                timeout_seconds=sim_cfg.timeout_seconds,
                max_retries=sim_cfg.max_retries,
                retry_backoff_seconds=sim_cfg.retry_backoff_seconds,
            )
            val_llm = LLMClientFactory.create(
                provider=val_cfg.provider,
                api_key=api_key,
                model=val_cfg.model,
                token_budget=val_cfg.token_budget,
                base_url=base_url,
                timeout_seconds=val_cfg.timeout_seconds,
                max_retries=val_cfg.max_retries,
                retry_backoff_seconds=val_cfg.retry_backoff_seconds,
            )

        simulator = Simulator(sim_llm)
        validator = Validator(val_llm)
        pipeline = Pipeline(loader, simulator, validator, retry_count=3)
        return pipeline.run(feature_path, arch_input_path)

    def _aggregate_arch_docs(self, arch_dir: str, output_dir: str | Path | None = None) -> str:
        """将目录中的所有 .md 文件聚合成一个临时文件。

        排序规则：
        1. README.md 优先
        2. 其他文件按字母顺序
        """
        from pathlib import Path

        arch_path = Path(arch_dir)
        tmp_dir = Path(output_dir) if output_dir else Path(".claude/skills/validate-arch/.tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)

        package = self._read_architecture_package_manifest(arch_path)
        artifact_names = package.get("artifacts", [])
        if artifact_names:
            md_files = [
                arch_path / name
                for name in artifact_names
                if str(name).lower().endswith(".md")
                and str(name).lower() not in {"readme.md", "child-handoff.md"}
                and (arch_path / name).is_file()
            ]
        else:
            md_files = sorted(
                arch_path.glob("*.md"),
                key=lambda p: (p.name.lower() != "readme.md", p.name.lower()),
            )

        lines = ["# Aggregated Architecture Documents\n"]
        if package:
            lines.append(
                "\n<!-- validate-arch-package: "
                + json.dumps(package, ensure_ascii=False, separators=(",", ":"))
                + " -->\n"
            )
        for f in md_files:
            lines.append(f"\n---\n\n## File: {f.name}\n\n")
            lines.append(f.read_text(encoding="utf-8"))

        aggregated_path = tmp_dir / "arch_aggregated.md"
        aggregated_path.write_text("".join(lines), encoding="utf-8")
        return str(aggregated_path)

    def _read_architecture_package_manifest(self, arch_path: Path) -> dict[str, Any]:
        """Normalize the manifest variants used by recursive L1 architecture packages."""
        manifest_path = arch_path / "architecture-manifest.yaml"
        if not manifest_path.is_file():
            return {}
        raw_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw_data, dict):
            return {}
        raw: dict[str, Any] = raw_data
        package: dict[str, Any] = raw["package"] if isinstance(raw.get("package"), dict) else {}
        current: dict[str, Any] = (
            raw["current_node"] if isinstance(raw.get("current_node"), dict) else {}
        )
        inputs: dict[str, Any] = raw["inputs"] if isinstance(raw.get("inputs"), dict) else {}
        artifacts = (
            raw.get("artifacts")
            or raw.get("artifact_inventory")
            or raw.get("generated_artifacts")
            or []
        )
        level = package.get("level") or raw.get("level") or raw.get("layer") or ""
        current_name = (
            package.get("current_node_name")
            or current.get("name")
            or raw.get("current_node_name")
            or ""
        )
        target_node_id = (
            package.get("target_node_id")
            or current.get("target_node_id")
            or raw.get("target_node_id")
            or current_name
        )
        responsibility = package.get("responsibility") or current.get("responsibility") or ""
        exclusions = package.get("exclusions") or current.get("exclusions") or []
        parent_ref = inputs.get("parent_architecture") or raw.get("parent_architecture") or ""
        return {
            "manifest": manifest_path.name,
            "level": str(level),
            "current_node_name": str(current_name),
            "target_node_id": str(target_node_id),
            "responsibility": str(responsibility),
            "exclusions": list(exclusions) if isinstance(exclusions, list) else [],
            "parent_ref": str(parent_ref),
            "status": str(raw.get("status") or package.get("status") or ""),
            "artifacts": [str(item) for item in artifacts] if isinstance(artifacts, list) else [],
        }

    def _preprocess_for_current_layer(
        self, arch_input_path: str, output_dir: str | Path | None = None
    ) -> str:
        """预处理架构文档内容，仅保留当前层验证所需信息。

        将 ``modules/*.md`` 等下一层引用标记为“未来工作”，避免 LLM
        因为下一层文档不存在而失败。
        """
        from pathlib import Path

        content = Path(arch_input_path).read_text(encoding="utf-8")

        scope_note = (
            "\n\n> **验证范围说明**：本次验证只针对当前传入的架构层。"
            "文档中引用的 `modules/*.md` 等下一层/子模块设计视为未来工作，"
            "不在本次验证范围内，请勿因此产生失败或建议创建这些文件。\n\n"
        )

        # 将 modules/xxx.md 引用替换为显式占位符
        def replace_child_ref(match: re.Match) -> str:
            ref = match.group(0)
            return f"[下一层设计：{ref}]"

        processed = re.sub(r"modules/[^\s\)\]\,]+\.md", replace_child_ref, content)

        tmp_dir = Path(output_dir) if output_dir else Path(".claude/skills/validate-arch/.tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        preprocessed_path = tmp_dir / "arch_current_layer.md"
        preprocessed_path.write_text(scope_note + processed, encoding="utf-8")
        return str(preprocessed_path)

    def _resolve_path(self, path: str) -> str:
        """解析路径（支持相对路径）"""
        p = Path(path)
        if p.is_absolute():
            return str(p)
        return str(Path.cwd() / p)

    def _write_report(self, report: ValidationReport, feature_path: str, arch_path: str) -> str:
        """写入报告文件。

        报告生成在 feature 文件所在目录的 reports/ 子文件夹下，
        文件名为 ``<feature-stem>-validation-report.md``。
        """
        feature_file = Path(feature_path)
        feature_stem = feature_file.stem
        report_dir = feature_file.parent / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        report_path = report_dir / f"{feature_stem}-validation-report.md"

        lines: list[str] = []
        lines.append("# Validation Report\n")
        lines.append(f"**Status**: {self._report_status(report)}\n")
        lines.append(f"**Feature**: {feature_path}\n")
        lines.append(f"**Architecture**: {arch_path}\n")
        lines.append(f"**Timestamp**: {report.timestamp}\n")
        lines.append(f"**Test Cases**: {report.summary.get('total_test_cases', 0)}\n")
        lines.append(
            f"**Summary**: {report.summary.get('passed', 0)} passed, "
            f"{report.summary.get('failed', 0)} failed, "
            f"{report.summary.get('warnings', 0)} warnings, "
            f"{report.summary.get('missing', 0)} missing\n"
        )
        lines.append("\n")

        # Per-test-case details
        for result in report.details:
            lines.append(f"## Test Case: {result.scenario_name}\n")
            lines.append(f"- **ID**: {result.test_case_id}\n")
            lines.append(f"- **Result**: {result.result}\n")
            lines.append("\n")

            if result.five_dimensions:
                lines.append("### Five Dimensions\n")
                lines.append("| Dimension | Status | Detail |\n")
                lines.append("|-----------|--------|--------|\n")
                for dim, detail in result.five_dimensions.items():
                    lines.append(f"| {dim} | {detail.status} | {detail.detail} |\n")
                lines.append("\n")

            if result.failure_analysis:
                lines.append("### Failure Analysis\n")
                fa = result.failure_analysis
                lines.append(f"- **Dimension**: {fa.dimension}\n")
                lines.append(f"- **Problem**: {fa.problem}\n")
                lines.append(f"- **Severity**: {fa.severity}\n")
                lines.append(f"- **Impact**: {fa.impact}\n")
                lines.append(f"- **Suggestion**: {fa.suggestion}\n")
                lines.append("\n")

            if result.warning_analysis:
                lines.append("### Warning Analysis\n")
                wa = result.warning_analysis
                lines.append(f"- **Dimension**: {wa.dimension}\n")
                lines.append(f"- **Problem**: {wa.problem}\n")
                lines.append(f"- **Suggestion**: {wa.suggestion}\n")
                lines.append("\n")

        # Recommendations
        if report.recommendations:
            lines.append("## Recommendations\n")
            for rec in report.recommendations:
                lines.append(
                    f"- **[{rec.priority}]** {rec.action} "
                    f"(affected: {', '.join(rec.affected_test_cases)})\n"
                )
            lines.append("\n")

        content = "".join(lines)
        report_path.write_text(content, encoding="utf-8")
        return str(report_path.resolve())

    def _report_status(self, report: ValidationReport) -> str:
        """根据 ValidationReport 计算整体状态."""
        if report.summary.get("failed", 0) > 0:
            return "FAIL"
        if report.summary.get("missing", 0) > 0:
            return "MISSING"
        if report.summary.get("warnings", 0) > 0:
            return "WARNING"
        return "PASS"
