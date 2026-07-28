# Configuration — tutor-app

## 规则

- secret 只允许来自环境变量；`.env` 仅本地开发且不入库（.gitignore）；样例见根目录 `.env.example`。
- 禁止把 secret 写入日志、异常消息、迁移或测试夹具。

## 环境变量

| 变量 | 消费方 | 必需 | 说明 |
|---|---|---|---|
| `DATABASE_URL` | server/worker | 运行时必需 | PostgreSQL DSN（DD-002），迁移同样使用 |
| `TEACHER_SESSION_SECRET` | server | 运行时必需 | 教师会话签名 secret（DD-004） |
| `DATA_DIR` | server | 否（默认 `./data`） | 材料磁盘根（KD-002） |
| `CONTRACTS_DIR` | server | 否（默认 `contracts/`） | 冻结契约目录 |
| `LOG_LEVEL` | 全部 | 否（默认 INFO） | 结构化日志级别 |
| `MODEL_PROVIDER` | worker | 否（默认 `fake`） | Phase 1 仅允许 `fake`；真实供应商配置为 DD-009 实现细节 |
| `MODEL_API_KEY` | worker | 真实供应商时必需 | secret；fake 模式忽略 |
| `CLAIM_LEASE_SECONDS` | worker | 否（默认 120） | 任务认领租约（MOD-04 LCD-002） |
| `TUTOR_RUN_ID` | 全部 | 否 | 运行标识（tutor-r01） |

## 部署差异

- 本地开发：`deploy/docker-compose.yml` 提供 PostgreSQL 16 与 DU-2/DU-3 容器。
- 生产：KD-003 基础级（单地域、HTTPS、存储加密、每日备份 30 天）；具体地域/域名/备份工具 Phase 6 定（TD-10 → DD-008）。
