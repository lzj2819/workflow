"""CMP-REVIEW-COMMAND 错误类型（CT-008 冻结错误码，不新增、不改名）。

HTTP 映射：VALIDATION_FAILED→400、AUTH_INVALID→401、FORBIDDEN→403、
NOT_FOUND→404、NO_ORIGINAL_GRADE→409。AUTH_INVALID/FORBIDDEN 由 ACCESS-GATE
端口实现抛出（实现归 backfill），本叶子只负责映射。
"""
from __future__ import annotations


class ReviewCommandError(Exception):
    """复核写侧错误基类：携带冻结错误码与 HTTP 状态。"""

    code = "VALIDATION_FAILED"
    http_status = 400


class ValidationFailedError(ReviewCommandError):
    """annotation 与 final_grade 皆缺、字段非法或请求体无法解析。"""

    code = "VALIDATION_FAILED"
    http_status = 400


class AuthInvalidError(ReviewCommandError):
    """教师会话缺失或失效（ACCESS-GATE 抛出）。"""

    code = "AUTH_INVALID"
    http_status = 401


class ForbiddenError(ReviewCommandError):
    """课程范围授权拒绝（ACCESS-GATE 抛出；AccessDeniedLogged 由 GATE 记录）。"""

    code = "FORBIDDEN"
    http_status = 403


class NotFoundError(ReviewCommandError):
    """目标 submission 不存在。"""

    code = "NOT_FOUND"
    http_status = 404


class NoOriginalGradeError(ReviewCommandError):
    """scoring_failed 且无原始等级时拒绝设置最终等级（禁伪造，P-禁伪造等级）。"""

    code = "NO_ORIGINAL_GRADE"
    http_status = 409
