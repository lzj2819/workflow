"""Pipeline - orchestrates Loader, Simulator, and Validator with BICR retry."""

from datetime import datetime, timezone
from typing import Any, Optional

from mock_framework.logger import get_logger
from mock_framework.models.arch import ArchDoc
from mock_framework.models.loader import TestCase
from mock_framework.models.simulator import ExecutionTrace
from mock_framework.models.validator import (
    DimensionResult,
    ValidationReport,
    ValidationResult,
)


class Pipeline:
    """Orchestrates the mock test execution pipeline with retry logic."""

    def __init__(
        self,
        loader: Any,
        simulator: Any,
        validator: Any,
        retry_count: int = 3,
    ) -> None:
        """Initialize Pipeline.

        Args:
            loader: Loader instance for loading test cases.
            simulator: Simulator instance for simulating execution.
            validator: Validator instance for validating traces.
            retry_count: Number of retry attempts for simulate/validate.
        """
        self.loader = loader
        self.simulator = simulator
        self.validator = validator
        self.retry_count = retry_count
        self.logger = get_logger("pipeline")

    def run(self, feature_path: str, arch_doc_path: str) -> ValidationReport:
        """Run the full pipeline.

        Args:
            feature_path: Path to the Gherkin feature file.
            arch_doc_path: Path to the architecture document.

        Returns:
            A ValidationReport.
        """
        self.logger.info("Pipeline started: %s", feature_path)

        try:
            loader_result = self.loader.load(feature_path, arch_doc_path)
        except Exception as exc:
            self.logger.error("Loader failed: %s", exc)
            return self._create_empty_report(feature_path, arch_doc_path)

        test_cases = loader_result.test_cases
        arch_doc = loader_result.arch_doc
        results: list[ValidationResult] = []

        for test_case in test_cases:
            result = self._process_single(test_case, arch_doc)
            results.append(result)

        report_id = f"VAL-{test_cases[0].test_case_id}" if test_cases else "VAL-UNKNOWN"

        report: ValidationReport = self.validator.report_assembler.build_report(  # type: ignore[no-any-return]
            report_id=report_id,
            architecture_doc=arch_doc_path,
            gherkin_source=feature_path,
            results=results,
        )

        self.logger.info(
            "Pipeline completed: %d/%d passed",
            report.summary.get("passed", 0),
            report.summary.get("total_test_cases", 0),
        )

        # 同步生成改进决策和修改建议
        from mock_framework.improvement import ImprovementEngine, ArchDocModifier, ReportRenderer

        engine = ImprovementEngine()
        decision = engine.decide(report)
        self.logger.info("改进决策: %s (priority=%s)", decision.action, decision.priority)

        # 为 FAIL 和 WARNING 结果生成架构修改建议
        modifier = ArchDocModifier()
        for detail in report.details:
            if detail.result == "FAIL" and detail.failure_analysis:
                suggestions = modifier.generate_suggestions(
                    detail.failure_analysis, [detail.test_case_id]
                )
                for suggestion in suggestions:
                    self.logger.info(
                        "修改建议 [FAIL][%s]: %s - %s",
                        suggestion.dimension,
                        suggestion.location,
                        suggestion.description,
                    )
            elif detail.result == "WARNING" and detail.warning_analysis:
                suggestions = modifier.generate_suggestions_from_warning(
                    detail.warning_analysis, [detail.test_case_id]
                )
                for suggestion in suggestions:
                    self.logger.info(
                        "修改建议 [WARNING][%s]: %s - %s",
                        suggestion.dimension,
                        suggestion.location,
                        suggestion.description,
                    )

        # 渲染 Markdown 报告
        renderer = ReportRenderer()
        markdown = renderer.render(report)
        self.logger.debug("Markdown 报告长度: %d 字符", len(markdown))

        return report

    def _process_single(self, test_case: TestCase, arch_doc: ArchDoc) -> ValidationResult:
        """Process a single test case (with Challenge mechanism).

        Args:
            test_case: The test case to process.
            arch_doc: Parsed architecture document.

        Returns:
            A ValidationResult.
        """
        trace = self._simulate_with_retry(test_case, arch_doc)
        if trace is None:
            return self._create_error_result(test_case, "Simulator failed after all retries")

        result = self._validate_with_retry(trace, test_case, arch_doc)

        # Challenge: if high severity FAIL, re-simulate and re-validate
        if (
            result.result == "FAIL"
            and result.failure_analysis
            and result.failure_analysis.severity == "high"
        ):
            self.logger.info("Challenge triggered: %s", test_case.test_case_id)
            new_trace = self._simulate_with_retry(test_case, arch_doc)
            if new_trace:
                new_result = self._validate_with_retry(new_trace, test_case, arch_doc)
                result = new_result

        return result

    def _simulate_with_retry(
        self, test_case: TestCase, arch_doc: ArchDoc
    ) -> Optional[ExecutionTrace]:
        """Simulate with retry logic.

        Args:
            test_case: The test case to simulate.
            arch_doc: Parsed architecture document.

        Returns:
            An ExecutionTrace or None if all retries exhausted.
        """
        for attempt in range(1, self.retry_count + 1):
            self.logger.info(
                "Simulating %s (attempt %d/%d)",
                test_case.test_case_id,
                attempt,
                self.retry_count,
            )
            try:
                trace: ExecutionTrace = self.simulator.simulate(test_case, arch_doc)  # type: ignore[no-any-return]
                return trace
            except Exception as exc:
                self.logger.warning(
                    "Simulate attempt %d failed for %s: %s",
                    attempt,
                    test_case.test_case_id,
                    exc,
                )

        self.logger.error(
            "Simulator exhausted all retries for %s",
            test_case.test_case_id,
        )
        return None

    def _validate_with_retry(
        self, trace: ExecutionTrace, test_case: TestCase, arch_doc: ArchDoc
    ) -> ValidationResult:
        """Validate with retry logic.

        Args:
            trace: The execution trace to validate.
            test_case: The test case with expectations.
            arch_doc: Parsed architecture document.

        Returns:
            A ValidationResult.
        """
        for attempt in range(1, self.retry_count + 1):
            self.logger.info(
                "Validating %s (attempt %d/%d)",
                test_case.test_case_id,
                attempt,
                self.retry_count,
            )
            try:
                result: ValidationResult = self.validator.validate(trace, test_case, arch_doc)  # type: ignore[no-any-return]
                return result
            except Exception as exc:
                self.logger.warning(
                    "Validate attempt %d failed for %s: %s",
                    attempt,
                    test_case.test_case_id,
                    exc,
                )

        self.logger.error(
            "Validator exhausted all retries for %s",
            test_case.test_case_id,
        )
        return self._create_error_result(test_case, "Validator failed after all retries")

    def _create_error_result(self, test_case: TestCase, message: str) -> ValidationResult:
        """Create an ERROR ValidationResult.

        Args:
            test_case: The test case that failed.
            message: Error message.

        Returns:
            A ValidationResult with result="ERROR".
        """
        return ValidationResult(
            test_case_id=test_case.test_case_id,
            scenario_name=test_case.gherkin.get("scenario", test_case.source_scenario),
            result="ERROR",
            five_dimensions={
                dim: DimensionResult(status="ERROR", detail=message)
                for dim in (
                    "structure",
                    "flow",
                    "state",
                    "contract",
                    "performance",
                )
            },
            failure_analysis=None,
            warning_analysis=None,
        )

    def _create_empty_report(self, feature_path: str, arch_doc_path: str) -> ValidationReport:
        """Create an empty ValidationReport.

        Args:
            feature_path: Path to the Gherkin feature file.
            arch_doc_path: Path to the architecture document.

        Returns:
            A ValidationReport with zero test cases.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ValidationReport(
            report_id="VAL-UNKNOWN",
            architecture_doc=arch_doc_path,
            gherkin_source=feature_path,
            timestamp=timestamp,
            summary={
                "total_test_cases": 0,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
                "missing": 0,
                "pass_rate": 0.0,
            },
            details=[],
            recommendations=[],
        )
