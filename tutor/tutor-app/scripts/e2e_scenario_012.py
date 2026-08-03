"""B-05 E2E：SCENARIO-012 模型评估调用与失败重试链路（真实组合根 + relay）。

对照 tutor/L0-root/architecture/02-runtime-architecture.md SCENARIO-012：
- 子场景 A：模型首次失败（MODEL_TIMEOUT）→ 任务内自动重试一次 → 成功 → scored；
- 子场景 B：两次均失败 → scoring_failed（不伪造等级）→ 教师端可见失败原因与重试记录。

运行：python scripts/e2e_scenario_012.py（退出码非零即失败）。
"""
from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "worker"), str(ROOT / "shared")]

from fastapi.testclient import TestClient  # noqa: E402

from tutor_shared.outbox import SqlaOutboxStore  # noqa: E402

from assessment_worker.assessment_engine.engine import AssessmentEngine  # noqa: E402
from assessment_worker.model_provider import DIMENSIONS, ModelProviderError  # noqa: E402
from assessment_worker.rubric.composer import RubricPromptComposer  # noqa: E402
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


class ScriptedProvider:
    """按脚本失败的 ModelProvider（标注 fake 来源；不发网络请求）。"""

    def __init__(self, fail_times: int, error: str = "MODEL_TIMEOUT") -> None:
        self._fail_times = fail_times
        self._error = error
        self.calls = 0

    def evaluate(self, request: dict) -> dict:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise ModelProviderError(self._error)
        return {
            "grade": "B",
            "dimension_rationales": [
                {"dimension": d, "rationale": f"scripted ok: {d}"} for d in DIMENSIONS
            ],
            "suggestions": ["scripted suggestion"],
        }


def submit_and_drive(comp, client, headers, assignment: str) -> tuple[str, ScoringOrchestrator]:
    submission_uuid = uuid.uuid4().hex
    r = client.post("/api/v1/submissions", json={
        "submission_uuid": submission_uuid,
        "invite_code": "INV-01",
        "student_name": "张三",
        "group_name": "第7组",
        "assignment": assignment,
        "material_chunks": [{"category": "代码", "filename": "a.py", "content_ref": "x"}],
    }, headers=headers)
    assert r.json()["status"] == "received", r.text
    submission_id = r.json()["submission_id"]
    with comp.session_scope() as s:
        store = SqlaOutboxStore(s)
        due = store.fetch_due(datetime.now(timezone.utc))
        ct004 = [r for r in due if r.contract_id == "CT-004"]
        orch = ScoringOrchestrator(
            session_factory=comp.session_factory,
            lease_store=SqlaTaskLeaseStore(comp.session_factory),
            outbox_store=SqlaOutboxStore(s),
        )
        orch.handle_submission_received(ct004[0].payload)
        store.mark_confirmed(ct004[0].record_id)
        now_utc = datetime.now(timezone.utc)
        for rec in due:
            if rec.record_id != ct004[0].record_id:
                store.mark_retry(rec.record_id, now_utc)
    comp.core_service.advance_to_processing(
        submission_id=submission_id, consumer_ack="task_persisted"
    )
    return submission_id, orch


def run_attempt(comp, orch, provider, composer):
    claimed = orch.claim_task(owner="worker-e2e")
    engine = AssessmentEngine(composer, UploadRegistryReader(), provider)
    return claimed, engine.run(claimed)


def main() -> int:
    data_dir = Path(tempfile.mkdtemp())
    db_url = "sqlite:///file:e2e012?mode=memory&cache=shared&uri=true"
    engine_db = migrate(db_url)
    settings = Settings(
        database_url=db_url,
        data_dir=data_dir,
        contracts_dir=ROOT / "contracts",
        teacher_session_secret="e2e-secret",
        log_level="WARNING",
    )
    comp = build_composition(settings, engine=engine_db)
    with comp.session_scope() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="VC2026")
        admin.import_roster(s, course_id="c-01", entries=[{"student_name": "张三", "group_name": "第7组"}])
    comp.access_gate.provision_teacher(account="teacher@example.com", password="pw-e2e", course_ids=("c-01",))
    app = create_app(settings=settings, composition=comp)
    client = TestClient(app)
    tok = client.post("/api/v1/auth/token", json={
        "invite_code": "INV-01", "student_name": "张三", "group_name": "第7组",
    })
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    with comp.session_factory() as s:
        composer = RubricPromptComposer(s)

    # ---- 子场景 A：首次 MODEL_TIMEOUT → 重试成功 → scored ----
    sub_a, orch_a = submit_and_drive(comp, client, headers, "hw-retry")
    provider_a = ScriptedProvider(fail_times=1)
    claimed_a, outcome_a1 = run_attempt(comp, orch_a, provider_a, composer)
    check("A: 首次评估失败（分类错误）", outcome_a1.ok is False)
    retry = orch_a.fail_assessment(
        claimed_a.task_id, owner="worker-e2e",
        attempt_no=claimed_a.attempt_no, error_kind=outcome_a1.payload["error_kind"],
    )
    check("A: 进入唯一重试（attempts→2）", retry.next_attempt_no == 2)
    outcome_a2 = AssessmentEngine(composer, UploadRegistryReader(), provider_a).run(claimed_a)
    check("A: 重试成功", outcome_a2.ok is True)
    with comp.session_scope() as s:
        payload = dict(outcome_a2.payload)
        payload.pop("attempt_no", None)
        committed = orch_a.complete_assessment(
            claimed_a.task_id, owner="worker-e2e", attempt_no=2, **payload
        )
    check("A: 重试成功回主链路 scored", committed.outcome == "scored")
    comp.relayer_tick()

    # ---- 子场景 B：两次均失败 → scoring_failed（不伪造等级） ----
    sub_b, orch_b = submit_and_drive(comp, client, headers, "hw-fail")
    provider_b = ScriptedProvider(fail_times=99)
    claimed_b, outcome_b1 = run_attempt(comp, orch_b, provider_b, composer)
    orch_b.fail_assessment(
        claimed_b.task_id, owner="worker-e2e",
        attempt_no=claimed_b.attempt_no, error_kind=outcome_b1.payload["error_kind"],
    )
    outcome_b2 = AssessmentEngine(composer, UploadRegistryReader(), provider_b).run(claimed_b)
    fin = orch_b.fail_assessment(
        claimed_b.task_id, owner="worker-e2e",
        attempt_no=2, error_kind=outcome_b2.payload["error_kind"],
    )
    check("B: 第二次失败 → scoring_failed 终态", fin.outcome == "scoring_failed")
    comp.relayer_tick()

    # ---- 教师端验证：A scored 有等级；B scoring_failed 有原因与重试记录、无等级 ----
    login = client.post("/teacher/login", data={"teacher_account": "teacher@example.com", "password": "pw-e2e"}, follow_redirects=False)
    ah = {"Authorization": f"Bearer {login.cookies.get('teacher_session')}"}
    da = client.get(f"/api/v1/teacher/courses/c-01/submissions/{sub_a}", headers=ah)
    check("A: CT-007 含 original_grade=B", da.status_code == 200 and da.json().get("original_grade") == "B")
    db_ = client.get(f"/api/v1/teacher/courses/c-01/submissions/{sub_b}", headers=ah)
    body = db_.json()
    check("B: CT-007 scoring_failed 有 failure_reason + retry_record",
          db_.status_code == 200 and body.get("failure_reason") is not None and body.get("retry_record") is not None)
    check("B: 无任何等级（不伪造）",
          body.get("original_grade") is None and body.get("final_grade") is None)
    page = client.get(f"/teacher/submissions/{sub_b}", cookies=login.cookies)
    check("B: SSR 页展示失败原因、无等级值", page.status_code == 200 and 'class="grade-value"' not in page.text)

    print()
    if FAILURES:
        print(f"E2E FAILED: {len(FAILURES)} 项失败")
        return 1
    print("E2E_OK: SCENARIO-012 模型失败重试链路（重试成功 + scoring_failed 可见性）全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
