"""DU-2 配置。常量锁定设计冻结值（KD-003/004、NFR-003），环境变量覆盖部署差异。

secret（TEACHER_SESSION_SECRET 等）只允许来自环境变量，无默认值。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tutor_shared.config import get_str, require_str

# KD-004：单次提交上限 500MB；单课程存储配额 200GB
MAX_SUBMISSION_BYTES = 500 * 1024 * 1024
COURSE_QUOTA_BYTES = 200 * 1024**3
# NFR-003：上传接收确认 30 秒；Agent 评分 10 分钟；CT-010 单次模型调用 ≤3 分钟
RECEIPT_TARGET_SECONDS = 30
SCORING_TARGET_SECONDS = 600
MODEL_CALL_TIMEOUT_SECONDS = 180
# API 前缀（KD-005）
API_PREFIX = "/api/v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACTS_DIR = REPO_ROOT / "contracts"


@dataclass(frozen=True)
class Settings:
    database_url: str  # PostgreSQL（DD-002）；本地开发见 deploy/docker-compose.yml
    data_dir: Path  # 材料磁盘根（KD-002 本地磁盘 + 存储加密由平台承担，DD-005）
    contracts_dir: Path
    teacher_session_secret: str  # secret：仅环境变量
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=require_str("DATABASE_URL"),
            data_dir=Path(get_str("DATA_DIR", "./data") or "./data"),
            contracts_dir=Path(get_str("CONTRACTS_DIR", str(DEFAULT_CONTRACTS_DIR)) or str(DEFAULT_CONTRACTS_DIR)),
            teacher_session_secret=require_str("TEACHER_SESSION_SECRET"),
            log_level=get_str("LOG_LEVEL", "INFO") or "INFO",
        )


def runtime_env_present(env: dict[str, str] | None = None) -> bool:
    """运行配置是否齐备（readiness 检查用；不泄露值）。"""
    env = os.environ if env is None else env
    return bool(env.get("DATABASE_URL")) and bool(env.get("TEACHER_SESSION_SECRET"))
