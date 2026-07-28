"""SI-API-AUTH：不透明令牌签发与认证（DD-004）+ ST-06 签发审计。

- 令牌为 `secrets.token_urlsafe` 生成的不透明串；服务端只存 sha256 哈希，
  明文绝不入库、绝不入日志；
- TTL 30 天（DD-004）；过期令牌不再通过认证；
- 每次签发（含凭据不匹配的被拒签发）写一条 ST-06 AuthTokenGrant 审计，
  姓名/邀请码以 sha256 指纹最小化留存；
- 审计写入失败则不应答令牌（与结论同一事务语义，类比 L01 P4）。
"""
from __future__ import annotations

import hashlib
import secrets
import uuid as uuidlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, ContextManager

from sqlalchemy.orm import Session

from .errors import AuthInvalidError
from .models import RESULT_GRANTED, RESULT_REJECTED, AuthTokenGrant
from .ports import MembershipResult

#: DD-004：不透明令牌，TTL 30 天（秒）。
TOKEN_TTL_SECONDS = 30 * 24 * 3600


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite 读回为 naive，一律按 UTC 解释。"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hash_token(token: str) -> str:
    """令牌 sha256 哈希（入库/比对唯一形态）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def subject_fingerprint(invite_code: str, student_name: str, group_name: str) -> str:
    """主体指纹：sha256(invite_code|student_name|group_name)，隐私最小化。"""
    raw = f"{invite_code}|{student_name}|{group_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedToken:
    """auth-token 应答要素（contracts/auth-token.json response）。"""

    access_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class AuthContext:
    """认证通过后的请求主体（LC-SIAPI-001 principal）。"""

    grant_id: str
    course_id: str | None
    subject_fingerprint: str


class TokenService:
    """SI-API-AUTH 令牌服务：签发（ST-06 审计）与 Bearer 认证。"""

    def __init__(
        self,
        session_factory: Callable[[], ContextManager[Session]],
        ttl_seconds: int = TOKEN_TTL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds

    def issue(
        self,
        *,
        membership: MembershipResult,
        invite_code: str,
        student_name: str,
        group_name: str,
        request_id: str | None = None,
    ) -> IssuedToken:
        """签发不透明令牌并写 ST-06 审计；凭据不匹配 → AuthInvalidError（同样留审计）。

        同一凭据重复换领返回新的有效令牌（每次签发独立审计，contracts/auth-token
        幂等条款：重复换领返回有效令牌）。
        """
        fingerprint = subject_fingerprint(invite_code, student_name, group_name)
        now = _utcnow()
        if not membership.verified:
            with self._session_factory() as session:
                session.add(
                    AuthTokenGrant(
                        grant_id=f"grt-{uuidlib.uuid4().hex}",
                        token_hash=None,
                        subject_fingerprint=fingerprint,
                        course_id=membership.course_id,
                        result=RESULT_REJECTED,
                        reason=membership.reason,
                        request_id=request_id,
                        issued_at=None,
                        expires_at=None,
                        created_at=now,
                    )
                )
            raise AuthInvalidError("credentials do not match course roster")
        token = secrets.token_urlsafe(32)
        with self._session_factory() as session:
            session.add(
                AuthTokenGrant(
                    grant_id=f"grt-{uuidlib.uuid4().hex}",
                    token_hash=hash_token(token),
                    subject_fingerprint=fingerprint,
                    course_id=membership.course_id,
                    result=RESULT_GRANTED,
                    reason=None,
                    request_id=request_id,
                    issued_at=now,
                    expires_at=now + timedelta(seconds=self._ttl_seconds),
                    created_at=now,
                )
            )
        return IssuedToken(
            access_token=token, token_type="Bearer", expires_in=self._ttl_seconds
        )

    def authenticate(self, token: str) -> AuthContext:
        """Bearer 认证：哈希命中 granted 记录且未过期；否则 AuthInvalidError。"""
        if not token:
            raise AuthInvalidError("missing bearer token")
        with self._session_factory() as session:
            grant = (
                session.query(AuthTokenGrant)
                .filter(
                    AuthTokenGrant.token_hash == hash_token(token),
                    AuthTokenGrant.result == RESULT_GRANTED,
                )
                .one_or_none()
            )
            if grant is None:
                raise AuthInvalidError("invalid bearer token")
            if grant.expires_at is None or _as_utc(grant.expires_at) <= _utcnow():
                raise AuthInvalidError("expired bearer token")
            return AuthContext(
                grant_id=grant.grant_id,
                course_id=grant.course_id,
                subject_fingerprint=grant.subject_fingerprint,
            )
