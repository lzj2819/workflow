"""L01 错误类型与拒绝原因编码。

P5：拒绝原因至少区分「邀请码无效」与「姓名/小组未命中名单」两类；
具体编码枚举 delegated 至本层（05-local-decisions §3），取值如下。
"""
from __future__ import annotations

# CT-003 reason 取值（verified=false 时返回，P5）
REASON_INVALID_INVITE_CODE = "INVALID_INVITE_CODE"
REASON_ROSTER_ENTRY_NOT_FOUND = "ROSTER_ENTRY_NOT_FOUND"

# CT-003 唯一错误码（契约冻结值）；不向调用方暴露内部细节
ERROR_ROSTER_UNAVAILABLE = "ROSTER_UNAVAILABLE"


class CourseRosterError(Exception):
    """MOD-03 内部错误基类。"""


class RosterStoreError(CourseRosterError):
    """CP-ROSTER-QUERY 存储故障（04 §3.2 ROSTER_STORE_ERROR）；由 VERIFIER 映射为 ROSTER_UNAVAILABLE。"""


class RosterUnavailableError(CourseRosterError):
    """CT-003 ROSTER_UNAVAILABLE：名单不可用，调用方按契约语义重试。"""


class CourseNotFoundError(CourseRosterError):
    """CT-013 NOT_FOUND：课程不存在（前置条件「课程已创建」未满足）。"""


class ProvisioningConflictError(CourseRosterError):
    """运维预置冲突：违反 P1 邀请码唯一映射课程。"""
