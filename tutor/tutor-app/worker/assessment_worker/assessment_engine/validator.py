"""CMP-AE-RESPONSE-VALIDATOR：模型应答的 CT-010 response schema 与领域校验。

规则（contracts/ct-010.json response + L2 局部不变量）：
- grade ∈ A–E；
- dimension_rationales 恰好 5 条，五维度各出现一次，rationale 非空；
- suggestions 为非空字符串列表（教师专用，经 ICT-005 teacher_suggestions 承载）；
- 不接受额外顶层字段（schema additionalProperties: false）。
校验失败抛 ResponseValidationError，由协调器映射 INVALID_RESPONSE_SCHEMA；
校验失败绝不产出等级或部分评分结果（L2 不变量 3）。
"""
from __future__ import annotations

from ..model_provider import DIMENSIONS, GRADES

from .errors import ResponseValidationError

_ALLOWED_TOP_LEVEL_KEYS = {"grade", "dimension_rationales", "suggestions"}


def validate_model_response(response: object) -> dict:
    """校验模型应答；通过则原样返回 dict，否则抛 ResponseValidationError。"""
    problems: list[str] = []
    if not isinstance(response, dict):
        raise ResponseValidationError("response must be an object")
    extra = set(response) - _ALLOWED_TOP_LEVEL_KEYS
    if extra:
        problems.append(f"unexpected response keys: {sorted(extra)}")

    grade = response.get("grade")
    if grade not in GRADES:
        problems.append(f"grade must be one of {GRADES}")

    rationales = response.get("dimension_rationales")
    if not isinstance(rationales, list) or len(rationales) != len(DIMENSIONS):
        problems.append("dimension_rationales must contain exactly five entries")
    else:
        seen: list[str] = []
        for entry in rationales:
            if (
                not isinstance(entry, dict)
                or set(entry) - {"dimension", "rationale"}
                or entry.get("dimension") not in DIMENSIONS
                or not isinstance(entry.get("rationale"), str)
                or not entry.get("rationale")
            ):
                problems.append(
                    "each rationale requires a valid dimension and non-empty rationale"
                )
                break
            seen.append(entry["dimension"])
        else:
            if sorted(seen) != sorted(DIMENSIONS):
                problems.append(
                    "dimension_rationales must cover each of the five dimensions once"
                )

    suggestions = response.get("suggestions")
    if not isinstance(suggestions, list) or any(
        not isinstance(item, str) or not item for item in suggestions
    ):
        problems.append("suggestions must be a list of non-empty strings")

    if problems:
        raise ResponseValidationError("; ".join(problems))
    return response
