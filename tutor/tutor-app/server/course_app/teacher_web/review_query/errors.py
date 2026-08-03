"""L15 CMP-REVIEW-QUERY 错误类型（消费方冻结面）。

- AUTH_INVALID / FORBIDDEN / NOT_FOUND / VALIDATION_FAILED 为 CT-007 父冻结错误码，
  仅做 HTTP 映射，不新增公共错误码。
- AUTH_INVALID / FORBIDDEN 由 CMP-ACCESS-GATE（owner，backfill 实现）在授权时抛出；
  本层只定义消费方可见的异常类型并映射 401/403。AccessDeniedLogged 的持久化
  归 ACCESS-GATE 实现，本层不写访问日志。
- RetryableQueryError：M05-IC-02 / M05-IC-06 端口读取失败时的整体可重试失败
  （LCD-RQ-004：禁止部分成功降级）；HTTP 映射为 503 且不携带新公共 code。
"""
from __future__ import annotations


class RqError(Exception):
    """L15 查询装配错误基类。"""

    code = "INTERNAL"
    http_status = 500


class AuthInvalidError(RqError):
    """AUTH_INVALID：缺失/非法教师会话（GATE 终止，CT-007 父错误码）。"""

    code = "AUTH_INVALID"
    http_status = 401


class AccessDeniedError(RqError):
    """FORBIDDEN：课程范围授权拒绝（GATE 终止并记录 AccessDeniedLogged）。"""

    code = "FORBIDDEN"
    http_status = 403


class NotFoundError(RqError):
    """NOT_FOUND：已授权选择范围在读模型中无对应课程/小组/学生/提交。"""

    code = "NOT_FOUND"
    http_status = 404


class ValidationFailedError(RqError):
    """VALIDATION_FAILED：选择条件结构不合法或违反 CT-007 输入约束。"""

    code = "VALIDATION_FAILED"
    http_status = 400


class ReadModelUnavailableError(RqError):
    """M05-IC-02 端口读取失败（PROJECTOR owner 的端口实现抛出）。"""


class RetentionViewUnavailableError(RqError):
    """M05-IC-06 端口读取失败（RETENTION-GOVERNANCE owner 的端口实现抛出）。"""


class RetryableQueryError(RqError):
    """整体可重试失败：任一必需端口失败，禁止 partial success。"""

    http_status = 503
