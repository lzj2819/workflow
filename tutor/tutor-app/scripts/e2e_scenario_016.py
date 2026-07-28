"""SCENARIO-016 验收 E2E（CCR-001 方案 A 实施后；AC-NFR-004-01 完整链路）。

链路：到期标记 → CT-011 确认（审计先行）→ CT-012 三消费方（MOD-02 材料/提交清除、
MOD-04 评分清除+墓碑、读模型清除）→ CT-014 + CT-015 双回流 → 批次完成。

六项验收条件：
1. 到期批次标记 + CT-011 确认成功，DeletionConfirmed 审计先于清除写入；
2. 双回流语义：CT-014 单路到达批次保持 executing，CT-015 到达后 completed，
   RecordsDeleted 审计闭合（含范围/操作者/时间）；
3. 提交材料与提交记录清除（CT-002 deleted/404）且评分记录清除
   （scoring_results/scoring_tasks = 0，墓碑 = 1）——AC-NFR-004-01「评分记录」口径；
4. 教师端不可再读（CT-007 详情 404）；
5. 幂等与重放守卫：重跑（CT-012 重发）无错误不双删、审计不重复追加；
   重放旧 CT-004 被墓碑守卫拒绝（tombstoned，不重建评分任务）；
6. 审计记录永久留存（清除后数量不减）。

运行：python -m scripts.e2e_scenario_016（退出码非零即失败）。
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
from scripts.e2e_scenario_001 import UploadRegistryReader, migrate  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())
    db_url = "sqlite:///file:scenario016?mode=memory&cache=shared&uri=true"
    engine = migrate(db_url)
    settings = Settings(
        database_url=db_url,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="s016-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings, engine=engine)
    with comp.session_scope() as s:
        admin.provision_course(
            s, course_id="c-01", invite_code="INV-01", name="VC2025",
            course_end_time=datetime.now(timezone.utc) - timedelta(days=370),
        )
        admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-s016", course_ids=("c-01",))
    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)

    # ---- 造一份 scored 提交（含评分结果，走真实 worker 侧装配） ----
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

    with comp.session_factory() as s:
        composer = RubricPromptComposer(s)
    outcome = AssessmentEngine(
        composer, UploadRegistryReader(), ModelServiceAcl(provider=FakeVendorAdapter())
    ).run(claimed)
    with comp.session_scope() as s:
        payload = dict(outcome.payload)
        payload.pop("attempt_no", None)
        orch.complete_assessment(claimed.task_id, owner="w", attempt_no=claimed.attempt_no, **payload)
    comp.relayer_tick()
    comp.relayer_tick()
    with comp.session_scope() as s:
        pre_results = s.execute(sa.text("select count(*) from scoring_results")).scalar()
        pre_tasks = s.execute(sa.text("select count(*) from scoring_tasks")).scalar()
    check("前置：评分结果与任务存在", pre_results == 1 and pre_tasks == 1)

    # ---- 条件 1：到期标记 + CT-011 确认（审计先行） ----
    marked = comp.retention.mark_due_batches()
    check("1a. 到期批次已标记（课程结束+1年）", len(marked.marked) >= 1)
    login = client.post(
        "/teacher/login",
        data={"teacher_account": "teacher@example.com", "password": "pw-s016"},
        follow_redirects=False,
    )
    ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}
    with comp.session_scope() as s:
        batch = s.execute(
            sa.text("select batch_id, status from deletion_batches order by created_at desc limit 1")
        ).first()
        audit_before = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
    batch_id = batch[0]
    confirm = client.post(
        f"/api/v1/teacher/deletion-batches/{batch_id}/confirm",
        json={"confirm": True, "exclusions": []},
        headers=ah,
    )
    check("1b. CT-011 确认成功", confirm.status_code == 200)
    with comp.session_scope() as s:
        audit_after = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
    check("1c. DeletionConfirmed 审计先于清除写入", audit_after == audit_before + 1)

    # ---- 条件 2：双回流（CT-012 投递后批次保持 executing，CT-015 到达后 completed） ----
    comp.relayer_tick()  # CT-012 → 三消费方；CT-014/CT-015 入队
    with comp.session_scope() as s:
        mid_status = s.execute(
            sa.text("select status from deletion_batches where batch_id=:b"), {"b": batch_id}
        ).scalar()
    check("2a. CT-012 消费后批次仍为 executing（双回流未齐）", mid_status == "executing")
    comp.relayer_tick()  # CT-014 + CT-015 → retention 双回流聚合
    with comp.session_scope() as s:
        final_status = s.execute(
            sa.text("select status from deletion_batches where batch_id=:b"), {"b": batch_id}
        ).scalar()
        audits = s.execute(
            sa.text("select action, scope, operator, submission_ids from deletion_audit_records order by created_at")
        ).all()
    check("2b. CT-014+CT-015 双到达后批次 completed", final_status == "completed")
    records_deleted = [a for a in audits if a[0] == "RecordsDeleted"]
    check(
        "2c. RecordsDeleted 审计闭合（含范围/操作者/提交集合）",
        len(records_deleted) == 1
        and records_deleted[0][1] == "course"
        and bool(records_deleted[0][2])  # operator=teacher_id（会话身份）
        and submission_id in (records_deleted[0][3] or ""),
    )

    # ---- 条件 3：提交侧 + 评分记录均清除（AC-NFR-004-01 完整口径） ----
    q = client.get(f"/api/v1/submissions/{submission_uuid}", headers=headers)
    check(
        "3a. 已清除提交 CT-002 不可再读（deleted/404）",
        q.status_code in (404, 410) or q.json().get("status") == "deleted",
    )
    with comp.session_scope() as s:
        results_left = s.execute(sa.text("select count(*) from scoring_results")).scalar()
        tasks_left = s.execute(sa.text("select count(*) from scoring_tasks")).scalar()
        tombstones = s.execute(sa.text("select count(*) from assessment_purge_tombstones")).scalar()
    check("3b. 评分记录已清除（scoring_results=0）", results_left == 0)
    check("3c. 评分任务已清除（scoring_tasks=0）", tasks_left == 0)
    check("3d. 最小墓碑已写入（不含评分内容）", tombstones == 1)

    # ---- 条件 4：教师端不可再读 ----
    detail = client.get(f"/api/v1/teacher/courses/c-01/submissions/{submission_id}", headers=ah)
    check("4. 教师端读模型已清除该提交（404/不可见）", detail.status_code in (404, 410))

    # ---- 条件 5：幂等重跑 + 重放守卫 ----
    with comp.session_scope() as s:
        audit_count_pre_rerun = s.execute(
            sa.text("select count(*) from deletion_audit_records")
        ).scalar()
        # 重跑：同批次 CT-012 重发（失败重跑同路径），经 relay 全链路再来一轮
        SqlaOutboxStore(s).enqueue(
            "CT-012",
            {
                "batch_id": batch_id,
                "submission_ids": [submission_id],
                "scope": "course",
                "operator": "teacher@example.com",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "audit_record_id": "audit-rerun",
                "v": 1,
            },
            f"{batch_id}:rerun",
        )
    comp.relayer_tick()
    comp.relayer_tick()
    with comp.session_scope() as s:
        rerun_status = s.execute(
            sa.text("select status from deletion_batches where batch_id=:b"), {"b": batch_id}
        ).scalar()
        audit_count_post_rerun = s.execute(
            sa.text("select count(*) from deletion_audit_records")
        ).scalar()
        tombstones_after = s.execute(sa.text("select count(*) from assessment_purge_tombstones")).scalar()
    check("5a. 重跑（CT-012 重发）无错误，批次保持 completed", rerun_status == "completed")
    check("5b. 重跑不双删（墓碑仍 = 1）", tombstones_after == 1)
    check("5c. 重跑不重复追加审计", audit_count_post_rerun == audit_count_pre_rerun)
    # 重放守卫：旧 CT-004 重放不重建评分任务
    ingress = orch.handle_submission_received(
        {
            "submission_id": submission_id,
            "course_id": "c-01",
            "assignment": "hw-old",
            "student_name": "张三",
            "group_name": "第7组",
            "material_refs": [],
            "missing_items": [],
            "received_at": datetime.now(timezone.utc).isoformat(),
            "v": 1,
        }
    )
    with comp.session_scope() as s:
        tasks_rebuilt = s.execute(sa.text("select count(*) from scoring_tasks")).scalar()
    check(
        "5d. 重放守卫：旧 CT-004 不重建评分任务（tombstoned）",
        ingress.tombstoned and not ingress.created and tasks_rebuilt == 0,
    )

    # ---- 条件 6：审计永久留存 ----
    with comp.session_scope() as s:
        audit_final = s.execute(sa.text("select count(*) from deletion_audit_records")).scalar()
    check("6. 删除审计记录永久留存（不在删除范围）", audit_final >= audit_after)

    print()
    if FAILURES:
        print(f"SCENARIO-016 FAILED: {len(FAILURES)} 项失败")
        return 1
    print("SCENARIO_016_OK: CCR-001 全链路验收通过（AC-NFR-004-01 含评分记录删除可宣称）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
