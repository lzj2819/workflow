from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Violation(BaseModel):
    """层间一致性违规"""
    rule: str
    detail: str
    severity: Literal["high", "medium", "low"]
    model_config = ConfigDict(frozen=True)


class ConsistencyReport(BaseModel):
    """层间一致性报告"""
    violations: list[Violation] = Field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        return len(self.violations) == 0

    @property
    def total_violations(self) -> int:
        return len(self.violations)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "high")

    model_config = ConfigDict(frozen=True)
