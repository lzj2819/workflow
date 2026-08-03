"""L09 SI-API 错误码与 HTTP 映射（L0 04-interface-contracts.md 错误码汇总）。

只映射父 CT-001/CT-002/auth-token 的冻结错误码；内部 IC 错误（ROSTER_UNAVAILABLE、
IC-SI-01 会话错误等）不得泄漏为新公共码：
- REJECTED_MEMBERSHIP 是业务终态（CT-001 应答 status=rejected），不是 HTTP 错误；
- 名单暂不可用 → 503 暂态失败（LCD-001，不暴露内部细节，客户端按幂等键重发）；
- 预算耗尽/非预期内部失败 → 500 暂态失败（不伪造 received，真实状态经 CT-002 可查）。
"""
from __future__ import annotations

AUTH_INVALID = "AUTH_INVALID"
VALIDATION_FAILED = "VALIDATION_FAILED"
NOT_FOUND = "NOT_FOUND"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
REJECTED_MEMBERSHIP = "REJECTED_MEMBERSHIP"  # 业务终态应答，无 HTTP 映射

#: 冻结错误码 → HTTP 状态映射表（contracts/ct-001.json、ct-002.json、auth-token.json）。
ERROR_HTTP_STATUS = {
    AUTH_INVALID: 401,
    VALIDATION_FAILED: 400,
    NOT_FOUND: 404,
    PAYLOAD_TOO_LARGE: 413,
    UNSUPPORTED_MEDIA_TYPE: 415,
}


class SiApiError(Exception):
    """SI-API 公共错误基类；`code` 为父契约冻结错误码。"""

    code = "SI_API_ERROR"
    http_status = 500

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class AuthInvalidError(SiApiError):
    """AUTH_INVALID：Bearer 令牌缺失/无效/过期，或 auth-token 凭据不匹配（KD-005）。"""

    code = AUTH_INVALID
    http_status = 401


class ValidationFailedError(SiApiError):
    """VALIDATION_FAILED：请求字段校验失败（缺必填项、格式错误）。"""

    code = VALIDATION_FAILED
    http_status = 400


class NotFoundApiError(SiApiError):
    """NOT_FOUND：未知 submission_uuid（CT-002）。"""

    code = NOT_FOUND
    http_status = 404


class PayloadTooLargeError(SiApiError):
    """PAYLOAD_TOO_LARGE：超过单次提交 500MB 上限（KD-004；IC-SI-01 SIZE_LIMIT_EXCEEDED）。"""

    code = PAYLOAD_TOO_LARGE
    http_status = 413


class UnsupportedMediaTypeError(SiApiError):
    """UNSUPPORTED_MEDIA_TYPE：文件类型不在白名单（KD-004；IC-SI-01 TYPE_NOT_ALLOWED）。"""

    code = UNSUPPORTED_MEDIA_TYPE
    http_status = 415


class MembershipUnavailableError(SiApiError):
    """名单核对暂不可用（IC-SI-03 ROSTER_UNAVAILABLE，有限快速重试后仍失败）。

    映射为 503 暂态失败（LCD-001）：不创建提交记录、不暴露内部细节；
    客户端按 CT-001 既有约定以同一 submission_uuid 重发或经 CT-002 查询。
    """

    code = "ROSTER_UNAVAILABLE_TRANSIENT"  # 内部标识，不出现在应答体
    http_status = 503


class IntakeBudgetExhaustedError(SiApiError):
    """30 秒同步预算耗尽或非预期编排失败（NFR-003）；不伪造 received。"""

    code = "INTAKE_BUDGET_EXHAUSTED"  # 内部标识，不出现在应答体
    http_status = 500
