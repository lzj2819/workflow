"""Validator 输出模型"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DimensionResult(BaseModel):
    """单维度验证结果"""

    status: str = Field(..., description="状态: PASS/FAIL/WARNING")
    detail: str = Field(default="", description="详细说明")

    model_config = ConfigDict(frozen=True)


class FailureAnalysis(BaseModel):
    """失败分析"""

    dimension: str = Field(..., description="失败维度")
    problem: str = Field(..., description="问题描述")
    severity: str = Field(..., description="严重级别: high/medium/low")
    impact: str = Field(..., description="影响")
    suggestion: str = Field(..., description="建议")
    scope: Optional[str] = Field(
        default=None,
        description="建议层级: top_level(当前架构层应定义但未定义) / module(已定义但需后续细化)",
    )

    model_config = ConfigDict(frozen=True)


class WarningAnalysis(BaseModel):
    """警告分析"""

    dimension: str = Field(..., description="警告维度")
    problem: str = Field(..., description="问题描述")
    suggestion: str = Field(..., description="建议")
    scope: Optional[str] = Field(
        default=None,
        description="建议层级: top_level(当前架构层应定义但未定义) / module(已定义但需后续细化)",
    )

    model_config = ConfigDict(frozen=True)


class ValidationResult(BaseModel):
    """单测试用例验证结果"""

    test_case_id: str = Field(..., description="测试用例ID")
    scenario_name: str = Field(..., description="场景名称")
    result: str = Field(..., description="结果: PASS/FAIL/WARNING/MISSING")
    five_dimensions: dict[str, DimensionResult] = Field(
        default_factory=dict, description="五维结果"
    )
    failure_analysis: Optional[FailureAnalysis] = Field(None, description="失败分析")
    warning_analysis: Optional[WarningAnalysis] = Field(None, description="警告分析")

    model_config = ConfigDict(frozen=True)


class Recommendation(BaseModel):
    """改进建议"""

    priority: str = Field(..., description="优先级: high/medium/low")
    action: str = Field(..., description="行动")
    affected_test_cases: list[str] = Field(default_factory=list, description="影响用例")
    estimated_effort: str = Field(default="", description="预估工作量")
    scope: str = Field(
        default="module", description="建议层级: top_level(顶层架构) / module(模块内部)"
    )

    model_config = ConfigDict(frozen=True)


class ValidationReport(BaseModel):
    """验证报告"""

    report_id: str = Field(..., description="报告ID")
    architecture_doc: str = Field(..., description="架构文档")
    gherkin_source: str = Field(..., description="Gherkin源文件")
    timestamp: str = Field(..., description="时间戳")
    summary: dict = Field(default_factory=dict, description="汇总")
    details: list[ValidationResult] = Field(default_factory=list, description="详情")
    recommendations: list[Recommendation] = Field(default_factory=list, description="建议")

    model_config = ConfigDict(frozen=True)
