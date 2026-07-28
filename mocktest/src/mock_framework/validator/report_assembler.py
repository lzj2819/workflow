"""ReportAssembler - assembles validation results and reports."""

from datetime import datetime, timezone
from typing import Optional

from mock_framework.models.validator import (
    DimensionResult,
    FailureAnalysis,
    Recommendation,
    ValidationReport,
    ValidationResult,
    WarningAnalysis,
)


class ReportAssembler:
    """Assembles ValidationResult from agent output and builds ValidationReport."""

    @staticmethod
    def _is_architecture_suggestion(action: str, dimension: str) -> bool:
        """判断建议是否反映架构设计问题，而非模拟过程错误。"""
        if dimension == "structure":
            return False
        lower = action.lower()
        process_hints = (
            "simulator",
            "invalid_json_response",
            "consumed_input_ok=false",
            "compact trace",
            "raw payload",
            "raw hop",
            "emit explicit given/when/then",
            "phase labels",
            "extend the trace",
            "extend the simulator trace",
            "run the when step",
            "execute an explicit when step",
            "execute a distinct when step",
            "execute the when step",
            "no explicit when phase",
            "no separate when phase",
            "given followed directly by then",
        )
        scenario_input_hints = (
            "provide the concrete selected_proficiency_level",
            "selected_proficiency_level in the scenario input",
            "provide the complete solution content as input",
            "scenario input",
            "test fixture",
        )
        if any(hint in lower for hint in process_hints):
            return False
        if any(hint in lower for hint in scenario_input_hints):
            return False
        if dimension == "interface_compat" and "复查孤儿组件" in action:
            return False
        return True

    @staticmethod
    def _classify_scope(action: str, dimension: str, llm_scope: Optional[str] = None) -> str:
        """把建议按粒度分为顶层架构问题（top_level）或模块内部问题（module）。

        优先使用 LLM 返回的 scope；缺失或无效时按抽象层级规则兜底：
        - top_level: 当前架构层应定义但未定义（组件缺失、职责错误、流程错误、
          核心状态/生命周期缺失、主要分支缺失）。
        - module: 已定义但具体细节不足（字段、文案、算法、命名、子状态、
          内部验证规则）。
        """
        if llm_scope in ("top_level", "module"):
            return llm_scope

        lower = action.lower()

        # 维度级快速判定
        if dimension in ("flow", "performance", "structure"):
            return "top_level"

        if dimension == "interface_compat":
            # 字段级缺失属于模块内部；接口缺失/不匹配属于顶层
            interface_module_hints: tuple[str, ...] = ("字段", "field", "补全上游输出")
            if any(h in lower for h in interface_module_hints):
                return "module"
            return "top_level"

        # state: 核心状态/生命周期缺失 → top_level；命名/from_state/trace 细节 → module
        if dimension == "state":
            state_module_hints: tuple[str, ...] = (
                "event names",
                "from_state",
                "state tracking",
                "trace",
                "命名",
                "trigger",
            )
            if any(h in lower for h in state_module_hints):
                return "module"
            return "top_level"

        # contract: 核心流程分支缺失 → top_level；字段/文案/算法/术语 → module
        if dimension == "contract":
            contract_module_hints: tuple[str, ...] = (
                "字段",
                "field",
                "文案",
                "copy",
                "算法",
                "algorithm",
                "术语",
                "terminology",
                "layered_hint",
                "direction",
                "follow-up",
                "key calculation",
                "step by step",
                "privacy prompt",
                "disclos",
                "model training",
                "traceability",
                "numerator",
                "denominator",
                "ratio",
                "success rate",
                "success-rate",
                "complete solution",
                "new verification code",
                "resend limit",
                "within 5 minutes",
                # 中文关键词
                "提示方向",
                "追问问题",
                "关键计算",
                "最终答案",
                "按步骤",
                "步骤说明",
                "标准术语",
                "隐私提示",
                "数据用途",
                "模型训练",
                "30 天后删除",
                "新验证码",
                "重发限制",
                "成功率",
                "比例",
                "完整解答",
                "按钮显示",
                "追溯",
            )
            if any(h in lower for h in contract_module_hints):
                return "module"
            return "top_level"

        return "module"

    def assemble_result(
        self, test_case_id: str, scenario_name: str, agent_output: dict
    ) -> ValidationResult:
        """Parse agent_output and assemble a ValidationResult.

        Args:
            test_case_id: The test case ID.
            scenario_name: The scenario name.
            agent_output: Dict from ValidatorAgentCore.validate().

        Returns:
            A ValidationResult with parsed dimensions and analysis.
        """
        five_dimensions: dict[str, DimensionResult] = {}
        for dim in ("structure", "flow", "state", "contract", "performance", "interface_compat"):
            dim_data = agent_output.get(dim, {})
            five_dimensions[dim] = DimensionResult(
                status=dim_data.get("status", "MISSING"),
                detail=dim_data.get("detail", ""),
            )

        overall = agent_output.get("overall", "MISSING")

        failure_analysis: Optional[FailureAnalysis] = None
        if overall == "FAIL" and "failure_analysis" in agent_output:
            fa = agent_output["failure_analysis"]
            if fa:
                candidate = FailureAnalysis(
                    dimension=fa.get("dimension", ""),
                    problem=fa.get("problem", ""),
                    severity=fa.get("severity", "medium"),
                    impact=fa.get("impact", ""),
                    suggestion=fa.get("suggestion", ""),
                    scope=fa.get("scope"),
                )
                if self._is_architecture_suggestion(candidate.suggestion, candidate.dimension):
                    failure_analysis = candidate

        warning_analysis: Optional[WarningAnalysis] = None
        if overall == "WARNING" and "warning_analysis" in agent_output:
            wa = agent_output["warning_analysis"]
            if wa:
                warn_candidate = WarningAnalysis(
                    dimension=wa.get("dimension", ""),
                    problem=wa.get("problem", ""),
                    suggestion=wa.get("suggestion", ""),
                    scope=wa.get("scope"),
                )
                if self._is_architecture_suggestion(
                    warn_candidate.suggestion, warn_candidate.dimension
                ):
                    warning_analysis = warn_candidate

        return ValidationResult(
            test_case_id=test_case_id,
            scenario_name=scenario_name,
            result=overall,
            five_dimensions=five_dimensions,
            failure_analysis=failure_analysis,
            warning_analysis=warning_analysis,
        )

    def build_report(
        self,
        report_id: str,
        architecture_doc: str,
        gherkin_source: str,
        results: list[ValidationResult],
    ) -> ValidationReport:
        """Build a ValidationReport from a list of ValidationResults.

        Args:
            report_id: The report ID.
            architecture_doc: The architecture document name.
            gherkin_source: The Gherkin source file name.
            results: List of ValidationResult.

        Returns:
            A ValidationReport with summary and recommendations.
        """
        total_test_cases = len(results)
        passed = sum(1 for r in results if r.result == "PASS")
        failed = sum(1 for r in results if r.result == "FAIL")
        warnings = sum(1 for r in results if r.result == "WARNING")
        missing = sum(1 for r in results if r.result == "MISSING")

        pass_rate = passed / total_test_cases if total_test_cases > 0 else 0.0

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        recommendations = self._build_recommendations(results)

        summary = {
            "total_test_cases": total_test_cases,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "missing": missing,
            "pass_rate": pass_rate,
        }

        return ValidationReport(
            report_id=report_id,
            architecture_doc=architecture_doc,
            gherkin_source=gherkin_source,
            timestamp=timestamp,
            summary=summary,
            details=results,
            recommendations=recommendations,
        )

    def _build_recommendations(self, results: list[ValidationResult]) -> list[Recommendation]:
        """Extract recommendations from failure and warning analyses.

        过滤掉模拟过程错误（如 phase 标签、simulator trace 补全等），
        只保留反映架构设计问题的建议。

        Args:
            results: List of ValidationResult.

        Returns:
            List of deduplicated Recommendation with merged affected test cases.
        """
        seen: dict[tuple[str, str], Recommendation] = {}

        def _ensure(
            action: str,
            dimension: str,
            priority: str,
            effort: str,
            tc_id: str,
            scope: str = "module",
        ) -> Recommendation:
            key = (action, dimension)
            rec = seen.get(key)
            if rec is None:
                rec = Recommendation(
                    priority=priority,
                    action=action,
                    affected_test_cases=[tc_id],
                    estimated_effort=effort,
                    scope=scope,
                )
                seen[key] = rec
            elif tc_id not in rec.affected_test_cases:
                rec.affected_test_cases.append(tc_id)
            return rec

        for result in results:
            if result.failure_analysis is not None:
                fa = result.failure_analysis
                if self._is_architecture_suggestion(fa.suggestion, fa.dimension):
                    scope = self._classify_scope(fa.suggestion, fa.dimension, fa.scope)
                    _ensure(
                        fa.suggestion,
                        fa.dimension,
                        fa.severity,
                        "30分钟",
                        result.test_case_id,
                        scope=scope,
                    )

            if result.warning_analysis is not None:
                wa = result.warning_analysis
                if self._is_architecture_suggestion(wa.suggestion, wa.dimension):
                    scope = self._classify_scope(wa.suggestion, wa.dimension, wa.scope)
                    _ensure(
                        wa.suggestion,
                        wa.dimension,
                        "medium",
                        "15分钟",
                        result.test_case_id,
                        scope=scope,
                    )

            if result.result == "MISSING":
                _ensure(
                    f"补充验证覆盖: {result.scenario_name}",
                    "missing",
                    "high",
                    "1小时",
                    result.test_case_id,
                    scope="top_level",
                )

        return list(seen.values())
