"""L16 CMP-PRESENTATION 错误码与 HTTP 映射（contracts/ct-009.json error_codes）。

只映射父 CT-009 冻结错误码：AUTH_INVALID / FORBIDDEN / VALIDATION_FAILED /
NO_AVAILABLE_SUBMISSION。内部读模型/写失败不新增公共码：映射为 500 暂态失败，
不携带 code 字段、不暴露内部细节（同 L09 约定）。
"""
from __future__ import annotations

AUTH_INVALID = "AUTH_INVALID"
FORBIDDEN = "FORBIDDEN"
VALIDATION_FAILED = "VALIDATION_FAILED"
NO_AVAILABLE_SUBMISSION = "NO_AVAILABLE_SUBMISSION"

#: 冻结错误码 → HTTP 状态映射表（contracts/ct-009.json）。
ERROR_HTTP_STATUS = {
    AUTH_INVALID: 401,
    FORBIDDEN: 403,
    VALIDATION_FAILED: 400,
    NO_AVAILABLE_SUBMISSION: 409,
}


class PresentationError(Exception):
    """CMP-PRESENTATION 公共错误基类；`code` 为父契约冻结错误码。"""

    code = "PRESENTATION_ERROR"
    http_status = 500

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class AuthInvalidError(PresentationError):
    """AUTH_INVALID：教师会话缺失/无效（由 ACCESS-GATE 端口抛出）。"""

    code = AUTH_INVALID
    http_status = 401


class ForbiddenError(PresentationError):
    """FORBIDDEN：教师对所选小组所属课程无授权范围（ACCESS-GATE 语义）。"""

    code = FORBIDDEN
    http_status = 403


class ValidationFailedError(PresentationError):
    """VALIDATION_FAILED：请求字段校验失败（缺 group_ids、空数组、多余字段）。"""

    code = VALIDATION_FAILED
    http_status = 400


class NoAvailableSubmissionError(PresentationError):
    """NO_AVAILABLE_SUBMISSION：任一选定小组无可用提交，整体拒绝、不写快照。"""

    code = NO_AVAILABLE_SUBMISSION
    http_status = 409


class ReadModelUnavailableError(PresentationError):
    """M05-IC-02 读模型暂态失败：500 暂态，不降级为缺字段成功应答。"""

    code = "READ_MODEL_TRANSIENT"  # 内部标识，不出现在应答体
    http_status = 500
