# Allowed Context — L14 REVIEW-COMMAND

## 可写路径（仅这些）

- `server/course_app/teacher_web/review_command/**`
- `server/migrations/versions/0007_review_records.py`（新建；`down_revision="b9c6e3d6276a"`）
- `server/tests/test_l14_review_command.py`（如需辅助文件用 `server/tests/l14_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余）、`server/migrations/**`（除上述新文件）、兄弟目录、`plugin/`、`worker/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装（fastapi/SQLAlchemy/alembic/pydantic/psycopg）；**禁止再安装**。
- 单测 SQLite（`sqlite:///:memory:`）；TestClient 场景引擎用 `poolclass=StaticPool, connect_args={"check_same_thread": False}`（跨线程共享，环境注记）。
- alembic 统一 `python -m alembic`。测试运行目录：worktree 根（`.worktrees/L14-review-command`）。
