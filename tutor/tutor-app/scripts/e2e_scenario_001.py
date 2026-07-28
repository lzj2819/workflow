"""B-05 E2E：SCENARIO-001 学生提交到评分完成主链路（真实组合根 + 真实 relay）。

链路（对照 tutor/L0-root/architecture/02-runtime-architecture.md SCENARIO-001）：
教师/课程预置 → 学生令牌 → CT-001 提交 → received（CT-004/006 入队）
→ 进程外 worker 侧消费 CT-004（本脚本驱动，生产为 DU-3 relay）
→ 认领 → L12(fake provider + 真实 rubric composer + 真实 ACL) → L03 完成
→ CT-005 经组合根 relay → L02 scored + projector（M05-IC-01 建复核记录）
→ CT-002 scored → 教师登录 → CT-007 详情 → CT-008 调整 → CT-009 展示 → SSR 页面。

运行：python scripts/e2e_scenario_001.py（退出码非零即失败）。
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from alembic import command as alembic_command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from assessment_worker.assessment_engine.engine import AssessmentEngine  # noqa: E402
from assessment_worker.model_acl.acl import ModelServiceAcl  # noqa: E402
from assessment_worker.model_acl.fake_adapter import FakeVendorAdapter  # noqa: E402
from assessment_worker.rubric.composer import RubricPromptComposer  # noqa: E402
from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import Settings  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def migrate(db_url: str):
    """创建锚定引擎并执行全部迁移，返回该引擎。

    shared-cache 内存库在所有连接关闭时销毁：锚定连接先于 alembic 打开，
    保证迁移结果在整个进程内对组合根可见。SQLite 专属参数仅对 sqlite URL 生效。
    """
    if db_url.startswith("sqlite"):
        engine = create_engine(db_url, poolclass=StaticPool, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(db_url)
    with engine.connect():  # anchor：保持 DB 存活
        os.environ["DATABASE_URL"] = db_url  # env.py 从环境变量取 URL
        cfg = AlembicConfig(str(ROOT / "server" / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "server" / "migrations"))
        alembic_command.upgrade(cfg, "head")
    return engine


class UploadRegistryReader:
    """ICT-003 测试侧实现：按提交时登记的材料内容供给（本 E2E 焦点为链路集成；
    存储读路径由 B01a 单测覆盖）。"""

    def __init__(self) -> None:
        self.contents: dict[str, tuple[str, str]] = {}  # ref -> (category, text)

    def register(self, ref: str, category: str, text: str) -> None:
        self.contents[ref] = (category, text)

    def load(self, material_refs: list) -> dict:
        materials = {}
        for item in material_refs:
            ref = item["ref"] if isinstance(item, dict) else item
            category, text = self.contents.get(ref, ("结果", f"content of {ref}"))
            materials[category] = text
        return {"materials": materials, "readability": []}


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())  # Windows 文件锁：不做自动清理
    # shared-cache 内存库（多线程 TestClient 安全；真实迁移经 alembic 执行）
    db_url = "sqlite:///file:e2e001?mode=memory&cache=shared&uri=true"
    engine = migrate(db_url)

    settings = Settings(
        database_url=db_url,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="e2e-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings, engine=engine)

    # ---- 预置：课程/名单/教师（运维路径） ----
    with comp.session_scope() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="VC2026")
        admin.import_roster(s, course_id="c-01", entries=[
            {"student_name": "张三", "group_name": "第7组"},
            {"student_name": "李四", "group_name": "第7组"},
        ])
    comp.access_gate.provision_teacher(
        account="teacher@example.com", password="pw-e2e", course_ids=("c-01",)
    )

    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)

    # ---- 学生令牌 + CT-001 提交 ----
    tok = client.post("/api/v1/auth/token", json={
        "invite_code": "INV-01", "student_name": "张三", "group_name": "第7组",
    })
    check("auth-token 200", tok.status_code == 200)
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    submission_uuid = uuid.uuid4().hex
    r1 = client.post("/api/v1/submissions", json={
        "submission_uuid": submission_uuid,
        "invite_code": "INV-01",
        "student_name": "张三",
        "group_name": "第7组",
        "assignment": "hw-01",
        "material_chunks": [
            {"category": "对话", "filename": "dialogue.json", "content_ref": "turns:[u,a]"},
            {"category": "代码", "filename": "main.py", "content_ref": "print('hw')"},
        ],
    }, headers=headers)
    check("CT-001 received", r1.status_code == 200 and r1.json()["status"] == "received")
    submission_id = r1.json()["submission_id"]

    # ---- 进程外 worker 侧：消费 CT-004（生产为 DU-3 relay，本脚本驱动一轮） ----
    with comp.session_scope() as s:
        store = SqlaOutboxStore(s)
        due = store.fetch_due(__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
        ct004 = [r for r in due if r.contract_id == "CT-004"]
        check("CT-004 已在 outbox 待投递", len(ct004) == 1)
        orch = ScoringOrchestrator(
            session_factory=comp.session_factory,
            lease_store=SqlaTaskLeaseStore(comp.session_factory),
            outbox_store=SqlaOutboxStore(s),
        )
        ingress = orch.handle_submission_received(ct004[0].payload)
        store.mark_confirmed(ct004[0].record_id)
        now_utc = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        for r in due:  # 非 CT-004 记录立即释放回 DU-2 relayer（本步骤只扮演 DU-3 消费方）
            if r.record_id != ct004[0].record_id:
                store.mark_retry(r.record_id, now_utc)
        check("worker 消费 CT-004 创建任务", ingress.created is True)

    # LCD-003：CT-004 任务持久化确认后 received → processing（生产接线登记见 e2e 报告 §遗留）
    moved = comp.core_service.advance_to_processing(
        submission_id=submission_id, consumer_ack="task_persisted"
    )
    check("L02 received → processing（task_persisted ack）", moved.status == "processing")

    # ---- 认领 + L12（真实 rubric composer + ACL fake adapter） ----
    reader = UploadRegistryReader()
    claimed = orch.claim_task(owner="worker-e2e")
    check("worker 认领任务", claimed is not None)
    with comp.session_factory() as s:
        composer = RubricPromptComposer(s)
    acl = ModelServiceAcl(provider=FakeVendorAdapter())
    engine = AssessmentEngine(composer, reader, acl)
    outcome = engine.run(claimed)
    check("L12 评估成功（rubric+ACL+fake 真实装配）", outcome.ok is True)

    with comp.session_scope() as s:
        payload = dict(outcome.payload)
        payload.pop("attempt_no", None)
        committed = orch.complete_assessment(
            claimed.task_id, owner="worker-e2e", attempt_no=claimed.attempt_no, **payload
        )
        check("L03 完成 scored", committed.outcome == "scored")

    # ---- relay：CT-005 → L02 + projector；CT-006 → projector（同轮或次轮） ----
    tick = comp.relayer_tick()
    check("relay tick 有投递确认", tick.get("confirmed", 0) >= 1)
    tick2 = comp.relayer_tick()
    check(
        "CT-005 与 CT-006 均已确认（两 tick 合计 ≥2）",
        tick.get("confirmed", 0) + tick2.get("confirmed", 0) >= 2,
    )
    q = client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
    check("CT-002 终态 scored", q.status_code == 200 and q.json()["status"] == "scored")

    # ---- 教师链路：登录 → 详情 → 调整 → 展示 → SSR ----
    login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "pw-e2e"}, follow_redirects=False)
    check("教师登录", login.status_code in (200, 303))
    cookies = login.cookies
    teacher_token = cookies.get("teacher_session")
    api_headers = {"Authorization": f"Bearer {teacher_token}"}  # CT-007/008/009 走 Bearer
    detail = client.get(f"/api/v1/teacher/courses/c-01/submissions/{submission_id}", headers=api_headers)
    check("CT-007 详情含 original_grade", detail.status_code == 200 and detail.json().get("original_grade") == "C")
    review = client.put(f"/api/v1/teacher/submissions/{submission_id}/review", json={
        "request_id": uuid.uuid4().hex, "final_grade": "A", "annotation": "过程扎实",
    }, headers=api_headers)
    check("CT-008 调整 final_grade=A", review.status_code == 200)
    pres = client.post("/api/v1/teacher/presentations", json={"group_ids": ["第7组"]}, headers=api_headers)
    check("CT-009 生成展示视图", pres.status_code == 200 and pres.json().get("presentation_id"))
    page = client.get(f"/teacher/submissions/{submission_id}", cookies=cookies)
    check("SSR 提交详情页含 final=A 与批注", page.status_code == 200 and "过程扎实" in page.text)

    # ---- 负例：错误邀请码 → rejected ----
    bad = client.post("/api/v1/submissions", json={
        "submission_uuid": uuid.uuid4().hex, "invite_code": "NOPE",
        "student_name": "张三", "group_name": "第7组", "assignment": "hw-01",
        "material_chunks": [{"category": "代码", "filename": "a.py", "content_ref": "x"}],
    }, headers=headers)
    check("归属拒绝 → status=rejected", bad.status_code == 200 and bad.json()["status"] == "rejected")

    print()
    comp.engine.dispose()  # Windows：释放 SQLite 文件锁后再清理临时目录
    if FAILURES:
        print(f"E2E FAILED: {len(FAILURES)} 项失败")
        return 1
    print("E2E_OK: SCENARIO-001 主链路（真实组合根 + relay + rubric/ACL fake）全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
