"""改进决策引擎"""

from pydantic import BaseModel, ConfigDict, Field

from mock_framework.models.validator import ValidationReport


class ImprovementDecision(BaseModel):
    """改进决策"""

    action: str = Field(..., description="PASS / FIX_ARCH / REVIEW / SUPPLEMENT")
    reason: str = Field(default="", description="决策原因")
    priority: str = Field(default="low", description="high / medium / low")
    affected_dimensions: list[str] = Field(default_factory=list, description="影响维度")
    next_step: str = Field(default="", description="下一步动作")

    model_config = ConfigDict(frozen=True)


class ImprovementEngine:
    """改进决策引擎"""

    def decide(self, report: ValidationReport) -> ImprovementDecision:
        """根据验证报告生成改进决策"""
        details = report.details

        # 收集各维度结果
        all_pass = all(d.result == "PASS" for d in details)
        any_fail = any(d.result == "FAIL" for d in details)
        any_warning = any(d.result == "WARNING" for d in details)
        any_missing = any(d.result == "MISSING" for d in details)

        # 收集影响维度
        affected_dims: set[str] = set()
        for detail in details:
            if detail.result in ("FAIL", "WARNING"):
                for dim, result in detail.five_dimensions.items():
                    if result.status in ("FAIL", "WARNING"):
                        affected_dims.add(dim)

        if all_pass:
            return ImprovementDecision(
                action="PASS",
                reason="所有 Gherkin 场景已验证，架构设计与 Gherkin 期望一致",
                priority="low",
                affected_dimensions=sorted(affected_dims),
                next_step="可进入下一层设计或编码阶段",
            )

        if any_fail:
            return ImprovementDecision(
                action="FIX_ARCH",
                reason="架构设计与 Gherkin 期望不一致",
                priority="high",
                affected_dimensions=sorted(affected_dims),
                next_step="定位失败维度，根据 failure_analysis 修改架构文档，重新执行 Mock 测试",
            )

        if any_missing:
            return ImprovementDecision(
                action="SUPPLEMENT",
                reason="架构覆盖不完整",
                priority="high",
                affected_dimensions=sorted(affected_dims),
                next_step="在架构文档中补充缺失的组件/接口/状态，重新执行 Mock 测试",
            )

        if any_warning:
            return ImprovementDecision(
                action="REVIEW",
                reason="设计存在歧义，建议人工审查",
                priority="medium",
                affected_dimensions=sorted(affected_dims),
                next_step="确认是否是设计意图，在 ADR 中记录决策，更新架构文档消除歧义",
            )

        return ImprovementDecision(
            action="PASS",
            reason="验证完成",
            priority="low",
            affected_dimensions=sorted(affected_dims),
        )
