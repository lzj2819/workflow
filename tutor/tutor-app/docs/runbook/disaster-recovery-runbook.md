# Disaster Recovery Runbook — tutor-app

> 等级：KD-003 基础级（RPO 24h / RTO 48h；每日备份保留 30 天）。

## 1. 备份（每日）

```bash
# 数据库（pg_dump，含 alembic_version 以核对迁移位点）
docker exec tutor-db-1 pg_dump -U tutor tutor > backup/tutor-$(date +%F).sql
# 材料磁盘（DATA_DIR）
rsync -a --delete data/materials/ backup/materials-$(date +%F)/
```

保留 30 天；每月异地复制一次（建议）。**演练证据（Phase 6，2026-07-22）**：pg_dump 1871 行备份 → downgrade base → 恢复 → 数据与 38 表齐备、迁移位点 `27867c368f7e` 一致。

## 2. 恢复（灾难后）

1. 准备干净 PostgreSQL 实例（**恢复目标必须为空库**；向非空库整库恢复会产生 alembic_version 冲突警告——Phase 6 演练实测）。
2. `psql -U tutor -d tutor < backup/tutor-<日期>.sql`
3. 恢复材料磁盘到 `DATA_DIR`（校验抽样 sha256 与 material_files 登记一致）。
4. `alembic current` 核对位点；如版本落后，`alembic upgrade head`。
5. 启动服务 → `/health/ready` 全 ok → 抽查提交状态与教师查询。

## 3. 故障场景处置

| 场景 | 处置 |
|---|---|
| DU-3 worker 崩溃 | 任务持久化不丢；重启后继续认领（租约到期重认领，reclaim>3 终态化）；积压监控告警 |
| DU-2 崩溃 | 修复后重启；Outbox 继续投递（无事件丢失）；`/health/ready` 恢复前不接流量 |
| 数据库不可用 | 提交保持待处理；恢复后 relay 续投；检查 `outbox_records` 中 retry_wait 积压 |
| 材料磁盘满（200GB 配额） | 配额写入前置拒绝（QUOTA_EXCEEDED）；清理 `data/uploads/` 过期暂存后评估扩容 |
| 模型服务不可用 | 评分失败自动重试一次 → scoring_failed + 教师端内通知；不伪造等级；恢复后由教师关注失败列表 |

## 4. 审计与证据保全

- `deletion_audit_records` 与 `access_denied_log` 为追加式、永久留存、**不在业务删除范围内**；
- 恢复演练每学期至少一次（本手册 §1-2 步骤）。
