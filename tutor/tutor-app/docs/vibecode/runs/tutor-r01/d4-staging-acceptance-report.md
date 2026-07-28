# D-4 staging 压测验收报告（tutor-r01）

- 日期：2026-07-23；执行：Integration Owner；环境：`deploy/docker-compose.staging.yml`（server:18000 + PostgreSQL 16:18001 + worker）
- 依据：final-gate-decision-pack D-4（用户批准建立 staging 压测环境）；MODEL_PROVIDER=fake；无真实材料/密钥/供应商。

## 验收结果

| 验收项 | pass_rule | 实测 | 结论 |
|---|---|---|---|
| AC-NFR-001 规模（100 学生/25 组创建、查询、展示） | 全通过 | 提交 20/20 received；CT-007 courses/groups 200；CT-009 presentation 200 | **PASS** |
| AC-NFR-002 30 并发 × 5 分钟接收率 | ≥95% 且接收 ≤30s | 1522 请求，成功 1522（**100.00%**）；p50=3.10s，max=4.16s | **PASS** |

- 名单预置：`scripts/staging_provision.py`（100 学生轮转分 25 组，imported=100，教师账号经 access_gate provision）。
- 复现：`NO_PROXY='*' python -m scripts.loadtest_nfr --scenario all`（见下方「环境注意事项」）。

## 本轮 staging 暴露并修复的缺口（4 项）

1. **httpx 502 空响应**：根因为 Windows 系统代理拦截 localhost（httpx `trust_env` 读取系统代理），与服务器无关（curl 直连 303 正常）。处置：压测/运维命令以 `NO_PROXY='*'` 运行；非产品缺陷。
2. **db 端口未发布**：staging compose 的 db 未映射主机端口，宿主机迁移/预置脚本无法直连。已补 `18001:5432`（compose 注释标明用途）。
3. **名单分组口径不一致**：staging_provision 顺序分组 vs loadtest 轮转分组 → token 401。已统一为轮转分组（`学生 i ∈ 第((i-1)%25)+1 组`）。
4. **DU-2 缺 relay 调度器（真实接线缺口）**：`main.py` 只挂载 router，组合根 `relayer_tick()` 无人驱动——Outbox 事件不投递、读模型不投影、CT-007/009 查不到数据（首轮 NFR-001 教师端 404 即此因）。已在 `create_app` lifespan 增加进程内调度器（默认 1s/轮，`RELAY_TICK_INTERVAL_SECONDS=0` 可关；tick 异常如实记录不中断）。修复后读模型正常投影，NFR-001 通过。

## 已知限制（如实登记，不阻塞本次验收）

- **DU-3 worker 入口仍是 Phase 1 桩**：`python -m assessment_worker` 打印配置摘要即退出（容器 Exited 0）。staging 中评分链路（CT-004 消费→认领→L12→CT-005/006）不落库运行；1522 条 CT-004 记录滞留 outbox pending 可观测。NFR pass_rule 均针对接收侧，不影响本次结论；**DU-3 常驻认领循环 + ICT-003 真实材料读端口**为后续工作（需用户批准范围，见 findings.md GAP-02）。
- staging 数据为合成数据；无真实学生材料；fake provider 不发起外部调用。

## 与 Phase 6 本地探针的关系

Phase 6 concurrency_probe（进程内 30 并发）p50=1.42s；本次经 Docker 网络 + PG 的真实服务 p50=3.10s，均远优于 30s 接收目标。
