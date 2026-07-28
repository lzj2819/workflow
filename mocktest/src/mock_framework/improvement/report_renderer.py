"""Markdown 报告渲染器"""

from mock_framework.models.validator import ValidationReport


class ReportRenderer:
    """Markdown 报告渲染器"""

    def _dimension_summary(self, report: ValidationReport) -> dict[str, dict[str, int]]:
        """统计每个维度的 PASS/FAIL/WARNING/MISSING 数量."""
        summary: dict[str, dict[str, int]] = {}
        for detail in report.details:
            for dim_name, dim_result in detail.five_dimensions.items():
                bucket = summary.setdefault(
                    dim_name, {"PASS": 0, "FAIL": 0, "WARNING": 0, "MISSING": 0}
                )
                bucket[dim_result.status] = bucket[dim_result.status] + 1
        return summary

    @staticmethod
    def _pass_rate(value: object) -> float:
        """Accept the numeric contract and legacy percentage-string fixtures."""
        if isinstance(value, str):
            text = value.strip()
            try:
                return float(text[:-1]) / 100 if text.endswith("%") else float(text)
            except ValueError:
                return 0.0
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    def render(self, report: ValidationReport) -> str:
        """将 ValidationReport 渲染为 Markdown"""
        lines: list[str] = []

        # 标题
        lines.append("# 验证报告")
        lines.append("")

        # 元信息
        lines.append(f"**报告 ID**: {report.report_id}")
        lines.append(f"**架构文档**: {report.architecture_doc}")
        lines.append(f"**Gherkin 源**: {report.gherkin_source}")
        lines.append(f"**时间**: {report.timestamp}")
        lines.append("")

        # 汇总
        lines.append("## 汇总")
        lines.append("")
        summary = report.summary
        lines.append(f"- 总场景数: {summary.get('total_test_cases', 0)}")
        lines.append(f"- 通过: {summary.get('passed', 0)}")
        lines.append(f"- 失败: {summary.get('failed', 0)}")
        lines.append(f"- 警告: {summary.get('warnings', 0)}")
        lines.append(f"- 缺失: {summary.get('missing', 0)}")
        lines.append(f"- 通过率: {self._pass_rate(summary.get('pass_rate', 0.0)):.2%}")
        lines.append("")

        # 维度汇总
        dim_summary = self._dimension_summary(report)
        if dim_summary:
            lines.append("## 维度汇总")
            lines.append("")
            for dim_name, counts in dim_summary.items():
                lines.append(
                    f"- **{dim_name}**: PASS={counts.get('PASS', 0)}, "
                    f"FAIL={counts.get('FAIL', 0)}, WARNING={counts.get('WARNING', 0)}, "
                    f"MISSING={counts.get('MISSING', 0)}"
                )
            lines.append("")

        # 详情
        lines.append("## 详情")
        lines.append("")
        for detail in report.details:
            status_icon = "PASS" if detail.result == "PASS" else detail.result
            lines.append(f"### {detail.test_case_id} - {detail.scenario_name} [{status_icon}]")
            lines.append("")
            for dim_name, dim_result in detail.five_dimensions.items():
                lines.append(f"- **{dim_name}**: {dim_result.status} - {dim_result.detail}")
            lines.append("")

            if detail.failure_analysis:
                fa = detail.failure_analysis
                lines.append(f"**失败分析**: {fa.problem}")
                lines.append(f"- 严重程度: {fa.severity}")
                lines.append(f"- 影响: {fa.impact}")
                lines.append(f"- 建议: {fa.suggestion}")
                lines.append("")

            if detail.warning_analysis:
                wa = detail.warning_analysis
                lines.append(f"**警告分析**: {wa.problem}")
                lines.append(f"- 建议: {wa.suggestion}")
                lines.append("")

        # 失败分类（按维度汇总所有 FAIL/WARNING 场景）
        failures_by_dimension: dict[str, set[str]] = {}
        warnings_by_dimension: dict[str, set[str]] = {}
        for detail in report.details:
            for dim_name, dim_result in detail.five_dimensions.items():
                if dim_result.status == "FAIL":
                    failures_by_dimension.setdefault(dim_name, set()).add(detail.test_case_id)
                elif dim_result.status == "WARNING":
                    warnings_by_dimension.setdefault(dim_name, set()).add(detail.test_case_id)

        if failures_by_dimension or warnings_by_dimension:
            lines.append("## 问题分类")
            lines.append("")
            for dim, ids in failures_by_dimension.items():
                lines.append(f"- **{dim}** (FAIL): {', '.join(sorted(ids))}")
            for dim, ids in warnings_by_dimension.items():
                lines.append(f"- **{dim}** (WARNING): {', '.join(sorted(ids))}")
            lines.append("")

        # 建议：分顶层架构问题与模块内部问题
        if report.recommendations:
            top_level = [
                r for r in report.recommendations if getattr(r, "scope", "module") == "top_level"
            ]
            module_level = [
                r for r in report.recommendations if getattr(r, "scope", "module") == "module"
            ]

            if top_level:
                lines.append("## 改进建议（最顶层架构设计问题）")
                lines.append("")
                for rec in top_level:
                    lines.append(f"- **{rec.priority}**: {rec.action}")
                    lines.append(f"  - 影响用例: {', '.join(rec.affected_test_cases)}")
                    lines.append(f"  - 预估工作量: {rec.estimated_effort}")
                    lines.append("")

            if module_level:
                lines.append("## 留待模块设计阶段验证的建议")
                lines.append("")
                for rec in module_level:
                    lines.append(f"- **{rec.priority}**: {rec.action}")
                    lines.append(f"  - 影响用例: {', '.join(rec.affected_test_cases)}")
                    lines.append(f"  - 预估工作量: {rec.estimated_effort}")
                    lines.append("")

        return "\n".join(lines)
