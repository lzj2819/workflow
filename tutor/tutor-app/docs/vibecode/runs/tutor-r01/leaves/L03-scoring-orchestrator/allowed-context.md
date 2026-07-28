# Allowed Context — L03 SCORING-ORCHESTRATOR

## 可写路径（仅这些）

- `worker/assessment_worker/scoring_orchestrator/**`（与 Phase 1 脚手架包位置一致，2026-07-20 更正）
- `server/migrations/versions/0004_scoring_tasks.py`（共享 DB 迁移链；新建；`down_revision="0001_baseline"`）
- `worker/tests/test_l03_scoring_orchestrator.py`（如需辅助文件用 `worker/tests/l03_*.py`）

## 只读输入

- `contracts/**`、`shared/**`、`server/`（除上述一个新迁移文件）、`worker/assessment_worker/**`（含 settings.py、model_provider.py）、`plugin/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- 依赖已装（fastapi/SQLAlchemy/alembic/pydantic/psycopg），**禁止再 pip/npm 安装**。
- 单测数据库 SQLite（`sqlite:///:memory:`）；模型禁用 PG 专有类型（用 sa.JSON）。
- 测试运行目录：worktree 根（`.worktrees/L03-scoring-orchestrator`）。
