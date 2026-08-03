# Allowed Context — L15 REVIEW-QUERY

## 可写路径（仅这些）

- `server/course_app/teacher_web/review_query/**`
- `server/tests/test_l15_review_query.py`（如需辅助文件用 `server/tests/l15_*.py`）

注意：本叶子**不建迁移**（读模型表归 PROJECTOR/backfill；经 M05-IC-02 端口注入消费）。

## 只读输入

- `contracts/**`、`shared/**`、`server/course_app/**`（其余）、`server/migrations/**`、兄弟目录、`plugin/`、`worker/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装；**禁止再安装**。单测 SQLite；TestClient 场景引擎用 StaticPool + check_same_thread=False。
- 测试运行目录：worktree 根（`.worktrees/L15-review-query`）。
