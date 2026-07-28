# Allowed Context — L08 SI-XFER

## 可写路径（仅这些）

- `server/course_app/submission_intake/xfer/**`
- `server/migrations/versions/0005_upload_sessions.py`（新建；`down_revision="9c99fa53f9f8"`）
- `server/tests/test_l08_si_xfer.py`（如需辅助文件用 `server/tests/l08_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余）、`server/migrations/**`（除上述新文件）
- 兄弟目录（core/api/course_roster/teacher_web/plugin/worker/deploy/docs）
- tutor 设计包（只读）

## 环境

- 依赖已装（fastapi/SQLAlchemy/alembic/pydantic/psycopg）；**禁止再安装**。
- 单测 SQLite（`sqlite:///:memory:`）；模型用 sa.JSON。
- 测试运行目录：worktree 根（`.worktrees/L08-si-xfer`）。统一用 `python -m alembic`（PATH 上 Anaconda alembic 与 Python 3.14 不兼容）。
