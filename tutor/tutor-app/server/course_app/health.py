"""DU-2 健康检查装配（纯函数；HTTP 绑定随 L09 SI-API 落地）。

readiness 检查项：
- config：运行环境变量齐备（DATABASE_URL、TEACHER_SESSION_SECRET，不泄露值）；
- contracts：冻结契约注册表可加载；
- database：PostgreSQL 连通（驱动未安装/未配置时报告 fail，不伪造 ok）。
"""
from __future__ import annotations

from pathlib import Path

from tutor_shared import health as shared_health

from course_app.settings import DEFAULT_CONTRACTS_DIR, runtime_env_present


def _check_config() -> tuple[bool, str]:
    ok = runtime_env_present()
    return ok, "env present" if ok else "missing DATABASE_URL or TEACHER_SESSION_SECRET"


def _check_contracts() -> tuple[bool, str]:
    try:
        from course_app.contracts_registry import load_registry

        registry = load_registry(DEFAULT_CONTRACTS_DIR)
    except Exception as exc:
        return False, f"contracts registry error: {exc}"
    return True, f"{len(registry)} contracts loaded"


def _check_database() -> tuple[bool, str]:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False, "psycopg not installed (runtime dependency, see server/requirements.txt)"
    try:
        from course_app.settings import Settings

        url = Settings.from_env().database_url
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        return False, f"database unreachable: {type(exc).__name__}"
    return True, "select 1 ok"


def _check_storage(data_dir: Path) -> tuple[bool, str]:
    return (True, "dir exists") if data_dir.exists() else (False, f"{data_dir} missing")


def liveness() -> dict:
    return shared_health.liveness()


def readiness(data_dir: Path | None = None) -> dict:
    checks = {
        "config": _check_config,
        "contracts": _check_contracts,
        "database": _check_database,
    }
    if data_dir is not None:
        checks["storage"] = lambda: _check_storage(data_dir)
    return shared_health.readiness(checks)
