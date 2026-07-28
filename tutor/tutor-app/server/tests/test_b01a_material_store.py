"""T-B01a SI-STORE 单元测试（tmp 磁盘 DATA_DIR + SQLite 内存库）。

覆盖任务验收面：
- write_stage 暂存：确定性 ref/文件名、sha256 登记、同 session/seq 重写幂等；
- 原子性：写入中断不留半成品（无 tmp/final 残留、无登记行）；
- promote_to_final：DD-005 目录布局（materials/{course}/{submission}/{category}/）、
  同 session 幂等（重复调用同 refs、配额不重复累计）、移动崩溃重试安全
  （源缺失但目标 sha 吻合视为已移动）、身份回退（_unassigned/submission_uuid）；
- 课程配额：超限抛 QUOTA_EXCEEDED，且不移动任何文件、不改登记；
- delete 幂等：final 删除扣减配额、重复删除/未知引用为空操作；
- read_metadata：L02 MaterialMetadataReader 兼容形状，未知/已删除引用抛
  MATERIAL_METADATA_UNAVAILABLE；
- 路径约束：拒绝逃逸 DATA_DIR 的路径段；
- 迁移 0009 可导入、revision/down_revision 正确、upgrade/downgrade 可执行。
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402

from course_app.db import session_scope  # noqa: E402
from course_app.submission_intake.core.errors import (  # noqa: E402
    MaterialMetadataUnavailableError,
)
from course_app.submission_intake.core.models import (  # noqa: E402
    Base as CoreBase,
    Submission,
)
from course_app.submission_intake.store import (  # noqa: E402
    Base as StoreBase,
    CourseQuotaUsage,
    FilesystemMaterialStore,
    MaterialFile,
    QuotaExceededError,
    StorageIoError,
)
from course_app.submission_intake.xfer.models import (  # noqa: E402
    Base as XferBase,
    UploadSession,
)

NOW = datetime(2026, 7, 21, 12, 0, 0, tzinfo=timezone.utc)


def make_engine():
    eng = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    XferBase.metadata.create_all(eng)
    CoreBase.metadata.create_all(eng)
    StoreBase.metadata.create_all(eng)
    return eng


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        self.eng = make_engine()
        self.addCleanup(self.eng.dispose)
        self.store = FilesystemMaterialStore(
            session_factory=partial(session_scope, self.eng),
            data_dir=self.data_dir,
            clock=lambda: NOW,
        )

    # ---- 辅助 ----

    def add_upload_session(self, session_id="sess-1", uuid="uuid-1"):
        with session_scope(self.eng) as s:
            s.add(
                UploadSession(
                    session_id=session_id,
                    submission_uuid=uuid,
                    declared_categories=["对话"],
                    state="receiving",
                    received_bytes=0,
                    next_expected_seq=0,
                    expires_at=NOW + timedelta(hours=24),
                    version=0,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )

    def add_submission(
        self, uuid="uuid-1", submission_id="sub-1", course_id="course-1"
    ):
        with session_scope(self.eng) as s:
            s.add(
                Submission(
                    submission_id=submission_id,
                    submission_uuid=uuid,
                    course_id=course_id,
                    assignment="hw1",
                    student_name="s",
                    group_name="g",
                    status="received",
                    version=0,
                    received_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )

    def material_row(self, ref):
        with session_scope(self.eng) as s:
            row = s.get(MaterialFile, ref)
            if row is not None:
                s.expunge(row)
            return row

    def material_rows(self):
        with session_scope(self.eng) as s:
            rows = s.scalars(sa.select(MaterialFile).order_by(MaterialFile.seq)).all()
            for r in rows:
                s.expunge(r)
            return list(rows)

    def usage(self, course_id):
        with session_scope(self.eng) as s:
            row = s.get(CourseQuotaUsage, course_id)
            if row is not None:
                s.expunge(row)
            return row

    def all_files(self):
        return sorted(
            p.relative_to(self.data_dir).as_posix()
            for p in self.data_dir.rglob("*")
            if p.is_file()
        )


class TestWriteStage(StoreTestCase):
    def test_write_stage_persists_file_and_registers_row(self):
        content = b"hello material" * 100
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="对话", content=content
        )
        self.assertEqual(ref, "staged://sess-1/000000")
        staged = self.data_dir / "uploads" / "sess-1" / "chunks" / "000000.chunk"
        self.assertEqual(staged.read_bytes(), content)
        row = self.material_row(ref)
        self.assertIsNotNone(row)
        self.assertEqual(row.state, "staged")
        self.assertEqual(row.category, "对话")
        self.assertEqual(row.size_bytes, len(content))
        self.assertEqual(row.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(row.path, "uploads/sess-1/chunks/000000.chunk")

    def test_write_stage_same_session_seq_is_deterministic(self):
        ref1 = self.store.write_stage(
            session_id="sess-1", seq=3, category="代码", content=b"v1"
        )
        ref2 = self.store.write_stage(
            session_id="sess-1", seq=3, category="代码", content=b"v1"
        )
        self.assertEqual(ref1, ref2)
        self.assertEqual(len(self.material_rows()), 1)

    def test_write_stage_rewrite_updates_registration(self):
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="代码", content=b"v1"
        )
        ref2 = self.store.write_stage(
            session_id="sess-1", seq=0, category="代码", content=b"v2-longer"
        )
        self.assertEqual(ref, ref2)
        row = self.material_row(ref)
        self.assertEqual(row.sha256, hashlib.sha256(b"v2-longer").hexdigest())
        self.assertEqual(row.size_bytes, len(b"v2-longer"))
        staged = self.data_dir / "uploads" / "sess-1" / "chunks" / "000000.chunk"
        self.assertEqual(staged.read_bytes(), b"v2-longer")

    def test_write_stage_failure_leaves_no_partial_artifacts(self):
        with mock.patch(
            "course_app.submission_intake.store.filesystem.os.replace",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaises(StorageIoError) as ctx:
                self.store.write_stage(
                    session_id="sess-1", seq=0, category="对话", content=b"x" * 10
                )
        self.assertEqual(ctx.exception.code, "STORAGE_IO_FAILED")
        self.assertEqual(self.all_files(), [])  # 无 tmp/final 残留
        self.assertEqual(self.material_rows(), [])  # 无登记行

    def test_write_stage_rejects_path_escape(self):
        with self.assertRaises(StorageIoError):
            self.store.write_stage(
                session_id="../evil", seq=0, category="对话", content=b"x"
            )
        self.assertEqual(self.all_files(), [])


class TestPromote(StoreTestCase):
    def stage_two_chunks(self, session_id="sess-1"):
        refs = [
            self.store.write_stage(
                session_id=session_id, seq=i, category=cat, content=content
            )
            for i, (cat, content) in enumerate(
                [("对话", b"dialog-bytes"), ("代码", b"code-bytes-more")]
            )
        ]
        return refs

    def test_promote_moves_to_dd005_layout_and_returns_stable_refs(self):
        self.add_upload_session()
        self.add_submission()
        staged_refs = self.stage_two_chunks()
        final_refs = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        self.assertEqual(len(final_refs), 2)
        for ref in final_refs:
            self.assertTrue(
                ref.startswith("material://course-1/sub-1/"), ref
            )
        files = self.all_files()
        self.assertEqual(len(files), 2)
        for f in files:
            self.assertTrue(f.startswith("materials/course-1/sub-1/"), f)
        self.assertTrue(any("/对话/" in f for f in files))
        self.assertTrue(any("/代码/" in f for f in files))
        # 暂存文件已移走
        self.assertFalse((self.data_dir / "uploads" / "sess-1").exists())
        rows = self.material_rows()
        self.assertEqual([r.state for r in rows], ["final", "final"])
        self.assertEqual({r.course_id for r in rows}, {"course-1"})
        self.assertEqual({r.submission_id for r in rows}, {"sub-1"})
        usage = self.usage("course-1")
        self.assertEqual(
            usage.used_bytes, len(b"dialog-bytes") + len(b"code-bytes-more")
        )
        # 确定性：refs 与文件名由 session/seq/sha 派生
        again = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        self.assertEqual(final_refs, again)

    def test_promote_idempotent_same_session_same_refs(self):
        self.add_upload_session()
        self.add_submission()
        staged_refs = self.stage_two_chunks()
        first = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        second = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.material_rows()), 2)
        # 配额不重复累计
        usage = self.usage("course-1")
        self.assertEqual(
            usage.used_bytes, len(b"dialog-bytes") + len(b"code-bytes-more")
        )

    def test_promote_fallback_identity_when_submission_not_registered(self):
        self.add_upload_session(uuid="uuid-x")
        staged_refs = self.stage_two_chunks()
        final_refs = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        for ref in final_refs:
            self.assertTrue(ref.startswith("material://_unassigned/uuid-x/"), ref)
        files = self.all_files()
        self.assertTrue(all(f.startswith("materials/_unassigned/uuid-x/") for f in files))
        usage = self.usage("_unassigned")
        self.assertIsNotNone(usage)

    def test_promote_retry_safe_when_source_already_moved(self):
        """崩溃重试：源已移动、目标 sha 吻合视为已完成，promote 整体仍成功。"""
        self.add_upload_session()
        self.add_submission()
        staged_refs = self.stage_two_chunks()
        # 模拟先前尝试：chunk0 已移动到最终位置但事务未提交（登记仍 staged）
        row0 = self.material_row(staged_refs[0])
        dst = (
            self.data_dir
            / "materials"
            / "course-1"
            / "sub-1"
            / row0.category
            / f"{row0.seq:06d}-{row0.sha256[:16]}.bin"
        )
        dst.parent.mkdir(parents=True, exist_ok=True)
        src = self.data_dir / row0.path
        dst.write_bytes(src.read_bytes())
        src.unlink()
        final_refs = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        )
        self.assertEqual(len(final_refs), 2)
        self.assertEqual(len(self.all_files()), 2)
        self.assertEqual([r.state for r in self.material_rows()], ["final", "final"])

    def test_promote_quota_exceeded_rejects_without_side_effects(self):
        self.add_upload_session()
        self.add_submission()
        small_quota = FilesystemMaterialStore(
            session_factory=partial(session_scope, self.eng),
            data_dir=self.data_dir,
            quota_bytes=10,
            clock=lambda: NOW,
        )
        staged_refs = self.stage_two_chunks()
        with self.assertRaises(QuotaExceededError) as ctx:
            small_quota.promote_to_final(session_id="sess-1", staged_refs=staged_refs)
        self.assertEqual(ctx.exception.code, "QUOTA_EXCEEDED")
        # 不移动任何文件：暂存仍在、无正式文件
        files = self.all_files()
        self.assertEqual(len(files), 2)
        self.assertTrue(all(f.startswith("uploads/") for f in files))
        # 登记不变、配额未累计
        self.assertEqual([r.state for r in self.material_rows()], ["staged", "staged"])
        self.assertIsNone(self.usage("course-1"))

    def test_promote_unknown_staged_ref_rejected(self):
        self.add_upload_session()
        with self.assertRaises(StorageIoError):
            self.store.promote_to_final(
                session_id="sess-1", staged_refs=["staged://sess-1/000099"]
            )

    def test_promote_ref_from_other_session_rejected(self):
        self.add_upload_session(session_id="sess-1", uuid="uuid-1")
        self.add_upload_session(session_id="sess-2", uuid="uuid-2")
        foreign = self.store.write_stage(
            session_id="sess-2", seq=0, category="对话", content=b"x"
        )
        with self.assertRaises(StorageIoError):
            self.store.promote_to_final(session_id="sess-1", staged_refs=[foreign])


class TestDelete(StoreTestCase):
    def test_delete_final_is_idempotent_and_releases_quota(self):
        self.add_upload_session()
        self.add_submission()
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="对话", content=b"payload"
        )
        final_ref = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=[ref])
        )[0]
        self.store.delete(final_ref)
        self.assertEqual(self.all_files(), [])
        row = self.material_row(final_ref)
        self.assertEqual(row.state, "deleted")
        self.assertEqual(self.usage("course-1").used_bytes, 0)
        # 重复删除为空操作
        self.store.delete(final_ref)
        self.assertEqual(self.material_row(final_ref).state, "deleted")

    def test_delete_staged_and_unknown_refs_are_noop_safe(self):
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="对话", content=b"payload"
        )
        self.store.delete(ref)
        self.assertEqual(self.all_files(), [])
        self.assertEqual(self.material_row(ref).state, "deleted")
        # 未知引用：空操作，不抛错
        self.store.delete("material://no/such/ref")
        self.store.delete(ref)


class TestReadMetadata(StoreTestCase):
    def test_read_metadata_matches_l02_shape(self):
        self.add_upload_session()
        self.add_submission()
        content = b"metadata-content"
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="截图", content=content
        )
        final_ref = list(
            self.store.promote_to_final(session_id="sess-1", staged_refs=[ref])
        )[0]
        meta = self.store.read_metadata(final_ref)
        self.assertEqual(meta.material_ref, final_ref)
        self.assertEqual(meta.category, "截图")
        self.assertEqual(meta.size_bytes, len(content))
        self.assertTrue(meta.declared)
        self.assertTrue(meta.filename.endswith(".bin"))

    def test_read_metadata_unknown_or_deleted_ref_unavailable(self):
        with self.assertRaises(MaterialMetadataUnavailableError):
            self.store.read_metadata("material://no/such/ref")
        ref = self.store.write_stage(
            session_id="sess-1", seq=0, category="对话", content=b"x"
        )
        self.store.delete(ref)
        with self.assertRaises(MaterialMetadataUnavailableError):
            self.store.read_metadata(ref)


class TestMigration(unittest.TestCase):
    def _load_module(self):
        path = (
            ROOT / "server" / "migrations" / "versions" / "0009_material_store.py"
        )
        spec = importlib.util.spec_from_file_location("mig_0009_material_store", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_revision_identifiers(self):
        module = self._load_module()
        self.assertEqual(module.revision, "0009_material_store")
        self.assertEqual(module.down_revision, "11a22f91f4b3")

    def test_upgrade_downgrade_on_sqlite(self):
        module = self._load_module()
        with tempfile.TemporaryDirectory() as tmp:
            eng = sa.create_engine(f"sqlite:///{Path(tmp) / 'mig.db'}")
            with eng.connect() as conn:
                ctx = MigrationContext.configure(conn)
                with Operations.context(ctx):
                    module.upgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    self.assertIn("material_files", tables)
                    self.assertIn("course_quota_usage", tables)
                    module.downgrade()
                    tables = set(sa.inspect(conn).get_table_names())
                    self.assertNotIn("material_files", tables)
                    self.assertNotIn("course_quota_usage", tables)
            eng.dispose()


class TestRelativeDataDir(StoreTestCase):
    def test_relative_data_dir_accepted(self):
        # 回归（Phase 6 并发探针发现的缺陷）：相对 data_dir 不再导致
        # relative_to/前缀校验对绝对子路径误判
        import os

        parent = tempfile.TemporaryDirectory()
        self.addCleanup(parent.cleanup)
        cwd = os.getcwd()
        os.chdir(parent.name)
        try:
            store = FilesystemMaterialStore(
                session_factory=partial(session_scope, self.eng),
                data_dir="relative-data",
                clock=lambda: NOW,
            )
            ref = store.write_stage(session_id="sess-1", seq=0, category="对话", content=b"x")
            self.assertEqual(ref, "staged://sess-1/000000")
            staged = Path(parent.name) / "relative-data" / "uploads" / "sess-1" / "chunks" / "000000.chunk"
            self.assertTrue(staged.exists())
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
