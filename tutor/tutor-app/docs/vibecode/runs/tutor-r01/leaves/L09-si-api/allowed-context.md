# Allowed Context — L09 SI-API

## 可写路径（仅这些）

- `server/course_app/submission_intake/api/**`
- `server/migrations/versions/0006_auth_tokens.py`（新建；`down_revision="9c99fa53f9f8"`）
- `server/tests/test_l09_si_api.py`（如需辅助文件用 `server/tests/l09_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余；可 import L01/L02 的公开端口用于注入，不得修改）
- `server/migrations/**`（除上述新文件）、兄弟目录、`plugin/`、`worker/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装（fastapi 0.135.3 等）；**禁止再安装**。fastapi TestClient 可用（httpx 已随 fastapi 安装）。
- 单测 SQLite；模型用 sa.JSON。
- 测试运行目录：worktree 根（`.worktrees/L09-si-api`）。统一用 `python -m alembic`。
