# Allowed Context — L01 course-roster

## 可写路径（仅这些；相对 worktree 根）

- `server/course_app/course_roster/**`（本叶子全部实现；与 Phase 1 脚手架包位置一致，2026-07-20 更正）
- `server/migrations/versions/0002_course_roster.py`（新建；`down_revision="0001_baseline"`）
- `server/tests/test_l01_course_roster.py`（新建；如需辅助文件用 `server/tests/l01_*.py`）

## 只读输入（禁止修改）

- `contracts/**`、`shared/**`、`server/course_app/**`、`server/migrations/**`（除上述一个新文件）
- `docs/**`、`plugin/**`、`worker/**`、`deploy/**`
- tutor 设计包（绝对路径只读）

## 环境

- 已安装：fastapi 0.135.3、SQLAlchemy 2.0.50、alembic 1.18.4、pydantic 2.13.4、psycopg 3.3.4。**不要再运行 pip/npm 安装。**
- 单元测试数据库：SQLite（`sqlite:///:memory:`，用户批准口径）；模型禁用 PG 专有类型（用 sa.JSON 而非 JSONB）。
- 测试运行目录：worktree 根（`.worktrees/L01-course-roster`）。
