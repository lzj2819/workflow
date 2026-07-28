"""Gherkin 解析结果模型"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class Step(BaseModel):
    """Gherkin 步骤"""

    keyword: str = Field(..., description="步骤关键字: Given/When/Then/And/But")
    text: str = Field(..., description="步骤文本")

    model_config = ConfigDict(frozen=True)


class ExamplesTable(BaseModel):
    """Examples 表格（Scenario Outline 用）"""

    headers: list[str] = Field(..., description="表头")
    rows: list[list[str]] = Field(default_factory=list, description="数据行")

    model_config = ConfigDict(frozen=True)


class Scenario(BaseModel):
    """Gherkin 场景"""

    id: str = Field(..., description="场景唯一标识")
    name: str = Field(..., description="场景名称")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    steps: list[Step] = Field(default_factory=list, description="步骤列表")
    examples: Optional[ExamplesTable] = Field(None, description="参数化数据")

    model_config = ConfigDict(frozen=True)


class Feature(BaseModel):
    """Gherkin Feature"""

    name: str = Field(..., description="特性名称")
    description: Optional[str] = Field(None, description="特性描述")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    background: Optional[Scenario] = Field(None, description="Background 共享前置步骤")
    scenarios: list[Scenario] = Field(default_factory=list, description="场景列表")

    model_config = ConfigDict(frozen=True)
