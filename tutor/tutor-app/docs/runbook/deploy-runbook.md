# Deploy Runbook — tutor-app（DU-2 course-app / DU-3 assessment-worker）

> 目标环境：租赁云服务器，单地域（KD-003 基础级）。本手册不执行部署，仅给出可重复步骤。

## 0. 前置

- 主机：Linux x86_64，Docker + Docker Compose v2；磁盘 ≥课程配额（200GB/课程）+ 30% 余量；全盘加密（平台层，KD-003）。
- 镜像：`docker compose -f deploy/docker-compose.yml build`（产出 tutor-server / tutor-worker）。
- 数据库：PostgreSQL 16（compose `db` 服务或外部实例；生产建议托管/独立卷）。
- 环境变量（**secret 只允许环境注入，不入库不入 .env 提交**）：
  - 必填：`DATABASE_URL`、`TEACHER_SESSION_SECRET`
  - 可选：`DATA_DIR`（默认 ./data）、`CONTRACTS_DIR`（默认仓库 contracts/）、`LOG_LEVEL`
- 模型供应商（2026-07-25 批准，**仅限 deepseek**，内部试用/灰度）：`MODEL_PROVIDER`（fake|deepseek）、`MODEL_API_KEY`（deepseek 必填，仅存 .env/环境，不入库不入日志）、`DEEPSEEK_BASE_URL`（默认 https://api.deepseek.com，境内）、`DEEPSEEK_MODEL`（默认 deepseek-chat）
- 供应商降级：`VENDOR_ENABLED`（0=禁用开关，停止认领不终态化任务）、`VENDOR_CIRCUIT_THRESHOLD`（连续失败熔断阈值，默认 5）、`VENDOR_CIRCUIT_COOLDOWN_SECONDS`（冷却，默认 60）
- DU-2 relay 调度器：`RELAY_TICK_INTERVAL_SECONDS`（默认 1.0，0=关闭）
- DU-3 worker（GAP-02 常驻循环）：`WORKER_CONCURRENCY`（认领线程数，默认 2）、`WORKER_POLL_INTERVAL_SECONDS`（默认 1.0）、`CLAIM_LEASE_SECONDS`（租约秒数，默认 120）、`WORKER_ID`（默认 主机名+pid）、`DATA_DIR`（与 server 同一材料根，**容器内只读挂载**）

## 1. 首次部署

```bash
# 1) 数据库初始化/升级（单 head；并行头先 merge）
cd server && DATABASE_URL=postgresql://user:pass@host:5432/tutor python -m alembic upgrade head

# 2) 预置课程与教师（幂等，v1 运维手工）
PYTHONPATH=../shared:. python -m course_app.course_roster.cli provision --course-id CS101 --invite-code <随机强口令> --name "课程名" --course-end-time 2026-09-01T00:00:00Z
PYTHONPATH=../shared:. python -m course_app.teacher_web.access_gate.cli provision --account teacher@example.com --course-id CS101   # 口令经 --password 或 ACCESS_GATE_PROVISION_PASSWORD，不回显

# 3) 启动
docker compose -f deploy/docker-compose.yml up -d db server worker

# 4) 冒烟
curl -s http://localhost:8000/health/live     # {"status":"ok"}
curl -s http://localhost:8000/health/ready    # status=ready 且 checks 全 ok
```

## 2. 升级部署

1. 备份（见 disaster-recovery-runbook）。
2. 拉新镜像 → `alembic upgrade head`（先验证 staging）→ 滚动重启 server → worker。
3. 验证：health/ready + 提交一笔测试提交并确认状态流转。

## 3. 配置复核清单（发布前）

- [ ] `TEACHER_SESSION_SECRET` 为高强度随机值且仅存于环境/密钥管理；
- [ ] `MODEL_PROVIDER` 为批准值（fake 或 deepseek；其他值启动即拒绝）；
- [ ] deepseek 启用时：`MODEL_API_KEY` 经 .env/环境注入且未入库；日志复核无密钥/无材料内容；`VENDOR_ENABLED=1` 与熔断参数已按灰度策略设定；
- [ ] 真实密钥首轮调用已验证（灰度前置：用真实 key 跑一笔 staging 假数据提交并核对 CT-007 等级——接入验证脚本 `python -m scripts.e2e_vendor_deepseek`（stub 形态）已通过；真实 key 验证属发布前人工步骤）；
- [ ] 磁盘加密已启用；备份任务已配置（每日，保留 30 天）；
- [ ] 迁移 `alembic current` = 单 head（当前：`0016_ccr001_assessment_purge`）；
- [ ] `/health/ready` 全 ok；`/metrics` 可抓取；
- [ ] worker 日志出现 `worker starting` + `worker recovery scan`；提交一笔测试提交后 CT-002 自动流转至 scored（无手工 tick）；
- [ ] worker 材料卷为只读挂载（compose `:ro`）；
- [ ] 课程/教师已预置且名单已导入（CT-013）。

## 4. 已知环境差异

- Windows 开发机 vs Linux 生产：路径分隔符、文件锁行为不同（材料存储已做 resolve 归一，见 Phase 6 修复）；
- SQLite 仅用于测试；运行时必须 PostgreSQL（DD-002）。**注意**：系统组件按设计各自管理独立小事务（多连接），SQLite 单写者库锁在嵌套事务流下必然自锁——全链 E2E（scripts/e2e_gap02_fullchain.py）必须在 PG 上运行。
- GAP-02 后 worker 为常驻认领循环（`python -m assessment_worker` 不再启动即退）：优雅关闭经 SIGTERM/SIGINT；崩溃/重启后租约过期自动重认领（LCD-002 reclaim 上限 3，超限任务终态化 scoring_failed 可观测）。
