# Allowed Context — L02 SI-CORE

## 可写路径（仅这些）

- `server/course_app/submission_intake/core/**`（与 Phase 1 脚手架包位置一致，2026-07-20 更正）
- `server/migrations/versions/0003_submission_core.py`（新建；`down_revision="0001_baseline"`）
- `server/tests/test_l02_si_core.py`（如需辅助文件用 `server/tests/l02_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`、`server/migrations/**`（除上述新文件）
- 兄弟目录 `server/submission_intake/api/`、`xfer/`、`course_roster/`、`teacher_web/`、`plugin/`、`worker/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装（fastapi/SQLAlchemy/alembic/pydantic/psycopg），**禁止再 pip/npm 安装**。
- 单测数据库 SQLite（`sqlite:///:memory:`）；模型禁用 PG 专有类型（用 sa.JSON）。
- 测试运行目录：worktree 根（`.worktrees/L02-si-core`）。
