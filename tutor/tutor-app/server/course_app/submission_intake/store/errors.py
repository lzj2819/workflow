"""SI-STORE 错误类型（T-B01a）。

StorageIoError 沿用 L08 `xfer.store` 的冻结定义（不在本包重复定义）；
QuotaExceededError 为配额拒绝的专用类型，稳定错误码 QUOTA_EXCEEDED，
HTTP/事件映射归后续映射层（本任务不接线）。
"""
from __future__ import annotations


class QuotaExceededError(Exception):
    """课程存储配额超限（KD-004 200GB）；promote 前检查，拒绝不产生任何写入。"""

    code = "QUOTA_EXCEEDED"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)
