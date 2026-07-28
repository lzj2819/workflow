"""SI-CORE 错误类型（IC-SI-04 错误语义）。

错误码沿用设计冻结值域：DUPLICATE_UUID（幂等命中，返回首次结果而非异常）、
ILLEGAL_TRANSITION、NOT_FOUND、MATERIAL_METADATA_UNAVAILABLE。
"""
from __future__ import annotations


class CoreError(Exception):
    """SI-CORE 命令错误基类；`code` 为对外稳定错误码。"""

    code = "CORE_ERROR"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class IllegalTransitionError(CoreError):
    """状态机守卫拒绝或前置条件不满足（INV-2）。"""

    code = "ILLEGAL_TRANSITION"


class NotFoundError(CoreError):
    """未知 submission_uuid / submission_id。"""

    code = "NOT_FOUND"


class MaterialMetadataUnavailableError(CoreError):
    """SI-STORE 元数据端口不可用；当前事务整体回滚，由上游按父重试策略处理。"""

    code = "MATERIAL_METADATA_UNAVAILABLE"


class ValidationError(CoreError):
    """命令字段不合法（如 outcome 值域、scoring_failed 缺 failure_reason）。"""

    code = "VALIDATION_FAILED"
