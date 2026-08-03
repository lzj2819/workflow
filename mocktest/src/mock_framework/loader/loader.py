"""Loader 主类"""

from typing import Any, Optional

from mock_framework.config import LoaderConfig
from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc
from mock_framework.models.gap import GapReport
from mock_framework.models.gherkin import Feature, Scenario, Step
from mock_framework.models.loader import Expectations, TestCase

from .arch_doc_parser import ArchDocParser
from .examples_expander import ExamplesExpander
from .gap_detector import GapDetector
from .gherkin_parser import GherkinParser
from .step_mapper import StepMapper


class LoaderResult:
    """Loader 输出结果"""

    def __init__(
        self,
        test_cases: list[TestCase],
        feature: Feature,
        arch_doc: ArchDoc,
        gap_report: GapReport,
    ):
        self.test_cases = test_cases
        self.feature = feature
        self.arch_doc = arch_doc
        self.gap_report = gap_report


class Loader:
    """Gherkin Loader 主类"""

    def __init__(self, config: LoaderConfig):
        self.config = config
        self.logger = get_logger("loader")
        self.gherkin_parser = GherkinParser()
        self.arch_doc_parser = ArchDocParser()
        self.examples_expander = ExamplesExpander()
        self.gap_detector = GapDetector(loader_config=config)

    def load(self, feature_file: str, arch_file: str) -> LoaderResult:
        """加载并处理 Gherkin 场景

        Args:
            feature_file: Gherkin 文件路径
            arch_file: 架构文档路径

        Returns:
            LoaderResult 包含 TestCase[]、Feature、ArchDoc、GapReport
        """
        self.logger.info(f"加载 Gherkin: {feature_file}")
        self.logger.info(f"加载架构文档: {arch_file}")

        # 1. 解析 Gherkin
        feature = self.gherkin_parser.parse(feature_file)
        self.logger.info(f"解析到 {len(feature.scenarios)} 个场景")

        # 2. 解析架构文档
        arch_doc = self.arch_doc_parser.parse(arch_file)
        self.logger.info(f"解析到 {len(arch_doc.components)} 个组件")

        # 3. 创建映射引擎
        step_mapper = StepMapper(arch_doc)

        # 4. 处理每个 Scenario
        test_cases = []
        for scenario in feature.scenarios:
            if scenario.examples:
                # Scenario Outline: 展开 Examples
                expanded = self.examples_expander.expand(scenario, feature.name)
                tcs = []
                for row in expanded:
                    expanded_scenario = Scenario(
                        id=row.test_case_id,
                        name=row.gherkin["scenario"],
                        tags=row.tags,
                        steps=[Step(**step) for step in row.gherkin["steps"]],
                        examples=None,
                    )
                    tcs.append(
                        self._create_test_case(
                            expanded_scenario,
                            feature.name,
                            step_mapper,
                            arch_doc,
                            feature.background,
                            source_scenario=scenario.id,
                            parameters=row.gherkin.get("parameters"),
                        )
                    )
                test_cases.extend(tcs)
                self.logger.info(f"展开 {scenario.name}: {len(tcs)} 个 TestCase")
            else:
                # 普通 Scenario: 直接映射（合并 Background 步骤）
                tc = self._create_test_case(
                    scenario, feature.name, step_mapper, arch_doc, feature.background
                )
                test_cases.append(tc)

        self.logger.info(f"总共生成 {len(test_cases)} 个 TestCase")

        # 5. Gap 检测
        gap_report = self.gap_detector.detect(test_cases, arch_doc)
        if gap_report.total_gaps > 0:
            self.logger.warning(f"检测到 {gap_report.total_gaps} 个 Gap")
            for gap in gap_report.gaps:
                self.logger.warning(f"  {gap.id}: {gap.type} - {gap.description}")

        return LoaderResult(
            test_cases=test_cases,
            feature=feature,
            arch_doc=arch_doc,
            gap_report=gap_report,
        )

    def _create_test_case(
        self,
        scenario: Scenario,
        feature_name: str,
        step_mapper: StepMapper,
        arch_doc: ArchDoc,
        background: Optional[Scenario] = None,
        source_scenario: Optional[str] = None,
        parameters: Optional[dict[str, str]] = None,
    ) -> TestCase:
        """创建单个 TestCase（自动合并 Background 步骤）"""
        given_mappings = []
        when_mappings = []
        then_mappings = []
        current_phase = "given"

        # 合并 Background 步骤到当前 Scenario
        all_steps: list[Step] = []
        if background:
            all_steps.extend(background.steps)
        all_steps.extend(scenario.steps)

        for idx, step in enumerate(all_steps):
            keyword = step.keyword.strip().lower()
            if keyword == "given":
                current_phase = "given"
            elif keyword == "when":
                current_phase = "when"
            elif keyword == "then":
                current_phase = "then"
            # And/But 不改变 current_phase，但需要在 map_step 中按当前 phase 映射

            step_mappings = step_mapper.map_step(step, idx, current_phase)
            if current_phase == "given":
                given_mappings.extend(step_mappings)
            elif current_phase == "when":
                when_mappings.extend(step_mappings)
            elif current_phase == "then":
                then_mappings.extend(step_mappings)

        expectations = self._build_expectations(then_mappings, arch_doc)

        gherkin: dict[str, Any] = {
            "feature": feature_name,
            "scenario": scenario.name,
            "steps": [{"keyword": s.keyword, "text": s.text} for s in scenario.steps],
        }
        if parameters is not None:
            gherkin["parameters"] = parameters

        return TestCase(
            test_case_id=scenario.id,
            source_feature=f"{feature_name}.feature",
            source_scenario=source_scenario or scenario.id,
            tags=scenario.tags,
            gherkin=gherkin,
            technical_mapping={
                "given_steps": given_mappings,
                "when_steps": when_mappings,
                "then_steps": then_mappings,
            },
            expectations=expectations,
        )

    def _build_expectations(self, then_mappings: list, arch_doc: ArchDoc) -> Expectations:
        """从 Then 映射构建 Expectations"""
        status_code = None
        response_schema = None
        touched_components: set[str] = set()
        side_effects: list[dict] = []
        performance = None

        for m in then_mappings:
            target = m.target
            if m.mapping_type == "response_validation":
                if "response_code" in target:
                    status_code = target["response_code"]
                if "response_schema" in target:
                    response_schema = target["response_schema"]
                if "component" in target:
                    touched_components.add(target["component"])

            elif m.mapping_type == "expected_side_effect":
                side_effects.append(
                    {
                        "type": target.get("operation", "write"),
                        "target": target.get("component", "unknown"),
                        "description": target.get("description", ""),
                    }
                )
                if "component" in target:
                    touched_components.add(target["component"])

            elif m.mapping_type == "performance_check":
                if "threshold_ms" in target:
                    performance = {"max_total_latency_ms": target["threshold_ms"]}

            elif m.mapping_type == "expected_call":
                if "component" in target:
                    touched_components.add(target["component"])

            elif m.mapping_type in ("interface_call", "interface_validation"):
                if "interface" in target:
                    touched_components.add(target["interface"])

            elif m.mapping_type == "state_validation":
                if "component" in target:
                    touched_components.add(target["component"])

        return Expectations(
            status_code=status_code,
            response_schema=response_schema,
            touched_components=list(touched_components),
            side_effects=side_effects,
            performance=performance,
        )
