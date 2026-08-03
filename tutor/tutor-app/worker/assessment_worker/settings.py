"""DU-3 配置。常量锁定设计冻结值（NFR-003、REQ-012、MOD-04 LCD-002/LCD-004、TD-07）。

secret（MODEL_API_KEY）只允许来自环境变量，无默认值、不打日志。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from tutor_shared.config import get_int, get_str, require_str

# NFR-003 / CT-010：任务总预算 10 分钟；单次模型调用 ≤3 分钟
TASK_BUDGET_SECONDS = 600
MODEL_CALL_TIMEOUT_SECONDS = 180
# REQ-012：评分失败自动重试一次（仅一次）
MAX_RETRY_ATTEMPTS = 1
# MOD-04 LCD-002：认领租约与重认领上限（>3 终态化）
CLAIM_LEASE_SECONDS = 120
MAX_RECLAIM_COUNT = 3
# TD-07 / 06-deployment：worker 部署基线 2–3 副本，按任务积压扩缩
WORKER_REPLICAS_BASELINE = (2, 3)


@dataclass(frozen=True)
class Settings:
    database_url: str  # 与 DU-2 同一数据库（KD-002 同组共部署）
    model_provider: str  # Phase 1 仅允许 "fake"；真实供应商配置为实现细节（DD-009）
    model_api_key: str | None  # 仅环境变量；fake 模式可为 None
    log_level: str = "INFO"
    claim_lease_seconds: int = CLAIM_LEASE_SECONDS
    # GAP-02 常驻循环配置
    data_dir: str = "data"  # 材料只读根（与 DU-2 同一 DATA_DIR；容器经只读卷挂载）
    worker_id: str = ""  # 认领 owner 前缀；空 → 主机名+pid 自动派生
    concurrency: int = 2  # 认领线程数（每线程独占一个任务租约）
    poll_interval_seconds: float = 1.0  # 无任务/无事件时的轮询间隔
    # 供应商降级策略（用户 2026-07-25 批准：不可用 → 无自动评分/稍后重试）
    vendor_enabled: bool = True  # VENDOR_ENABLED=0 禁用开关：停止认领，任务保持 pending
    circuit_threshold: int = 5  # 连续供应商失败（MODEL_TIMEOUT/MODEL_ERROR）熔断阈值
    circuit_cooldown_seconds: float = 60.0  # 熔断冷却（期间不认领，任务稍后自动重试）

    @classmethod
    def from_env(cls) -> "Settings":
        provider = get_str("MODEL_PROVIDER", "fake") or "fake"
        return cls(
            database_url=require_str("DATABASE_URL"),
            model_provider=provider,
            model_api_key=get_str("MODEL_API_KEY"),
            log_level=get_str("LOG_LEVEL", "INFO") or "INFO",
            claim_lease_seconds=get_int("CLAIM_LEASE_SECONDS", CLAIM_LEASE_SECONDS),
            data_dir=get_str("DATA_DIR", "data") or "data",
            worker_id=get_str("WORKER_ID", "") or "",
            concurrency=get_int("WORKER_CONCURRENCY", 2),
            poll_interval_seconds=float(get_str("WORKER_POLL_INTERVAL_SECONDS", "1.0") or "1.0"),
            vendor_enabled=(get_str("VENDOR_ENABLED", "1") or "1") not in ("0", "false", "no"),
            circuit_threshold=get_int("VENDOR_CIRCUIT_THRESHOLD", 5),
            circuit_cooldown_seconds=float(get_str("VENDOR_CIRCUIT_COOLDOWN_SECONDS", "60") or "60"),
        )


def runtime_env_present(env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(env.get("DATABASE_URL"))
