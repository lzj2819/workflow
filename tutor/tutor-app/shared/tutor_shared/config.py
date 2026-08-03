"""环境变量配置助手（stdlib）。

规则（AGENTS.md / KD）：
- secret 一律来自环境变量，不写默认值、不入库、不打日志；
- 非 secret 配置允许默认值；
- .env 仅用于本地开发（docker compose env_file），生产用真实环境变量。
"""
from __future__ import annotations

import os


class ConfigError(RuntimeError):
    """必需配置缺失或非法。"""


def get_str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def require_str(name: str) -> str:
    value = get_str(name)
    if value is None:
        raise ConfigError(f"missing required env var: {name}")
    return value


def get_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"env var {name} must be int, got {value!r}") from exc


def get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"env var {name} must be bool, got {value!r}")
