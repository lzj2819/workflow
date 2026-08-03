"""数据库引擎与事务边界（PostgreSQL 运行时，DD-002）。

事务边界规则（03-data-and-consistency）：
- 聚合写入与其 Outbox 行在同一本地事务提交；
- 状态机迁移 + 材料清单 + 完整性报告同事务；
- 审计记录先于清除写入。

第三方依赖（sqlalchemy/psycopg）在此集中、惰性导入：未安装时除
engine()/session_scope() 外其余功能不受影响（单元测试不需要真实数据库）。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from course_app.settings import Settings


def _import_sqlalchemy():
    try:
        import sqlalchemy  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "sqlalchemy is required at runtime; install server/requirements.txt"
        ) from exc
    return sqlalchemy


def normalize_db_url(url: str) -> str:
    """统一 PostgreSQL 驱动为 psycopg v3（sqlalchemy `postgresql://` 默认 psycopg2，
    运行环境仅安装 psycopg[binary]；staging 镜像实测暴露）。"""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def engine(settings: Settings):
    sa = _import_sqlalchemy()
    kwargs: dict = {"pool_pre_ping": True}
    if not settings.database_url.startswith("sqlite"):
        # 池尺寸按 NFR-002（30 并发提交，每请求多小事务）配置；
        # PG 默认 max_connections=100，单实例 DU-2 下 20+30 有充足余量
        kwargs.update(pool_size=20, max_overflow=30)
    return sa.create_engine(normalize_db_url(settings.database_url), **kwargs)


@contextmanager
def session_scope(eng) -> Iterator:
    """单事务作用域：聚合写入 + Outbox 行同事务提交；异常回滚。"""
    sa = _import_sqlalchemy()
    with sa.orm.Session(eng) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
