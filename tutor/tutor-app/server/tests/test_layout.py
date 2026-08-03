"""布局测试：模块边界可导入、迁移入口与部署/文档基线文件齐备。"""
from __future__ import annotations

import configparser
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

PACKAGES = [
    "course_app",
    "course_app.submission_intake",
    "course_app.submission_intake.api",
    "course_app.submission_intake.core",
    "course_app.submission_intake.xfer",
    "course_app.course_roster",
    "course_app.teacher_web",
    "course_app.teacher_web.review_command",
    "course_app.teacher_web.review_query",
    "course_app.teacher_web.presentation",
    "course_app.teacher_web.ui",
    "tutor_shared",
]

BASELINE_FILES = [
    "server/alembic.ini",
    "server/migrations/env.py",
    "server/migrations/script.py.mako",
    "server/migrations/versions/0001_baseline.py",
    "server/requirements.txt",
    "worker/requirements.txt",
    "deploy/docker-compose.yml",
    "deploy/Dockerfile.server",
    "deploy/Dockerfile.worker",
    ".env.example",
    "docs/development.md",
    "docs/testing.md",
    "docs/configuration.md",
    "docs/operations.md",
    "docs/recovery.md",
    "docs/design/phase-1-detail-design.md",
    "docs/vibecode/runs/tutor-r01/contract-change-request.md",
]


class TestLayout(unittest.TestCase):
    def test_packages_importable(self):
        for name in PACKAGES:
            importlib.import_module(name)

    def test_baseline_files_exist(self):
        for rel in BASELINE_FILES:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_alembic_ini_parses(self):
        parser = configparser.ConfigParser()
        parser.read(ROOT / "server/alembic.ini", encoding="utf-8")
        self.assertEqual(parser.get("alembic", "script_location"), "migrations")

    def test_env_example_has_no_real_secret(self):
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("TEACHER_SESSION_SECRET=set-me-in-your-env", text)
        self.assertIn("MODEL_PROVIDER=fake", text)


if __name__ == "__main__":
    unittest.main()
