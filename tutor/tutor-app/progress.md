# tutor-app Progress

## 2026-07-25 — deepseek 供应商受限接入（已完成；等待最终发布批准）

用户批准真实供应商接入（仅 deepseek；外发限最小化材料文本；密钥 .env；内部试用/灰度；不可用 → 无自动评分/稍后重试）：

- **DeepSeekProvider**（`model_provider_deepseek.py`）：OpenAI 兼容 Chat Completions + JSON 模式；最小化闸（业务标识零外发）；强制超时 ≤180s；密钥仅 .env/环境、零日志；`MODEL_PROVIDER=fake|deepseek`，其他值启动即拒。
- **降级**：`VENDOR_ENABLED=0` kill switch（停认领不终态化）+ 连续失败熔断（阈值/冷却可配，半开自动恢复）；`vendor_calls/failures/timeouts/circuit_opens/kill_switch` metrics 告警面。
- **验证**：provider 单测 10/10（含密钥/内容零日志、零外发断言）；kill switch/熔断 2/2；staging 端到端（stub 供应商，**未接触真实供应商/真实密钥**）8/8——假数据自动 scored、外发无业务标识、CT-007 投影正确；全量回归 473 绿 + ruff 净 + E2E 001/016 复跑。
- **文档**：vendor-compliance-memo 追加决策节（境内端点、.env 密钥、灰度、降级）；.env.example、deploy-runbook（发布检查表含**真实密钥首轮人工验证**前置项）、operations 告警面更新。
- 报告：`vendor-integration-report.md`（已知边界：真实 key 首轮调用为发布前人工步骤）。
- **停止点：等待用户最终发布批准。**

## 2026-07-25 — GAP-02 实施（已完成；仅剩供应商决策与最终发布门禁）

用户批准 GAP-02（基线 `dbe2b66`）：DU-3 常驻认领循环 + ICT-003 材料读端口生产实现 + 配置/监控/测试/Runbook。

- **DU-3 worker 常驻循环**（`worker/assessment_worker/runner.py`）：CT-004 入站（contract_ids 过滤，不触碰 DU-2 契约）、N 槽并发认领、租约心跳续期（ttl/3）、REQ-012 任务内重试（同租约 attempt 2）、未分类异常释放租约、SIGTERM/SIGINT 优雅关闭、崩溃重认领恢复、12 项 metrics 告警面。
- **ICT-003 生产实现**（`submission_intake/store/reader.py`）：L02 清单授权（跨提交/跨课程整体拒绝、不返回部分内容）、final 限定、DATA_DIR 限界、500MB 派生上限、只读无副作用、成功/拒绝均可观测。
- **关键缺陷修复（5 项）**：Outbox 跨 DU 认领竞争（DU-2 退避循环饿死 DU-3 → fetch_due contract 过滤）；授权键对齐 D-P5-01 勘误（清单为准）；alembic fileConfig 禁用既有 logger（静默吞日志断言）；SQLite 伪并发假象（测试分层：功能面 SQLite、并发正确性 PG）；worker 连接池 5+10 → 10+20。
- **验证**：runner 10 测 + reader 13 测；PG 全链 E2E（`e2e_gap02_fullchain.py`，3 提交全程无手工 tick 自动 scored + 读模型投影，8/8）；staging 容器级：NFR-001 复跑 PASS（20/20 自动 scored）、**NFR-002 复跑 1624/1624=100%（p50=2.88s）PASS**、restart 恢复与 SIGTERM 优雅关闭实证；全量回归 463 绿（两轮一致）+ plugin 117 绿 + smoke×3 + E2E×3 + drill + ruff 净。
- 报告：`docs/vibecode/runs/tutor-r01/gap-02-verification-report.md`。
- **结论：功能/工程阻塞项全部清零；仅剩 ① 供应商决策（D-5 后续）② 最终发布门禁，均待用户决定。**

## 2026-07-23 — 最终门禁决策 D-1~D-5 实施（已完成；发布门禁仍待用户）

用户 2026-07-22 逐项批准：D-1 选 A、D-2 批准 CCR-001 方案 A、D-3 批准推荐方案、D-4 建立 staging、D-5 先只读合规调研。实施结果：

- **D-1（TD-01 关闭）**：L07 CMP-DIALOGUE-COLLECTOR 宿主导出适配合入 main（merge `5420657`）；codex rollout jsonl 只读导出 + HostUnsupportedError 可观测；plugin 15/15 绿；task-registry T-07 → done。
- **D-2（CCR-001 方案 A 落地）**：
  - 契约：CT-012 消费者扩展 `[MOD-02, MOD-04, MOD-05]`；新增 CT-015 AssessmentPurgeCompleted（镜像 CT-014）；内部索引 +ICT-009/M05-IC-07；契约测试 16/16；contract-freeze GAP-01 关闭。
  - MOD-04：`scoring_orchestrator/purge.py`（ICT-009）清除评分结果+任务、写最小墓碑、回传 CT-015；CT-004 重放守卫（tombstoned 拒绝重建任务）；迁移 `0016_ccr001_assessment_purge`（墓碑表 + 批次双回流列）；5/5 单测。
  - MOD-05：批次状态改双回流聚合（CT-014 单路到达保持 executing；双到达且无失败 → completed + RecordsDeleted 审计闭合；失败项标注 flow 供重跑；已完成批次重跑不重复审计）；retention 测试更新 82/82。
  - 组合根：CT-012 注册第三消费方（MOD-04 评分清除，同库共部署经 DU-2 relay；DU-3 常驻循环落地后迁回，见 GAP-02）+ CT-015 路由；Dockerfile.server 纳入 worker 包。
  - **SCENARIO-016 验收 E2E 17/17 通过**（六项条件：审计先行/双回流/评分记录清除/教师端不可读/幂等重跑+重放守卫/审计留存）；retention_drill 同步更新为闭环断言。
- **D-3**：relayer CT-004 confirmed 扫描钩子（`_advance_confirmed_submissions`）+ 2/2 验收测试（此前已完成，本轮随全量验证回归）。
- **D-4**：staging 压测验收——AC-NFR-001（100 学生/25 组创建/查询/展示）PASS；AC-NFR-002（30 并发 × 5 分钟）**1522/1522 = 100%**（≥95%），p50=3.10s、max=4.16s（≤30s）。修复 4 项 staging 缺口（Windows 代理 502 根因、db 端口、名单分组口径、**DU-2 relay 调度器真实接线缺口**——lifespan 进程内调度器）。报告 `d4-staging-acceptance-report.md`。
- **D-5**：`vendor-compliance-memo.md`（只读调研，此前完成）。
- **新登记 GAP-02**：DU-3 worker 入口仍为 Phase 1 桩（无常驻认领循环）+ ICT-003 材料读端口无生产实现；staging 中 CT-004 滞留可观测；需用户批准范围后实施。
- 全量回归：server+worker 440 绿、plugin 117 绿、smoke×3、E2E 001/012/016、retention_drill、ruff 全净。
- **停止点：最终发布仍未批准，等待用户发布门禁决定。**


## 2026-07-22 — 最终门禁决策准备（已完成编制；等待逐项决策）

- 输出 `docs/vibecode/runs/tutor-r01/final-gate-decision-pack.md`，五项决策包：
  D-1 TD-01 对话采集（A 宿主导出适配 / B 范围移除或降级 / C 暂不发布）；
  D-2 CCR-001 正式契约变更方案（CT-012 扩消费者 + 新增 CT-015 回流 + 墓碑重放守卫 + 双回流批次聚合 + 审计只增 + 失败重跑 + 迁移与 SCENARIO-016 六条验收条件）；
  D-3 received→processing 生产接线点（推荐 DU-2 relayer 的 CT-004 confirmed 扫描钩子 + 失败告警 + 监控指标 + 4 条验收测试）；
  D-4 正式压测与部署验收（AC-NFR-001/002/003 场景、规模、阈值、前置、通过标准）；
  D-5 供应商合规清单（选择/DPA、最小化、授权、密钥、保留、审计、回退、强制超时层；不接入不发送真实数据）。
- **最终发布仍被 D-1~D-5 阻塞；未修改业务代码、未部署、未接入供应商。**


## 2026-07-22 — Phase 6 发布准备与硬化验证（已完成；正式发布未批准）

- 配置/密钥复核：无硬编码 secret、无日志泄露、.env.example 仅占位、CLI 与 create_app 工厂可用。
- PG 演练：升级→种子→pg_dump 备份→downgrade base→恢复→38 表与迁移位点一致→幂等复跑，全过。
- hardening_check：15 断言（health/日志/401/403/AccessDeniedLogged/令牌哈希/metrics/无堆栈泄露）。
- retention_drill：到期标记→CT-011→CT-012→purge→CT-014 批次完成；审计先行留存；**显式断言 AssessmentResult 未删（CCR-001 缺口证据，未声称 SCENARIO-016/NFR-004）**。
- 并发探针（真实 PG）：30/30 提交成功，p50=1.42s / max=1.55s（30s 目标达成，探针口径）。
- 构建：tutor-server/tutor-worker 镜像构建成功并可运行（worker 入口 + server 工厂验证）；pip check 仅环境级无关冲突。
- 硬化修复 7 项：store 根路径 resolve 归一、连接池 20+30、补 jinja2 声明、Dockerfile CMD 切 uvicorn、内存库 URI（file:→mode=memory+锚定保活）、hardening 悬空检查修正、镜像站 403 插曲。
- Runbook ×4：deploy / disaster-recovery / rollback / operations（已更新）。
- 报告：`docs/vibecode/runs/tutor-r01/release-readiness-report.md`。
- **停止点：等待用户最终产品范围与发布门禁决定。**


## 2026-07-21 — Phase 5 受限回填（已完成）

- B-01~B-04 全部合入 main：SI-STORE `47c3b67`、SI-RELAY `4ea8b68`、SI-PURGE `fd44fd6`(+0015 补迁移)、multipart `93d5a78`、model-acl `3dbf9fa`、rubric/metrics `458121c`、access-gate `e013713`、projector `d392956`、retention `3373e48`、组合根 `c694746`、插件组装 `3bdf36d`；跨组件缺陷修复（projector 去重键）`1ab6da9`。
- B-05：`scripts/e2e_scenario_001.py` 与 `e2e_scenario_012.py` 均 **E2E_OK**；SCENARIO-016 保持 blocked 并留证（`docs/vibecode/runs/tutor-r01/e2e-report.md`）。
- 迁移：7 头合并为 `27867c368f7e`（单一 head）；真实 PG upgrade 复跑干净、**38 表**齐备；PG SKIP LOCKED 并发认领 0 重叠。
- 全量：server 326 OK · worker 104 OK · plugin 102/102 · 三冒烟无回归 · ruff · py_compile · node --check · compose config。
- 报告：`docs/vibecode/runs/tutor-r01/phase-5-verification-report.md`（含 TD-01/CCR-001 阻塞清单与发布准备条件评估）。
- **停止点：等待用户最终门禁决定。**


## 2026-07-20 — Wave 3 集成（已完成）

- 集成批准（用户）：integration/wave-3 按 L14→L17 顺序 `--no-ff` 合并，零冲突，路径核验合规。
- Alembic：merge-head `11a22f91f4b3`（单一 head）；PG upgrade 验证 **19 表**齐备。
- 指定核验：① M05-IC-02 双侧面兼容（单一 StubReadModel 同数据集驱动 L15/L16）；② L14→L15/L16→L17 真实链路（scored+调整、scoring_failed 显式缺失无等级值、空小组 NO_AVAILABLE）；③ 409 映射统一（真实 HTTP，契约语义未改）。
- 全量验证：server 183 OK · worker 45 OK · plugin 85/85 · smoke_wave1/2/3 · ruff · py_compile · node --check · compose config · PG 迁移。
- 报告：`docs/vibecode/runs/tutor-r01/wave-3-integration-verification-report.md`；Phase 5 前置条件已满足（等放行）。


## 2026-07-20 — Wave 3 叶子实现（完成，待集成批准）

- 四个叶子全部返回 done 并通过协调者核验：L14 `58b6ee9`（17）· L15 `c846a36`（15）· L16 `34bb13b`（13）· L17 `70119ae`（19）；串行派发一次通过；契约影响=无。
- 关键边界遵守：L14 理由保持可选；L15 未建读模型表；L16 快照/幂等/缺失标记；L17 仅消费已定义 API（CT-011 spy 断言）。
- **Wave 3 readiness review 已输出**：4/4 可合并，6 项非阻塞注记（迁移合并、M05-IC-02 对齐、409 映射、时间窗粒度、SSR 挂载、MOD-05 backfill）。
- **17 叶子进度：16/17 完成；L07 blocked（TD-01）。**
- **停止点：等待用户集成批准**；Phase 5 未放行。


## 2026-07-20 — Wave 2 集成（已完成）

- 集成批准（用户）：integration/wave-2 按 L08→L13 顺序 `--no-ff` 合并，零冲突，路径核验合规。
- Alembic：merge-head `b9c6e3d6276a`（单一 head）；PG upgrade 验证 14 表齐备。
- 六项接线：① IC-SI-01 真实接线完成（`server/course_app/submission_intake/wiring.py`）；② L11/L13 状态枚举对齐完成（L13 追加 5 键 + 失败原因展示）；③~⑥ checkpoint 持久化注入点、三桶映射口径、IC-PQ-004、abort 前缀区分均已登记（归 B-01/B-02/B-04/Phase 5）。
- 全量验证：server 119 OK · worker 45 OK · plugin 85/85 · smoke_wave1 + smoke_wave2（服务端全链路经 TestClient）· ruff · py_compile · node --check · compose config · PG 迁移。
- 报告：`docs/vibecode/runs/tutor-r01/wave-2-integration-verification-report.md`。


## 2026-07-20 — Wave 2 叶子实现（完成，待集成批准）

- 六个叶子全部返回 done 并通过协调者核验（范围 ⊆ allowed-context、新增测试全绿、全量无回归、契约影响=无）：
  L08 `a59c906`（25）· L09 `1e715be`（18）· L10 `4ec5ac0`（12）· L11 `f061ed9`（10）· L12 `3e560c0`（13）· L13 `848cb86`（16）。
- 串行派发（API 配额约束；L08 首次 403 一次，恢复后完成）。
- 关键边界遵守：L10 类别映射=叶子内常量表（未触发 CCR）；L11 对 TD-01 unsupported 显式失败不伪造；L12 仅 fake provider 且 CT-010 请求无业务标识；L13 不伪造结论。
- **Wave 2 readiness review 已输出**：6/6 可合并，7 项非阻塞注记（迁移合并、IC-SI-01 接线、状态枚举对齐、checkpoint 持久化注入、CT-010 三桶映射细化、IC-PQ-004、abort 区分）。
- **停止点：等待用户集成批准**；Wave 3 未放行。

## 2026-07-20 — Wave 1 集成（已完成）

- 集成批准（用户，仅 L01~L06）：`integration/wave-1` 从 main 切出，按 L01→L06 顺序 `--no-ff` 合并，**零冲突**，每次合并核对变更路径 ⊆ allowed-context。
- Alembic：三头 → `alembic merge` 生成 merge-head `9c99fa53f9f8`（单一 head）；真实 PostgreSQL 上 upgrade/downgrade base/重 upgrade 全过，8 表齐备。
- 全量验证（集成分支）：server 76 OK · worker 32 OK · plugin 43/43 · `scripts/smoke_wave1.py` SMOKE_OK（L01+L02+L03 链路 20 断言）· 插件链路冒烟（L04+L05+L06）· ruff · py_compile · node --check · compose config。
- 报告：`docs/vibecode/runs/tutor-r01/wave-1-integration-verification-report.md`。
- 控制面：task-registry/log/plan/findings 已更新；L07 blocked、CCR-001 pending、Phase 5 遗留项（PG Outbox 绑定、SI-STORE/VERIFY/PURGE、鉴权注入、类别映射）已登记。

## 2026-07-20 — Phase 2 / Wave 1（叶子实现完成，待集成批准）

- 六个叶子全部返回 done 并通过协调者核验（范围 ⊆ allowed-context、新增测试全绿、全量无回归、契约影响=无）：
  L01 `972e1f9`（18）· L02 `2970b01`（22）· L03 `066e516`（24）· L04 `12927a5`（10）· L05 `8610326`（15）· L06 `f7f4dc2`（9）。
- **Wave 1 readiness review 已输出**：`docs/vibecode/runs/tutor-r01/wave-1-readiness-review.md`——6/6 可合并，0 返工，0 阻塞；7 项非阻塞注记（迁移合并、Outbox PG 绑定、类别映射、鉴权注入等）。
- 过程记录：API 配额中断 → 串行恢复完成；协调者修复路径勘误（`52072eb`）、基线测试（`2ad9dc6`）、ct-003 落地（`80ace9f`）。
- **停止点：等待用户集成批准**（合并六分支 + alembic merge heads + 全量回归）；Wave 2 未放行。

## 2026-07-20 — Phase 2 / Wave 1（进行中，仅 L01~L06）

- **Wave 1 开工批准：approved（2026-07-20，用户）**，仅 L01~L06；L07 blocked（TD-01）；CCR-001 pending；Wave 2/3、Phase 5、最终发布未批准。
- 执行环境更正（用户）：协调者与全部 Leaf Owner 均为 Claude Code，不使用 Codex 对话。
- server 依赖已安装：fastapi 0.135.3 / SQLAlchemy 2.0.50 / alembic 1.18.4 / pydantic 2.13.4 / psycopg 3.3.4（叶子单测用 SQLite）。
- 已创建 6 个隔离 worktree/分支（`.worktrees/<leaf>`，`tutor-r01/<leaf>`）与 6 套任务包（`docs/vibecode/runs/tutor-r01/leaves/<leaf>/` 四件套）。
- 六个 Leaf Owner 已并行派发；协调者仅登记、范围审查、收集完成包；不提前合并、不做跨叶子接线。

## 2026-07-20 — Phase 1（已完成）

**matrix human gate：approved（2026-07-19）**，已写入全部控制文件。Phase 1 生产基线完成：

- contracts/：16 个机器可读契约 schema + 内部契约索引；契约正式冻结（例外：CCR-001 pending，CT-012/014 冻结不改）。
- monorepo 骨架：`plugin/`（Node 零依赖：host 端口/fixture/配置校验/核心端口）、`server/`（MOD-02/03/05 边界 + settings + contracts_registry + health + db 事务边界 + alembic baseline）、`worker/`（ModelProvider 协议 + FakeModelProvider + 数据最小化校验 + 任务入口）、`shared/`（config/logging/metrics/health/outbox/lease）。
- 工程基线：PostgreSQL 16 运行时（DD-002）+ alembic 迁移入口 + docker-compose + .env.example（secret 不入库）+ 结构化日志 + metrics + readiness/liveness + ruff。
- TD-01 边界落实：L07 仅端口 + fixture + 显式 HostUnsupportedError，未虚构宿主 API。
- MOD-02 三项「待复验」复核：全部通过（详见验证报告 §5）。
- 验证报告：`docs/vibecode/runs/tutor-r01/phase-1-verification-report.md`。

**验证结果（全绿）**：

| 命令 | 结果 |
|---|---|
| py_compile 全部 .py | OK |
| node --check 全部 .js | OK |
| `python -m unittest discover -s server/tests` | 35 tests OK |
| `python -m unittest discover -s worker/tests` | 8 tests OK |
| `cd plugin && npm test` | 8 pass / 0 fail |
| `ruff check server worker shared` | OK |
| `docker compose -f deploy/docker-compose.yml config --quiet` | OK |

## 2026-07-19 — Phase 0（已完成）

- 通读 tutor 设计包；确认 17 叶子范围；`git init`；创建控制文件与 tutor-r01 run 文档。

## 阻塞

- **等待用户放行 Phase 2 / Wave 1**（L01~L06 已具备条件）。
- CCR-001（TD-08）：待用户 contract-change 批准；批准前 CT-012/CT-014 冻结不改、不实施。
- TD-01：L07 真实宿主适配 blocked，待确认 Codex 对话导出机制。
