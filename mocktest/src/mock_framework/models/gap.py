"""Gap 检测模型"""

from pydantic import BaseModel, ConfigDict, Field


class GapLocation(BaseModel):
    """Gap 位置"""

    gherkin_file: str = Field(..., description="Gherkin文件")
    scenario: str = Field(..., description="场景")
    step: str = Field(..., description="步骤")

    model_config = ConfigDict(frozen=True)


class Gap(BaseModel):
    """Gap 记录"""

    id: str = Field(..., description="Gap ID")
    type: str = Field(..., description="类型: Missing Component/API/State/NFR/Vague")
    severity: str = Field(..., description="严重级别: ERROR/WARNING/INFO")
    location: GapLocation = Field(..., description="位置")
    description: str = Field(..., description="描述")
    suggestion: str = Field(..., description="建议")

    model_config = ConfigDict(frozen=True)


class GapReport(BaseModel):
    """Gap 报告"""

    total_gaps: int = Field(default=0, description="总数")
    gaps: list[Gap] = Field(default_factory=list, description="Gap列表")

    model_config = ConfigDict(frozen=True)
