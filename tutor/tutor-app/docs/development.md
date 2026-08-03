# Development — tutor-app

## 环境

- Python 3.12+（开发与验证 3.14 已验证）；Node 20+（24 已验证）。
- 运行时依赖（`server/requirements.txt`、`worker/requirements.txt`）在需要真实运行时前安装：`pip install -r server/requirements.txt`。Phase 1 的单元/契约测试**不需要**第三方依赖。
- 本地数据库：PostgreSQL 16（`deploy/docker-compose.yml`）。

## 边界（AGENTS.md 摘要）

- 代码只写本仓库；`../tutor/` 设计包只读。
- 叶子只能改 execution-matrix 中自己的 `allowed_paths`；`contracts/`、`shared/` 仅 Integration Owner 维护。
- 共享契约变更必须先 contract-change-request 并获批准。
- 禁止：接入真实外部模型、发送学生材料、读取未授权 Codex 日志/会话文件（Phase 1）。

## 目录约定

- `server/course_app/submission_intake/{api,core,xfer}` → L09/L02/L08；`course_roster` → L01；`teacher_web/{review_command,review_query,presentation,ui}` → L14/L15/L16/L17。
- `worker/assessment_worker/{scoring_orchestrator,assessment_engine}` → L03/L12。
- `plugin/src/` → L04~L07、L10、L11、L13（Wave 1/2 创建实现目录）。

## 数据库迁移

```bash
cd server
DATABASE_URL=postgresql://tutor:tutor@localhost:5432/tutor alembic upgrade head
DATABASE_URL=... alembic revision -m "l02 submission core"   # 新迁移
```

规则：聚合表与其 Outbox 相关约束在同一 migration；事务边界见 `course_app/db.py` docstring。

## 详细设计记录

`docs/design/phase-1-detail-design.md`（DD-001~DD-009）。实现中落地的 defer/implementation_detail 项须登记到 `findings.md`。
