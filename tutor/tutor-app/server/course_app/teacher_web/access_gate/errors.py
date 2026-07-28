"""ACCESS-GATE 内部错误类型。

服务层只抛这两种内部错误；三种冻结端口形状的适配器（adapters.py）负责翻译为
各叶子冻结错误类型（L14 AuthInvalidError/ForbiddenError、L15 AuthInvalidError/
AccessDeniedError、L16 AuthInvalidError），本包不修改 L14/L15/L16 代码。
"""
from __future__ import annotations


class AccessGateError(Exception):
    """ACCESS-GATE 内部错误基类。"""


class AuthInvalidError(AccessGateError):
    """401 语义：会话缺失/非法/过期，或登录凭据无效（不区分账号不存在与口令错误）。"""


class AccessDeniedError(AccessGateError):
    """403 语义：课程范围授权拒绝（已追加 AccessDeniedLogged 审计）。"""
