"""Wave 3 集成冒烟：M05-IC-02 端口兼容性 + L14→L15/L16→L17 教师端/审核链路。

验证项（用户指定）：
1. M05-IC-02 兼容性：同一数据集上由单一 StubReadModel 同时实现 L15 的 query()
   与 L16 的 group_view() 两个消费侧面（证明 PROJECTOR 单实现可服务两叶子）。
2. L14→L15/L16→L17 真实链路：真实状态/错误/空结果展示（scored+复核调整、
   scoring_failed 无等级、无提交小组 NO_AVAILABLE_SUBMISSION）。
3. 409 映射统一验证：scoring_failed 无原始等级时设 final_grade → HTTP 409 +
   NO_ORIGINAL_GRADE；仅批注 → 200（契约错误码不改语义，仅行为核验）。

运行：python scripts/smoke_wave3.py（从 tutor-app 根；退出码非零即失败）。
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
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from tutor_shared.outbox import InMemoryOutboxStore  # noqa: E402

from assessment_worker.scoring_orchestrator.lease_store import SqlaTaskLeaseStore  # noqa: E402
from assessment_worker.scoring_orchestrator.models import (  # noqa: E402
    OrchestratorBase,
    ScoringResult,
    ScoringTask,
)
from assessment_worker.scoring_orchestrator.orchestrator import ScoringOrchestrator  # noqa: E402
from course_app.course_roster import admin  # noqa: E402
from course_app.course_roster.models import Base as RosterBase, RosterEntry  # noqa: E402
from course_app.submission_intake.core.integrity import MaterialMetadata  # noqa: E402
from course_app.submission_intake.core.models import Base as CoreBase, Submission, SubmissionMaterial  # noqa: E402
from course_app.submission_intake.core.service import SubmissionCoreService  # noqa: E402
from course_app.teacher_web.presentation.coordinator import PresentationCoordinator  # noqa: E402
from course_app.teacher_web.presentation.errors import NoAvailableSubmissionError  # noqa: E402
from course_app.teacher_web.presentation.models import Base as PresentationBase  # noqa: E402
from course_app.teacher_web.presentation.ports import AuthContext as L16Auth  # noqa: E402
from course_app.teacher_web.presentation.store import SnapshotStore  # noqa: E402
from course_app.teacher_web.review_command.models import Base as ReviewBase, ReviewRecord  # noqa: E402
from course_app.teacher_web.review_command.router import create_router as create_l14_router  # noqa: E402
from course_app.teacher_web.review_command.service import ReviewCommandService  # noqa: E402
from course_app.teacher_web.review_query.facade import create_facade  # noqa: E402
from course_app.teacher_web.review_query.ports import AuthorizedQueryContext  # noqa: E402
from course_app.teacher_web.ui.views import create_router as create_l17_router  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILURES.append(name)


class StubMetadataReader:
    def read_metadata(self, material_ref: str) -> MaterialMetadata:
        category = {"m-对话": "对话", "m-代码": "代码"}[material_ref]
        return MaterialMetadata(material_ref, category, 64, True, None)


# ---- ACCESS-GATE stubs（三种冻结端口形状，真实实现归 B-03） ----


class Gate14:
    def authorize(self, *, teacher_session: str | None, submission_id: str):
        from course_app.teacher_web.review_command.ports import AccessGrant

        if not teacher_session:
            from course_app.teacher_web.review_command.errors import AuthInvalidError

            raise AuthInvalidError("missing session")
        return AccessGrant(operator="teacher-1")


class Gate15:
    def authorize(self, *, teacher_session: str, course_id: str | None):
        if course_id == "c-99":
            from course_app.teacher_web.review_query.errors import AccessDeniedError

            raise AccessDeniedError("no scope")
        return AuthorizedQueryContext(teacher_id="teacher-1", course_id=course_id)


class Gate16:
    def authorize(self, *, authorization: str | None) -> L16Auth:
        if not authorization:
            from course_app.teacher_web.presentation.errors import AuthInvalidError

            raise AuthInvalidError("missing")
        return L16Auth(teacher_id="teacher-1", course_ids=("c-01",))


class RetentionStub:
    def list_batches(self, **kwargs) -> tuple:
        return ()


# ---- M05-IC-02 单实现双侧面（兼容性验证主体；真实 PROJECTOR 归 B-03） ----


class StubReadModel:
    """同一数据集上同时实现 L15 query() 与 L16 group_view()。"""

    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def _submission_rows(self):
        from types import SimpleNamespace as NS

        with self._sf() as s:
            subs = [
                NS(submission_id=r.submission_id, course_id=r.course_id,
                   student_name=r.student_name, group_name=r.group_name, status=r.status)
                for r in s.scalars(select(Submission)).all()
            ]
            mats = [
                NS(submission_id=m.submission_id, category=m.category, material_ref=m.material_ref)
                for m in s.scalars(select(SubmissionMaterial)).all()
            ]
            reviews = [
                NS(submission_id=r.submission_id, original_grade=r.original_grade,
                   final_grade=r.final_grade, annotation=r.annotation,
                   operator=r.operator, updated_at=r.updated_at)
                for r in s.scalars(select(ReviewRecord)).all()
            ]
            tasks = [
                NS(submission_id=t.submission_id, status=t.status,
                   failure_reason=t.failure_reason, retry_record=t.retry_record)
                for t in s.scalars(select(ScoringTask)).all()
            ]
            results = [
                NS(submission_id=r.submission_id, original_grade=r.original_grade,
                   dimension_rationales=r.dimension_rationales,
                   teacher_suggestions=r.teacher_suggestions, scored_at=r.scored_at)
                for r in s.scalars(select(ScoringResult)).all()
            ]
        return subs, mats, reviews, tasks, results

    def _group_ids(self):
        with self._sf() as s:
            return sorted({r.group_name for r in s.scalars(select(RosterEntry)).all()})

    # ---- L15 侧面：ReadModelQueryPort.query() ----
    def query(self, *, course_id=None, group_id=None, student_id=None, submission_id=None):
        from course_app.teacher_web.review_query.ports import ReadModelView

        subs, mats, reviews, tasks, results = self._submission_rows()
        by_id = {r.submission_id: r for r in reviews}
        task_by_sub = {t.submission_id: t for t in tasks}
        result_by_sub = {r.submission_id: r for r in results}
        out = []
        for sub in subs:
            if submission_id and sub.submission_id != submission_id:
                continue
            rev = by_id.get(sub.submission_id)
            task = task_by_sub.get(sub.submission_id)
            out.append({
                "submission_id": sub.submission_id,
                "course_id": sub.course_id,
                "student_name": sub.student_name,
                "group_name": sub.group_name,
                "status": sub.status,
                "original_grade": rev.original_grade if rev else None,
                "final_grade": rev.final_grade if rev else None,
                "annotations": (
                    [{"text": rev.annotation, "operator": rev.operator, "updated_at": str(rev.updated_at)}]
                    if rev and rev.annotation else []
                ),
                "failure_reason": task.failure_reason if task and task.status == "scoring_failed" else None,
                "retry_record": task.retry_record if task and task.status == "scoring_failed" else None,
            })
        top = {}
        if submission_id and out:
            sub = out[0]
            rev = by_id.get(submission_id)
            task = task_by_sub.get(submission_id)
            result = result_by_sub.get(submission_id)
            cats = {m.category for m in mats if m.submission_id == submission_id}
            top = {
                "material_refs": tuple(
                    {"category": m.category, "ref": m.material_ref}
                    for m in mats if m.submission_id == submission_id
                ),
                "status": sub["status"],
                "original_grade": result.original_grade if result else None,
                "dimension_rationales": tuple(result.dimension_rationales) if result else (),
                "teacher_suggestions": tuple(result.teacher_suggestions) if result else (),
                "annotations": tuple(sub["annotations"]),
                "final_grade": rev.final_grade if rev else None,
                "missing_marks": tuple({"对话", "代码", "截图", "结果"} - cats),
                "failure_reason": sub["failure_reason"],
                "retry_record": sub["retry_record"],
            }
        return ReadModelView(
            courses=({"course_id": "c-01", "name": "VC2026"},),
            groups=tuple({"group_id": g} for g in self._group_ids()),
            students=(),
            submissions=tuple(out),
            **top,
        )

    # ---- L16 侧面：ReadModelQueryPort.group_view() ----
    def group_view(self, *, group_id: str, course_id=None, student_id=None, submission_id=None):
        from course_app.teacher_web.presentation.ports import (
            AnnotationView,
            GroupReadView,
            MaterialRef,
            SubmissionView,
        )

        subs, mats, reviews, tasks, _results = self._submission_rows()
        by_id = {r.submission_id: r for r in reviews}
        views = []
        for sub in subs:
            if sub.group_name != group_id:
                continue
            rev = by_id.get(sub.submission_id)
            views.append(SubmissionView(
                submission_id=sub.submission_id,
                status=sub.status,
                material_refs=tuple(
                    MaterialRef(m.category, m.material_ref) for m in mats if m.submission_id == sub.submission_id
                ),
                original_grade=rev.original_grade if rev else None,
                final_grade=rev.final_grade if rev else None,
                annotations=(
                    (AnnotationView(rev.operator, rev.annotation[:40], str(rev.updated_at)),)
                    if rev and rev.annotation else ()
                ),
                missing_marks=tuple({"对话", "代码", "截图", "结果"} - {m.category for m in mats if m.submission_id == sub.submission_id}),
            ))
        if not views:
            return GroupReadView(course_id="c-01", group_id=group_id, submissions=())
        return GroupReadView(course_id="c-01", group_id=group_id, submissions=tuple(views))


# ---- L17 进程内 API 客户端（TeacherApiClient 协议实现，仅接线不实现后端） ----


class InProcessTeacherApiClient:
    def __init__(self, query_service, review_service, coordinator) -> None:
        self._query = query_service
        self._review = review_service
        self._coordinator = coordinator
        self.confirm_calls: list[dict] = []

    def create_session(self, *, teacher_account: str, password: str):
        from course_app.teacher_web.ui.client import TeacherSession

        return TeacherSession(token="sess-1")

    def query_view(self, *, teacher_session: str, course_id=None, group_id=None, student_id=None, submission_id=None) -> dict:
        if submission_id:
            return self._query.submission_detail(
                teacher_session=teacher_session, course_id=course_id or "c-01", submission_id=submission_id
            )
        if group_id:
            return self._query.group_list(teacher_session=teacher_session, course_id=course_id, group_id=group_id)
        if course_id:
            return self._query.group_list(teacher_session=teacher_session, course_id=course_id)
        return self._query.course_list(teacher_session=teacher_session)

    def save_review(self, *, teacher_session: str, submission_id: str, request_id: str,
                    annotation=None, final_grade=None, adjustment_reason=None) -> dict:
        outcome = self._review.apply_review(
            operator="teacher-1", submission_id=submission_id, request_id=request_id,
            annotation=annotation, final_grade=final_grade, adjustment_reason=adjustment_reason,
        )
        return outcome.payload

    def generate_presentation(self, *, teacher_session: str, group_ids) -> dict:
        snap = self._coordinator.generate(auth=L16Auth("teacher-1", ("c-01",)), group_ids=list(group_ids))
        return {"presentation_id": snap.presentation_id, "blocks": list(snap.blocks)}

    def confirm_deletion_batch(self, *, teacher_session: str, batch_id: str, confirm: bool = True, exclusions=None) -> dict:
        self.confirm_calls.append({"batch_id": batch_id, "confirm": confirm, "exclusions": list(exclusions or [])})
        return {"batch_id": batch_id, "batch_status": "confirmed", "pending_deletion_scope": []}


def main() -> int:
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for base in (RosterBase, CoreBase, OrchestratorBase, ReviewBase, PresentationBase):
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

    # ---- 数据：L01 课程/名单；L02 两个提交；L03 scored / scoring_failed ----
    with tx() as s:
        admin.provision_course(s, course_id="c-01", invite_code="INV-01", name="VC2026")
        admin.import_roster(s, course_id="c-01", entries=[
            {"student_name": "张三", "group_name": "第7组"},
            {"student_name": "李四", "group_name": "第9组"},
        ])
    outbox = InMemoryOutboxStore()
    core = SubmissionCoreService(session_factory=tx, outbox_store=outbox, metadata_reader=StubMetadataReader())

    def make_submission(student: str, group: str, assignment: str, refs: list[str]):
        return core.confirm_received(
            submission_uuid=uuid.uuid4().hex, course_id="c-01", assignment=assignment,
            student_name=student, group_name=group, material_refs=refs,
            expected_categories=["对话", "代码", "截图", "结果"], verification={"verified": True},
        )

    sub1 = make_submission("张三", "第7组", "hw-01", ["m-对话", "m-代码"])
    sub2 = make_submission("张三", "第7组", "hw-02", ["m-对话"])
    core.advance_to_processing(submission_id=sub1.submission_id, consumer_ack="task_persisted")
    core.advance_to_processing(submission_id=sub2.submission_id, consumer_ack="task_persisted")

    outbox2 = InMemoryOutboxStore()
    orch = ScoringOrchestrator(session_factory=sm, lease_store=SqlaTaskLeaseStore(sm), outbox_store=outbox2)
    ct004s = {r.payload["submission_id"]: r.payload for r in outbox._records.values() if r.contract_id == "CT-004"}

    # sub1 → scored（B）
    orch.handle_submission_received(ct004s[sub1.submission_id])
    c1 = orch.claim_task(owner="worker-1")
    orch.complete_assessment(
        c1.task_id, owner="worker-1", attempt_no=c1.attempt_no,
        original_grade="B",
        dimension_rationales=[{"dimension": d, "rationale": f"ok {d}"} for d in ("需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性")],
        teacher_suggestions=["s1"],
    )
    core.apply_scoring_outcome(submission_id=sub1.submission_id, outcome="scored")

    # sub2 → scoring_failed（重试一次后仍失败）
    orch.handle_submission_received(ct004s[sub2.submission_id])
    c2 = orch.claim_task(owner="worker-1")
    r = orch.fail_assessment(c2.task_id, owner="worker-1", attempt_no=c2.attempt_no, error_kind="MODEL_TIMEOUT")
    check("L03 首次失败进入唯一重试（attempts→2）", r.next_attempt_no == 2)
    # 任务内重试：同一租约下以 attempt_no=2 直接回调（无需重新认领）
    fin = orch.fail_assessment(c2.task_id, owner="worker-1", attempt_no=2, error_kind="MODEL_TIMEOUT")
    check("L03 第二次失败 → scoring_failed 终态", fin.outcome == "scoring_failed")
    core.apply_scoring_outcome(submission_id=sub2.submission_id, outcome="scoring_failed", failure_reason="MODEL_TIMEOUT")

    # ---- L14：M05-IC-01 创建复核记录 + CT-008 调整 ----
    review_svc = ReviewCommandService(tx)
    created = review_svc.create_review_record(submission_id=sub1.submission_id, original_grade="B")
    check("L14 M05-IC-01 创建复核记录（original_grade=B）", created["original_grade"] == "B")
    outcome = review_svc.apply_review(
        operator="teacher-1", submission_id=sub1.submission_id, request_id="req-1",
        annotation="过程扎实", final_grade="A",
    )
    check("L14 调整 final_grade=A + 批注", outcome.payload["final_grade"] == "A")
    dup = review_svc.apply_review(
        operator="teacher-1", submission_id=sub1.submission_id, request_id="req-1",
        annotation="过程扎实", final_grade="A",
    )
    check("L14 同 request_id 幂等", dup.duplicate is True)

    # ---- M05-IC-02 兼容性：单实现双侧面 ----
    read_model = StubReadModel(tx)
    query_svc = create_facade(access_gate=Gate15(), read_model=read_model, retention_view=RetentionStub())
    detail = query_svc.submission_detail(teacher_session="sess-1", course_id="c-01", submission_id=sub1.submission_id)
    check("L15 提交详情含 original/final/annotation",
          detail.get("original_grade") == "B" and detail.get("final_grade") == "A"
          and any("过程扎实" in (a.get("text") or "") for a in detail.get("annotations", [])))
    failed_view = query_svc.submission_detail(teacher_session="sess-1", course_id="c-01", submission_id=sub2.submission_id)
    check("L15 scoring_failed 展示原因+重试记录、无等级",
          failed_view.get("failure_reason") is not None and failed_view.get("retry_record") is not None
          and failed_view.get("original_grade") is None and failed_view.get("final_grade") is None)

    coordinator = PresentationCoordinator(read_model=read_model, store=SnapshotStore(tx))
    snap = coordinator.generate(auth=L16Auth("teacher-1", ("c-01",)), group_ids=["第7组"])
    check("L16 生成展示快照（blocks 非空）", len(list(snap.blocks)) == 1)
    snap2 = coordinator.generate(auth=L16Auth("teacher-1", ("c-01",)), group_ids=["第7组"])
    check("L16 同参数幂等命中（同 presentation_id）", snap2.presentation_id == snap.presentation_id)
    try:
        coordinator.generate(auth=L16Auth("teacher-1", ("c-01",)), group_ids=["第9组"])
        check("L16 无提交小组 → NO_AVAILABLE_SUBMISSION", False)
    except NoAvailableSubmissionError:
        check("L16 无提交小组 → NO_AVAILABLE_SUBMISSION", True)

    # ---- L17：SSR 页面（真实数据驱动） ----
    app = FastAPI()
    app.include_router(create_l17_router(api_client=InProcessTeacherApiClient(query_svc, review_svc, coordinator)))
    client = TestClient(app)
    login = client.get("/teacher/login")
    check("L17 登录页 200 且无令牌明文", login.status_code == 200 and "sess-1" not in login.text)

    cookies = {"teacher_session": "sess-1"}
    courses = client.get("/teacher/courses", cookies=cookies)
    check("L17 课程页含课程", courses.status_code == 200 and "c-01" in courses.text)
    detail_page = client.get(f"/teacher/submissions/{sub1.submission_id}", cookies=cookies)
    check("L17 提交详情页含 final=A 与批注",
          detail_page.status_code == 200 and "过程扎实" in detail_page.text and "A" in detail_page.text)
    failed_page = client.get(f"/teacher/submissions/{sub2.submission_id}", cookies=cookies)
    check("L17 scoring_failed 页展示原因、显式缺失、无等级值",
          failed_page.status_code == 200 and "MODEL_TIMEOUT" in failed_page.text
          and 'class="grade-value"' not in failed_page.text
          and 'class="missing-value"' in failed_page.text)
    pres_page = client.post("/teacher/presentations", data={"group_ids": "第7组"}, cookies=cookies, follow_redirects=False)
    check("L17 展示视图页生成", pres_page.status_code in (200, 303))

    # ---- 409 映射统一验证（L14 router，真实 HTTP） ----
    app14 = FastAPI()
    app14.include_router(create_l14_router(service=review_svc, access_gate=Gate14()))
    c14 = TestClient(app14)
    conflict = c14.put(
        f"/api/v1/teacher/submissions/{sub2.submission_id}/review",
        json={"request_id": uuid.uuid4().hex, "final_grade": "A"},
        headers={"Authorization": "Bearer sess-1"},
    )
    check("409 映射：无原始等级设 final_grade → 409 + NO_ORIGINAL_GRADE",
          conflict.status_code == 409 and "NO_ORIGINAL_GRADE" in conflict.text)
    note = c14.put(
        f"/api/v1/teacher/submissions/{sub2.submission_id}/review",
        json={"request_id": uuid.uuid4().hex, "annotation": "已知悉失败原因"},
        headers={"Authorization": "Bearer sess-1"},
    )
    check("409 映射：仅批注 → 200（不触发 NO_ORIGINAL_GRADE）", note.status_code == 200)

    print()
    if FAILURES:
        print(f"SMOKE FAILED: {len(FAILURES)} 项失败")
        return 1
    print("SMOKE_OK: Wave 3 教师端/审核链路（M05-IC-02 兼容 + L14→L15/L16→L17 + 409）全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
