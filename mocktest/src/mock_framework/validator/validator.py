"""Validator main class."""

from typing import Optional

from mock_framework.config import ValidatorConfig, load_config
from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc
from mock_framework.models.loader import TestCase
from mock_framework.models.simulator import ExecutionTrace
from mock_framework.models.validator import ValidationReport, ValidationResult
from mock_framework.simulator.llm_client import LLMClient
from mock_framework.validator.agent_core import ValidatorAgentCore
from mock_framework.validator.report_assembler import ReportAssembler


class Validator:
    """Main validator class that orchestrates validation."""

    def __init__(self, llm_client: LLMClient, config_path: Optional[str] = None) -> None:
        """Initialize Validator.

        Args:
            llm_client: LLM client for making completion calls.
            config_path: Optional path to configuration file.
        """
        config: ValidatorConfig = load_config(config_path).validator
        self.logger = get_logger("validator")
        self.agent_core = ValidatorAgentCore(llm_client, token_budget=config.token_budget)
        self.report_assembler = ReportAssembler()

    def validate(
        self, trace: ExecutionTrace, test_case: TestCase, arch_doc: ArchDoc
    ) -> ValidationResult:
        """Validate a single execution trace.

        Args:
            trace: Execution trace from the simulator.
            test_case: Test case with expectations.
            arch_doc: Architecture document with NFRs and constraints.

        Returns:
            A ValidationResult.
        """
        self.logger.info("开始验证: %s", trace.test_case_id)
        agent_output = self.agent_core.validate(trace, test_case, arch_doc)
        result = self.report_assembler.assemble_result(
            test_case_id=trace.test_case_id,
            scenario_name=test_case.source_scenario,
            agent_output=agent_output,
        )
        self.logger.info("验证完成: %s", result.result)
        return result

    def validate_batch(
        self,
        traces: list[ExecutionTrace],
        test_cases: list[TestCase],
        arch_doc: ArchDoc,
    ) -> ValidationReport:
        """Validate a batch of execution traces.

        Args:
            traces: List of execution traces.
            test_cases: List of test cases (same order as traces).
            arch_doc: Architecture document with NFRs and constraints.

        Returns:
            A ValidationReport with summary and recommendations.
        """
        self.logger.info("开始批量验证: %d 个场景", len(traces))
        results: list[ValidationResult] = []
        for trace, test_case in zip(traces, test_cases):
            result = self.validate(trace, test_case, arch_doc)
            results.append(result)

        report_id = f"VAL-{traces[0].test_case_id}" if traces else "VAL-UNKNOWN"
        report = self.report_assembler.build_report(
            report_id=report_id,
            architecture_doc="",
            gherkin_source="",
            results=results,
        )
        self.logger.info(
            "批量验证完成: 通过 %d/%d",
            report.summary["passed"],
            report.summary["total_test_cases"],
        )
        return report
