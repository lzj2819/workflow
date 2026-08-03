"""T-B03a ACCESS-GATE 单元测试（SQLite 内存库）。

覆盖任务验收面：
- 运维预置幂等：重复预置收敛同一 teacher_id、授权只增不删、重预置后新口令可登录；
- 登录成功/失败：错误口令、未知账号、禁用账号均 AuthInvalidError（不区分原因）；
- 会话：不透明令牌只存 sha256 哈希（明文不入库）、12h 滑动续期、过期失效；
- 三种 authorize 形状：L14 operator 形 / L15 AuthorizedQueryContext 形 /
  L16 AuthContext 形（含 401/403 映射）；
- 403 审计追加：AccessDeniedLogged 记录教师/课程/动作/来源，不含口令/令牌明文；
- CLI provision：幂等、口令经环境变量传入、缺口令报错；
- 迁移 0012 可导入、revision/down_revision 正确、upgrade/downgrade 可执行。
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core.models import (  # noqa: E402
    Base as CoreBase,
    Submission,
)
from course_app.teacher_web.access_gate import (  # noqa: E402
    AccessDeniedLog,
    AccessGateService,
    Base as GateBase,
    PresentationAccessGate,
    ReviewCommandAccessGate,
    ReviewQueryAccessGate,
    TeacherAccount,
    TeacherAccessGrant,
    TeacherSession,
)
from course_app.teacher_web.access_gate.cli import main as cli_main  # noqa: E402
from course_app.teacher_web.access_gate.errors import (  # noqa: E402
    AccessDeniedError,
    AuthInvalidError,
)
from course_app.teacher_web.presentation import errors as pr_errors  # noqa: E402
from course_app.teacher_web.review_command import errors as rc_errors  # noqa: E402
from course_app.teacher_web.review_query import errors as rq_errors  # noqa: E402

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)
ACCOUNT = "teacher@example.com"
PASSWORD = "s3cret-口令"
COURSE = "CS101"
OTHER_COURSE = "CS102"


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    CoreBase.metadata.create_all(eng)
    GateBase.metadata.create_all(eng)
    return eng


class GateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        self.addCleanup(self.eng.dispose)
        self.now = NOW
        self.service = AccessGateService(
            session_factory=partial(session_scope, self.eng),
            now_fn=lambda: self.now,
        )

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)

    def provision(self, password: str = PASSWORD, course_ids=(COURSE,)) -> str:
        return self.service.provision_teacher(
            account=ACCOUNT, password=password, course_ids=course_ids
        )

    def login(self, password: str = PASSWORD) -> str:
        self.provision()
        return self.service.login(account=ACCOUNT, password=password)

    def add_submission(self, submission_id: str, course_id: str | None) -> None:
        with session_scope(self.eng) as session:
            session.add(
                Submission(
                    submission_id=submission_id,
                    submission_uuid=f"uuid-{submission_id}",
                    course_id=course_id,
                    status="scored",
                    version=0,
                    received_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )

    def denied_rows(self) -> list[tuple]:
        with session_scope(self.eng) as session:
            return [
                (r.teacher_id, r.course_id, r.action, r.source)
                for r in session.scalars(sa.select(AccessDeniedLog)).all()
            ]


class TestProvision(GateTestCase):
    def test_provision_is_idempotent(self):
        first = self.provision()
        second = self.provision()
        self.assertEqual(first, second)
        with session_scope(self.eng) as session:
            accounts = session.scalars(sa.select(TeacherAccount)).all()
            self.assertEqual(len(accounts), 1)
            grants = session.scalars(
                sa.select(TeacherAccessGrant.course_id)
            ).all()
            self.assertEqual(grants, [COURSE])

    def test_reprovision_adds_grants_without_removing(self):
        self.provision(course_ids=(COURSE,))
        self.service.provision_teacher(
            account=ACCOUNT, password=PASSWORD, course_ids=(OTHER_COURSE,)
        )
        with session_scope(self.eng) as session:
            grants = set(
                session.scalars(sa.select(TeacherAccessGrant.course_id)).all()
            )
            self.assertEqual(grants, {COURSE, OTHER_COURSE})

    def test_reprovision_updates_password(self):
        self.provision(password="old-password")
        self.provision(password="new-password")
        with self.assertRaises(AuthInvalidError):
            self.service.login(account=ACCOUNT, password="old-password")
        token = self.service.login(account=ACCOUNT, password="new-password")
        self.assertTrue(token)

    def test_password_stored_only_as_hash(self):
        self.provision()
        with session_scope(self.eng) as session:
            row = session.scalar(sa.select(TeacherAccount))
            self.assertNotIn(PASSWORD, row.password_hash)
            self.assertNotIn(PASSWORD, row.password_salt)
            self.assertEqual(
                row.password_hash,
                hashlib.pbkdf2_hmac(
                    "sha256",
                    PASSWORD.encode("utf-8"),
                    bytes.fromhex(row.password_salt),
                    row.password_iterations,
                ).hex(),
            )


class TestLoginAndSession(GateTestCase):
    def test_login_success_and_verify(self):
        token = self.login()
        identity = self.service.verify_session(token)
        self.assertEqual(identity.teacher_id, f"teacher-{hashlib.sha256(ACCOUNT.encode()).hexdigest()[:12]}")
        self.assertEqual(identity.course_ids, (COURSE,))

    def test_login_wrong_password_rejected(self):
        self.provision()
        with self.assertRaises(AuthInvalidError):
            self.service.login(account=ACCOUNT, password="wrong")
        with self.assertRaises(AuthInvalidError):
            self.service.login(account="nobody@example.com", password=PASSWORD)

    def test_login_disabled_account_rejected(self):
        teacher_id = self.provision()
        with session_scope(self.eng) as session:
            session.get(TeacherAccount, teacher_id).status = "disabled"
        with self.assertRaises(AuthInvalidError):
            self.service.login(account=ACCOUNT, password=PASSWORD)

    def test_token_plaintext_never_stored(self):
        token = self.login()
        with session_scope(self.eng) as session:
            rows = session.scalars(sa.select(TeacherSession)).all()
            self.assertEqual(len(rows), 1)
            self.assertNotEqual(rows[0].token_hash, token)
            self.assertEqual(
                rows[0].token_hash, hashlib.sha256(token.encode("utf-8")).hexdigest()
            )

    def test_verify_rejects_missing_or_unknown_token(self):
        for bad in (None, "", "   ", "not-a-token"):
            with self.assertRaises(AuthInvalidError):
                self.service.verify_session(bad)

    def test_session_sliding_renewal(self):
        token = self.login()
        self.advance(hours=11)
        identity = self.service.verify_session(token)  # 续期至 23h
        self.assertTrue(identity.teacher_id)
        self.advance(hours=11)  # 累计 22h，距上次活动 11h < 12h
        self.assertTrue(self.service.verify_session(token).teacher_id)

    def test_session_expires_without_activity(self):
        token = self.login()
        self.advance(hours=12, seconds=1)
        with self.assertRaises(AuthInvalidError):
            self.service.verify_session(token)

    def test_sliding_renewal_persisted(self):
        token = self.login()
        self.advance(hours=6)
        self.service.verify_session(token)
        with session_scope(self.eng) as session:
            row = session.scalar(sa.select(TeacherSession))
            expected = (self.now + timedelta(hours=12)).replace(tzinfo=None)
            self.assertEqual(row.expires_at, expected)


class TestAuthorizeAndAudit(GateTestCase):
    def test_require_grant_allowed(self):
        token = self.login()
        identity = self.service.verify_session(token)
        self.service.require_grant(
            identity, course_id=COURSE, action="authorize.query", source="test"
        )
        self.assertEqual(self.denied_rows(), [])

    def test_require_grant_denied_appends_audit(self):
        token = self.login()
        identity = self.service.verify_session(token)
        with self.assertRaises(AccessDeniedError):
            self.service.require_grant(
                identity,
                course_id=OTHER_COURSE,
                action="authorize.query",
                source="test",
            )
        rows = self.denied_rows()
        self.assertEqual(len(rows), 1)
        teacher_id, course_id, action, source = rows[0]
        self.assertEqual(teacher_id, identity.teacher_id)
        self.assertEqual(course_id, OTHER_COURSE)
        self.assertEqual(action, "authorize.query")
        self.assertEqual(source, "test")

    def test_audit_is_append_only(self):
        token = self.login()
        identity = self.service.verify_session(token)
        for _ in range(2):
            with self.assertRaises(AccessDeniedError):
                self.service.require_grant(
                    identity, course_id=OTHER_COURSE, action="a", source="s"
                )
        self.assertEqual(len(self.denied_rows()), 2)

    def test_audit_contains_no_plaintext_secrets(self):
        token = self.login()
        identity = self.service.verify_session(token)
        with self.assertRaises(AccessDeniedError):
            self.service.require_grant(
                identity, course_id=OTHER_COURSE, action="a", source="s"
            )
        row = self.denied_rows()[0]
        for value in row:
            self.assertNotIn(PASSWORD, str(value))
            self.assertNotIn(token, str(value))


class TestReviewCommandAdapter(GateTestCase):
    def setUp(self):
        super().setUp()
        self.gate = ReviewCommandAccessGate(
            service=self.service,
            session_factory=partial(session_scope, self.eng),
        )

    def test_authorize_granted_returns_operator(self):
        token = self.login()
        self.add_submission("sub-1", COURSE)
        grant = self.gate.authorize(teacher_session=token, submission_id="sub-1")
        self.assertTrue(grant.operator.startswith("teacher-"))

    def test_authorize_denied_raises_forbidden_and_audits(self):
        token = self.login()
        self.add_submission("sub-2", OTHER_COURSE)
        with self.assertRaises(rc_errors.ForbiddenError) as ctx:
            self.gate.authorize(teacher_session=token, submission_id="sub-2")
        self.assertEqual(ctx.exception.http_status, 403)
        rows = self.denied_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], OTHER_COURSE)
        self.assertEqual(rows[0][3], "L14-review-command")

    def test_authorize_invalid_session_raises_auth_invalid(self):
        self.add_submission("sub-3", COURSE)
        for bad in (None, "bad-token"):
            with self.assertRaises(rc_errors.AuthInvalidError) as ctx:
                self.gate.authorize(teacher_session=bad, submission_id="sub-3")
            self.assertEqual(ctx.exception.http_status, 401)

    def test_authorize_unknown_submission_passes_auth_only(self):
        token = self.login()
        grant = self.gate.authorize(teacher_session=token, submission_id="missing")
        self.assertTrue(grant.operator)
        self.assertEqual(self.denied_rows(), [])


class TestReviewQueryAdapter(GateTestCase):
    def setUp(self):
        super().setUp()
        self.gate = ReviewQueryAccessGate(service=self.service)

    def test_authorize_granted_course(self):
        token = self.login()
        ctx = self.gate.authorize(teacher_session=token, course_id=COURSE)
        self.assertEqual(ctx.course_id, COURSE)
        self.assertTrue(ctx.teacher_id)

    def test_authorize_course_list_requires_auth_only(self):
        token = self.login()
        ctx = self.gate.authorize(teacher_session=token, course_id=None)
        self.assertIsNone(ctx.course_id)
        with self.assertRaises(rq_errors.AuthInvalidError):
            self.gate.authorize(teacher_session="bad", course_id=None)

    def test_authorize_denied_raises_access_denied_and_audits(self):
        token = self.login()
        with self.assertRaises(rq_errors.AccessDeniedError) as ctx:
            self.gate.authorize(teacher_session=token, course_id=OTHER_COURSE)
        self.assertEqual(ctx.exception.code, "FORBIDDEN")
        self.assertEqual(ctx.exception.http_status, 403)
        rows = self.denied_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][3], "L15-review-query")

    def test_authorize_invalid_session(self):
        with self.assertRaises(rq_errors.AuthInvalidError) as ctx:
            self.gate.authorize(teacher_session="bad", course_id=COURSE)
        self.assertEqual(ctx.exception.http_status, 401)


class TestPresentationAdapter(GateTestCase):
    def setUp(self):
        super().setUp()
        self.gate = PresentationAccessGate(service=self.service)

    def test_authorize_returns_auth_context(self):
        token = self.login()
        auth = self.gate.authorize(authorization=f"Bearer {token}")
        self.assertEqual(auth.course_ids, (COURSE,))
        self.assertTrue(auth.teacher_id)

    def test_authorize_missing_or_malformed_header(self):
        for bad in (None, "", "Basic abc", "Bearer"):
            with self.assertRaises(pr_errors.AuthInvalidError) as ctx:
                self.gate.authorize(authorization=bad)
            self.assertEqual(ctx.exception.http_status, 401)

    def test_authorize_invalid_token(self):
        with self.assertRaises(pr_errors.AuthInvalidError):
            self.gate.authorize(authorization="Bearer not-a-token")


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "cli.db"
        self.db_url = f"sqlite:///{self.db_path}"
        eng = sa.create_engine(self.db_url)
        GateBase.metadata.create_all(eng)
        eng.dispose()

    def _run(self, *args: str) -> int:
        return cli_main(["provision", "--database-url", self.db_url, *args])

    def test_provision_idempotent_via_cli(self):
        for _ in range(2):
            rc = self._run(
                "--account", ACCOUNT,
                "--password", PASSWORD,
                "--course-id", COURSE,
            )
            self.assertEqual(rc, 0)
        eng = sa.create_engine(self.db_url)
        with session_scope(eng) as session:
            self.assertEqual(len(session.scalars(sa.select(TeacherAccount)).all()), 1)
            self.assertEqual(
                session.scalars(sa.select(TeacherAccessGrant.course_id)).all(),
                [COURSE],
            )
        eng.dispose()

    def test_password_from_environment(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"ACCESS_GATE_PROVISION_PASSWORD": PASSWORD}):
            rc = self._run("--account", ACCOUNT, "--course-id", COURSE)
        self.assertEqual(rc, 0)

    def test_missing_password_is_usage_error(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                self._run("--account", ACCOUNT)
            self.assertEqual(ctx.exception.code, 2)


class TestMigration(unittest.TestCase):
    def _load_module(self):
        path = ROOT / "server" / "migrations" / "versions" / "0012_access_gate.py"
        spec = importlib.util.spec_from_file_location("mig_0012_access_gate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_identifiers(self):
        module = self._load_module()
        self.assertEqual(module.revision, "0012_access_gate")
        self.assertEqual(module.down_revision, "11a22f91f4b3")

    def test_upgrade_downgrade_on_sqlite(self):
        module = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            eng = sa.create_engine(f"sqlite:///{Path(tmp) / 'mig.db'}")
            with eng.connect() as conn:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    module.upgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    self.assertIn("teacher_accounts", tables)
                    self.assertIn("teacher_sessions", tables)
                    self.assertIn("teacher_access_grants", tables)
                    self.assertIn("access_denied_log", tables)
                    module.downgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    for gone in (
                        "teacher_accounts",
                        "teacher_sessions",
                        "teacher_access_grants",
                        "access_denied_log",
                    ):
                        self.assertNotIn(gone, tables)
            eng.dispose()


if __name__ == "__main__":
    unittest.main()
