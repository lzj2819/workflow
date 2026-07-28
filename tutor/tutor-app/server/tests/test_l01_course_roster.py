"""L01 MOD-03 course-roster 语义测试（verification-checklist.md 全量覆盖）。

SQLite 单测库（sqlite:///:memory:，用户批准口径）。覆盖：
- CT-003 命中/拒绝（区分邀请码无效/名单未命中）、每次直读无缓存、逐条校验记录、
  名单不可用 → ROSTER_UNAVAILABLE 且不泄露内部细节；
- CT-013 去重/逐项格式错误报告/conflicts[]/部分成功可见/重复导入幂等；
- router 应答必填字段与 contracts/ct-003.json、ct-013.json 一致；
- CP-COURSE-ENDTIME 只读端口；运维预置 CLI（可运行、幂等）；迁移可导入。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from course_app.course_roster import admin, verifier  # noqa: E402
from course_app.course_roster.api import create_router  # noqa: E402
from course_app.course_roster.cli import main as cli_main  # noqa: E402
from course_app.course_roster.errors import (  # noqa: E402
    ERROR_ROSTER_UNAVAILABLE,
    REASON_INVALID_INVITE_CODE,
    REASON_ROSTER_ENTRY_NOT_FOUND,
    CourseNotFoundError,
    ProvisioningConflictError,
    RosterStoreError,
    RosterUnavailableError,
)
from course_app.course_roster.models import (  # noqa: E402
    Base,
    Course,
    InviteCode,
    RosterEntry,
    VerificationRecord,
)
from course_app.db import session_scope  # noqa: E402

CONTRACTS_DIR = ROOT / "contracts"
END_TIME = datetime(2026, 9, 1, tzinfo=timezone.utc)
ROSTER = [
    {"student_name": "张三", "group_name": "G1"},
    {"student_name": "李四", "group_name": "G2"},
]


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class RosterTestCase(unittest.TestCase):
    def setUp(self):
        # StaticPool + check_same_thread=False：单内存连接跨线程共享（TestClient 在独立线程运行）
        self.engine = sa.create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=sa.pool.StaticPool,
        )
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def scope(self):
        return session_scope(self.engine)

    def provision(self, course_id="C101", invite="INV-1", entries=ROSTER):
        with self.scope() as s:
            admin.provision_course(
                s,
                course_id=course_id,
                invite_code=invite,
                course_end_time=END_TIME,
                name="计算机导论",
            )
            if entries:
                admin.import_roster(s, course_id=course_id, entries=entries)

    def verify(self, invite="INV-1", name="张三", group="G1"):
        with self.scope() as s:
            return verifier.verify_membership(
                s, invite_code=invite, student_name=name, group_name=group
            )

    def verification_rows(self):
        with self.scope() as s:
            return s.execute(
                sa.select(
                    VerificationRecord.verification_id,
                    VerificationRecord.invite_code,
                    VerificationRecord.student_name,
                    VerificationRecord.group_name,
                    VerificationRecord.verified,
                    VerificationRecord.reason,
                    VerificationRecord.course_id,
                    VerificationRecord.verified_at,
                )
            ).all()


class TestVerifyMembership(RosterTestCase):
    """CT-003：命中 / 拒绝原因区分 / 无缓存直读 / 逐条记录 / 不可用语义。"""

    def test_hit_returns_verified_and_course_id(self):
        self.provision()
        outcome = self.verify()
        self.assertTrue(outcome.verified)
        self.assertEqual(outcome.course_id, "C101")
        self.assertIsNone(outcome.reason)

    def test_invalid_invite_code_reason(self):
        self.provision()
        outcome = self.verify(invite="NOPE")
        self.assertFalse(outcome.verified)
        self.assertEqual(outcome.reason, REASON_INVALID_INVITE_CODE)

    def test_roster_miss_reason(self):
        self.provision()
        by_name = self.verify(name="王五")
        by_group = self.verify(group="G9")
        for outcome in (by_name, by_group):
            self.assertFalse(outcome.verified)
            self.assertEqual(outcome.reason, REASON_ROSTER_ENTRY_NOT_FOUND)
            self.assertEqual(outcome.course_id, "C101")  # 课程已解析，仅名单未命中
        # P5：两类拒绝原因可区分
        self.assertNotEqual(REASON_INVALID_INVITE_CODE, REASON_ROSTER_ENTRY_NOT_FOUND)

    def test_rereads_current_roster_no_cache(self):
        self.provision(entries=[])
        self.assertFalse(self.verify(name="张三").verified)  # 名单未命中
        with self.scope() as s:  # 名单变更提交后
            admin.import_roster(s, course_id="C101", entries=[{"student_name": "张三", "group_name": "G1"}])
        outcome = self.verify(name="张三")  # 下一次调用即生效（LCD-002 无缓存）
        self.assertTrue(outcome.verified)
        self.assertEqual(outcome.course_id, "C101")

    def test_each_call_writes_independent_record(self):
        self.provision()
        self.verify()
        self.verify(name="王五")
        self.verify()  # 与第一次要素完全相同，仍产生独立记录（P4，不去重）
        rows = self.verification_rows()
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({r.verification_id for r in rows}), 3)
        first, second, third = rows
        self.assertEqual(
            (first.invite_code, first.student_name, first.group_name), ("INV-1", "张三", "G1")
        )
        self.assertTrue(first.verified)
        self.assertIsNone(first.reason)
        self.assertEqual(first.course_id, "C101")
        self.assertIsNotNone(first.verified_at)
        self.assertFalse(second.verified)
        self.assertEqual(second.reason, REASON_ROSTER_ENTRY_NOT_FOUND)
        self.assertTrue(third.verified)

    def test_record_model_has_no_submission_id(self):
        # LCD-003：校验记录不携带 submission_id（CT-003 契约无该字段）
        self.assertNotIn("submission_id", VerificationRecord.__table__.columns.keys())
        self.assertEqual(
            set(VerificationRecord.__table__.columns.keys()),
            {
                "verification_id",
                "invite_code",
                "student_name",
                "group_name",
                "verified",
                "reason",
                "course_id",
                "verified_at",
            },
        )

    def test_roster_unavailable_no_record_no_internals(self):
        self.provision()
        with mock.patch.object(admin, "query_roster", side_effect=RosterStoreError("boom-detail")):
            with self.scope() as s:
                with self.assertRaises(RosterUnavailableError) as ctx:
                    verifier.verify_membership(
                        s, invite_code="INV-1", student_name="张三", group_name="G1"
                    )
        # 不向调用方暴露内部细节
        self.assertNotIn("boom-detail", str(ctx.exception))
        # 不可用调用不产生通过/拒绝校验记录（R2）
        self.assertEqual(self.verification_rows(), [])


class TestImportRoster(RosterTestCase):
    """CT-013：去重 / 逐项格式错误报告 / conflicts[] / 部分成功可见 / 幂等。"""

    ENTRIES = [
        {"student_name": "张三", "group_name": "G1"},
        {"student_name": "张三", "group_name": "G1"},  # 文件内重复 → skipped
        {"student_name": "", "group_name": "G2"},  # 格式错误 → conflicts
        {"student_name": "李四", "group_name": "G2"},
    ]

    def _roster_count(self):
        with self.scope() as s:
            return s.scalar(sa.select(sa.func.count()).select_from(RosterEntry))

    def test_import_dedup_conflicts_partial_success(self):
        self.provision(entries=[])
        with self.scope() as s:
            result = admin.import_roster(s, course_id="C101", entries=self.ENTRIES)
        self.assertEqual(result.imported_count, 2)  # 部分成功可见
        self.assertEqual(len(result.skipped_duplicates), 1)
        self.assertEqual(result.skipped_duplicates[0]["student_name"], "张三")
        self.assertEqual(result.skipped_duplicates[0]["reason"], "DUPLICATE")
        self.assertEqual(len(result.conflicts), 1)  # 逐项报告
        self.assertEqual(result.conflicts[0]["index"], 2)
        self.assertEqual(result.conflicts[0]["error"], "FORMAT_ERROR")
        self.assertIn("student_name", result.conflicts[0]["message"])
        self.assertEqual(self._roster_count(), 2)

    def test_reimport_is_idempotent(self):
        self.provision(entries=[])
        with self.scope() as s:
            admin.import_roster(s, course_id="C101", entries=self.ENTRIES)
        with self.scope() as s:  # 同一文件重复导入
            again = admin.import_roster(s, course_id="C101", entries=self.ENTRIES)
        self.assertEqual(again.imported_count, 0)
        self.assertEqual(len(again.skipped_duplicates), 3)  # 全部按 (姓名+小组) 去重
        self.assertEqual(len(again.conflicts), 1)
        self.assertEqual(self._roster_count(), 2)  # 不产生重复条目

    def test_import_unknown_course_raises_not_found(self):
        with self.scope() as s:
            with self.assertRaises(CourseNotFoundError):
                admin.import_roster(s, course_id="GHOST", entries=self.ENTRIES)


class TestCourseEndTimePort(RosterTestCase):
    """CP-COURSE-ENDTIME（FLOW-011 实现形态，只读）。"""

    def test_returns_course_end_time_and_none_for_unknown(self):
        self.provision(entries=[])
        with self.scope() as s:
            end = admin.get_course_end_time(s, "C101")
            missing = admin.get_course_end_time(s, "GHOST")
        self.assertEqual(_as_utc(end), END_TIME)
        self.assertIsNone(missing)  # 「未找到」语义，由消费方按无课程处理


class TestProvisioning(RosterTestCase):
    """运维预置（LCD-004）：幂等 + P1 唯一映射。"""

    def test_provision_idempotent_and_p1_conflict(self):
        self.provision(entries=[])
        with self.scope() as s:  # 重复执行幂等
            admin.provision_course(
                s, course_id="C101", invite_code="INV-1", course_end_time=END_TIME, name="计算机导论"
            )
        with self.scope() as s:  # 邀请码已映射其他课程 → P1 冲突
            with self.assertRaises(ProvisioningConflictError):
                admin.provision_course(s, course_id="C202", invite_code="INV-1")
        with self.scope() as s:
            courses = s.scalar(sa.select(sa.func.count()).select_from(Course))
            codes = s.scalar(sa.select(sa.func.count()).select_from(InviteCode))
        self.assertEqual((courses, codes), (1, 1))


class TestApiRouter(RosterTestCase):
    """router 应答必填字段与 contracts/ct-003.json、ct-013.json 一致。"""

    def _client(self, engine=None):
        from fastapi import FastAPI  # noqa: PLC0415
        from fastapi.testclient import TestClient  # noqa: PLC0415

        eng = engine or self.engine
        app = FastAPI()
        app.include_router(create_router(lambda: session_scope(eng)))
        return TestClient(app)

    @staticmethod
    def _contract(name):
        return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))

    def test_ct003_response_fields_match_contract(self):
        self.provision()
        client = self._client()
        schema = self._contract("ct-003.json")["schemas"]["response"]
        allowed = set(schema["properties"])
        required = set(schema["required"])

        hit = client.post(
            "/api/v1/courses/verify-membership",
            json={"invite_code": "INV-1", "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(hit.status_code, 200)
        body = hit.json()
        self.assertTrue(required <= set(body))
        self.assertTrue(set(body) <= allowed)  # additionalProperties=false
        self.assertIs(body["verified"], True)
        self.assertEqual(body["course_id"], "C101")
        self.assertNotIn("reason", body)  # reason 仅 verified=false 时返回

        miss = client.post(
            "/api/v1/courses/verify-membership",
            json={"invite_code": "NOPE", "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(miss.status_code, 200)
        body = miss.json()
        self.assertTrue(required <= set(body))
        self.assertTrue(set(body) <= allowed)
        self.assertIs(body["verified"], False)
        self.assertEqual(body["reason"], REASON_INVALID_INVITE_CODE)

    def test_ct003_store_failure_maps_roster_unavailable(self):
        broken = sa.create_engine(  # 未建表 → 存储故障
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=sa.pool.StaticPool,
        )
        client = self._client(engine=broken)
        resp = client.post(
            "/api/v1/courses/verify-membership",
            json={"invite_code": "INV-1", "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertEqual(body["code"], ERROR_ROSTER_UNAVAILABLE)
        self.assertNotIn("no such table", json.dumps(body))  # 不暴露内部细节
        broken.dispose()

    def test_ct013_response_fields_match_contract(self):
        self.provision(entries=[])
        client = self._client()
        schema = self._contract("ct-013.json")["schemas"]["response"]
        resp = client.post(
            "/api/v1/courses/C101/roster",
            json={
                "roster_entries": [
                    {"student_name": "张三", "group_name": "G1"},
                    {"student_name": " ", "group_name": "G2"},
                ]
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body), {"import_result"})  # additionalProperties=false
        result_schema = schema["properties"]["import_result"]
        self.assertTrue(set(result_schema["required"]) <= set(body["import_result"]))
        result = body["import_result"]
        self.assertEqual(result["imported_count"], 1)
        self.assertIsInstance(result["skipped_duplicates"], list)
        self.assertEqual(len(result["conflicts"]), 1)  # 格式错误逐项报告

    def test_ct013_unknown_course_404(self):
        self.provision(entries=[])
        client = self._client()
        resp = client.post(
            "/api/v1/courses/GHOST/roster",
            json={"roster_entries": [{"student_name": "张三", "group_name": "G1"}]},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")


class TestProvisioningCli(unittest.TestCase):
    """运维预置工具：CLI 可运行、幂等（LCD-004）。"""

    def test_cli_provision_idempotent_and_conflict(self):
        # Windows 上 sqlite 文件句柄释放有延迟，清理失败不影响断言
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "roster.db"
            url = f"sqlite:///{db_path.as_posix()}"
            engine = sa.create_engine(url)
            Base.metadata.create_all(engine)
            engine.dispose()

            argv = [
                "provision",
                "--database-url", url,
                "--course-id", "C9",
                "--invite-code", "INV-9",
                "--name", "操作系统",
                "--course-end-time", "2026-09-01T00:00:00+00:00",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli_main(argv), 0)
                self.assertEqual(cli_main(argv), 0)  # 幂等
                conflict = [
                    "provision", "--database-url", url,
                    "--course-id", "C10", "--invite-code", "INV-9",
                ]
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cli_main(conflict), 1)  # P1 冲突

            engine = sa.create_engine(url)
            with session_scope(engine) as s:
                row = s.execute(
                    sa.select(Course.course_id, Course.course_end_time).where(
                        Course.course_id == "C9"
                    )
                ).one()
                codes = s.scalar(sa.select(sa.func.count()).select_from(InviteCode))
            self.assertEqual(row.course_id, "C9")
            self.assertEqual(codes, 1)
            self.assertEqual(_as_utc(row.course_end_time), END_TIME)
            engine.dispose()


class TestMigration(unittest.TestCase):
    """迁移文件可导入、revision/down_revision 正确。"""

    def test_migration_importable_and_revisions(self):
        path = ROOT / "server/migrations/versions/0002_course_roster.py"
        spec = importlib.util.spec_from_file_location("migration_0002_course_roster", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0002_course_roster")
        self.assertEqual(module.down_revision, "0001_baseline")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
