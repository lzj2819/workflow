"""Loader 输出模型"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TechnicalMapping(BaseModel):
    """技术映射信息"""

    step_index: int = Field(..., description="步骤索引")
    text: str = Field(..., description="步骤文本")
    mapping_type: str = Field(..., description="映射类型")
    target: dict = Field(default_factory=dict, description="映射目标")
    assertion: Optional[dict] = Field(default=None, description="验证断言")
    confidence: str = Field(default="medium", description="置信度: high/medium/low")

    model_config = ConfigDict(frozen=True)


class Expectations(BaseModel):
    """测试期望"""

    status_code: Optional[int] = Field(default=None, description="期望状态码")
    response_schema: Optional[str] = Field(default=None, description="响应Schema")
    touched_components: list[str] = Field(default_factory=list, description="涉及组件")
    side_effects: list[dict] = Field(default_factory=list, description="副作用")
    performance: Optional[dict] = Field(default=None, description="性能指标")

    model_config = ConfigDict(frozen=True)


class TestCase(BaseModel):
    """结构化测试用例"""

    test_case_id: str = Field(..., description="测试用例ID")
    source_feature: str = Field(..., description="来源Feature文件")
    source_scenario: str = Field(..., description="来源Scenario ID")
    tags: list[str] = Field(default_factory=list, description="标签")
    gherkin: dict = Field(default_factory=dict, description="原始Gherkin")
    technical_mapping: dict = Field(default_factory=dict, description="技术映射")
    expectations: Expectations = Field(default_factory=lambda: Expectations(), description="期望")

    model_config = ConfigDict(frozen=True)
