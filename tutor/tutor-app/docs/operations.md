# Operations — tutor-app（KD-003 基础级运维基线）

## 健康与观测

- `/health/live`、`/health/ready`：readiness 检查 config / contracts / database / storage（装配见 `server/course_app/health.py`；HTTP 绑定随 L09 落地）。
- `/metrics`：文本暴露（`tutor_shared/metrics.py`）。SM-001~003 统计报表由 Phase 5 backfill 的监控落地（KD-003）。
- 结构化日志：JSON 行（`tutor_shared/logging.py`）；禁止记录 secret 与学生材料内容。

## 部署形态（06-deployment）

- DU-1 plugin：学生本机分发（无服务端运维）。
- DU-2 course-app：MOD-02/03/05 同部署单元；垂直扩容（磁盘、带宽）为主。
- DU-3 assessment-worker：独立扩缩；基线 2–3 副本，按评分任务积压调整（TD-07/DD-006）。
- 共享：单一 PostgreSQL + 材料本地磁盘 + Outbox（同组共部署，KD-002）。

## 备份与恢复

- 每日备份保留 30 天（数据库 + 材料磁盘）；RPO 24h / RTO 48h；恢复演练每学期至少一次（建议）。
- 备份工具与地域 Phase 6 定（DD-008）。

## 保留治理

- retention_due_at = 课程结束时间 + 1 年（MOD-05 批处理，FLOW-011 只读引用）。
- 到期 → 教师 CT-007 可见批次 → CT-011 确认 → CT-012 清除（MOD-02 材料 + MOD-04 评分记录 + 读模型）→ CT-014 + CT-015 双回流（CCR-001 已实施）→ 批次 completed。
- 审计记录永久留存，不随业务数据删除。

## 告警（基础级）

进程存活、磁盘水位（200GB/课程配额）、评分任务积压、模型调用失败率、上传成功率。

GAP-02 worker 可观测（日志/metrics 计数，worker 日志为唯一导出面）：

- `worker_backlog_pending` / `worker_backlog_in_progress`（启动扫描 gauge；积压告警口径）；
- `worker_tasks_failed_total` / `worker_tasks_retried_total`（失败/重试速率；持续上升 → 模型或材料链异常）；
- `worker_task_exceptions_total`（未分类异常；>0 即应排查）、`worker_stale_callbacks_total`（租约竞争）；
- `worker_lease_renew_errors_total` / `worker_lease_renew_failures_total`（DB 连通性或租约丢失）；
- `material_reads_total` / `material_read_denied_total`（材料读取与越权拒绝；denied>0 即告警——跨课程/越权访问信号）；
- `worker_ct004_confirmed_total` / `worker_ct004_tombstoned_total`（入站吞吐与墓碑守卫命中）。

供应商接入可观测（deepseek，2026-07-25 批准）：

- `vendor_calls_total` / `vendor_failures_total` / `vendor_timeouts_total`（供应商调用成败与超时；失败率突增 → 供应商侧或网络异常）；
- `vendor_circuit_opens_total`（熔断开启次数；>0 即降级发生，期间无自动评分、任务稍后重试）；
- `vendor_kill_switch`（gauge：1=禁用开关生效中，0=正常）。

## 组合根启动与 relay 驱动（T-B03d）

- 组合根：`course_app.composition.build_composition(settings)` 装配全部组件与
  router；ASGI 入口 `uvicorn course_app.main:create_app --factory`（工作目录
  `server/`，环境变量 `DATABASE_URL`、`TEACHER_SESSION_SECRET`、`DATA_DIR`、
  `CONTRACTS_DIR`）。
- 迁移：启动不自动迁移（缺模式只告警）；部署/升级前先执行
  `cd server && alembic upgrade heads`（并行多头先 `alembic merge heads`）。
- 预置（幂等，v1 运维手工）：
  - 课程/邀请码：`python -m course_app.course_roster.cli provision --course-id CS101 --invite-code INV-2026-CS101 [--name ...] [--course-end-time ...]`
  - 教师账号 + 课程授权：`python -m course_app.teacher_web.access_gate.cli provision --account teacher@example.com --course-id CS101`（口令经 `--password` 或 `ACCESS_GATE_PROVISION_PASSWORD`，不回显）
- relay 驱动：`app.state.composition.relayer_tick()` 单轮投递（CT-005/006/012/014/015
  消费注册，每 consumer 经 InboundDedup 包装）；**ASGI lifespan 进程内调度器周期
  调用**（`RELAY_TICK_INTERVAL_SECONDS`，默认 1.0s，0=关闭），不在请求路径上阻塞。
  只认领已注册契约（fetch_due contract_ids 过滤）；CT-004 归 DU-3 worker（GAP-02
  常驻循环），本组合根不认领、不退避。
- DU-3 worker：`python -m assessment_worker` 常驻循环（GAP-02）——CT-004 入站 +
  并发认领执行（租约续期/REQ-012 任务内重试/优雅关闭/崩溃重认领恢复）；材料经
  ICT-003 只读端口读取（DATA_DIR 只读挂载；L02 清单授权、final 限定、500MB 上限派生）。
- readiness：`/health/ready` 检查 config / contracts / database（组合根 engine
  SELECT 1）/ storage，失败如实上报，不伪造 ok。
