"""L16 CMP-PRESENTATION 单元测试（fastapi TestClient + SQLite 内存库）。

覆盖 verification-checklist 语义断言：
- 选定小组生成视图：presentation_id + blocks[] 与所选小组一一对应
  （project_result/process_summary/grades/annotations/missing_marks）；
- 任一小组无可用提交 → 409 NO_AVAILABLE_SUBMISSION + 原因说明，不产生视图；
- 相同参数重复生成（同时间窗）→ 返回最新快照，不产生重复视图记录（幂等）；
- 小组缺某类材料 → blocks 中 missing_marks 显式列出（不隐藏）；
- 快照写入后不随读模型后续变化而改变（一次性快照）；
- 应答字段与 contracts/ct-009.json 一致（含 missing_marks 冻结枚举）；
- 新时间窗再生成 → 新快照、旧快照 superseded、幂等记录指向最新；
- AUTH_INVALID / FORBIDDEN / VALIDATION_FAILED 冻结错误码映射；
- 展示导出为静态 HTML（DD-003/LCD-008，v1 不做 PDF）；
- 迁移文件可导入、revision/down_revision 正确。

注入：M05-IC-02 读模型查询端口与 ACCESS-GATE 端口均为冻结端口 fake
（L15/PROJECTOR/backfill 未集成）；数据源只经 M05-IC-02（LCD-004）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.teacher_web.presentation import (  # noqa: E402
    MATERIAL_CATEGORIES,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    AnnotationView,
    AuthContext,
    AuthInvalidError,
    Base as PresBase,
    GroupReadView,
    MaterialRef,
    SnapshotStore,
    SubmissionView,
    create_router,
    render_html,
)
from course_app.teacher_web.presentation.errors import (  # noqa: E402
    AUTH_INVALID,
    FORBIDDEN,
    NO_AVAILABLE_SUBMISSION,
    VALIDATION_FAILED,
)

CONTRACTS_DIR = ROOT / "contracts"
MIGRATION = ROOT / "server/migrations/versions/0008_presentation_views.py"
TEACHER = "teacher-1"
COURSE = "course-1"
TOKEN = "Bearer valid-teacher-token"


def load_contract(name: str) -> dict:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    PresBase.metadata.create_all(eng)
    return eng


def submission(
    sid: str,
    *,
    status: str = "scored",
    categories: tuple[str, ...] = MATERIAL_CATEGORIES,
    original_grade: str | None = "B",
    final_grade: str | None = "A",
    annotations: tuple[AnnotationView, ...] = (),
    missing: tuple[str, ...] = (),
) -> SubmissionView:
    return SubmissionView(
        submission_id=sid,
        status=status,
        student_id=f"stu-{sid}",
        material_refs=tuple(
            MaterialRef(category=c, ref=f"ref-{sid}-{c}") for c in categories
        ),
        original_grade=original_grade,
        final_grade=final_grade,
        annotations=annotations,
        missing_marks=missing,
        submitted_at="2026-07-19T10:00:00+00:00",
    )


class FakeReadModel:
    """M05-IC-02 冻结端口 fake：按 group_id 返回小组视图；可运行时变更。"""

    def __init__(self, views: dict[str, GroupReadView | None]) -> None:
        self.views = views
        self.calls = 0

    def group_view(self, *, group_id, course_id=None, student_id=None, submission_id=None):
        self.calls += 1
        return self.views.get(group_id)


class FakeAccessGate:
    """ACCESS-GATE 冻结端口 fake：固定令牌 → 授权上下文；否则 AUTH_INVALID。"""

    def __init__(self, course_ids=(COURSE,)) -> None:
        self.course_ids = course_ids

    def authorize(self, *, authorization):
        if authorization != TOKEN:
            raise AuthInvalidError("missing or invalid teacher session")
        return AuthContext(teacher_id=TEACHER, course_ids=tuple(self.course_ids))


def make_client(read_model, *, window: list[str] | None = None, gate=None):
    eng = make_engine()
    session_factory = partial(session_scope, eng)
    window = window if window is not None else ["2026-07-20"]
    router = create_router(
        session_factory=session_factory,
        access_gate=gate or FakeAccessGate(),
        read_model=read_model,
        time_window_fn=lambda: window[0],
    )
    app = FastAPI()
    app.include_router(router)
    return TestClient(app), SnapshotStore(session_factory), window


def full_group(group_id: str, *, course_id: str = COURSE) -> GroupReadView:
    return GroupReadView(
        course_id=course_id,
        group_id=group_id,
        read_model_version=f"rmv-{group_id}-1",
        submissions=(
            submission(
                f"sub-{group_id}-1",
                annotations=(
                    AnnotationView(
                        operator=TEACHER,
                        excerpt="结构清晰",
                        updated_at="2026-07-19T12:00:00+00:00",
                    ),
                ),
            ),
        ),
    )


class TestGeneratePresentation(unittest.TestCase):
    def setUp(self):
        self.read_model = FakeReadModel(
            {"g-1": full_group("g-1"), "g-2": full_group("g-2")}
        )
        self.client, self.store, self.window = make_client(self.read_model)

    def post(self, payload, *, token=TOKEN):
        headers = {"Authorization": token} if token else {}
        return self.client.post("/api/v1/teacher/presentations", json=payload, headers=headers)

    def test_generate_blocks_match_selected_groups(self):
        resp = self.post({"group_ids": ["g-1", "g-2"]})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["presentation_id"])
        blocks = {b["group_id"]: b for b in body["blocks"]}
        self.assertEqual(set(blocks), {"g-1", "g-2"})
        block = blocks["g-1"]
        self.assertEqual(
            set(block),
            {
                "group_id",
                "project_result",
                "process_summary",
                "grades",
                "annotations",
                "missing_marks",
            },
        )
        self.assertEqual(
            block["project_result"],
            {"submission_id": "sub-g-1-1", "result_ref": "ref-sub-g-1-1-结果"},
        )
        self.assertIsInstance(block["process_summary"], str)
        self.assertTrue(block["process_summary"])
        self.assertEqual(
            block["grades"],
            [
                {
                    "submission_id": "sub-g-1-1",
                    "original_grade": "B",
                    "final_grade": "A",
                }
            ],
        )
        self.assertEqual(block["annotations"][0]["excerpt"], "结构清晰")
        self.assertEqual(block["missing_marks"], [])

    def test_response_matches_ct009_schema(self):
        contract = load_contract("ct-009.json")
        schema = contract["schemas"]["response"]
        resp = self.post({"group_ids": ["g-1"]})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # additionalProperties=false（顶层）
        self.assertEqual(set(body), set(schema["required"]))
        block_required = schema["properties"]["blocks"]["items"]["required"]
        enum = schema["properties"]["blocks"]["items"]["properties"]["missing_marks"][
            "items"
        ]["enum"]
        for block in body["blocks"]:
            self.assertTrue(set(block_required) <= set(block))
            self.assertTrue(set(block["missing_marks"]) <= set(enum))
        self.assertEqual(list(enum), list(MATERIAL_CATEGORIES))

    def test_group_without_available_submission_rejected(self):
        self.read_model.views["g-2"] = GroupReadView(
            course_id=COURSE,
            group_id="g-2",
            read_model_version="rmv-g-2-1",
            submissions=(submission("sub-g-2-1", status="rejected"),),
        )
        resp = self.post({"group_ids": ["g-1", "g-2"]})
        self.assertEqual(resp.status_code, 409, resp.text)
        body = resp.json()
        self.assertEqual(body["code"], NO_AVAILABLE_SUBMISSION)
        self.assertIn("g-2", body["message"])  # 原因说明
        self.assertEqual(self.store.count_views(), 0)  # 不产生视图

    def test_unknown_group_rejected_with_reason(self):
        resp = self.post({"group_ids": ["g-1", "g-404"]})
        self.assertEqual(resp.status_code, 409, resp.text)
        body = resp.json()
        self.assertEqual(body["code"], NO_AVAILABLE_SUBMISSION)
        self.assertIn("g-404", body["message"])
        self.assertEqual(self.store.count_views(), 0)

    def test_idempotent_regeneration_same_window(self):
        first = self.post({"group_ids": ["g-1", "g-2"]})
        self.assertEqual(first.status_code, 200, first.text)
        calls_after_first = self.read_model.calls
        second = self.post({"group_ids": ["g-2", "g-1"]})  # 顺序不同，集合相同
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(
            first.json()["presentation_id"], second.json()["presentation_id"]
        )
        self.assertEqual(first.json()["blocks"], second.json()["blocks"])
        self.assertEqual(self.store.count_views(), 1)  # 不产生重复记录
        self.assertEqual(self.read_model.calls, calls_after_first)  # 命中不重读

    def test_missing_marks_visible_not_hidden(self):
        self.read_model.views["g-1"] = GroupReadView(
            course_id=COURSE,
            group_id="g-1",
            read_model_version="rmv-g-1-1",
            submissions=(
                submission(
                    "sub-g-1-1",
                    categories=("对话", "代码"),
                    original_grade=None,
                    final_grade=None,
                ),
            ),
        )
        resp = self.post({"group_ids": ["g-1"]})
        self.assertEqual(resp.status_code, 200, resp.text)
        block = resp.json()["blocks"][0]
        self.assertEqual(block["missing_marks"], ["截图", "结果"])  # 冻结枚举序
        self.assertIsNone(block["project_result"])  # 缺「结果」不伪造引用
        self.assertEqual(block["grades"], [])  # 无评分不伪造

    def test_snapshot_not_updated_by_read_model_changes(self):
        first = self.post({"group_ids": ["g-1"]})
        self.assertEqual(first.status_code, 200, first.text)
        # 读模型随后变化（评分调整投影完成）
        self.read_model.views["g-1"] = GroupReadView(
            course_id=COURSE,
            group_id="g-1",
            read_model_version="rmv-g-1-2",
            submissions=(submission("sub-g-1-1", final_grade="A+"),),
        )
        second = self.post({"group_ids": ["g-1"]})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json(), second.json())  # 一次性快照不变
        snapshot = self.store.get(first.json()["presentation_id"])
        self.assertEqual(snapshot.status, STATUS_ACTIVE)
        grades = snapshot.blocks[0]["grades"]
        self.assertEqual(grades[0]["final_grade"], "A")

    def test_new_time_window_creates_new_snapshot_and_supersedes(self):
        first = self.post({"group_ids": ["g-1"]})
        self.assertEqual(first.status_code, 200, first.text)
        self.read_model.views["g-1"] = GroupReadView(
            course_id=COURSE,
            group_id="g-1",
            read_model_version="rmv-g-1-2",
            submissions=(submission("sub-g-1-1", final_grade="A+"),),
        )
        self.window[0] = "2026-07-21"  # 新时间窗 → 重新生成
        second = self.post({"group_ids": ["g-1"]})
        self.assertEqual(second.status_code, 200, second.text)
        self.assertNotEqual(
            first.json()["presentation_id"], second.json()["presentation_id"]
        )
        self.assertEqual(self.store.count_views(), 2)
        old = self.store.get(first.json()["presentation_id"])
        new = self.store.get(second.json()["presentation_id"])
        self.assertEqual(old.status, STATUS_SUPERSEDED)
        self.assertEqual(new.status, STATUS_ACTIVE)
        self.assertEqual(new.blocks[0]["grades"][0]["final_grade"], "A+")
        # 同键再请求仍命中最新快照
        third = self.post({"group_ids": ["g-1"]})
        self.assertEqual(
            third.json()["presentation_id"], second.json()["presentation_id"]
        )
        self.assertEqual(self.store.count_views(), 2)

    def test_validation_failed(self):
        for payload in (
            {},
            {"group_ids": []},
            {"group_ids": [""]},
            {"group_ids": ["g-1"], "extra": 1},
        ):
            resp = self.post(payload)
            self.assertEqual(resp.status_code, 400, (payload, resp.text))
            self.assertEqual(resp.json()["code"], VALIDATION_FAILED)
        self.assertEqual(self.store.count_views(), 0)

    def test_auth_invalid(self):
        for token in (None, "Bearer wrong-token"):
            resp = self.post({"group_ids": ["g-1"]}, token=token)
            self.assertEqual(resp.status_code, 401, resp.text)
            self.assertEqual(resp.json()["code"], AUTH_INVALID)

    def test_forbidden_out_of_course_scope(self):
        self.read_model.views["g-9"] = full_group("g-9", course_id="course-2")
        resp = self.post({"group_ids": ["g-1", "g-9"]})
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(resp.json()["code"], FORBIDDEN)
        self.assertEqual(self.store.count_views(), 0)

    def test_html_export_static(self):
        resp = self.post({"group_ids": ["g-1"]})
        self.assertEqual(resp.status_code, 200, resp.text)
        snapshot = self.store.get(resp.json()["presentation_id"])
        html = render_html(snapshot)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("g-1", html)
        self.assertIn("结构清晰", html)
        self.assertIn("缺失标记", html)
        self.assertNotIn("<script", html)  # 静态导出，无外部脚本


class TestMigration(unittest.TestCase):
    def test_migration_importable_and_revision(self):
        spec = importlib.util.spec_from_file_location(
            "migration_0008_presentation_views", MIGRATION
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.revision, "0008_presentation_views")
        self.assertEqual(module.down_revision, "b9c6e3d6276a")


if __name__ == "__main__":
    unittest.main()
