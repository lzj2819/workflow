"""Alembic 迁移环境（DU-2 course-app，PostgreSQL）。

URL 来自环境变量 DATABASE_URL（tutor_shared.config.require_str），不入库。
表结构随叶子落地（Phase 2 起）：每个叶子的 migration 必须在同一事务内
包含其聚合表与对应 Outbox 相关约束（见 03-data-and-consistency 事务边界）。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

config = context.config
if config.config_file_name is not None:
    # disable_existing_loggers=False：迁移进程不得禁用宿主既有 logger
    # （pytest 同进程跑迁移时会把业务模块 logger 全部 disabled，静默吞掉日志断言）
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None  # Phase 2 起改为 course_app 的 Base.metadata


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for migrations")
    if url.startswith("postgresql://"):  # 统一 psycopg v3 驱动（环境仅装 psycopg[binary]）
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        {"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
