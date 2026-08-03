"""Examples 参数化展开器"""

import re

from mock_framework.models.gherkin import Scenario
from mock_framework.models.loader import TestCase, Expectations


class ExamplesExpander:
    """Examples 参数化展开器"""

    EXPANDED_ID_FORMAT = "TC-{feature}-{scenario:03d}-{row:03d}"

    def expand(self, scenario: Scenario, feature_name: str) -> list[TestCase]:
        """展开参数化场景

        Args:
            scenario: Scenario Outline（含 Examples）
            feature_name: 所属 Feature 名称

        Returns:
            展开的 TestCase 列表
        """
        if not scenario.examples:
            return []

        test_cases = []
        feature_prefix = self._slug(feature_name)

        for row_idx, row in enumerate(scenario.examples.rows):
            params = dict(zip(scenario.examples.headers, row))

            # 替换步骤文本中的占位符
            expanded_steps = []
            for step in scenario.steps:
                expanded_text = self._replace_placeholders(step.text, params)
                expanded_steps.append({"keyword": step.keyword, "text": expanded_text})

            tc_id = self.EXPANDED_ID_FORMAT.format(
                feature=feature_prefix,
                scenario=int(scenario.id.split("-")[-1]),
                row=row_idx + 1,
            )

            test_cases.append(
                TestCase(
                    test_case_id=tc_id,
                    source_feature=f"{feature_prefix}.feature",
                    source_scenario=scenario.id,
                    tags=scenario.tags,
                    gherkin={
                        "feature": feature_name,
                        "scenario": scenario.name,
                        "steps": expanded_steps,
                        "parameters": params,
                    },
                )
            )

        return test_cases

    def _replace_placeholders(self, text: str, params: dict) -> str:
        """替换文本中的占位符 <key> 为实际值"""
        result = text
        for key, value in params.items():
            result = result.replace(f"<{key}>", value)
        return result

    def _slug(self, text: str) -> str:
        """将中文/英文转为短标识"""
        # 简单实现：取前4个字符的大写
        cleaned = re.sub(r"[^\w]", "", text)
        return cleaned[:8].upper()
