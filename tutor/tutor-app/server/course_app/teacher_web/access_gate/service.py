"""T-B03a ACCESS-GATE 核心服务（MOD-05 / A-001 / KD-005 教师侧）。

职责：
- 运维预置（provision_teacher）：建教师 + 课程授权；幂等（同账号重复预置收敛到
  同一 teacher_id、口令哈希更新为本次参数、授权只增不删）；
- login：口令校验（PBKDF2-HMAC-SHA256，标准库 hashlib）→ 签发不透明会话令牌；
- verify_session：令牌校验 + 12h 滑动续期（DD-004），服务端只存 sha256 哈希；
- require_grant：课程范围授权检查（LCD-006 本地持有），拒绝时追加
  AccessDeniedLogged 审计（ST-ACCESS-DENIED-LOG，只追加不删除）后抛
  AccessDeniedError。

安全口径：明文口令/令牌不入库、不出现在返回值与审计记录；登录失败不区分
"账号不存在"与"口令错误"（防账号枚举）。
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, ContextManager, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import AccessDeniedError, AuthInvalidError
from .models import (
    STATUS_ACTIVE,
    AccessDeniedLog,
    Base,
    TeacherAccessGrant,
    TeacherAccount,
    TeacherSession,
)

#: DD-004：会话 12h 滑动续期。
SESSION_TTL = timedelta(hours=12)
#: PBKDF2-HMAC-SHA256 迭代次数（标准库实现，DD-004 口径）。
PBKDF2_ITERATIONS = 200_000
_PBKDF2_SALT_BYTES = 16


@dataclass(frozen=True)
class TeacherIdentity:
    """已认证教师身份与课程授权范围（请求内瞬时，不持久化）。"""

    teacher_id: str
    course_ids: tuple[str, ...]


def _hash_password(password: str, *, salt: bytes, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return digest.hex()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def derive_teacher_id(account: str) -> str:
    """由账号确定性派生 teacher_id（保证预置幂等：同账号收敛同一标识）。"""

    return "teacher-" + hashlib.sha256(account.strip().lower().encode("utf-8")).hexdigest()[:12]


class AccessGateService:
    """认证授权闸核心服务。session_factory 提供单事务会话（同 course_app.db.session_scope）。

    now_fn / token_fn 可注入（测试用固定时间与确定性令牌）。
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], ContextManager[Session]],
        now_fn: Callable[[], datetime] | None = None,
        token_fn: Callable[[], str] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._token_fn = token_fn or (lambda: secrets.token_urlsafe(32))

    # ---- 时间 ----

    def _now(self) -> datetime:
        """naive UTC（与 models 时间列口径一致）。"""
        now = self._now_fn()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        return now

    # ---- 运维预置（幂等） ----

    def provision_teacher(
        self,
        *,
        account: str,
        password: str,
        course_ids: Sequence[str] = (),
    ) -> str:
        """建教师 + 授权课程；幂等。口令只经参数传入，只存哈希。"""
        account = account.strip()
        if not account:
            raise ValueError("account must be non-empty")
        if not password:
            raise ValueError("password must be non-empty")
        now = self._now()
        teacher_id = derive_teacher_id(account)
        salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
        password_hash = _hash_password(
            password, salt=salt, iterations=PBKDF2_ITERATIONS
        )
        with self._session_factory() as session:
            row = session.get(TeacherAccount, teacher_id)
            if row is None:
                row = TeacherAccount(
                    teacher_id=teacher_id,
                    account=account,
                    password_hash=password_hash,
                    password_salt=salt.hex(),
                    password_iterations=PBKDF2_ITERATIONS,
                    status=STATUS_ACTIVE,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                # 幂等收敛：口令哈希更新为本次参数（重跑同参数结果一致）。
                row.password_hash = password_hash
                row.password_salt = salt.hex()
                row.password_iterations = PBKDF2_ITERATIONS
                row.updated_at = now
            existing = set(
                session.scalars(
                    select(TeacherAccessGrant.course_id).where(
                        TeacherAccessGrant.teacher_id == teacher_id
                    )
                ).all()
            )
            for course_id in dict.fromkeys(course_ids):
                if course_id not in existing:
                    session.add(
                        TeacherAccessGrant(
                            teacher_id=teacher_id,
                            course_id=course_id,
                            created_at=now,
                        )
                    )
        return teacher_id

    # ---- 登录 / 会话 ----

    def login(self, *, account: str, password: str) -> str:
        """口令校验 → 签发不透明会话令牌（明文只返回给调用方，不入库）。"""
        now = self._now()
        with self._session_factory() as session:
            row = session.scalar(
                select(TeacherAccount).where(TeacherAccount.account == account.strip())
            )
            if row is None or row.status != STATUS_ACTIVE:
                raise AuthInvalidError("invalid credentials")
            candidate = _hash_password(
                password,
                salt=bytes.fromhex(row.password_salt),
                iterations=row.password_iterations,
            )
            if not secrets.compare_digest(candidate, row.password_hash):
                raise AuthInvalidError("invalid credentials")
            token = self._token_fn()
            session.add(
                TeacherSession(
                    token_hash=_token_hash(token),
                    teacher_id=row.teacher_id,
                    created_at=now,
                    last_seen_at=now,
                    expires_at=now + SESSION_TTL,
                )
            )
            return token

    def verify_session(self, token: str | None) -> TeacherIdentity:
        """校验会话 → 教师身份与授权范围；非法/过期抛 AuthInvalidError。

        滑动续期（DD-004）：每次校验成功将 expires_at 顺延至 now + 12h。
        """
        if not token or not token.strip():
            raise AuthInvalidError("teacher session required")
        now = self._now()
        with self._session_factory() as session:
            row = session.get(TeacherSession, _token_hash(token.strip()))
            if row is None or row.expires_at <= now:
                raise AuthInvalidError("teacher session invalid or expired")
            account = session.get(TeacherAccount, row.teacher_id)
            if account is None or account.status != STATUS_ACTIVE:
                raise AuthInvalidError("teacher session invalid or expired")
            row.last_seen_at = now
            row.expires_at = now + SESSION_TTL
            course_ids = tuple(
                session.scalars(
                    select(TeacherAccessGrant.course_id)
                    .where(TeacherAccessGrant.teacher_id == row.teacher_id)
                    .order_by(TeacherAccessGrant.course_id)
                ).all()
            )
            return TeacherIdentity(teacher_id=row.teacher_id, course_ids=course_ids)

    # ---- 课程范围授权 ----

    def require_grant(
        self,
        identity: TeacherIdentity,
        *,
        course_id: str,
        action: str,
        source: str,
    ) -> None:
        """课程授权检查；拒绝时追加 AccessDeniedLogged 审计后抛 AccessDeniedError。"""
        if course_id in identity.course_ids:
            return
        self._log_denied(
            teacher_id=identity.teacher_id,
            course_id=course_id,
            action=action,
            source=source,
        )
        raise AccessDeniedError("course access denied")

    def _log_denied(
        self,
        *,
        teacher_id: str | None,
        course_id: str | None,
        action: str,
        source: str,
    ) -> None:
        """AccessDeniedLogged 追加式审计（独立事务，不含口令/令牌明文）。"""
        with self._session_factory() as session:
            session.add(
                AccessDeniedLog(
                    teacher_id=teacher_id,
                    course_id=course_id,
                    action=action,
                    source=source,
                    created_at=self._now(),
                )
            )


__all__ = [
    "AccessGateService",
    "Base",
    "PBKDF2_ITERATIONS",
    "SESSION_TTL",
    "TeacherIdentity",
    "derive_teacher_id",
]
