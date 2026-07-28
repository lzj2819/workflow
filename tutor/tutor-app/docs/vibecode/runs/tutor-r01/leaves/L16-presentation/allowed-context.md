# Allowed Context — L16 PRESENTATION

## 可写路径（仅这些）

- `server/course_app/teacher_web/presentation/**`
- `server/migrations/versions/0008_presentation_views.py`（新建；`down_revision="b9c6e3d6276a"`）
- `server/tests/test_l16_presentation.py`（如需辅助文件用 `server/tests/l16_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余）、`server/migrations/**`（除上述新文件）、兄弟目录、`plugin/`、`worker/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装；**禁止再安装**。单测 SQLite；TestClient 场景引擎用 StaticPool + check_same_thread=False。
- alembic 统一 `python -m alembic`。测试运行目录：worktree 根（`.worktrees/L16-presentation`）。
