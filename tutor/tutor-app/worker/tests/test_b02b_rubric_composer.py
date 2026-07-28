"""T-B02b RUBRIC-PROMPT-COMPOSER 单元测试（SQLite）。

覆盖任务卡语义断言：
- 迁移 0011：revision 链、SQLite upgrade/downgrade、种子 v1 行（五维与
  contracts/ct-010.json 一致、含缺失材料影响提示）、同库 active 唯一约束、
  迁移表结构与 ORM 模型一致；
- compose()：ICT-002 端口形状（evaluation_prompt/prompt_version/rubric_version）、
  确定性（同版本同输入同输出）、缺失材料声明注入（missing_items 标签化）、
  无 active 策略 → PromptAssemblyFailedError；
- 三桶预算编排：折叠口径与 L12 _minimize_materials 完全一致（未超预算无缺失时
  逐桶相等）、确定性截断（超预算加固定标记、同输入同输出）、缺失类别标签化
  （含未识别缺失类别折叠进 result_description）。

仅 SQLite 本地库；无网络、无真实供应商。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "worker"), str(ROOT / "shared")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from assessment_worker.assessment_engine.engine import AssessmentEngine  # noqa: E402
from assessment_worker.assessment_engine.errors import PromptAssemblyFailedError  # noqa: E402
from assessment_worker.rubric import (  # noqa: E402
    BUCKET_BUDGETS,
    TRUNCATION_MARKER,
    RubricPolicy,
    RubricPromptComposer,
    missing_label,
    orchestrate_material_buckets,
    truncate_to_budget,
)

MIGRATION_PATH = ROOT / "server" / "migrations" / "versions" / "0011_rubric_policies.py"
CT010_DIMENSIONS = ["需求理解", "Codex 迭代过程", "代码质量", "最终功能", "文档/展示完整性"]

ASSIGNMENT = "实现命令行待办管理器"
MATERIAL_REFS = [
    {"category": "代码", "ref": "materials/sub-1/main.py", "filename": "main.py"},
    {"category": "对话", "ref": "materials/sub-1/dialogue.md"},
]


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0011_rubric_policies", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.engine = sa.create_engine(f"sqlite:///{Path(self._tmp.name) / 'rubric.db'}")
        self.module = load_migration()
        with self.engine.connect() as conn:
            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            with Operations.context(MigrationContext.configure(conn)):
                self.module.upgrade()
            conn.commit()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmp.cleanup()


class TestMigration(MigrationTestBase):
    def test_revision_chain(self):
        self.assertEqual(self.module.revision, "0011_rubric_policies")
        self.assertEqual(self.module.down_revision, "11a22f91f4b3")

    def test_upgrade_creates_table_and_seed(self):
        with self.engine.connect() as conn:
            self.assertIn("rubric_policies", sa.inspect(conn).get_table_names())
            rows = conn.execute(sa.text("SELECT * FROM rubric_policies")).mappings().all()
        self.assertEqual(len(rows), 1)
        seed = rows[0]
        self.assertEqual(seed["rubric_version"], "rubric-v1")
        self.assertEqual(seed["prompt_version"], "prompt-v1")
        self.assertEqual(seed["status"], "active")
        dims = seed["dimensions"]
        if isinstance(dims, str):
            dims = json.loads(dims)
        self.assertEqual(dims, CT010_DIMENSIONS)
        bands = seed["grade_bands"]
        if isinstance(bands, str):
            bands = json.loads(bands)
        self.assertEqual(bands, {"A": "90–100", "B": "80–89", "C": "70–79", "D": "60–69", "E": "0–59"})
        # 种子 v1 模板含五维与缺失材料影响提示
        for dim in CT010_DIMENSIONS:
            self.assertIn(dim, seed["template_body"])
        self.assertIn("缺失材料影响提示", seed["template_body"])

    def test_downgrade_drops_table(self):
        with self.engine.connect() as conn:
            from alembic.migration import MigrationContext
            from alembic.operations import Operations

            with Operations.context(MigrationContext.configure(conn)):
                self.module.downgrade()
            self.assertNotIn("rubric_policies", sa.inspect(conn).get_table_names())

    def test_active_unique_constraint(self):
        with self.Session() as session:
            session.add(
                RubricPolicy(
                    rubric_version="rubric-v2",
                    prompt_version="prompt-v2",
                    template_body="x {{assignment}} {{material_manifest}} {{missing_declaration}}",
                    dimensions=CT010_DIMENSIONS,
                    grade_bands={"A": "90–100"},
                    status="active",
                    created_at=datetime(2026, 7, 21),
                )
            )
            with self.assertRaises(sa.exc.IntegrityError):
                session.commit()

    def test_superseded_does_not_conflict(self):
        with self.Session() as session:
            session.add(
                RubricPolicy(
                    rubric_version="rubric-v0",
                    prompt_version="prompt-v0",
                    template_body="x {{assignment}} {{material_manifest}} {{missing_declaration}}",
                    dimensions=CT010_DIMENSIONS,
                    grade_bands={"A": "90–100"},
                    status="superseded",
                    created_at=datetime(2026, 7, 20),
                )
            )
            session.commit()

    def test_migration_schema_matches_orm(self):
        with self.engine.connect() as conn:
            migrated = {c["name"] for c in sa.inspect(conn).get_columns("rubric_policies")}
        from assessment_worker.rubric.models import RubricBase

        modeled = set(RubricBase.metadata.tables["rubric_policies"].columns.keys())
        self.assertEqual(migrated, modeled)


class ComposerTestBase(MigrationTestBase):
    def composer(self, session) -> RubricPromptComposer:
        return RubricPromptComposer(session)


class TestComposer(ComposerTestBase):
    def test_compose_output_shape_and_versions(self):
        with self.Session() as session:
            out = self.composer(session).compose(ASSIGNMENT, MATERIAL_REFS, [])
        self.assertEqual(set(out), {"evaluation_prompt", "prompt_version", "rubric_version"})
        self.assertIsInstance(out["evaluation_prompt"], str)
        self.assertTrue(out["evaluation_prompt"])
        self.assertEqual(out["prompt_version"], "prompt-v1")
        self.assertEqual(out["rubric_version"], "rubric-v1")
        prompt = out["evaluation_prompt"]
        self.assertIn(ASSIGNMENT, prompt)
        for dim in CT010_DIMENSIONS:
            self.assertIn(dim, prompt)
        self.assertIn("90–100", prompt)
        # 无占位符残留
        self.assertNotIn("{{", prompt)
        # 数据最小化：类别标注进入清单，filename/ref 不进入
        self.assertIn("类别：代码", prompt)
        self.assertNotIn("main.py", prompt)
        self.assertNotIn("materials/sub-1", prompt)

    def test_compose_deterministic_same_version_same_output(self):
        with self.Session() as session:
            composer = self.composer(session)
            first = composer.compose(ASSIGNMENT, MATERIAL_REFS, ["结果描述"])
            second = composer.compose(ASSIGNMENT, MATERIAL_REFS, ["结果描述"])
        self.assertEqual(first, second)

    def test_compose_missing_declaration_injected(self):
        with self.Session() as session:
            out = self.composer(session).compose(ASSIGNMENT, MATERIAL_REFS, ["代码", "对话"])
        prompt = out["evaluation_prompt"]
        self.assertIn("本次评估缺少以下材料类别：", prompt)
        self.assertIn("- 代码：该类别材料缺失，对应维度仅能依据其余已提供材料推断", prompt)
        self.assertIn("- 对话：该类别材料缺失，对应维度仅能依据其余已提供材料推断", prompt)
        self.assertIn("缺失材料影响提示", prompt)

    def test_compose_no_missing_items(self):
        with self.Session() as session:
            out = self.composer(session).compose(ASSIGNMENT, MATERIAL_REFS, [])
        self.assertIn("本次提交材料完整，无缺失类别。", out["evaluation_prompt"])

    def test_compose_empty_material_refs(self):
        with self.Session() as session:
            out = self.composer(session).compose(ASSIGNMENT, [], [])
        self.assertIn("（未声明材料）", out["evaluation_prompt"])

    def test_compose_no_active_policy_raises(self):
        with self.Session() as session:
            session.execute(sa.text("UPDATE rubric_policies SET status='superseded'"))
            session.commit()
            with self.assertRaises(PromptAssemblyFailedError):
                self.composer(session).compose(ASSIGNMENT, MATERIAL_REFS, [])

    def test_compose_bad_assignment_raises(self):
        with self.Session() as session:
            with self.assertRaises(PromptAssemblyFailedError):
                self.composer(session).compose("", MATERIAL_REFS, [])

    def test_compose_bad_material_ref_raises(self):
        with self.Session() as session:
            with self.assertRaises(PromptAssemblyFailedError):
                self.composer(session).compose(ASSIGNMENT, [{"ref": "x"}], [])


class TestBucketOrchestration(unittest.TestCase):
    CONTENTS = {
        "对话": "学生与 Codex 的对话摘要",
        "代码": "def main(): ...",
        "结果描述": "程序输出符合预期",
    }

    def test_folding_matches_l12_minimize(self):
        # 未超预算且无缺失时，逐桶与 L12 _minimize_materials 完全一致
        unknown = dict(self.CONTENTS)
        unknown["未识别类别"] = "额外材料"
        expected = AssessmentEngine._minimize_materials(unknown)
        got = orchestrate_material_buckets(unknown, [])
        self.assertEqual(got, expected)
        # 未识别类别折叠进 result_description 并带类别标签
        self.assertIn("[未识别类别]\n额外材料", got["result_description"])

    def test_empty_buckets_empty_strings(self):
        got = orchestrate_material_buckets({}, [])
        self.assertEqual(got, {"dialogue_summary": "", "code": "", "result_description": ""})

    def test_truncation_deterministic_and_marked(self):
        long_code = "x" * (BUCKET_BUDGETS["code"] + 500)
        first = orchestrate_material_buckets({"代码": long_code}, [])
        second = orchestrate_material_buckets({"代码": long_code}, [])
        self.assertEqual(first, second)
        code = first["code"]
        self.assertTrue(code.endswith(TRUNCATION_MARKER))
        self.assertEqual(len(code), BUCKET_BUDGETS["code"] + len(TRUNCATION_MARKER))
        # 未超预算的桶保持原样
        under = orchestrate_material_buckets(self.CONTENTS, [])
        self.assertEqual(under["code"], self.CONTENTS["代码"])

    def test_truncate_to_budget_exact_boundary(self):
        self.assertEqual(truncate_to_budget("abc", 3), "abc")
        self.assertEqual(truncate_to_budget("abcd", 3), "abc" + TRUNCATION_MARKER)
        with self.assertRaises(ValueError):
            truncate_to_budget("abc", 0)

    def test_missing_labels_in_mapped_buckets(self):
        got = orchestrate_material_buckets(self.CONTENTS, ["对话", "结果描述"])
        self.assertIn(missing_label("对话"), got["dialogue_summary"])
        self.assertIn(missing_label("结果描述"), got["result_description"])
        self.assertNotIn("缺失材料", got["code"])

    def test_missing_unknown_category_folds_to_result_description(self):
        got = orchestrate_material_buckets(self.CONTENTS, ["未识别类别"])
        self.assertIn(missing_label("未识别类别"), got["result_description"])

    def test_missing_label_survives_truncation(self):
        long_dialogue = "y" * (BUCKET_BUDGETS["dialogue_summary"] + 100)
        got = orchestrate_material_buckets({"对话": long_dialogue}, ["对话"])
        self.assertTrue(got["dialogue_summary"].endswith(missing_label("对话")))


if __name__ == "__main__":
    unittest.main()
