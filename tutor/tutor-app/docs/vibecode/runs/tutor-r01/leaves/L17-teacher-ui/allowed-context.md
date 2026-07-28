# Allowed Context — L17 TEACHER-UI

## 可写路径（仅这些）

- `server/course_app/teacher_web/ui/**`（模板、静态资源、SSR 视图与 API 客户端层）
- `server/tests/test_l17_teacher_ui.py`（如需辅助文件用 `server/tests/l17_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余）、兄弟目录、`plugin/`、`worker/`、`deploy/`、`docs/`、`server/migrations/**`
- tutor 设计包（只读）

## 环境

- 依赖已装；**禁止再安装**（Jinja2 随 fastapi 已装）。不引入前端框架/npm 依赖/构建链。
- 单测 SQLite；TestClient 场景引擎用 StaticPool + check_same_thread=False。
- 测试运行目录：worktree 根（`.worktrees/L17-teacher-ui`）。
