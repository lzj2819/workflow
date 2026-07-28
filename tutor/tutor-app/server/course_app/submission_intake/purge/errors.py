"""SI-PURGE 错误类型（T-B01c）。"""
from __future__ import annotations


class PurgeValidationError(ValueError):
    """CT-012 载荷不满足冻结契约（缺字段/类型错误/版本不符/多余字段）。

    入站重试/隔离归 SI-RELAY（ST-05）；本错误表示事件本体不可执行，不进入
    逐项清除与 PurgeExecution 登记。
    """
