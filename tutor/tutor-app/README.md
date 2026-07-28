# tutor-app

tutor（Vibe Coding 课程评估系统）实现仓库。设计输入：`../tutor/`（只读）。运行控制面：`docs/vibecode/runs/tutor-r01/`。

## 布局

| 目录 | 内容 |
|---|---|
| `plugin/` | DU-1 MOD-01 codex-plugin（Node ESM，零依赖；Phase 1：host 端口/配置/核心端口/测试骨架） |
| `server/` | DU-2 course-app（MOD-02/03/05；Python + FastAPI 基线 + PostgreSQL + alembic 迁移入口） |
| `worker/` | DU-3 assessment-worker（MOD-04；Python；ModelProvider 端口 + fake provider） |
| `shared/` | DU-2/DU-3 共享平台层（config/logging/metrics/health/outbox/lease，stdlib） |
| `contracts/` | 冻结契约机器可读 schema（仅 Integration Owner 维护） |
| `deploy/` | Dockerfile × 2 + docker-compose（PostgreSQL 本地开发） |
| `docs/` | 开发/测试/配置/运维/恢复说明 + 详细设计记录 + 运行控制文件 |

## 快速开始

```bash
cp .env.example .env            # 填写 TEACHER_SESSION_SECRET 等
# 运行验证（无需安装依赖）：
PYTHONPATH="shared;server;worker" python -m unittest discover -s server/tests -t . -v
PYTHONPATH="shared;server;worker" python -m unittest discover -s worker/tests -t . -v
cd plugin && npm test           # node --test，零依赖
```

详见 `docs/development.md`、`docs/testing.md`。当前阶段：Phase 1（生产基线），见 `task_plan.md`。
