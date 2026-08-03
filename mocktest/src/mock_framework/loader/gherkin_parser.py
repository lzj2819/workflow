"""Gherkin 文件解析器"""

from pathlib import Path

from gherkin.parser import Parser
from gherkin.token_scanner import TokenScanner

from mock_framework.models.gherkin import Feature, Scenario, Step, ExamplesTable


class GherkinParser:
    """Gherkin 文件解析器"""

    def __init__(self) -> None:
        self.parser = Parser()

    def parse(self, feature_file: str) -> Feature:
        """解析 .feature 文件

        Args:
            feature_file: Gherkin 文件路径

        Returns:
            Feature 对象
        """
        content = Path(feature_file).read_text(encoding="utf-8")
        gherkin_doc = self.parser.parse(content)

        feature_data = gherkin_doc.get("feature", {})

        background = None
        scenarios = []
        scenario_counter = 1

        for child in feature_data.get("children", []):
            if "background" in child:
                background = self._convert_background(child["background"])
            elif "scenario" in child:
                scenario_data = child["scenario"]
                keyword = scenario_data.get("keyword", "")
                if "Outline" in keyword:
                    scenario = self._convert_scenario_outline(scenario_data, scenario_counter)
                else:
                    scenario = self._convert_scenario(scenario_data, scenario_counter)
                scenarios.append(scenario)
                scenario_counter += 1

        return Feature(
            name=feature_data.get("name", ""),
            description=feature_data.get("description", None),
            tags=[t["name"] for t in feature_data.get("tags", [])],
            background=background,
            scenarios=scenarios,
        )

    def _convert_background(self, gherkin_background: dict) -> Scenario:
        """将 Background 转为内部 Scenario（复用 Scenario 模型）"""
        return Scenario(
            id="BACKGROUND",
            name=gherkin_background.get("name", ""),
            tags=[],
            steps=[self._convert_step(s) for s in gherkin_background.get("steps", [])],
            examples=None,
        )

    def _convert_step(self, gherkin_step: dict) -> Step:
        """将 gherkin-official 的 step 转为内部 Step"""
        return Step(
            keyword=gherkin_step.get("keyword", "").strip(),
            text=gherkin_step.get("text", ""),
        )

    def _convert_scenario(self, gherkin_scenario: dict, counter: int) -> Scenario:
        """将普通 scenario 转为内部 Scenario"""
        return Scenario(
            id=f"SCENARIO-{counter:03d}",
            name=gherkin_scenario.get("name", ""),
            tags=[t["name"] for t in gherkin_scenario.get("tags", [])],
            steps=[self._convert_step(s) for s in gherkin_scenario.get("steps", [])],
            examples=None,
        )

    def _convert_scenario_outline(self, gherkin_outline: dict, counter: int) -> Scenario:
        """将 Scenario Outline 转为内部 Scenario（含 Examples）"""
        examples_list = gherkin_outline.get("examples", [])
        examples = None

        if examples_list:
            first_example = examples_list[0]
            table_header = first_example.get("tableHeader", {})
            table_body = first_example.get("tableBody", [])

            headers = [cell["value"] for cell in table_header.get("cells", [])]
            rows = [[cell["value"] for cell in row.get("cells", [])] for row in table_body]

            examples = ExamplesTable(headers=headers, rows=rows)

        return Scenario(
            id=f"SCENARIO-{counter:03d}",
            name=gherkin_outline.get("name", ""),
            tags=[t["name"] for t in gherkin_outline.get("tags", [])],
            steps=[self._convert_step(s) for s in gherkin_outline.get("steps", [])],
            examples=examples,
        )
