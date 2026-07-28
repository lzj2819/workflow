"""SI-STORE：材料存储真实实现（T-B01a 回填；IC-SI-02 / DD-005 / KD-004）。

公共入口：`FilesystemMaterialStore`（MaterialStorePort + MaterialMetadataReader）、
`QuotaExceededError`（稳定错误码 QUOTA_EXCEEDED）、登记模型 `MaterialFile` /
`CourseQuotaUsage`。StorageIoError 沿用 L08 `xfer.store` 冻结定义。
"""
from __future__ import annotations

from course_app.submission_intake.xfer.store import MaterialStorePort, StorageIoError

from .errors import QuotaExceededError
from .filesystem import (
    FINAL_SCHEME,
    STAGED_SCHEME,
    UNASSIGNED_COURSE,
    FilesystemMaterialStore,
    default_identity_resolver,
)
from .models import (
    STATE_DELETED,
    STATE_FINAL,
    STATE_STAGED,
    Base,
    CourseQuotaUsage,
    MaterialFile,
)

__all__ = [
    "Base",
    "CourseQuotaUsage",
    "FINAL_SCHEME",
    "FilesystemMaterialStore",
    "MaterialFile",
    "MaterialStorePort",
    "QuotaExceededError",
    "STAGED_SCHEME",
    "STATE_DELETED",
    "STATE_FINAL",
    "STATE_STAGED",
    "StorageIoError",
    "UNASSIGNED_COURSE",
    "default_identity_resolver",
]
