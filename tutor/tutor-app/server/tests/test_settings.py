"""server 配置测试：KD/NFR 冻结常量与环境变量加载。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "shared")]

from tutor_shared.config import ConfigError  # noqa: E402

from course_app import settings  # noqa: E402


class TestFrozenConstants(unittest.TestCase):
    def test_kd004_limits(self):
        self.assertEqual(settings.MAX_SUBMISSION_BYTES, 500 * 1024 * 1024)
        self.assertEqual(settings.COURSE_QUOTA_BYTES, 200 * 1024**3)

    def test_nfr003_targets(self):
        self.assertEqual(settings.RECEIPT_TARGET_SECONDS, 30)
        self.assertEqual(settings.SCORING_TARGET_SECONDS, 600)
        self.assertEqual(settings.MODEL_CALL_TIMEOUT_SECONDS, 180)

    def test_api_prefix(self):
        self.assertEqual(settings.API_PREFIX, "/api/v1")


class TestSettingsFromEnv(unittest.TestCase):
    def test_full_env(self):
        env = {
            "DATABASE_URL": "postgresql://tutor:tutor@localhost:5432/tutor",
            "TEACHER_SESSION_SECRET": "s3cret",
            "DATA_DIR": "./data",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            cfg = settings.Settings.from_env()
        self.assertTrue(cfg.database_url.startswith("postgresql://"))
        self.assertEqual(cfg.log_level, "INFO")

    def test_missing_secret_rejected(self):
        env = {"DATABASE_URL": "postgresql://x"}
        with mock.patch.dict("os.environ", env, clear=True):
            with self.assertRaises(ConfigError):
                settings.Settings.from_env()

    def test_runtime_env_present_never_leaks(self):
        self.assertFalse(settings.runtime_env_present({}))
        self.assertTrue(settings.runtime_env_present({
            "DATABASE_URL": "x", "TEACHER_SESSION_SECRET": "y",
        }))


if __name__ == "__main__":
    unittest.main()
