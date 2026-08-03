"""T-B03c RETENTION-GOVERNANCE 错误类型（只映射 CT-011 父冻结错误码）。"""
from __future__ import annotations


class RetentionError(Exception):
    """保留治理错误基类。"""

    code = "INTERNAL"
    http_status = 500


class BatchNotFoundError(RetentionError):
    """NOT_FOUND：批次不存在（CT-011 父冻结错误码）。"""

    code = "NOT_FOUND"
    http_status = 404


class BatchNotExpiredError(RetentionError):
    """BATCH_NOT_EXPIRED：批次未到期，拒绝确认（CT-011 父冻结错误码）。"""

    code = "BATCH_NOT_EXPIRED"
    http_status = 409


class Ct014ValidationError(ValueError):
    """CT-014 载荷不满足冻结契约（缺字段/类型错误/版本不符/多余字段）。

    事件本体不可处理，不更新批次状态；入站重试/隔离归投递层。
    """
