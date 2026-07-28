"""L09 SI-API 单元测试（fastapi TestClient + SQLite 内存库）。

覆盖 verification-checklist 语义断言：
- auth/token：正确凭据 → 200 + access_token/Bearer/expires_in；错误凭据 → 401
  AUTH_INVALID；签发审计落库（ST-06，只存哈希与指纹，不含明文令牌）；
- CT-001：有效提交 → 200 + submission_id/received_at/status=received/missing_items；
  缺字段/非法类别/多余字段 → 400 VALIDATION_FAILED；未知/过期令牌 → 401；
- 归属校验拒绝 → 200 status=rejected + rejection_reason（业务终态，非 4xx/5xx）；
- 同一 submission_uuid 重复提交 → 同一 submission_id（幂等，无重复记录/事件，
  且不重复调用 IC-SI-01 合并）；
- CT-002：已知 uuid → status/failure_reason?/missing_items；未知 uuid → 404 NOT_FOUND；
- IC-SI-01 错误映射：SIZE_LIMIT_EXCEEDED → 413、TYPE_NOT_ALLOWED → 415；
- 名单暂不可用 → 有限快速重试后 503 暂态失败，不创建提交记录（LCD-001）；
- 应答字段与 contracts/ct-001.json、ct-002.json、auth-token.json 一致；
- 迁移文件可导入、revision/down_revision 正确。

注入（DD-004，进程内）：IC-SI-03 用 L01 verify_membership 包装；IC-SI-04 用 L02
SubmissionCoreService 真实实现；IC-SI-01 用冻结端口 stub（L08 同波次未集成）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
import uuid as uuidlib
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.course_roster import admin  # noqa: E402
from course_app.course_roster.errors import RosterUnavailableError  # noqa: E402
from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.course_roster.verifier import verify_membership  # noqa: E402
from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.api import (  # noqa: E402
    TOKEN_TTL_SECONDS,
    AuthTokenGrant,
)
from course_app.submission_intake.api import Base as ApiBase  # noqa: E402
from course_app.submission_intake.api.models import (  # noqa: E402
    RESULT_GRANTED,
    RESULT_REJECTED,
)
from course_app.submission_intake.api.ports import (  # noqa: E402
    XFER_ERROR_SIZE_LIMIT,
    XFER_ERROR_TYPE_NOT_ALLOWED,
    XFER_STATE_FAILED_TERMINAL,
    XFER_STATE_MERGED,
    MembershipResult,
    TransferResult,
)
from course_app.submission_intake.api.router import create_router  # noqa: E402
from course_app.submission_intake.api.tokens import hash_token  # noqa: E402
from course_app.submission_intake.core import (  # noqa: E402
    Base as CoreBase,
    MaterialMetadata,
    NotFoundError,
    SubmissionCoreService,
)
from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

CONTRACTS_DIR = ROOT / "contracts"
INVITE = "INV-1"
COURSE = "course-1"
CHUNKS = [
    {"category": "对话", "filename": "dialog.md", "size_bytes": 100},
    {"category": "代码", "filename": "main.py", "size_bytes": 200},
]


def load_contract(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    RosterBase.metadata.create_all(eng)
    CoreBase.metadata.create_all(eng)
    ApiBase.metadata.create_all(eng)
    return eng


class StubXfer:
    """IC-SI-01 冻结端口 stub：合并成功并登记 SI-STORE 元数据；可注入错误。"""

    def __init__(self, metadata: dict[str, MaterialMetadata]) -> None:
        self._metadata = metadata
        self.calls = 0
        self.error_code: str | None = None

    def ingest(self, *, submission_uuid, declared_categories, chunks):
        self.calls += 1
        if self.error_code is not None:
            return TransferResult(
                state=XFER_STATE_FAILED_TERMINAL,
                failure_reason="stub transfer failure",
                error_code=self.error_code,
            )
        refs = []
        for index, chunk in enumerate(chunks):
            ref = f"ref-{submission_uuid}-{index}"
            self._metadata[ref] = MaterialMetadata(
                ref, chunk.category, chunk.size_bytes, True, chunk.filename
            )
            refs.append(ref)
        return TransferResult(state=XFER_STATE_MERGED, material_refs=tuple(refs))


class FakeMetadataReader:
    """SI-STORE 元数据端口 fake（同 L02 测试口径）。"""

    def __init__(self, entries: dict[str, MaterialMetadata]) -> None:
        self._entries = entries

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        return self._entries[material_ref]


def make_roster_verifier(eng):
    """IC-SI-03 注入：L01 verify_membership 进程内包装（每次实时调用）。"""

    def verify(*, invite_code: str, student_name: str, group_name: str):
        with session_scope(eng) as session:
            outcome = verify_membership(
                session,
                invite_code=invite_code,
                student_name=student_name,
                group_name=group_name,
            )
        return MembershipResult(
            verified=outcome.verified,
            course_id=outcome.course_id or None,
            reason=outcome.reason,
        )

    return verify


class SiApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.eng = make_engine()
        with session_scope(self.eng) as session:
            admin.provision_course(session, course_id=COURSE, invite_code=INVITE)
            admin.import_roster(
                session,
                course_id=COURSE,
                entries=[
                    {"student_name": "张三", "group_name": "G1"},
                    {"student_name": "李四", "group_name": "G2"},
                ],
            )
        self.metadata: dict[str, MaterialMetadata] = {}
        self.outbox = InMemoryOutboxStore()
        self.core = SubmissionCoreService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            metadata_reader=FakeMetadataReader(self.metadata),
        )
        self.xfer = StubXfer(self.metadata)
        self.verifier = make_roster_verifier(self.eng)
        app = FastAPI()
        app.include_router(
            create_router(
                session_factory=partial(session_scope, self.eng),
                membership_verifier=self.verifier,
                transfer_port=self.xfer,
                core_service=self.core,
            )
        )
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.eng.dispose()

    # ---- 辅助 ----

    def issue_token(self, invite=INVITE, name="张三", group="G1") -> str:
        resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": invite, "student_name": name, "group_name": group},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    def post_submission(self, token, submission_uuid, **overrides):
        body = {
            "submission_uuid": submission_uuid,
            "invite_code": INVITE,
            "student_name": "张三",
            "group_name": "G1",
            "assignment": "hw-1",
            "material_chunks": CHUNKS,
        }
        body.update(overrides)
        return self.client.post(
            "/api/v1/submissions",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )

    def grants(self) -> list:
        with session_scope(self.eng) as session:
            return [
                SimpleNamespace(
                    result=g.result,
                    course_id=g.course_id,
                    token_hash=g.token_hash,
                    subject_fingerprint=g.subject_fingerprint,
                )
                for g in session.query(AuthTokenGrant).all()
            ]

    def assert_contract_keys(self, payload: dict, schema: dict) -> None:
        self.assertTrue(set(schema["required"]) <= set(payload), payload)
        if schema.get("additionalProperties") is False:
            self.assertTrue(set(payload) <= set(schema["properties"]), payload)

    # ---- auth-token ----

    def test_auth_token_success_contract_and_audit(self):
        resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assert_contract_keys(
            payload, load_contract("auth-token.json")["schemas"]["response"]
        )
        self.assertEqual(payload["token_type"], "Bearer")
        self.assertEqual(payload["expires_in"], TOKEN_TTL_SECONDS)
        self.assertTrue(payload["access_token"])
        # ST-06 审计落库：结果 granted；只存哈希/指纹，不含明文令牌。
        grants = self.grants()
        self.assertEqual(len(grants), 1)
        grant = grants[0]
        self.assertEqual(grant.result, RESULT_GRANTED)
        self.assertEqual(grant.course_id, COURSE)
        self.assertEqual(grant.token_hash, hash_token(payload["access_token"]))
        self.assertNotEqual(grant.token_hash, payload["access_token"])
        self.assertNotIn(payload["access_token"], grant.subject_fingerprint)

    def test_auth_token_invalid_credentials_401_with_reject_audit(self):
        resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "王五", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")
        grants = self.grants()
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].result, RESULT_REJECTED)
        self.assertIsNone(grants[0].token_hash)

    def test_auth_token_unknown_invite_code_401(self):
        resp = self.client.post(
            "/api/v1/auth/token",
            json={"invite_code": "NOPE", "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    # ---- CT-001 接收 ----

    def test_submission_received_contract_and_30s_budget(self):
        token = self.issue_token()
        started = datetime.now(timezone.utc)
        resp = self.post_submission(token, str(uuidlib.uuid4()))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assert_contract_keys(
            payload, load_contract("ct-001.json")["schemas"]["response_received"]
        )
        self.assertEqual(payload["status"], "received")
        self.assertTrue(payload["submission_id"])
        self.assertEqual(payload["missing_items"], ["截图", "结果"])
        # received_at 为 ISO date-time 且在 30 秒预算内（NFR-003）
        received_at = datetime.fromisoformat(payload["received_at"])
        self.assertIsNotNone(received_at.tzinfo)
        self.assertLess(elapsed, 30.0)

    def test_submission_empty_chunks_marks_all_missing_but_received(self):
        token = self.issue_token()
        resp = self.post_submission(token, str(uuidlib.uuid4()), material_chunks=[])
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "received")
        self.assertEqual(payload["missing_items"], ["对话", "代码", "截图", "结果"])

    def test_submission_validation_failed_400(self):
        token = self.issue_token()
        uid = str(uuidlib.uuid4())
        headers = {"Authorization": f"Bearer {token}"}
        base = {
            "submission_uuid": uid,
            "invite_code": INVITE,
            "student_name": "张三",
            "group_name": "G1",
            "assignment": "hw-1",
            "material_chunks": CHUNKS,
        }
        for field in base:
            broken = {k: v for k, v in base.items() if k != field}
            resp = self.client.post("/api/v1/submissions", json=broken, headers=headers)
            self.assertEqual(resp.status_code, 400, field)
            self.assertEqual(resp.json()["code"], "VALIDATION_FAILED", field)
        # 多余字段（additionalProperties=false）
        resp = self.client.post(
            "/api/v1/submissions", json={**base, "extra": 1}, headers=headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")
        # 非法材料类别（冻结枚举）
        resp = self.client.post(
            "/api/v1/submissions",
            json={**base, "material_chunks": [{"category": "视频"}]},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    def test_submission_unknown_or_missing_token_401(self):
        uid = str(uuidlib.uuid4())
        resp = self.post_submission("not-a-token", uid)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")
        body = {
            "submission_uuid": uid,
            "invite_code": INVITE,
            "student_name": "张三",
            "group_name": "G1",
            "assignment": "hw-1",
            "material_chunks": CHUNKS,
        }
        resp = self.client.post("/api/v1/submissions", json=body)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_expired_token_401(self):
        token = self.issue_token()
        with session_scope(self.eng) as session:
            grant = session.query(AuthTokenGrant).one()
            grant.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        resp = self.post_submission(token, str(uuidlib.uuid4()))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_rejected_membership_is_business_terminal(self):
        token = self.issue_token()
        uid = str(uuidlib.uuid4())
        resp = self.post_submission(token, uid, student_name="王五")
        # 业务终态：HTTP 200 + status=rejected，非 4xx/5xx
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assert_contract_keys(
            payload, load_contract("ct-001.json")["schemas"]["response_rejected"]
        )
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("ROSTER_ENTRY_NOT_FOUND", payload["rejection_reason"])
        # CT-002 可见终态与原因
        view = self.client.get(
            f"/api/v1/submissions/{uid}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        self.assertEqual(view["status"], "rejected")
        self.assertEqual(view["failure_reason"], payload["rejection_reason"])

    def test_idempotent_resubmit_same_submission_id(self):
        token = self.issue_token()
        uid = str(uuidlib.uuid4())
        first = self.post_submission(token, uid).json()
        drained = self.outbox.fetch_due(
            datetime.now(timezone.utc) + timedelta(days=1), limit=100
        )
        self.assertEqual(len(drained), 2)  # CT-004 + CT-006
        second = self.post_submission(token, uid)
        self.assertEqual(second.status_code, 200, second.text)
        payload = second.json()
        self.assertEqual(payload["submission_id"], first["submission_id"])
        self.assertEqual(payload["status"], "received")
        self.assertEqual(payload["received_at"], first["received_at"])
        self.assertEqual(payload["missing_items"], first["missing_items"])
        # 无重复提交记录、无重复事件、不重复调用 IC-SI-01 合并
        with session_scope(self.eng) as session:
            from course_app.submission_intake.core import Submission

            self.assertEqual(session.query(Submission).count(), 1)
        self.assertEqual(
            self.outbox.fetch_due(
                datetime.now(timezone.utc) + timedelta(days=1), limit=100
            ),
            [],
        )
        self.assertEqual(self.xfer.calls, 1)

    # ---- IC-SI-01 错误映射 ----

    def test_xfer_size_limit_maps_413(self):
        self.xfer.error_code = XFER_ERROR_SIZE_LIMIT
        resp = self.post_submission(self.issue_token(), str(uuidlib.uuid4()))
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json()["code"], "PAYLOAD_TOO_LARGE")

    def test_xfer_type_not_allowed_maps_415(self):
        self.xfer.error_code = XFER_ERROR_TYPE_NOT_ALLOWED
        resp = self.post_submission(self.issue_token(), str(uuidlib.uuid4()))
        self.assertEqual(resp.status_code, 415)
        self.assertEqual(resp.json()["code"], "UNSUPPORTED_MEDIA_TYPE")

    # ---- 名单暂不可用（LCD-001） ----

    def test_roster_unavailable_503_and_no_submission_created(self):
        def unavailable(*, invite_code, student_name, group_name):
            raise RosterUnavailableError("roster down")

        app = FastAPI()
        app.include_router(
            create_router(
                session_factory=partial(session_scope, self.eng),
                membership_verifier=unavailable,
                transfer_port=self.xfer,
                core_service=self.core,
            )
        )
        client = TestClient(app)
        # auth-token 同样暂态失败（不签发、不暴露内部细节）
        resp = client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn("code", resp.json())
        # CT-001 暂态失败且不创建提交记录
        uid = str(uuidlib.uuid4())
        resp = client.post(
            "/api/v1/submissions",
            json={
                "submission_uuid": uid,
                "invite_code": INVITE,
                "student_name": "张三",
                "group_name": "G1",
                "assignment": "hw-1",
                "material_chunks": CHUNKS,
            },
            headers={"Authorization": f"Bearer {self.issue_token()}"},
        )
        self.assertEqual(resp.status_code, 503)
        with self.assertRaises(NotFoundError):
            self.core.query_by_uuid(uid)

    def test_roster_unavailable_limited_retry_then_success(self):
        attempts = {"count": 0}
        real = self.verifier

        def flaky(*, invite_code, student_name, group_name):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RosterUnavailableError("roster down")
            return real(
                invite_code=invite_code,
                student_name=student_name,
                group_name=group_name,
            )

        app = FastAPI()
        app.include_router(
            create_router(
                session_factory=partial(session_scope, self.eng),
                membership_verifier=flaky,
                transfer_port=self.xfer,
                core_service=self.core,
            )
        )
        client = TestClient(app)
        resp = client.post(
            "/api/v1/auth/token",
            json={"invite_code": INVITE, "student_name": "张三", "group_name": "G1"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(attempts["count"], 2)

    # ---- CT-002 查询 ----

    def test_ct002_known_uuid_contract(self):
        token = self.issue_token()
        uid = str(uuidlib.uuid4())
        created = self.post_submission(token, uid).json()
        resp = self.client.get(
            f"/api/v1/submissions/{uid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assert_contract_keys(
            payload, load_contract("ct-002.json")["schemas"]["response"]
        )
        self.assertEqual(payload["submission_id"], created["submission_id"])
        self.assertEqual(payload["status"], "received")
        self.assertEqual(payload["missing_items"], ["截图", "结果"])
        self.assertNotIn("failure_reason", payload)  # received 不返回

    def test_ct002_unknown_uuid_404(self):
        token = self.issue_token()
        resp = self.client.get(
            f"/api/v1/submissions/{uuidlib.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_ct002_requires_auth_401(self):
        resp = self.client.get(f"/api/v1/submissions/{uuidlib.uuid4()}")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    # ---- 迁移 ----

    def test_migration_importable_with_correct_revisions(self):
        path = ROOT / "server" / "migrations" / "versions" / "0006_auth_tokens.py"
        spec = importlib.util.spec_from_file_location("migration_0006", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0006_auth_tokens")
        self.assertEqual(module.down_revision, "9c99fa53f9f8")
        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))


if __name__ == "__main__":
    unittest.main()
