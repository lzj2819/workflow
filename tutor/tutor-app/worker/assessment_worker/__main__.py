"""DU-3 任务入口：`python -m assessment_worker`（GAP-02 常驻认领循环）。

启动 WorkerRunner：CT-004 入站消费 + 并发认领执行（租约续期/失败重试/
优雅关闭/重启恢复）。配置全部经环境变量（见 assessment_worker.settings）；
MODEL_PROVIDER 仅允许 fake（不接入真实供应商）；secret 只经环境变量传入。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "shared"), str(ROOT / "server")]

from tutor_shared.logging import get_logger  # noqa: E402

from assessment_worker.runner import WorkerRunner  # noqa: E402
from assessment_worker.settings import Settings  # noqa: E402


def main() -> int:
    settings = Settings.from_env()
    logger = get_logger("assessment_worker", settings.log_level)
    logger.info(
        "worker entry",
        extra={
            "run_id": os.environ.get("TUTOR_RUN_ID", "tutor-r01"),
            "model_provider": settings.model_provider,
            "concurrency": settings.concurrency,
        },
    )
    return WorkerRunner(settings).run()


if __name__ == "__main__":
    raise SystemExit(main())
