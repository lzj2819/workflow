# Rollback Runbook — tutor-app

> 适用于升级后需回退的场景。原则：先保数据，再回版本；迁移可回滚到 base 但生产禁止（数据丢失），生产回滚以「应用版本回退 + 迁移保持」为主。

## 1. 快速回退（应用层）

1. 备份当前数据库与材料磁盘（见 disaster-recovery-runbook §1）。
2. 部署上一个已知良好镜像（`docker compose ... up -d --force-recreate server worker`，镜像 tag 用上一发布版）。
3. 验证 `/health/ready` 与关键链路（auth-token → 提交 → 状态查询）。

## 2. 迁移相关回退

- 应用代码与 schema 兼容（新列/新表追加式）：**只回退应用**，不执行 `alembic downgrade`。
- 应用要求旧 schema：评估 `alembic downgrade <目标版本>`（**仅在已备份且确认无新增数据依赖时**；执行前再次备份；执行后 `alembic current` 核对）。
- 绝对禁止：在未备份的生产库上 `downgrade base`（全表删除）。

## 3. 配置回退

- 环境变量/compose 变更回退：恢复上一版 `.env`（不入库的密钥管理记录）与 `deploy/docker-compose.yml` 至上一发布 tag。

## 4. 回退验证清单

- [ ] `/health/live` `/health/ready` 全 ok
- [ ] `alembic current` 与预期版本一致
- [ ] auth-token 换领 + 提交 + CT-002 状态正常
- [ ] Outbox 无异常积压（`select status, count(*) from outbox_records group by 1`）
- [ ] 教师登录 + CT-007 查询正常

## 5. 回退后动作

- 记录回退原因与时间到运维日志；
- 修复验证后再按 deploy-runbook §2 重新升级。
