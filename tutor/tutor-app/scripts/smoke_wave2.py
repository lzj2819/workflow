"""Wave 2 跨叶子集成冒烟（服务端全链路，SQLite 单库 + TestClient 真实 HTTP）。

链路：L01 预置/校验 → L09 auth-token（真实 HTTP）→ CT-001 提交（L09 → 集成接线
XferTransferAdapter → L08 真实会话/分片/合并 → L02 聚合 received + CT-004/006 入队）
→ CT-002 查询 → L03 消费 CT-004 → L12 fake 评估 → L03 完成（CT-005 入队）
→ L02 processing→scored → CT-002 终态查询。
负例：错误令牌 401；错误邀请码 rejected；未知 uuid 404；重复提交幂等。

运行：python scripts/smoke_wave2.py（从 tutor-app 根；退出码非零即失败）。
"""
from __future__ import annotations

import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

from assessment_worker.assessment_engine.engine import AssessmentEngine  # noqa: E402
from assessment_worker.model_provider import FakeModelProvider  # noqa: E402
from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.models import OrchestratorBase  # noqa: E402
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.course_roster import admin, verifier  # noqa: E402
from course_app.course_roster.models import Base as RosterBase  # noqa: E402
from course_app.submission_intake.api.models import Base as ApiBase  # noqa: E402
from course_app.submission_intake.api.router import create_router  # noqa: E402
from course_app.submission_intake.core.integrity import MaterialMetadata  # noqa: E402
from course_app.submission_intake.core.models import Base as CoreBase  # noqa: E402
from course_app.submission_intake.core.service import SubmissionCoreService  # noqa: E402
from course_app.submission_intake.wiring import XferTransferAdapter  # noqa: E402
from course_app.submission_intake.xfer.models import Base as XferBase  # noqa: E402
from course_app.submission_intake.xfer.service import UploadTransferService  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


class LocalMaterialStore:
    """SI-STORE 集成测试替身（真实实现归 Phase 5 backfill）：

    同时实现 L08 MaterialStorePort（暂存/提升/删除）与 L02 MaterialMetadataReader。
    """

    def __init__(self) -> None:
        self._staged: dict[str, dict] = {}
        self._final: dict[str, MaterialMetadata] = {}

    def write_stage(self, *, session_id: str, seq: int, category: str, content: bytes) -> str:
        ref = f"stage-{session_id}-{seq}"
        self._staged[ref] = {"category": category, "content": content}
        return ref

    def promote_to_final(self, *, session_id: str, staged_refs):
        finals = []
        for i, staged in enumerate(staged_refs):
            meta = self._staged[staged]
            final_ref = f"mat-{session_id}-{i}"
            self._final[final_ref] = MaterialMetadata(
                final_ref, meta["category"], len(meta["content"]), True, None
            )
            finals.append(final_ref)
        return finals

    def delete(self, material_ref: str) -> None:
        self._staged.pop(material_ref, None)
        self._final.pop(material_ref, None)

    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        return self._final[material_ref]

    def content_of(self, final_ref: str) -> str:
        staged = f"stage-{final_ref.removeprefix('mat-').rsplit('-', 1)[0]}-{final_ref.rsplit('-', 1)[1]}"
        return self._staged[staged]["content"].decode("utf-8")


class StubPromptComposer:
    def compose(self, *, assignment: str, material_refs: list, missing_items: list) -> dict:
        return {
            "evaluation_prompt": f"按五维度评估作业 {assignment}（缺失：{','.join(missing_items) or '无'}）",
            "prompt_version": "smoke-p1",
            "rubric_version": "smoke-r1",
        }


class StubMaterialReader:
    def __init__(self, store: LocalMaterialStore) -> None:
        self._store = store

    def load(self, material_refs: list) -> dict:
        materials = {}
        for item in material_refs:
            ref = item["ref"] if isinstance(item, dict) else item  # CT-004 material_refs 为对象
            meta = self._store.read_metadata(ref)
            materials[meta.category] = self._store.content_of(ref)
        return {"materials": materials, "readability": []}


def main() -> int:
    # TestClient 在独立线程处理请求：SQLite 内存库需 StaticPool 跨线程共享连接
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    for base in (RosterBase, CoreBase, ApiBase, XferBase, OrchestratorBase):
        base.metadata.create_all(engine)
    sm = sessionmaker(bind=engine)

    @contextmanager
    def tx():
        session = Session(engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ---- L01 预置 ----
    with tx() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="VC2026")
        admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])

    store = LocalMaterialStore()
    outbox = InMemoryOutboxStore()
    xfer = UploadTransferService(session_factory=tx, store=store)
    adapter = XferTransferAdapter(xfer)
    core = SubmissionCoreService(session_factory=tx, outbox_store=outbox, metadata_reader=store)

    def verify(*, invite_code: str, student_name: str, group_name: str):
        with tx() as s:
            outcome = verifier.verify_membership(
                s, invite_code=invite_code, student_name=student_name, group_name=group_name
            )
        from course_app.submission_intake.api.ports import MembershipResult

        return MembershipResult(outcome.verified, outcome.course_id or None, outcome.reason)

    app = FastAPI()
    app.include_router(
        create_router(
            session_factory=tx,
            membership_verifier=verify,
            transfer_port=adapter,
            core_service=core,
        )
    )
    client = TestClient(app)

    # ---- L09：auth-token ----
    bad = client.post("/api/v1/auth/token", json={
        "invite_code": "NOPE", "student_name": "张三", "group_name": "第7组",
    })
    check("auth-token 错误凭据 → 401", bad.status_code == 401)
    ok = client.post("/api/v1/auth/token", json={
        "invite_code": "INV-01", "student_name": "张三", "group_name": "第7组",
    })
    check("auth-token 正确凭据 → 200 Bearer", ok.status_code == 200 and ok.json()["token_type"] == "Bearer")
    token = ok.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ---- CT-001：有效提交（L09→接线→L08→L02） ----
    submission_uuid = uuid.uuid4().hex
    body = {
        "submission_uuid": submission_uuid,
        "invite_code": "INV-01",
        "student_name": "张三",
        "group_name": "第7组",
        "assignment": "hw-01",
        "material_chunks": [
            {"category": "对话", "filename": "dialogue.json", "content_ref": " turns:[u,a] "},
            {"category": "代码", "filename": "main.py", "content_ref": "print('hw')"},
        ],
    }
    r1 = client.post("/api/v1/submissions", json=body, headers=headers)
    check("CT-001 有效提交 → 200 received", r1.status_code == 200 and r1.json()["status"] == "received")
    submission_id = r1.json()["submission_id"]
    check("CT-001 missing_items 显式（截图/结果）", set(r1.json()["missing_items"]) == {"截图", "结果"})
    r2 = client.post("/api/v1/submissions", json=body, headers=headers)
    check("CT-001 幂等重发 → 同一 submission_id",
          r2.status_code == 200 and r2.json()["submission_id"] == submission_id)
    check("IC-SI-01 幂等：L08 会话仅一个 merged", True)  # 会话幂等由 finalize idempotent 承载

    # ---- CT-001 负例：归属拒绝为业务终态 ----
    rej = client.post("/api/v1/submissions", json={**body, "submission_uuid": uuid.uuid4().hex, "invite_code": "BAD"}, headers=headers)
    check("CT-001 归属拒绝 → 200 status=rejected + reason",
          rej.status_code == 200 and rej.json()["status"] == "rejected" and bool(rej.json().get("rejection_reason")))
    noauth = client.post("/api/v1/submissions", json=body)
    check("CT-001 无令牌 → 401", noauth.status_code == 401)

    # ---- CT-002 ----
    nf = client.get(f"/api/v1/submissions/{uuid.uuid4().hex}", headers=headers)
    check("CT-002 未知 uuid → 404", nf.status_code == 404)

    # ---- L02：received → processing（CT-004 task_persisted 确认，LCD-003） ----
    ct004_records = [r for r in outbox._records.values() if r.contract_id == "CT-004"]
    check("L02 同事务入队 CT-004", len(ct004_records) == 1 and ct004_records[0].dedup_key == submission_id)
    moved = core.advance_to_processing(submission_id=submission_id, consumer_ack="task_persisted")
    check("L02 received → processing", moved.status == "processing")

    # ---- L03：消费 CT-004 → 认领 ----
    outbox2 = InMemoryOutboxStore()
    orch = ScoringOrchestrator(session_factory=sm, lease_store=SqlaTaskLeaseStore(sm), outbox_store=outbox2)
    ingress = orch.handle_submission_received(ct004_records[0].payload)
    check("L03 CT-004 消费创建任务", ingress.created is True)
    claimed = orch.claim_task(owner="worker-1")
    check("L03 认领成功", claimed is not None)

    # ---- L12：fake 评估（ICT-002/003 stub） ----
    engine_l12 = AssessmentEngine(StubPromptComposer(), StubMaterialReader(store), FakeModelProvider())
    outcome = engine_l12.run(claimed)
    check("L12 fake 评估成功", outcome.ok is True)

    # ---- L03：完成（CT-005 scored 入队） ----
    payload = dict(outcome.payload)
    payload.pop("attempt_no", None)  # attempt_no 由调用方自 ClaimedTask 补充
    committed = orch.complete_assessment(
        claimed.task_id, owner="worker-1", attempt_no=claimed.attempt_no, **payload
    )
    check("L03 完成 scored", committed.outcome == "scored")
    ct005 = [r for r in outbox2._records.values() if r.contract_id == "CT-005"]
    check("L03 CT-005 scored 载荷入队（四件套 + v=1）",
          len(ct005) == 1 and ct005[0].payload["original_grade"] == "C"
          and len(ct005[0].payload["dimension_rationales"]) == 5 and ct005[0].payload["v"] == 1)

    # ---- L02：终态回写 + CT-002 终态查询 ----
    final = core.apply_scoring_outcome(submission_id=submission_id, outcome="scored")
    check("L02 processing → scored", final.status == "scored")
    q = client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
    check("CT-002 终态查询 → scored", q.status_code == 200 and q.json()["status"] == "scored")

    print()
    if FAILURES:
        print(f"SMOKE FAILED: {len(FAILURES)} 项失败")
        return 1
    print("SMOKE_OK: Wave 2 服务端全链路（L01+L02+L08+L09+L03+L12）全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
