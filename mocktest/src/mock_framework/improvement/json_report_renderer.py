"""JSON 报告渲染器"""

import json

from mock_framework.models.validator import ValidationReport


class JsonReportRenderer:
    """将 ValidationReport 渲染为 JSON 字符串."""

    def render(self, report: ValidationReport) -> str:
        """将 ValidationReport 渲染为格式化的 JSON 字符串."""
        return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
