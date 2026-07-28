"""Phase 6 保留行为验证演练（CT-011→CT-012→SI-PURGE+MOD-04 评分清除→CT-014/CT-015→批次完成）。

CCR-001 方案 A 已实施（2026-07-23）：AssessmentResult（MOD-04）到期删除接线
落地（CT-012 第三消费方 + 墓碑 + CT-015 双回流）。本演练验证完整删除链路
（提交材料 + 提交记录 + 评分记录 + 读模型）；SCENARIO-016 的六项验收条件
见 scripts/e2e_scenario_016.py。演练末尾断言评分结果已删除（CCR-001 闭环证据）。

运行：python scripts/retention_drill.py（退出码非零即失败）。
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.composition import build_composition  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.main import create_app  # noqa: E402
from course_app.settings import Settings  # noqa: E402
from scripts.e2e_scenario_001 import migrate  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())
    db_url = "sqlite:///file:retention?mode=memory&cache=shared&uri=true"
    engine = migrate(db_url)
    settings = Settings(
        database_url=db_url,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="retention-secret",
        log_level="WARNING",
    )
    # 时钟注入：课程结束时间设为一「年」前 → 批次到期
    comp = build_composition(settings, engine=engine)
    with comp.session_scope() as s:
        admin.provision_course(
            s, course_id="c-01", invite_code="INV-01", name="VC2025",
            course_end_time=datetime.now(timezone.utc) - timedelta(days=370),
        )
        admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-r", course_ids=("c-01",))
    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)

    # ---- 造一份 scored 提交（含评分结果） ----
    tok = client.post("/api/v1/auth/token", json={
        "invite_code": "INV-01", "student_name": "张三", "group_name": "第7组",
    })
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    submission_uuid = uuid.uuid4().hex
    r1 = client.post("/api/v1/submissions", json={
        "submission_uuid": submission_uuid,
        "invite_code": "INV-01",
        "student_name": "张三",
        "group_name": "第7组",
        "assignment": "hw-old",
        "material_chunks": [{"category": "代码", "filename": "a.py", "content_ref": "x"}],
    }, headers=headers)
    submission_id = r1.json()["submission_id"]
    with comp.session_scope() as s:
        store = SqlaOutboxStore(s)
        due = store.fetch_due(datetime.now(timezone.utc))
        ct004 = [r for r in due if r.contract_id == "CT-004"][0]
        orch = ScoringOrchestrator(
            session_factory=comp.session_factory,
            lease_store=SqlaTaskLeaseStore(comp.session_factory),
            outbox_store=SqlaOutboxStore(s),
        )
        orch.handle_submission_received(ct004.payload)
        store.mark_confirmed(ct004.record_id)
        now_utc = datetime.now(timezone.utc)
        for rec in due:
            if rec.record_id != ct004.record_id:
                store.mark_retry(rec.record_id, now_utc)
    comp.core_service.advance_to_processing(submission_id=submission_id, consumer_ack="task_persisted")
    claimed = orch.claim_task(owner="w")
    from assessment_worker.assessment_engine.engine import AssessmentEngine  # noqa: PLC0415
    from assessment_worker.model_acl.acl import ModelServiceAcl  # noqa: PLC0415
    from assessment_worker.model_acl.fake_adapter import FakeVendorAdapter  # noqa: PLC0415
    from assessment_worker.rubric.composer import RubricPromptComposer  # noqa: PLC0415
    from scripts.e2e_scenario_001 import UploadRegistryReader  # noqa: PLC0415

    with comp.session_factory() as s:
        composer = RubricPromptComposer(s)
    outcome = AssessmentEngine(composer, UploadRegistryReader(), ModelServiceAcl(provider=FakeVendorAdapter())).run(claimed)
    with comp.session_scope() as s:
        payload = dict(outcome.payload)
        payload.pop("attempt_no", None)
        orch.complete_assessment(claimed.task_id, owner="w", attempt_no=claimed.attempt_no, **payload)
    comp.relayer_tick()
    comp.relayer_tick()

    # ---- 到期标记 → CT-011 确认 → CT-012 → purge → CT-014 回写 ----
    marked = comp.retention.mark_due_batches()
    check("到期批次已标记（课程结束+1年）", len(marked.marked) >= 1)
    login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "pw-r"}, follow_redirects=False)
    ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}
    batches = client.get("/api/v1/teacher/courses", headers=ah)
    check("教师可见课程（读模型正常）", batches.status_code == 200)

    with comp.session_scope() as s:
        batch = s.execute(sa.text("select batch_id, status from deletion_batches order by created_at desc limit 1")).first()
    check("批次处于待确认状态", batch is not None and batch[1] in ("awaiting_confirm", "pending_mark"))
    batch_id = batch[0]

    # 审计先行：确认前审计记录数
    with comp.session_scope() as s:
        audit_before = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
    confirm = client.post(f"/api/v1/teacher/deletion-batches/{batch_id}/confirm", json={"confirm": True, "exclusions": []}, headers=ah)
    check("CT-011 确认成功", confirm.status_code == 200)
    with comp.session_scope() as s:
        audit_after = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
    check("审计记录先于清除写入（confirm 即增）", audit_after > audit_before)

    # relay：CT-012 → SI-PURGE 清除 → CT-014 回写批次
    comp.relayer_tick()
    comp.relayer_tick()
    with comp.session_scope() as s:
        status = s.execute(sa.text("select status from deletion_batches where batch_id=:b"), {"b": batch_id}).scalar()
    check("批次完成（CT-014 回写）", status == "completed")

    # 提交与读模型不可再读；审计留存；评分结果已删除（CCR-001 闭环证据）
    q = client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
    check("已清除提交 → CT-002 不可再读（deleted/404）", q.status_code in (404, 410) or q.json().get("status") == "deleted")
    with comp.session_scope() as s:
        audit_keep = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
        scoring_rows = s.execute(sa.text("select count(*) from scoring_results")).scalar()
        tombstones = s.execute(sa.text("select count(*) from assessment_purge_tombstones")).scalar()
    check("删除审计记录永久留存（不在删除范围）", audit_keep >= audit_after)
    check("AssessmentResult 已删除（CCR-001 闭环）", scoring_rows == 0)
    check("评分清除墓碑已写入（重放守卫）", tombstones == 1)
    detail = client.get(f"/api/v1/teacher/courses/c-01/submissions/{submission_id}", headers=ah)
    check("教师端读模型已清除该提交（404/不可见）", detail.status_code in (404, 410))

    print()
    if FAILURES:
        print(f"RETENTION DRILL FAILED: {len(FAILURES)} 项失败")
        return 1
    print("RETENTION_DRILL_OK: 保留删除链路（提交侧 + 评分记录）验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
