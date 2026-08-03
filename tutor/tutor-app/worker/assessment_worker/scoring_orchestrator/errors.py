"""L03 编排器本地诊断错误（不改变父契约错误语义）。

父层面错误保持继承语义：无效评估结果为 ``INVALID_RESPONSE_SCHEMA``，事务失败为
``TRANSACTION_FAILED``；``STALE_TERMINAL_CALLBACK`` / ``DUPLICATE_TERMINAL_CALLBACK``
仅为本地诊断分支（L2 04 §5）。
"""
from __future__ import annotations

STALE_TERMINAL_CALLBACK = "STALE_TERMINAL_CALLBACK"
DUPLICATE_TERMINAL_CALLBACK = "DUPLICATE_TERMINAL_CALLBACK"


class OrchestratorError(Exception):
    """L03 编排器错误基类。"""


class TerminalCallbackRejected(OrchestratorError):
    """过期、重复或不匹配的终态回调被拒绝；不产生任何业务状态变更。"""

    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


class InvalidAssessmentResult(OrchestratorError):
    """ICT-005 领域校验失败（映射父层 INVALID_RESPONSE_SCHEMA，INV-4）。"""


class InvalidAssessmentFailure(OrchestratorError):
    """ICT-006 失败分类不在继承的错误分类法内，拒绝录入。"""
