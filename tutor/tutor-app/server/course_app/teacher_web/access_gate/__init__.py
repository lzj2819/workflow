"""CMP-ACCESS-GATE 实现包（T-B03a / MOD-05 认证授权闸）。

教师账号（v1 运维预置，DD-004）+ 会话签发/校验（不透明令牌、12h 滑动续期）+
课程范围授权（TeacherAccessGrant，LCD-006 本地持有）+ AccessDeniedLogged 追加审计。

三种冻结端口形状的适配器在 adapters.py（L14 operator 形 / L15
AuthorizedQueryContext 形 / L16 AuthContext 形），不修改 L14/L15/L16 代码。
"""
from .adapters import (
    PresentationAccessGate,
    ReviewCommandAccessGate,
    ReviewQueryAccessGate,
)
from .errors import AccessDeniedError, AccessGateError, AuthInvalidError
from .models import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    AccessDeniedLog,
    Base,
    TeacherAccessGrant,
    TeacherAccount,
    TeacherSession,
)
from .service import (
    PBKDF2_ITERATIONS,
    SESSION_TTL,
    AccessGateService,
    TeacherIdentity,
    derive_teacher_id,
)

__all__ = [
    "PBKDF2_ITERATIONS",
    "SESSION_TTL",
    "STATUS_ACTIVE",
    "STATUS_DISABLED",
    "AccessDeniedError",
    "AccessDeniedLog",
    "AccessGateError",
    "AccessGateService",
    "AuthInvalidError",
    "Base",
    "PresentationAccessGate",
    "ReviewCommandAccessGate",
    "ReviewQueryAccessGate",
    "TeacherAccessGrant",
    "TeacherAccount",
    "TeacherIdentity",
    "TeacherSession",
    "derive_teacher_id",
]
