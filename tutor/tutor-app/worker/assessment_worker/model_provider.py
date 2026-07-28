"""CT-010 ModelProvider 端口与 fake 实现（Phase 1）。

边界（用户指令 / KD-001 / AGENTS.md）：
- 真实供应商适配为实现细节（DD-009）；真实密钥不入库；
- Phase 1 禁止接入真实外部模型、禁止发送任何学生材料；
- FakeModelProvider 仅产生语法上满足 contracts/ct-010.json 应答 schema 的
  确定性结果，供链路测试使用；不表达任何真实评估能力。
"""
from __future__ import annotations

from typing import Protocol

DIMENSIONS = ["需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性"]
GRADES = ("A", "B", "C", "D", "E")

REQUIRED_MATERIAL_KEYS = ("dialogue_summary", "code", "result_description")


class ModelProviderError(RuntimeError):
    """供应商调用失败基类（映射 CT-010 错误分类）。"""


class UnsupportedModelProviderError(ModelProviderError):
    """配置了 Phase 1 不支持的供应商（仅允许 fake）。"""


class InvalidRequestError(ModelProviderError):
    """请求不满足 CT-010 入参形状。"""


class ModelProvider(Protocol):
    def evaluate(self, request: dict) -> dict:
        """按 CT-010 执行一次评估推理；返回应答 schema 兼容的 dict。"""
        ...


def validate_request(request: dict) -> list[str]:
    problems: list[str] = []
    if not isinstance(request.get("evaluation_prompt"), str) or not request.get("evaluation_prompt"):
        problems.append("evaluation_prompt required")
    materials = request.get("materials")
    if not isinstance(materials, dict):
        problems.append("materials required")
    else:
        for key in REQUIRED_MATERIAL_KEYS:
            if key not in materials:
                problems.append(f"materials.{key} required")
    # 数据最小化（KD-001）：不得携带业务标识
    for forbidden in ("submission_id", "student_name", "group_name", "invite_code", "course_id"):
        if forbidden in request:
            problems.append(f"data minimization violation: {forbidden} must not be sent")
    return problems


class FakeModelProvider:
    """确定性 fake：无网络、无外部调用；应答满足 CT-010 schema。"""

    def evaluate(self, request: dict) -> dict:
        problems = validate_request(request)
        if problems:
            raise InvalidRequestError("; ".join(problems))
        return {
            "grade": "C",
            "dimension_rationales": [
                {"dimension": d, "rationale": f"fake rationale: {d}"} for d in DIMENSIONS
            ],
            "suggestions": ["fake suggestion: improve requirement understanding"],
        }


def build_provider(name: str) -> ModelProvider:
    """按配置名构造 provider。

    - "fake"：确定性 fake（默认；无网络）；
    - "deepseek"：真实供应商（用户 2026-07-25 批准，仅限 deepseek；
      密钥经 MODEL_API_KEY 环境变量，见 model_provider_deepseek）。
    """
    if name == "fake":
        return FakeModelProvider()
    if name == "deepseek":
        from .model_provider_deepseek import DeepSeekProvider  # noqa: PLC0415

        return DeepSeekProvider.from_env()
    raise UnsupportedModelProviderError(
        f"model provider {name!r} is not approved (allowed: 'fake', 'deepseek')"
    )
