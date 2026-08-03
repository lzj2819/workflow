"""架构文档修改建议生成器"""

from pydantic import BaseModel, ConfigDict, Field

from mock_framework.models.validator import FailureAnalysis, WarningAnalysis


class ModificationSuggestion(BaseModel):
    """修改建议"""

    dimension: str = Field(..., description="失败维度")
    location: str = Field(..., description="修改位置")
    change_type: str = Field(default="补充", description="补充 / 修正 / 调整")
    description: str = Field(default="", description="修改描述")
    example: str = Field(default="", description="修改示例")
    affected_test_cases: list[str] = Field(default_factory=list, description="影响用例")

    model_config = ConfigDict(frozen=True)


class ArchDocModifier:
    """架构文档修改建议生成器"""

    # dimension -> (location, change_type, description_template, example_template)
    _DIMENSION_MAP: dict[str, tuple[str, str, str, str]] = {
        "state": (
            "状态机章节（Mermaid stateDiagram）",
            "补充",
            "补充状态和转换条件",
            "添加 `Active --> Locked : fail_count >= 5`",
        ),
        "structure": (
            "OpenAPI 定义（YAML 代码块）",
            "修正",
            "修正参数类型/格式/约束",
            "`username: {type: string, minLength: 3}`",
        ),
        "flow": (
            "Sequence 图（Mermaid sequenceDiagram）",
            "补充",
            "补充缺失的处理步骤",
            "添加 `Login Service->>Audit Logger: log event`",
        ),
        "contract": (
            "架构设计章节",
            "补充",
            "补充并发控制设计",
            "添加分布式锁或乐观锁设计",
        ),
        "performance": (
            "NFR 设计章节（Markdown 表格）",
            "调整",
            "调整架构策略",
            "添加缓存层或异步化处理",
        ),
    }

    def generate_suggestions(
        self, failure: FailureAnalysis, affected_test_cases: list[str]
    ) -> list[ModificationSuggestion]:
        """根据失败分析生成修改建议"""
        dimension = failure.dimension
        mapping = self._DIMENSION_MAP.get(dimension)

        if not mapping:
            return [
                ModificationSuggestion(
                    dimension=dimension,
                    location="架构文档",
                    change_type="审查",
                    description=failure.problem,
                    example=failure.suggestion,
                    affected_test_cases=affected_test_cases,
                )
            ]

        location, change_type, description, example = mapping
        return [
            ModificationSuggestion(
                dimension=dimension,
                location=location,
                change_type=change_type,
                description=f"{description}: {failure.problem}",
                example=example,
                affected_test_cases=affected_test_cases,
            )
        ]

    def generate_suggestions_from_warning(
        self, warning: WarningAnalysis, affected_test_cases: list[str]
    ) -> list[ModificationSuggestion]:
        """根据警告分析生成修改建议"""
        dimension = warning.dimension
        mapping = self._DIMENSION_MAP.get(dimension)

        if not mapping:
            return [
                ModificationSuggestion(
                    dimension=dimension,
                    location="架构文档",
                    change_type="审查",
                    description=warning.problem,
                    example=warning.suggestion,
                    affected_test_cases=affected_test_cases,
                )
            ]

        location, change_type, description, example = mapping
        return [
            ModificationSuggestion(
                dimension=dimension,
                location=location,
                change_type="调整",
                description=f"{description}: {warning.problem}",
                example=example,
                affected_test_cases=affected_test_cases,
            )
        ]
