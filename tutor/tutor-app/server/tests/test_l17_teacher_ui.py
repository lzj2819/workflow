"""L17 CMP-TEACHER-UI 单元测试（fastapi TestClient + 注入式 spy 客户端）。

覆盖 verification-checklist 语义断言：
- 课程/小组/学生/提交详情页渲染：材料清单、状态、原始等级、五维依据、
  教师建议、批注、最终等级编辑入口（stub API 数据驱动）；
- 展示视图页渲染 blocks 与 missing_marks（缺失可见不隐藏）；
- 删除批次页渲染批次状态/到期/范围/排除标记 + 确认入口（仅发起 CT-011
  调用，spy 断言，不实现端点）；
- scoring_failed 页展示失败原因与重试结果，无等级显示；
- 最终等级编辑表单提交走 CT-008 客户端（spy 断言 request_id 幂等键携带）；
- 登录页仅对接会话 API；页面不含 secret/令牌明文；
- 无权限访问 → 403 访问拒绝页；未登录 → 重定向登录页。

注入：TeacherApiClient 全部用 spy stub（L14/L15/L16 同波次未集成，按冻结
契约注入，不做跨叶子真实接线）；CT-011 只断言调用、不断言服务端效果。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.teacher_web.ui.client import (  # noqa: E402
    AUTH_INVALID,
    BATCH_NOT_EXPIRED,
    FORBIDDEN,
    NO_AVAILABLE_SUBMISSION,
    NO_ORIGINAL_GRADE,
    TeacherApiError,
    TeacherSession,
)
from course_app.teacher_web.ui.views import SESSION_COOKIE, create_router  # noqa: E402

TOKEN = "sess-token-xyz"
SUB_ID = "sub-1"

DETAIL_PAYLOAD = {
    "submission_id": SUB_ID,
    "material_refs": [
        {"ref": "ref-1", "category": "对话", "filename": "dialog.md"},
        {"ref": "ref-2", "category": "代码", "filename": "main.py"},
    ],
    "status": "scored",
    "original_grade": "B",
    "dimension_rationales": [
        {"dimension": "正确性", "rationale": "核心逻辑正确"},
        {"dimension": "过程留痕", "rationale": "对话记录完整"},
        {"dimension": "代码质量", "rationale": "结构清晰"},
        {"dimension": "结果呈现", "rationale": "截图充分"},
        {"dimension": "协作", "rationale": "分工明确"},
    ],
    "teacher_suggestions": ["补充异常处理", "完善测试"],
    "annotations": [
        {"text": "整体不错", "operator": "teacher-1", "updated_at": "2026-07-01T09:00:00Z"}
    ],
    "final_grade": "A",
}

FAILED_PAYLOAD = {
    "submission_id": "sub-fail",
    "material_refs": [{"ref": "ref-9", "category": "对话", "filename": "dialog.md"}],
    "status": "scoring_failed",
    "failure_reason": "rubric 加载失败",
    "retry_record": {"attempts": 2, "result": "仍失败"},
}

BATCH = {
    "batch_id": "batch-1",
    "retention_due_at": "2026-07-15T00:00:00Z",
    "scope": "course-1 全部提交",
    "batch_status": "pending_confirmation",
    "exclusions": ["sub-keep-1"],
}


class SpyTeacherApiClient:
    """冻结契约注入 stub：记录调用（spy），按编程返回/抛错。"""

    def __init__(self) -> None:
        self.session_calls: list[dict] = []
        self.view_calls: list[dict] = []
        self.review_calls: list[dict] = []
        self.presentation_calls: list[dict] = []
        self.confirm_calls: list[dict] = []
        self.view_response: dict = {}
        self.review_response: dict = {
            "review_record": {
                "original_grade": "B",
                "final_grade": "A",
                "annotation": "整体不错",
                "operator": "teacher-1",
                "updated_at": "2026-07-02T10:00:00Z",
            }
        }
        self.presentation_response: dict = {}
        self.confirm_response: dict = {}
        self.error_on: dict[str, TeacherApiError] = {}

    def _maybe_raise(self, method: str) -> None:
        if method in self.error_on:
            raise self.error_on[method]

    def create_session(self, *, teacher_account, password):
        self._maybe_raise("create_session")
        self.session_calls.append(
            {"teacher_account": teacher_account, "password": password}
        )
        return TeacherSession(token=TOKEN)

    def query_view(self, *, teacher_session, **scope):
        self._maybe_raise("query_view")
        self.view_calls.append({"teacher_session": teacher_session, **scope})
        return self.view_response

    def save_review(self, *, teacher_session, submission_id, request_id, **fields):
        self._maybe_raise("save_review")
        self.review_calls.append(
            {
                "teacher_session": teacher_session,
                "submission_id": submission_id,
                "request_id": request_id,
                **fields,
            }
        )
        return self.review_response

    def generate_presentation(self, *, teacher_session, group_ids):
        self._maybe_raise("generate_presentation")
        self.presentation_calls.append(
            {"teacher_session": teacher_session, "group_ids": list(group_ids)}
        )
        return self.presentation_response

    def confirm_deletion_batch(self, *, teacher_session, batch_id, confirm, exclusions):
        self._maybe_raise("confirm_deletion_batch")
        self.confirm_calls.append(
            {
                "teacher_session": teacher_session,
                "batch_id": batch_id,
                "confirm": confirm,
                "exclusions": exclusions,
            }
        )
        return self.confirm_response


def make_client(spy: SpyTeacherApiClient) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(api_client=spy))
    return TestClient(app)


def login(client: TestClient):
    return client.post(
        "/teacher/login",
        data={"teacher_account": "teacher-1", "password": "pw"},
        follow_redirects=False,
    )


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.spy = SpyTeacherApiClient()
        self.client = make_client(self.spy)

    def test_login_page_renders_form_without_secret(self):
        resp = self.client.get("/teacher/login")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('name="teacher_account"', resp.text)
        self.assertIn('type="password"', resp.text)
        self.assertNotIn(TOKEN, resp.text)

    def test_login_success_sets_httponly_cookie_and_redirects(self):
        resp = login(self.client)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/teacher/courses")
        self.assertEqual(
            self.spy.session_calls,
            [{"teacher_account": "teacher-1", "password": "pw"}],
        )
        set_cookie = resp.headers["set-cookie"]
        self.assertIn(f"{SESSION_COOKIE}=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)

    def test_login_failure_rerenders_with_error(self):
        self.spy.error_on["create_session"] = TeacherApiError(
            AUTH_INVALID, "账号或密码错误"
        )
        resp = login(self.client)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("账号或密码错误", resp.text)

    def test_unauthenticated_redirects_to_login(self):
        resp = self.client.get("/teacher/courses", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/teacher/login")


class BrowseTests(unittest.TestCase):
    def setUp(self):
        self.spy = SpyTeacherApiClient()
        self.client = make_client(self.spy)
        login(self.client)

    def test_courses_page_lists_courses_and_deletion_batches(self):
        self.spy.view_response = {
            "courses": [{"course_id": "c1", "name": "软件工程"}],
            "deletion_batches": [BATCH],
        }
        resp = self.client.get("/teacher/courses")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("软件工程", resp.text)
        self.assertIn("batch-1", resp.text)
        self.assertIn("pending_confirmation", resp.text)
        self.assertIn("2026-07-15T00:00:00Z", resp.text)
        self.assertIn("course-1 全部提交", resp.text)
        self.assertIn("sub-keep-1", resp.text)
        # 会话凭证经注入客户端传递（CT-007 teacher_session）。
        self.assertEqual(self.spy.view_calls[0]["teacher_session"], TOKEN)

    def test_groups_page_lists_groups(self):
        self.spy.view_response = {"groups": [{"group_id": "g1", "name": "第一组"}]}
        resp = self.client.get("/teacher/courses/c1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("第一组", resp.text)
        self.assertEqual(self.spy.view_calls[0]["course_id"], "c1")

    def test_students_page_lists_students_and_submissions(self):
        self.spy.view_response = {
            "students": [{"student_id": "s1", "name": "张三"}],
            "submissions": [
                {"submission_id": SUB_ID, "student_name": "张三", "status": "scored"}
            ],
        }
        resp = self.client.get("/teacher/courses/c1/groups/g1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("张三", resp.text)
        self.assertIn(SUB_ID, resp.text)
        self.assertIn("scored", resp.text)
        call = self.spy.view_calls[0]
        self.assertEqual((call["course_id"], call["group_id"]), ("c1", "g1"))

    def test_forbidden_shows_access_denied(self):
        self.spy.error_on["query_view"] = TeacherApiError(FORBIDDEN, "denied")
        resp = self.client.get("/teacher/courses")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("无权限访问", resp.text)
        self.assertIn(FORBIDDEN, resp.text)

    def test_pages_do_not_leak_session_token(self):
        self.spy.view_response = DETAIL_PAYLOAD
        resp = self.client.get(f"/teacher/submissions/{SUB_ID}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(TOKEN, resp.text)


class SubmissionDetailTests(unittest.TestCase):
    def setUp(self):
        self.spy = SpyTeacherApiClient()
        self.client = make_client(self.spy)
        login(self.client)

    def test_detail_page_renders_all_review_fields(self):
        self.spy.view_response = DETAIL_PAYLOAD
        resp = self.client.get(f"/teacher/submissions/{SUB_ID}")
        html = resp.text
        self.assertEqual(resp.status_code, 200)
        # 材料清单 / 状态 / 原始等级 / 最终等级
        self.assertIn("dialog.md", html)
        self.assertIn("main.py", html)
        self.assertIn("scored", html)
        self.assertIn(">B</strong>", html)
        self.assertIn(">A</strong>", html)
        # 五维依据 / 教师建议 / 批注
        for dimension in ("正确性", "过程留痕", "代码质量", "结果呈现", "协作"):
            self.assertIn(dimension, html)
        self.assertIn("补充异常处理", html)
        self.assertIn("整体不错", html)
        self.assertIn("teacher-1", html)
        # 最终等级编辑入口
        self.assertIn(f'action="/teacher/submissions/{SUB_ID}/review"', html)
        self.assertIn('name="final_grade"', html)

    def test_scoring_failed_shows_reason_and_retry_without_grade(self):
        self.spy.view_response = FAILED_PAYLOAD
        resp = self.client.get("/teacher/submissions/sub-fail")
        html = resp.text
        self.assertEqual(resp.status_code, 200)
        # 真实失败原因与重试结果可见（A-005 / LCD-TUI-004）。
        self.assertIn("rubric 加载失败", html)
        self.assertIn("仍失败", html)
        self.assertIn("scoring_failed", html)
        # 不显示伪造等级：无等级值、无最终等级编辑入口。
        self.assertNotIn('class="grade-value"', html)
        self.assertNotIn('name="final_grade"', html)
        self.assertIn("不能设置最终等级", html)

    def test_review_submit_calls_ct008_with_request_id(self):
        self.spy.view_response = DETAIL_PAYLOAD
        resp = self.client.post(
            f"/teacher/submissions/{SUB_ID}/review",
            data={"annotation": "同意原始等级", "final_grade": "A"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.spy.review_calls), 1)
        call = self.spy.review_calls[0]
        self.assertEqual(call["submission_id"], SUB_ID)
        self.assertEqual(call["teacher_session"], TOKEN)
        # request_id 幂等键携带（CT-008）。
        self.assertTrue(call["request_id"])
        self.assertIsInstance(call["request_id"], str)
        self.assertEqual(call["annotation"], "同意原始等级")
        self.assertEqual(call["final_grade"], "A")
        # 保存结果可见（操作者与时间来自服务端 review_record）。
        self.assertIn("复核已保存", resp.text)
        self.assertIn("teacher-1", resp.text)

    def test_review_submit_requires_annotation_or_grade(self):
        self.spy.view_response = DETAIL_PAYLOAD
        resp = self.client.post(f"/teacher/submissions/{SUB_ID}/review", data={})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("至少填写其一", resp.text)
        self.assertEqual(self.spy.review_calls, [])

    def test_review_no_original_grade_error_keeps_draft(self):
        self.spy.view_response = FAILED_PAYLOAD
        self.spy.error_on["save_review"] = TeacherApiError(
            NO_ORIGINAL_GRADE, "no original grade"
        )
        resp = self.client.post(
            "/teacher/submissions/sub-fail/review",
            data={"annotation": "待重试后再评"},
        )
        html = resp.text
        self.assertIn(NO_ORIGINAL_GRADE, html)
        self.assertIn("不得伪造等级", html)
        # 失败保留草稿（显式重试，不自动重试父写契约）。
        self.assertIn("待重试后再评", html)


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.spy = SpyTeacherApiClient()
        self.client = make_client(self.spy)
        login(self.client)

    def test_presentation_page_renders_blocks_and_missing_marks(self):
        self.spy.presentation_response = {
            "presentation_id": "pres-1",
            "blocks": [
                {
                    "group_id": "g1",
                    "project_result": {"summary": "完成了图书管理系统"},
                    "process_summary": "三轮迭代完成",
                    "grades": [{"student_name": "张三", "original_grade": "B", "final_grade": "A"}],
                    "annotations": [{"text": "整体不错", "operator": "teacher-1", "updated_at": "2026-07-01T09:00:00Z"}],
                    "missing_marks": ["截图"],
                },
                {
                    "group_id": "g2",
                    "project_result": None,
                    "process_summary": "仅完成一轮",
                    "grades": [],
                    "annotations": [],
                    "missing_marks": ["对话", "代码", "截图", "结果"],
                },
            ],
        }
        resp = self.client.post(
            "/teacher/presentations",
            data={"course_id": "c1", "group_ids": ["g1", "g2"]},
        )
        html = resp.text
        self.assertEqual(resp.status_code, 200)
        # 选定小组与视图小组一致（CT-009 group_ids 透传）。
        self.assertEqual(
            self.spy.presentation_calls,
            [{"teacher_session": TOKEN, "group_ids": ["g1", "g2"]}],
        )
        self.assertIn("pres-1", html)
        self.assertIn("完成了图书管理系统", html)
        self.assertIn("三轮迭代完成", html)
        self.assertIn("整体不错", html)
        # missing_marks 缺失可见不隐藏。
        self.assertIn("missing-mark", html)
        self.assertIn("缺失：截图", html)
        self.assertIn("缺失：对话", html)
        # 缺失字段显式呈现，不填默认值。
        self.assertIn("项目结果缺失", html)

    def test_presentation_no_available_submission_shows_reason(self):
        self.spy.error_on["generate_presentation"] = TeacherApiError(
            NO_AVAILABLE_SUBMISSION, "小组 g1 无可用提交"
        )
        resp = self.client.post(
            "/teacher/presentations",
            data={"course_id": "c1", "group_ids": ["g1"]},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("小组 g1 无可用提交", resp.text)
        self.assertIn(NO_AVAILABLE_SUBMISSION, resp.text)


class DeletionBatchTests(unittest.TestCase):
    def setUp(self):
        self.spy = SpyTeacherApiClient()
        self.client = make_client(self.spy)
        login(self.client)
        self.spy.view_response = {"deletion_batches": [BATCH]}

    def test_deletion_batch_page_renders_state_and_confirm_entry(self):
        resp = self.client.get("/teacher/deletion-batches/batch-1")
        html = resp.text
        self.assertEqual(resp.status_code, 200)
        self.assertIn("pending_confirmation", html)
        self.assertIn("2026-07-15T00:00:00Z", html)
        self.assertIn("course-1 全部提交", html)
        self.assertIn("sub-keep-1", html)
        self.assertIn(
            'action="/teacher/deletion-batches/batch-1/confirm"', html
        )

    def test_deletion_batch_confirm_only_calls_ct011(self):
        self.spy.confirm_response = {
            "batch_id": "batch-1",
            "batch_status": "confirmed",
            "pending_deletion_scope": ["sub-1", "sub-2"],
        }
        resp = self.client.post(
            "/teacher/deletion-batches/batch-1/confirm",
            data={"exclusions": "sub-keep-1, sub-keep-2"},
        )
        html = resp.text
        self.assertEqual(resp.status_code, 200)
        # 仅发起 CT-011 调用（spy 断言；端点实现归 backfill）。
        self.assertEqual(len(self.spy.confirm_calls), 1)
        call = self.spy.confirm_calls[0]
        self.assertEqual(call["batch_id"], "batch-1")
        self.assertIs(call["confirm"], True)
        self.assertEqual(call["exclusions"], ["sub-keep-1", "sub-keep-2"])
        self.assertEqual(call["teacher_session"], TOKEN)
        self.assertIn("confirmed", html)
        self.assertIn("sub-1", html)

    def test_deletion_confirm_batch_not_expired(self):
        self.spy.error_on["confirm_deletion_batch"] = TeacherApiError(
            BATCH_NOT_EXPIRED, "批次未到期"
        )
        resp = self.client.post("/teacher/deletion-batches/batch-1/confirm", data={})
        self.assertEqual(resp.status_code, 409)
        self.assertIn(BATCH_NOT_EXPIRED, resp.text)
        self.assertIn("批次未到期", resp.text)


if __name__ == "__main__":
    unittest.main()
