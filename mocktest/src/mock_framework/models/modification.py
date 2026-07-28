from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class Modification(BaseModel):
    """单个修改指令"""
    location: str
    type: Literal["add", "modify", "delete", "restructure"]
    reason: str
    severity: Literal["high", "medium", "low"]
    original_content: Optional[str] = None
    new_content: str
    dimension: Optional[str] = None
    related_test_cases: list[str] = Field(default_factory=list)
    model_config = ConfigDict(frozen=True)


class ModificationPlan(BaseModel):
    """修改计划"""
    modifications: list[Modification]
    summary: str
    risks: list[str] = Field(default_factory=list)
    full_document: str
    model_config = ConfigDict(frozen=True)
