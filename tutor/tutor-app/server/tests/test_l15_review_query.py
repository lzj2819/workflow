"""L15 CMP-REVIEW-QUERY 单元测试（fastapi TestClient + 端口 stub 注入）。

覆盖 verification-checklist 语义断言：
- 课程/小组/学生/提交详情各视图返回 CT-007 出参字段（material_refs/status/
  original_grade/dimension_rationales/teacher_suggestions/annotations/
  final_grade）；
- 提交详情含 deletion_batches[]（batch_id/retention_due_at/scope/
  batch_status/exclusions），无批次返回空数组（LCD-RQ-003）；
- scoring_failed → failure_reason + retry_record，无任何等级字段填充
  （LCD-RQ-002，不伪造等级）；
- 无权课程 → 403 FORBIDDEN 且 ACCESS-GATE 端口被调用（AccessDeniedLogged
  由其实现）；缺会话 → 401 AUTH_INVALID；
- 读模型/批次端口失败 → 503 可重试失败，禁止部分成功（LCD-RQ-004）；
- 应答字段与 contracts/ct-007.json 一致；读模型经 M05-IC-02 端口注入
  （本叶子不建读模型表，测试以内存 stub 充当 PROJECTOR 投影结果）。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.teacher_web.review_query import (  # noqa: E402
    AccessDeniedError,
    AuthInvalidError,
    AuthorizedQueryContext,
    ReadModelUnavailableError,
    ReadModelView,
    RetentionBatchView,
    RetentionViewUnavailableError,
    create_router,
)

CONTRACTS_DIR = ROOT / "contracts"

SESSION = "sess-teacher-1"
COURSE = "course-1"
GROUP1 = "group-1"
GROUP2 = "group-2"
STUDENT1 = "student-1"
STUDENT2 = "student-2"
SUB_SCORED = "sub-scored"
SUB_FAILED = "sub-failed"
BATCH = "batch-1"


def load_contract(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


# ---- 端口 stub（M05-IC-02 / M05-IC-06 / ACCESS-GATE 的注入实现） ----


class StubAccessGate:
    """ACCESS-GATE 端口 stub：记录调用；拒绝时抛 AccessDeniedError 并登记
    AccessDeniedLogged（真实持久化归 backfill 实现）。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.denied_logged: list[str] = []
        self.valid_sessions = {SESSION}
        self.allowed_courses = {COURSE}

    def authorize(self, *, teacher_session, course_id):
        self.calls.append((teacher_session, course_id))
        if teacher_session not in self.valid_sessions:
            raise AuthInvalidError("unknown teacher session")
        if course_id is not None and course_id not in self.allowed_courses:
            self.denied_logged.append(course_id)  # AccessDeniedLogged 由其实现
            raise AccessDeniedError("course scope not authorized")
        return AuthorizedQueryContext(teacher_id="teacher-1", course_id=course_id)


class StubReadModel:
    """M05-IC-02 端口 stub：内存中充当 PROJECTOR 投影后的 ST-READ-MODEL 事实。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None

    def query(self, *, course_id=None, group_id=None, student_id=None,
              submission_id=None):
        self.calls.append(
            {
                "course_id": course_id,
                "group_id": group_id,
                "student_id": student_id,
                "submission_id": submission_id,
            }
        )
        if self.error is not None:
            raise self.error
        if submission_id is not None:
            return self._submission_view(submission_id)
        if student_id is not None:
            return self._student_view(student_id)
        if group_id is not None:
            return self._group_view(group_id)
        if course_id is not None:
            return self._course_groups_view(course_id)
        return ReadModelView(
            courses=({"course_id": COURSE, "title": "课程一"},)
        )

    @staticmethod
    def _course_groups_view(course_id: str) -> ReadModelView:
        if course_id != COURSE:
            return ReadModelView()
        return ReadModelView(
            groups=(
                {"group_id": GROUP1, "name": "一组"},
                {"group_id": GROUP2, "name": "二组"},
            )
        )

    @staticmethod
    def _group_view(group_id: str) -> ReadModelView:
        groups = {GROUP1: "一组", GROUP2: "二组"}
        if group_id not in groups:
            return ReadModelView()
        students = {
            GROUP1: ({"student_id": STUDENT1, "name": "学生一"},),
            GROUP2: ({"student_id": STUDENT2, "name": "学生二"},),
        }
        return ReadModelView(
            groups=({"group_id": group_id, "name": groups[group_id]},),
            students=students[group_id],
        )

    @staticmethod
    def _student_view(student_id: str) -> ReadModelView:
        known = {
            STUDENT1: (SUB_SCORED,),
            STUDENT2: (SUB_FAILED,),
        }
        if student_id not in known:
            return ReadModelView()
        return ReadModelView(
            students=({"student_id": student_id, "name": "学生"},),
            submissions=tuple(
                {"submission_id": sid, "assignment": "作业一"}
                for sid in known[student_id]
            ),
        )

    @staticmethod
    def _submission_view(submission_id: str) -> ReadModelView:
        if submission_id == SUB_SCORED:
            return ReadModelView(
                submissions=(
                    {"submission_id": SUB_SCORED, "student_id": STUDENT1},
                ),
                material_refs=(
                    {"ref": "ref-1", "category": "代码", "filename": "main.py"},
                ),
                status="scored",
                original_grade="B",
                dimension_rationales=(
                    {"dimension": "正确性", "rationale": "基本正确"},
                ),
                teacher_suggestions=("补充边界测试",),
                annotations=(
                    {
                        "text": "整体不错",
                        "operator": "teacher-1",
                        "updated_at": "2026-07-01T08:00:00+00:00",
                    },
                ),
                final_grade="A",
            )
        if submission_id == SUB_FAILED:
            return ReadModelView(
                submissions=(
                    {"submission_id": SUB_FAILED, "student_id": STUDENT2},
                ),
                material_refs=(
                    {"ref": "ref-2", "category": "对话", "filename": "d.md"},
                ),
                status="scoring_failed",
                failure_reason="scoring agent timeout",
                retry_record={
                    "attempts": 2,
                    "last_attempt_at": "2026-07-02T09:00:00+00:00",
                    "result": "failed",
                },
            )
        return ReadModelView()


class StubRetentionView:
    """M05-IC-06 端口 stub：按 submission_id 返回删除批次只读视图。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.by_submission = {
            SUB_SCORED: (
                RetentionBatchView(
                    batch_id=BATCH,
                    retention_due_at="2027-07-01T00:00:00+00:00",
                    scope="course",
                    batch_status="pending",
                    exclusions=("sub-excluded",),
                    cleared_submission_ids=(),
                ),
            )
        }

    def list_batches(self, *, course_id=None, batch_id=None, submission_id=None):
        self.calls.append(
            {
                "course_id": course_id,
                "batch_id": batch_id,
                "submission_id": submission_id,
            }
        )
        if self.error is not None:
            raise self.error
        return self.by_submission.get(submission_id, ())


class ReviewQueryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = StubAccessGate()
        self.read_model = StubReadModel()
        self.retention = StubRetentionView()
        app = FastAPI()
        app.include_router(
            create_router(
                access_gate=self.gate,
                read_model=self.read_model,
                retention_view=self.retention,
            )
        )
        self.client = TestClient(app)
        self.auth = {"Authorization": f"Bearer {SESSION}"}

    # ---- 课程/小组/学生层级视图 ----

    def test_course_list_returns_courses(self) -> None:
        resp = self.client.get("/api/v1/teacher/courses", headers=self.auth)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["courses"], [{"course_id": COURSE, "title": "课程一"}])
        # ACCESS-GATE 端口被调用（课程列表不带 course_id 范围）。
        self.assertEqual(self.gate.calls, [(SESSION, None)])

    def test_group_list_returns_groups(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/groups", headers=self.auth
        )
        self.assertEqual(resp.status_code, 200)
        groups = resp.json()["groups"]
        self.assertEqual([g["group_id"] for g in groups], [GROUP1, GROUP2])
        self.assertEqual(self.gate.calls, [(SESSION, COURSE)])

    def test_group_list_with_group_filter_returns_students(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/groups",
            params={"group_id": GROUP1},
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["groups"][0]["group_id"], GROUP1)
        self.assertEqual(body["students"][0]["student_id"], STUDENT1)

    def test_student_detail_returns_student_and_submissions(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/students/{STUDENT1}",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["students"][0]["student_id"], STUDENT1)
        self.assertEqual(
            [s["submission_id"] for s in body["submissions"]], [SUB_SCORED]
        )

    # ---- 提交详情（CT-007 出参超集） ----

    def test_submission_detail_scored_full_fields(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{SUB_SCORED}",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["submissions"][0]["submission_id"], SUB_SCORED)
        self.assertEqual(body["material_refs"][0]["ref"], "ref-1")
        self.assertEqual(body["status"], "scored")
        self.assertEqual(body["original_grade"], "B")
        self.assertEqual(
            body["dimension_rationales"][0]["dimension"], "正确性"
        )
        self.assertEqual(body["teacher_suggestions"], ["补充边界测试"])
        annotation = body["annotations"][0]
        self.assertEqual(annotation["operator"], "teacher-1")
        self.assertEqual(body["final_grade"], "A")
        # deletion_batches[] 必需出参：完整批次字段。
        batches = body["deletion_batches"]
        self.assertEqual(len(batches), 1)
        batch = batches[0]
        for key in (
            "batch_id",
            "retention_due_at",
            "scope",
            "batch_status",
            "exclusions",
        ):
            self.assertIn(key, batch)
        self.assertEqual(batch["batch_id"], BATCH)
        self.assertEqual(batch["exclusions"], ["sub-excluded"])
        # M05-IC-02 与 M05-IC-06 端口均被经端口注入调用。
        self.assertEqual(self.read_model.calls[0]["submission_id"], SUB_SCORED)
        self.assertEqual(self.retention.calls[0]["submission_id"], SUB_SCORED)

    def test_submission_detail_scoring_failed_no_fabricated_grade(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{SUB_FAILED}",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "scoring_failed")
        self.assertEqual(body["failure_reason"], "scoring agent timeout")
        self.assertEqual(body["retry_record"]["attempts"], 2)
        # 不伪造等级：无任何等级/依据/建议字段填充。
        for key in (
            "original_grade",
            "final_grade",
            "dimension_rationales",
            "teacher_suggestions",
        ):
            self.assertNotIn(key, body)
        # 无批次也必须返回空数组（LCD-RQ-003），字段不省略。
        self.assertEqual(body["deletion_batches"], [])

    # ---- 授权与错误语义 ----

    def test_forbidden_course_returns_403_and_gate_called(self) -> None:
        resp = self.client.get(
            "/api/v1/teacher/courses/course-9/groups", headers=self.auth
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "FORBIDDEN")
        # ACCESS-GATE 端口被调用；AccessDeniedLogged 由其实现（stub 登记）。
        self.assertEqual(self.gate.calls, [(SESSION, "course-9")])
        self.assertEqual(self.gate.denied_logged, ["course-9"])
        # 授权在 GATE 终止：读模型端口未被调用。
        self.assertEqual(self.read_model.calls, [])

    def test_missing_session_returns_401(self) -> None:
        resp = self.client.get("/api/v1/teacher/courses")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_unknown_session_returns_401(self) -> None:
        resp = self.client.get(
            "/api/v1/teacher/courses",
            headers={"Authorization": "Bearer sess-unknown"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()["code"], "AUTH_INVALID")

    def test_unknown_submission_returns_404(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/sub-unknown",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_unknown_student_returns_404(self) -> None:
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/students/student-9",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["code"], "NOT_FOUND")

    def test_read_model_failure_is_retryable_no_partial_success(self) -> None:
        self.read_model.error = ReadModelUnavailableError("projector down")
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{SUB_SCORED}",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        # 禁止部分成功：不携带 CT-007 业务字段，也不新增公共错误码。
        self.assertNotIn("code", body)
        for key in ("submissions", "material_refs", "status", "deletion_batches"):
            self.assertNotIn(key, body)

    def test_retention_failure_is_retryable_keeps_batches_required(self) -> None:
        self.retention.error = RetentionViewUnavailableError("rg down")
        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{SUB_SCORED}",
            headers=self.auth,
        )
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn("deletion_batches", resp.json())

    # ---- 契约一致性 ----

    def test_response_fields_conform_ct007(self) -> None:
        contract = load_contract("ct-007.json")
        props = set(contract["schemas"]["response"]["properties"])
        status_enum = set(
            contract["schemas"]["response"]["properties"]["status"]["enum"]
        )
        grade_enum = set(
            contract["schemas"]["response"]["properties"]["original_grade"]["enum"]
        )

        resp = self.client.get(
            f"/api/v1/teacher/courses/{COURSE}/submissions/{SUB_SCORED}",
            headers=self.auth,
        )
        body = resp.json()
        # 应答字段为 CT-007 出参子集（additionalProperties=true，但不超集滥用）。
        self.assertLessEqual(set(body), props | {"missing_marks"})
        self.assertIn(body["status"], status_enum)
        self.assertIn(body["original_grade"], grade_enum)
        self.assertIn(body["final_grade"], grade_enum)
        # deletion_batches item 必需字段与契约一致。
        item_required = contract["schemas"]["response"]["properties"][
            "deletion_batches"
        ]["items"]["required"]
        for key in item_required:
            self.assertIn(key, body["deletion_batches"][0])
        # annotations item 必需字段（text/operator/updated_at）。
        annotation_required = contract["schemas"]["response"]["properties"][
            "annotations"
        ]["items"]["required"]
        for key in annotation_required:
            self.assertIn(key, body["annotations"][0])

    def test_hierarchy_responses_use_ct007_field_names(self) -> None:
        contract = load_contract("ct-007.json")
        props = set(contract["schemas"]["response"]["properties"])
        for url in (
            "/api/v1/teacher/courses",
            f"/api/v1/teacher/courses/{COURSE}/groups",
            f"/api/v1/teacher/courses/{COURSE}/students/{STUDENT1}",
        ):
            resp = self.client.get(url, headers=self.auth)
            self.assertEqual(resp.status_code, 200)
            self.assertLessEqual(set(resp.json()), props)


if __name__ == "__main__":
    unittest.main()
