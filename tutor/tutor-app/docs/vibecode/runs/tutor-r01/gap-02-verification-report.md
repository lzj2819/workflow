# GAP-02 Verification Report — DU-3 常驻认领循环 + ICT-003 材料读端口

- 日期：2026-07-25；执行：Integration Owner；基线：main `dbe2b66`（用户批准 GAP-02 范围）
- 范围：① DU-3 worker 常驻认领循环；② ICT-003 材料读端口生产实现；③ 配置/监控/测试/Runbook/控制面。
- 边界遵守：未修改共享契约语义（Outbox `fetch_due` 增可选过滤参数为内部抽象演进，非冻结契约）；未接入真实供应商/密钥/学生数据；未部署；最终发布未批准。

## 1. 交付物

| 项 | 位置 | 说明 |
|---|---|---|
| DU-3 常驻循环 | `worker/assessment_worker/runner.py` + `__main__.py` | CT-004 入站（contract_ids 过滤）+ N 槽并发认领 + L12 真实装配 |
| 租约续期 | runner `_heartbeat` | 执行期间按 lease_ttl/3 心跳续约；续约失败仅记录，终态回调由 orchestrator 守卫 |
| 失败重试 | runner `_execute_claimed` | REQ-012 任务内重试（同租约 attempt_no=2，不重新认领）；未分类异常释放租约不耗业务预算 |
| 优雅关闭/重启恢复 | runner `run`/`request_shutdown` | SIGTERM/SIGINT 停认领、在飞任务完成；崩溃后租约过期自动重认领（LCD-002 上限终态化） |
| ICT-003 生产实现 | `server/course_app/submission_intake/store/reader.py` | MOD-02 所有权只读端口 |
| Outbox 分工过滤 | `shared/tutor_shared/outbox.py` + relay/relayer.py + runner | `fetch_due(contract_ids=)`：DU-2 只认领已注册契约、DU-3 只认领 CT-004 |
| 配置 | worker `settings.py` + `.env.example` + compose ×2 | WORKER_CONCURRENCY/POLL_INTERVAL/CLAIM_LEASE/WORKER_ID/DATA_DIR、RELAY_TICK_INTERVAL_SECONDS |
| 监控 | metrics 计数 ×12 + 结构化日志 | 见 docs/operations.md「GAP-02 worker 可观测」清单 |
| 部署接线 | Dockerfile.worker/server + compose.staging | worker 镜像含 server 包（ICT-003 宿主）；材料卷 `:ro` 只读挂载 |

## 2. ICT-003 授权与边界（生产语义）

- **授权以 L02 提交清单（submission_materials）为准**：仅可读当前评分提交清单内的 ref；跨提交/跨课程整体拒绝（不返回部分内容，防越权侧信道）。
  - 设计注记：不以 `material_files.course_id` 判定——D-P5-01 勘误形态下登记为 `_unassigned`（promote 先于课程归属），权威归属链是清单。staging 首轮 E2E 即因此暴露 MATERIAL_UNREADABLE，已修正。
- 仅 `state=final` 可读（staged/deleted/未登记拒绝）；路径 `_confined` 限定 DATA_DIR；单文件上限 = MAX_SUBMISSION_BYTES（KD-004 派生，不新造口径）。
- 只读无副作用（状态/时间戳不变）；成功与拒绝均结构化日志 + 计数（`material_reads_total` / `material_read_denied_total`，denied>0 即越权告警信号）。

## 3. 验证证据

### 3.1 单元/组件（worker/tests/test_gap02_runner.py 10 项 + server/tests/test_gap02_material_reader.py 13 项，全绿 ×4 轮稳定）

- 重启/恢复：租约过期自动重认领并完成（reclaim_count 递增）；
- 重复投递：同一 CT-004 两条 outbox 记录 → 单任务、双确认（幂等）；
- 并发认领：双槽并行两任务均 scored、scoring_results 无重复（PG 层并发互斥另由全链 E2E + Phase 5 SKIP LOCKED 探针覆盖）；
- 失败重试：首次 MODEL_TIMEOUT → 任务内重试 → scored（attempts=2，retry_record 完整）；
- 租约续期：心跳线程确定性续约 ≥1 次且 lease_expires_at 推进；慢任务（执行>ttl）照常 scored；
- 优雅关闭：request_shutdown 后 run() 正常返回、线程收敛；
- 材料端口：授权读取/同类合并/跨课程/跨提交/未登记/deleted/staged/超限/路径逃逸/部分内容不返回/非 UTF-8 可读性备注/只读无副作用/拒绝日志可观测，共 13 项。

### 3.2 CT-004 → worker → 后续处理/读模型 端到端（scripts/e2e_gap02_fullchain.py，PostgreSQL）

3 份提交连发，**全程无手工 tick**：received →（D-3 钩子 + worker CT-004 确认）→ processing →（worker 常驻循环，并发 3 槽）→ scored →（DU-2 lifespan 调度器 relay）→ CT-007 读模型 original_grade/五维依据/教师建议可读；scoring_results 无重复；worker 优雅关闭。**结果：GAP02_FULLCHAIN_OK（8/8，复跑两轮一致）。**

注：本 E2E 必须在 PG 上运行——系统组件按设计各自管理独立小事务（多连接），SQLite 单写者库锁在嵌套事务流下必然自锁（已在脚本头部注明）。

### 3.3 staging（docker-compose.staging.yml 全容器）

- worker 容器常驻运行：`worker starting` + `worker recovery scan` 日志正常；
- NFR-001 复跑 PASS 后，20/20 提交全部由容器 worker 自动 scored（无需任何手工驱动）；
- NFR-002 复跑（30 并发 × 5 分钟）：**1624/1624 = 100%**（pass_rule ≥95%），p50=2.88s、max=4.07s（≤30s），PASS；压测期间 worker 持续 draining；
- **重启恢复（容器级）**：`restart worker` → recovery scan 如实报告 pending/in_progress/reclaimable，租约重认领后继续推进（scored 由 89 → 1646+ 全量 drained）；
- **优雅关闭（容器级）**：`stop worker`（SIGTERM）→ `shutdown signal received (signal=15)` → `worker stopped, 全部在飞任务已完成`；
- 压测突发暴露 worker 默认连接池（5+10）在热表行锁等待下耗尽（ERROR 可观测、可自愈但吞吐受损）→ build_engine 池调至 10+20（缺陷 #5）。

### 3.4 全量回归与迁移

- server+worker **463 tests 全绿（两轮一致）**；plugin 117 绿（逐文件）；smoke×3、E2E 001/012/016、retention_drill 全过；ruff 全净；
- 迁移：无新迁移（GAP-02 不改表结构）；head 保持 `0016_ccr001_assessment_purge`；
- NFR-002 复跑：1624/1624 = 100%，p50=2.88s、max=4.07s，PASS。

## 4. 过程中发现并修复的缺陷（4 项）

1. **Outbox 跨 DU 认领竞争（真实设计缺陷）**：DU-2 relayer 对未注册契约（CT-004）做指数退避重试，会反复认领并推迟 next_attempt_at，进程外 DU-3 消费方被饿死。修复：`fetch_due(contract_ids=)` 分工过滤——DU-2 只认领已注册契约，DU-3 只认领 CT-004（对齐 KD-002 同组共部署、按 DU 分工的既定形态）。
2. **ICT-003 授权键与现实登记形态不符**：D-P5-01 勘误使 material_files.course_id=`_unassigned`、submission_id=submission_uuid；改以 L02 清单（submission_materials）为授权准绳（更贴近所有权语义）。
3. **alembic env.py `fileConfig` 默认 `disable_existing_loggers=True`**：同进程跑迁移会把业务模块 logger 全部 disabled，静默吞掉日志断言（L12 traceability 测试）。修复：`disable_existing_loggers=False`。
4. **SQLite 单连接伪并发假象**：StaticPool 单连接跨会话回滚/隐式提交会污染多线程断言；测试分层澄清——SQLite 单测只做功能面，并发/隔离正确性全部上 PG 验证（已在测试与脚本注释固化）。
5. **worker 连接池容量**：staging NFR-002 突发下默认池（5+10）在热表行锁等待中耗尽（ERROR 可观测、可自愈但吞吐受损）；build_engine 调至 10+20（仍远小于 PG 余量）。

## 5. 结论：是否仅剩供应商决策与最终发布门禁

**是。** GAP-02 关闭后，tutor-r01 的功能/工程阻塞项全部清零：

| 项 | 状态 |
|---|---|
| TD-01（L07 对话导出） | ✅ 关闭（D-1） |
| CCR-001（评分记录删除，SCENARIO-016/AC-NFR-004-01） | ✅ 关闭（D-2） |
| D-3 received→processing 自动推进 | ✅ 关闭 |
| D-4 staging 压测验收（AC-NFR-001/002） | ✅ PASS |
| D-5 供应商合规调研 | ✅ 完成（决策待用户） |
| GAP-02（DU-3 常驻循环 + ICT-003） | ✅ 本报告关闭 |

**剩余门禁（均需用户决定）**：
1. **供应商决策**：是否/选哪家真实模型供应商接入（D-5 备忘录支持；接入需另批范围：真实 provider、强制超时层、密钥管理、学生授权、最小化复核）；
2. **最终发布门禁**：正式发布仍未批准。

附带说明（非阻塞）：TD-07 worker 多副本部署形态已在 compose 支持（WORKER_ID + SKIP LOCKED 互斥），副本数扩缩属运维决策。
