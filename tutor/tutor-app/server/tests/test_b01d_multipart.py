"""T-B01d：CT-001 真实 multipart 接入与分片会话协议测试。

自装配（正式挂载归 T-B03d 组合根）：FastAPI TestClient + 真实 L08
UploadTransferService + SI-STORE 内存 fake + 真实 L02 SI-CORE + L01 名单校验；
multipart router 先挂载（POST /api/v1/submissions 由其分发），L09 既有 router
提供 auth/token 与 CT-002。

协议事实来源 plugin/src/upload_client/session-driver.js：单端点
POST /api/v1/submissions，phase ∈ {create_session, chunk, merge}；
create_session 应答 upload_session_id，chunk 应答 acked=true，
merge 应答 CT-001 received/rejected 形状。

覆盖：
- multipart 二进制单次上传 → received（字节直达 SI-STORE，不经 content_ref 占位）；
- 分片协议三阶段（JSON content 与 multipart 二进制两条通道）→ received；
- 断点续传：已确认分片重放按 duplicate 去重，不重复落盘；
- 413（请求体守卫 / 会话累计超限，小上限注入）、415（类别/类型白名单外）、
  401（未知令牌）、400（缺 metadata / 未知 phase / 分片未齐即 merge）；
- JSON 兼容通道（content_ref 占位）不回归；REJECTED_MEMBERSHIP 业务终态；
- CT-002 查询与幂等重放（同一 submission_id）。
"""
from __future__ import annotations

import json
import sys
import unittest
import uuid as uuidlib
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.course_roster import admin  # noqa: E402
from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.course_roster.verifier import verify_membership  # noqa: E402
from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.api import Base as ApiBase  # noqa: E402
from course_app.submission_intake.api.multipart import (  # noqa: E402
    create_multipart_router,
)
from course_app.submission_intake.api.orchestrator import (  # noqa: E402
    IntakeOrchestrator,
)
from course_app.submission_intake.api.ports import MembershipResult  # noqa: E402
from course_app.submission_intake.api.router import create_router  # noqa: E402
from course_app.submission_intake.core import (  # noqa: E402
    Base as CoreBase,
    MaterialMetadata,
    SubmissionCoreService,
)
from course_app.submission_intake.wiring import XferTransferAdapter  # noqa: E402
from course_app.submission_intake.xfer.models import Base as XferBase  # noqa: E402
from course_app.submission_intake.xfer.service import (  # noqa: E402
    MAX_SUBMISSION_BYTES,
    UploadTransferService,
)
from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

INVITE = "INV-1"
COURSE = "course-1"
BOUNDARY = "b01dboundary"


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    RosterBase.metadata.create_all(eng)
    CoreBase.metadata.create_all(eng)
    ApiBase.metadata.create_all(eng)
    XferBase.metadata.create_all(eng)
    return eng


class FakeMaterialStore:
    """SI-STORE 内存 fake：暂存/提升字节留存，登记 SI-CORE 完整性所需元数据。"""

    def __init__(self, metadata: dict[str, MaterialMetadata]) -> None:
        self._metadata = metadata
        self.staged: dict[str, bytes] = {}
        self.promoted: dict[str, bytes] = {}
        self._category: dict[str, str] = {}
        self.write_calls = 0

    def write_stage(self, *, session_id, seq, category, content):
        self.write_calls += 1
        ref = f"stage-{session_id}-{seq}"
        self.staged[ref] = bytes(content)
        self._category[ref] = category
        return ref

    def promote_to_final(self, *, session_id, staged_refs):
        refs = []
        for staged in staged_refs:
            final = f"mat-{staged}"
            if final not in self.promoted:
                self.promoted[final] = self.staged[staged]
                self._metadata[final] = MaterialMetadata(
                    final, self._category[staged], len(self.staged[staged]), True, None
                )
            refs.append(final)
        return refs

    def delete(self, material_ref):
        self.staged.pop(material_ref, None)
        self.promoted.pop(material_ref, None)


class FakeMetadataReader:
    def __init__(self, entries: dict[str, MaterialMetadata]) -> None:
        self._entries = entries

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        return self._entries[material_ref]


def encode_multipart(metadata: dict, binaries: list[bytes]) -> tuple[bytes, str]:
    """构造 multipart/form-data 体：metadata JSON part + 二进制 parts。"""
    lines: list[bytes] = []
    lines.append(f"--{BOUNDARY}\r\n".encode())
    lines.append(b'Content-Disposition: form-data; name="metadata"\r\n')
    lines.append(b"Content-Type: application/json\r\n\r\n")
    lines.append(json.dumps(metadata).encode("utf-8"))
    lines.append(b"\r\n")
    for blob in binaries:
        lines.append(f"--{BOUNDARY}\r\n".encode())
        lines.append(
            b'Content-Disposition: form-data; name="chunk"; filename="blob.bin"\r\n'
        )
        lines.append(b"Content-Type: application/octet-stream\r\n\r\n")
        lines.append(blob)
        lines.append(b"\r\n")
    lines.append(f"--{BOUNDARY}--\r\n".encode())
    return b"".join(lines), f"multipart/form-data; boundary={BOUNDARY}"


class B01dBase(unittest.TestCase):
    """公共装配：真实 L08 + 内存 SI-STORE + L02 SI-CORE + L01 名单 + 双 router。"""

    max_bytes = MAX_SUBMISSION_BYTES
    max_request_bytes = MAX_SUBMISSION_BYTES

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
        self.store = FakeMaterialStore(self.metadata)
        self.outbox = InMemoryOutboxStore()
        self.core = SubmissionCoreService(
            session_factory=partial(session_scope, self.eng),
            outbox_store=self.outbox,
            metadata_reader=FakeMetadataReader(self.metadata),
        )
        self.xfer = UploadTransferService(
            session_factory=partial(session_scope, self.eng),
            store=self.store,
            max_bytes=self.max_bytes,
        )
        adapter = XferTransferAdapter(self.xfer)

        self.verifier_override: MembershipResult | None = None

        def verifier(*, invite_code, student_name, group_name):
            if self.verifier_override is not None:
                return self.verifier_override
            with session_scope(self.eng) as session:
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

        self.orchestrator = IntakeOrchestrator(
            core_service=self.core,
            transfer_port=adapter,
            membership_verifier=verifier,
        )
        app = FastAPI()
        # multipart router 先挂载：POST /api/v1/submissions 由其统一分发
        # （含无 phase 的 JSON 兼容通道委托）；L09 router 提供 auth/token 与 CT-002。
        app.include_router(
            create_multipart_router(
                session_factory=partial(session_scope, self.eng),
                xfer=self.xfer,
                orchestrator=self.orchestrator,
                max_request_bytes=self.max_request_bytes,
            )
        )
        app.include_router(
            create_router(
                session_factory=partial(session_scope, self.eng),
                membership_verifier=verifier,
                transfer_port=adapter,
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

    def auth(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def identity(self) -> dict:
        return {
            "invite_code": INVITE,
            "student_name": "张三",
            "group_name": "G1",
            "assignment": "hw-1",
        }

    def create_session(self, token, uuid, chunks_meta) -> str:
        resp = self.client.post(
            "/api/v1/submissions",
            json={
                "phase": "create_session",
                "submission_uuid": uuid,
                **self.identity(),
                "material_chunks": chunks_meta,
                "total_chunks": len(chunks_meta),
            },
            headers=self.auth(token),
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["upload_session_id"]

    def post_chunk_json(self, token, uuid, session_id, index, meta, content):
        return self.client.post(
            "/api/v1/submissions",
            json={
                "phase": "chunk",
                "submission_uuid": uuid,
                "upload_session_id": session_id,
                "chunk_index": index,
                "chunk": {**meta, "content": content},
            },
            headers=self.auth(token),
        )

    def merge(self, token, uuid, session_id):
        return self.client.post(
            "/api/v1/submissions",
            json={
                "phase": "merge",
                "submission_uuid": uuid,
                "upload_session_id": session_id,
            },
            headers=self.auth(token),
        )


class B01dMultipartTestCase(B01dBase):
    """默认 500MB 上限下的功能用例。"""

    # ---- multipart 单次上传 ----

    def test_multipart_single_shot_received(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        blobs = [b"DIALOGUE-BYTES-\x00\x01", b"CODE-BYTES-\xff"]
        metadata = {
            "submission_uuid": uuid,
            **self.identity(),
            "material_chunks": [
                {"category": "对话", "filename": "dialog.md", "size_bytes": len(blobs[0])},
                {"category": "代码", "filename": "main.py", "size_bytes": len(blobs[1])},
            ],
        }
        body, ctype = encode_multipart(metadata, blobs)
        resp = self.client.post(
            "/api/v1/submissions",
            content=body,
            headers={**self.auth(token), "Content-Type": ctype},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "received")
        self.assertEqual(
            set(payload), {"submission_id", "received_at", "status", "missing_items"}
        )
        # 字节直达 SI-STORE 正式区（不经 content_ref 占位）
        self.assertEqual(sorted(self.store.promoted.values()), sorted(blobs))
        self.assertEqual(len(self.metadata), 2)
        # CT-002 可查
        view = self.client.get(f"/api/v1/submissions/{uuid}", headers=self.auth(token))
        self.assertEqual(view.status_code, 200)
        self.assertEqual(view.json()["status"], "received")
        # 幂等重放：同一 submission_id，不重复落盘
        writes = self.store.write_calls
        replay = self.client.post(
            "/api/v1/submissions",
            content=body,
            headers={**self.auth(token), "Content-Type": ctype},
        )
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["submission_id"], payload["submission_id"])
        self.assertEqual(self.store.write_calls, writes)

    def test_multipart_missing_metadata_400(self):
        token = self.issue_token()
        body = (
            f"--{BOUNDARY}\r\n"
            'Content-Disposition: form-data; name="chunk"; filename="a.bin"\r\n\r\n'
            "XX\r\n"
            f"--{BOUNDARY}--\r\n"
        ).encode()
        resp = self.client.post(
            "/api/v1/submissions",
            content=body,
            headers={
                **self.auth(token),
                "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    # ---- 分片协议三阶段 ----

    def test_phased_protocol_json_channel_received(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [
            {"category": "对话", "filename": "dialog.md"},
            {"category": "代码", "filename": "main.py"},
        ]
        session_id = self.create_session(token, uuid, metas)
        contents = ["对话内容", "print('hi')"]
        for i, content in enumerate(contents):
            resp = self.post_chunk_json(token, uuid, session_id, i, metas[i], content)
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertTrue(resp.json()["acked"])
            self.assertEqual(resp.json()["chunk_index"], i)
        resp = self.merge(token, uuid, session_id)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "received")
        self.assertEqual(
            sorted(self.store.promoted.values()),
            sorted(c.encode("utf-8") for c in contents),
        )

    def test_phased_protocol_multipart_chunk_received(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [{"category": "截图", "filename": "s.png"}]
        session_id = self.create_session(token, uuid, metas)
        blob = b"\x89PNG-binary\r\n\x00"
        body, ctype = encode_multipart(
            {
                "phase": "chunk",
                "submission_uuid": uuid,
                "upload_session_id": session_id,
                "chunk_index": 0,
                "chunk": metas[0],
            },
            [blob],
        )
        resp = self.client.post(
            "/api/v1/submissions",
            content=body,
            headers={**self.auth(token), "Content-Type": ctype},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["acked"])
        resp = self.merge(token, uuid, session_id)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["status"], "received")
        self.assertEqual(list(self.store.promoted.values()), [blob])

    def test_resume_replay_confirmed_chunks_deduplicated(self):
        """断点续传：重发 create_session 复用会话；已确认分片重放 duplicate 不落盘。"""
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [
            {"category": "对话", "filename": "dialog.md"},
            {"category": "结果", "filename": "out.csv"},
        ]
        session_id = self.create_session(token, uuid, metas)
        resp = self.post_chunk_json(token, uuid, session_id, 0, metas[0], "D0")
        self.assertTrue(resp.json()["acked"])
        writes_after_first = self.store.write_calls
        # 客户端重发 create_session（本地 checkpoint 丢失后恢复场景）
        session_id_again = self.create_session(token, uuid, metas)
        self.assertEqual(session_id_again, session_id)
        # 重放已确认分片：duplicate，不重复写暂存
        resp = self.post_chunk_json(token, uuid, session_id, 0, metas[0], "D0")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["acked"])
        self.assertTrue(resp.json()["duplicate"])
        self.assertEqual(self.store.write_calls, writes_after_first)
        # 续传剩余分片并合并
        resp = self.post_chunk_json(token, uuid, session_id, 1, metas[1], "R1")
        self.assertTrue(resp.json()["acked"])
        self.assertFalse(resp.json()["duplicate"])
        resp = self.merge(token, uuid, session_id)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["status"], "received")

    def test_merge_before_all_chunks_400(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [{"category": "对话"}, {"category": "代码"}]
        session_id = self.create_session(token, uuid, metas)
        resp = self.post_chunk_json(token, uuid, session_id, 0, metas[0], "D0")
        self.assertTrue(resp.json()["acked"])
        resp = self.merge(token, uuid, session_id)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    # ---- 错误映射 ----

    def test_unknown_token_401(self):
        uuid = str(uuidlib.uuid4())
        resp = self.client.post(
            "/api/v1/submissions",
            json={
                "phase": "create_session",
                "submission_uuid": uuid,
                **self.identity(),
                "material_chunks": [{"category": "对话"}],
                "total_chunks": 1,
            },
            headers={"Authorization": "Bearer no-such-token"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_whitelist_violations_415(self):
        token = self.issue_token()
        # 类别白名单外（KD-004）
        resp = self.client.post(
            "/api/v1/submissions",
            json={
                "phase": "create_session",
                "submission_uuid": str(uuidlib.uuid4()),
                **self.identity(),
                "material_chunks": [{"category": "视频"}],
                "total_chunks": 1,
            },
            headers=self.auth(token),
        )
        self.assertEqual(resp.status_code, 415, resp.text)
        self.assertEqual(resp.json()["code"], "UNSUPPORTED_MEDIA_TYPE")
        # 文件类型白名单外（media_type 不在 file_type_whitelist）
        uuid = str(uuidlib.uuid4())
        session_id = self.create_session(token, uuid, [{"category": "对话"}])
        resp = self.post_chunk_json(
            token,
            uuid,
            session_id,
            0,
            {"category": "对话", "media_type": "可执行程序"},
            "X",
        )
        self.assertEqual(resp.status_code, 415, resp.text)
        self.assertEqual(resp.json()["code"], "UNSUPPORTED_MEDIA_TYPE")

    def test_unknown_phase_400(self):
        token = self.issue_token()
        resp = self.client.post(
            "/api/v1/submissions",
            json={"phase": "teleport", "submission_uuid": str(uuidlib.uuid4())},
            headers=self.auth(token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDATION_FAILED")

    # ---- JSON 兼容通道不回归 ----

    def test_legacy_json_content_ref_channel_not_regressed(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        body = {
            "submission_uuid": uuid,
            **self.identity(),
            "material_chunks": [
                {"category": "对话", "filename": "d.md", "content_ref": "REF-D"},
                {"category": "代码", "filename": "m.py", "content_ref": "REF-C"},
            ],
        }
        resp = self.client.post(
            "/api/v1/submissions", json=body, headers=self.auth(token)
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "received")
        # content_ref 占位通道：字节为 content_ref 字面编码（既有传输约定）
        self.assertEqual(sorted(self.store.promoted.values()), [b"REF-C", b"REF-D"])
        # 幂等重放
        replay = self.client.post(
            "/api/v1/submissions", json=body, headers=self.auth(token)
        )
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json()["submission_id"], payload["submission_id"])

    def test_rejected_membership_business_terminal(self):
        # 名单核对每次实时执行（REQ-006）：令牌签发时通过、merge 时不再通过。
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [{"category": "对话"}]
        session_id = self.create_session(token, uuid, metas)
        resp = self.post_chunk_json(token, uuid, session_id, 0, metas[0], "D0")
        self.assertTrue(resp.json()["acked"])
        self.verifier_override = MembershipResult(
            verified=False, course_id=None, reason="roster changed"
        )
        resp = self.merge(token, uuid, session_id)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual(payload["status"], "rejected")
        self.assertIn("REJECTED_MEMBERSHIP", payload["rejection_reason"])


class B01dLimitsTestCase(B01dBase):
    """缩小上限注入：500MB 守卫映射（会话累计 64B；请求体守卫 64B）。"""

    max_bytes = 64
    max_request_bytes = 64

    def test_size_limit_413(self):
        token = self.issue_token()
        uuid = str(uuidlib.uuid4())
        metas = [{"category": "对话"}, {"category": "对话"}]
        session_id = self.create_session(token, uuid, metas)
        resp = self.post_chunk_json(token, uuid, session_id, 0, metas[0], "A" * 40)
        self.assertTrue(resp.json()["acked"])
        resp = self.post_chunk_json(token, uuid, session_id, 1, metas[1], "B" * 40)
        self.assertEqual(resp.status_code, 413, resp.text)
        self.assertEqual(resp.json()["code"], "PAYLOAD_TOO_LARGE")

    def test_request_body_guard_413(self):
        token = self.issue_token()
        metadata = {
            "submission_uuid": str(uuidlib.uuid4()),
            **self.identity(),
            "material_chunks": [{"category": "对话", "size_bytes": 100}],
        }
        body, ctype = encode_multipart(metadata, [b"X" * 100])
        resp = self.client.post(
            "/api/v1/submissions",
            content=body,
            headers={**self.auth(token), "Content-Type": ctype},
        )
        self.assertEqual(resp.status_code, 413, resp.text)
        self.assertEqual(resp.json()["code"], "PAYLOAD_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
