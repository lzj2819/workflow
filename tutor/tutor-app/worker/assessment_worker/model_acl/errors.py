"""MODEL-SERVICE-ACL 错误类型与三分类稳定码。

分类码与 L03 orchestrator.ERROR_TAXONOMY / L12 MODEL_ERROR_KINDS 保持一致
（只读引用其常量，不重定义字面量语义）：
- MODEL_TIMEOUT：单次调用超预算或供应商超时；
- MODEL_ERROR：出站最小化校验拒绝（不外发）或供应商调用失败；
- INVALID_RESPONSE_SCHEMA：应答未通过 CT-010 response schema 校验。
"""
from __future__ import annotations

from assessment_worker.assessment_engine.errors import (
    ERROR_INVALID_RESPONSE_SCHEMA,
    ERROR_MODEL_ERROR,
    ERROR_MODEL_TIMEOUT,
    MODEL_ERROR_KINDS,
)
from assessment_worker.model_provider import ModelProviderError

__all__ = [
    "ACL_ERROR_CODES",
    "ERROR_INVALID_RESPONSE_SCHEMA",
    "ERROR_MODEL_ERROR",
    "ERROR_MODEL_TIMEOUT",
    "AclError",
]

ACL_ERROR_CODES = MODEL_ERROR_KINDS


class AclError(ModelProviderError):
    """ACL 分类异常：携带稳定 ``code``（三分类之一）。

    同时暴露 ``error_kind`` 属性，使 L12 AssessmentEngine 的既有
    ``getattr(exc, "error_kind", None)`` 映射无需改动即可把 ACL 异常
    归入 ICT-006 对应分类。
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in ACL_ERROR_CODES:
            raise ValueError(f"unknown ACL error code: {code!r}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.error_kind = code
