"""ST-004 RubricPolicy 持久化模型（MOD-04 / CMP-RUBRIC-PROMPT-COMPOSER 所有）。

约束：单测库为 SQLite（sqlite:///:memory: 或临时文件），禁用 PG 专有类型
（dimensions/grade_bands 用 sa.JSON）；生产 PostgreSQL 表结构由
server/migrations/versions/0011_rubric_policies.py 落地。
评分主路径只读；写路径仅为发布/调优流程（配置变更）。
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"


class RubricBase(DeclarativeBase):
    """ST-004 聚合声明式基类（仅 rubric_policies 一表）。"""


class RubricPolicy(RubricBase):
    """ST-004 RubricPolicy 行：版本化评分准则与提示模板存证。"""

    __tablename__ = "rubric_policies"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    rubric_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    template_body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    dimensions: Mapped[list] = mapped_column(sa.JSON, nullable=False)
    grade_bands: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    # active / superseded；同库 active 唯一由迁移部分唯一索引保证
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
