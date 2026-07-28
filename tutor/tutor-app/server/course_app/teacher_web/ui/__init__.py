"""L17 CMP-TEACHER-UI：教师网页前端（SSR，DD-003）。

- client：CT-007/008/009/011 冻结契约的注入式客户端端口（只消费，不实现端点）；
- view_models：PageViewModel 装配（缺失显式、不伪造等级）；
- views：Jinja2 SSR 路由工厂（create_router，不挂载）。
"""
from __future__ import annotations

from .client import (
    AUTH_INVALID,
    BATCH_NOT_EXPIRED,
    FORBIDDEN,
    GRADES,
    NOT_FOUND,
    NO_AVAILABLE_SUBMISSION,
    NO_ORIGINAL_GRADE,
    STATUS_SCORING_FAILED,
    VALIDATION_FAILED,
    HttpTeacherApiClient,
    TeacherApiClient,
    TeacherApiError,
    TeacherSession,
)
from .view_models import (
    MISSING_MARK,
    deletion_batches_vm,
    presentation_vm,
    submission_detail_vm,
)
from .views import SESSION_COOKIE, create_router

__all__ = [
    "AUTH_INVALID",
    "BATCH_NOT_EXPIRED",
    "FORBIDDEN",
    "GRADES",
    "MISSING_MARK",
    "NOT_FOUND",
    "NO_AVAILABLE_SUBMISSION",
    "NO_ORIGINAL_GRADE",
    "SESSION_COOKIE",
    "STATUS_SCORING_FAILED",
    "VALIDATION_FAILED",
    "HttpTeacherApiClient",
    "TeacherApiClient",
    "TeacherApiError",
    "TeacherSession",
    "create_router",
    "deletion_batches_vm",
    "presentation_vm",
    "submission_detail_vm",
]
