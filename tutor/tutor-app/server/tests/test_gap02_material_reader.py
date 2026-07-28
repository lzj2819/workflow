"""GAP-02 ICT-003 材料只读端口验收：授权、课程/提交隔离、大小限制、异常与审计边界。

边界断言：仅 final 且归属匹配的登记材料可读；越权/未登记/删除/超限/路径逃逸
一律整体拒绝（不返回部分内容）；读取只读无副作用；拒绝与成功均可观测（日志+计数）。
"""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "server"), str(ROOT / "shared")]

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core.models import (  # noqa: E402
    Base as CoreBase,
    SubmissionMaterial,
)
from course_app.submission_intake.store.models import (  # noqa: E402
    Base,
    MaterialFile,
    STATE_DELETED,
    STATE_FINAL,
    STATE_STAGED,
)
from course_app.submission_intake.store.reader import (  # noqa: E402
    MaterialContentReader,
    MaterialContentUnreadableError,
)

NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=timezone.utc)


class MaterialReaderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name) / "materials"
        self.data_dir.mkdir()
        self.engine = sa.create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        CoreBase.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.reader = MaterialContentReader(
            lambda: session_scope(self.engine), self.data_dir, max_bytes=1024
        )

    def make_material(
        self,
        ref: str,
        *,
        course_id: str = "c-1",
        submission_id: str = "sub-1",
        category: str = "代码",
        state: str = STATE_FINAL,
        content: bytes = b"print('hello')",
        path: str | None = None,
    ) -> str:
        rel = path or f"{course_id}/{submission_id}/{ref}.txt"
        if path is None:  # 路径逃逸用例不写盘
            target = self.data_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        with session_scope(self.engine) as s:
            if course_id == "c-1" and submission_id == "sub-1":
                # 授权以 L02 清单为准：仅授权上下文（c-1/sub-1）的材料入清单
                s.add(
                    SubmissionMaterial(
                        submission_id=submission_id,
                        material_ref=ref,
                        category=category,
                        size_bytes=len(content),
                        declared=True,
                        filename=f"{ref}.txt",
                    )
                )
            s.add(
                MaterialFile(
                    material_ref=ref,
                    session_id="sess-1",
                    seq=0,
                    course_id=course_id,
                    submission_id=submission_id,
                    category=category,
                    path=rel,
                    size_bytes=len(content),
                    sha256="0" * 64,
                    state=state,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        return ref

    def load(self, refs, course_id="c-1", submission_id="sub-1") -> dict:
        return self.reader.load_for(
            course_id=course_id, submission_id=submission_id, material_refs=refs
        )

    # ---- 授权读取（正常路径） ----

    def test_authorized_read_ok(self) -> None:
        self.make_material("m1", content="print(1)".encode())
        self.make_material("m2", category="对话", content="turns".encode())
        out = self.load(["m1", "m2"])
        self.assertEqual(out["materials"]["代码"], "print(1)")
        self.assertEqual(out["materials"]["对话"], "turns")
        self.assertEqual(out["readability"], [])

    def test_same_category_files_merged(self) -> None:
        self.make_material("m1", content=b"a")
        self.make_material("m2", content=b"b")
        out = self.load(["m1", "m2"])
        self.assertEqual(out["materials"]["代码"], "a\nb")

    # ---- 课程/提交隔离 ----

    def test_cross_course_denied(self) -> None:
        self.make_material("m1", course_id="c-2")
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])  # 授权上下文 c-1/sub-1，材料属 c-2

    def test_cross_submission_denied(self) -> None:
        self.make_material("m1", submission_id="sub-2")
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])

    def test_unregistered_ref_denied(self) -> None:
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["ghost"])

    def test_deleted_material_denied(self) -> None:
        self.make_material("m1", state=STATE_DELETED)
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])

    def test_staged_material_denied(self) -> None:
        self.make_material("m1", state=STATE_STAGED)
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])  # 仅 final 可读

    def test_denial_returns_no_partial_content(self) -> None:
        self.make_material("m1", content=b"legit")
        self.make_material("m2", course_id="c-2")
        try:
            self.load(["m1", "m2"])
            self.fail("should raise")
        except MaterialContentUnreadableError:
            pass  # 整体失败：不返回 m1 内容（防越权侧信道）

    # ---- 大小限制与路径边界 ----

    def test_size_limit_denied(self) -> None:
        self.make_material("m1", content=b"x" * 2048)  # max_bytes=1024
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])

    def test_path_escape_denied(self) -> None:
        self.make_material("m1", path="../outside.txt")
        with self.assertRaises(MaterialContentUnreadableError):
            self.load(["m1"])

    # ---- 可读性备注与审计边界 ----

    def test_non_utf8_noted_in_readability(self) -> None:
        self.make_material("m1", content=b"\xff\xfe binary")
        out = self.load(["m1"])
        self.assertEqual(len(out["readability"]), 1)
        self.assertIn("non-utf8", out["readability"][0]["note"])

    def test_read_is_side_effect_free(self) -> None:
        self.make_material("m1")
        self.load(["m1"])
        with session_scope(self.engine) as s:
            state, updated_at = s.execute(
                sa.text("select state, updated_at from material_files where material_ref='m1'")
            ).one()
        self.assertEqual(state, STATE_FINAL)  # 状态未被读取改变
        self.assertEqual(str(updated_at), "2026-07-23 12:00:00.000000")  # 无写回

    def test_denial_observable_via_log(self) -> None:
        self.make_material("m1", course_id="c-2")
        logger = logging.getLogger("course_app.material_reader")
        with self.assertLogs(logger, level="WARNING") as captured:
            with self.assertRaises(MaterialContentUnreadableError):
                self.load(["m1"])
        self.assertTrue(any("denied" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
