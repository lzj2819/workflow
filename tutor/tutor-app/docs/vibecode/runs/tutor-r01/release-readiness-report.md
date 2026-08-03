# Release Readiness Report — tutor-r01 / Phase 6

- 日期：2026-07-22；基线：main `3e73290`（+ 本阶段硬化修复，见 §5）
- 执行：Integration Owner / Workflow Coordinator
- 结论：**就当前批准范围，系统具备发布候选条件；TD-01 与 CCR-001 两项既有阻塞解除前，REQ-003 与 SCENARIO-016/AC-NFR-004-01 不可宣称完成，不发布。**

## 1. 可发布能力（已验证）

| 能力 | 证据 |
|---|---|
| 学生令牌认证 + 提交接收（CT-001/CT-002/auth-token；JSON 与 multipart 双通道） | E2E SCENARIO-001（18 断言）；T-B01d 13 测试 |
| 归属校验（CT-003，每次实时、无缓存、逐条记录） | L01 18 测试 + E2E |
| 异步评分链路（CT-004→L03→L12(fake+真实 rubric/ACL)→CT-005→L02+projector） | E2E 双场景（真实组合根+relay） |
| 评分失败重试一次与 scoring_failed 可见性（不伪造等级） | E2E SCENARIO-012（9 断言） |
| 教师端（CT-007/008/009/011 + SSR；授权 403 + 审计） | E2E 教师链路 + smoke_wave3 + hardening |
| 事件可靠性（数据库 Outbox + 投递 + 入站去重 + PG SKIP LOCKED） | T-B01b 15 测试 + PG 并发认领 0 重叠 |
| 材料存储（原子写入、500MB/200GB 配额、删除幂等） | T-B01a 19 测试（含相对路径回归） |
| 保留删除链路（提交侧：到期标记→CT-011→CT-012→清除→CT-014；审计先行且留存） | retention_drill（含「AssessmentResult 未删」的 CCR-001 缺口显式断言） |
| 30 并发提交与 30 秒接收确认（探针口径） | concurrency_probe：30/30 成功，p50=1.42s / max=1.55s（真实 PG） |
| 健康/日志/metrics/错误响应/安全边界 | hardening_check（15 断言全过；401/403/审计/令牌哈希/无堆栈泄露） |
| 数据库迁移（升级/回滚/备份/恢复/幂等） | PG 演练全周期（38 表、单头 `27867c368f7e`） |
| 发布构建（Docker 镜像 ×2 可运行） | tutor-server/tutor-worker 构建 + worker 入口冒烟 + server 工厂创建 app 验证 |

## 2. 不可发布 / 不可宣称完成项

| 项 | 状态 | 说明 |
|---|---|---|
| REQ-003 完整 Codex 对话采集（L07） | **blocked（TD-01）** | 宿主导出机制未确认；插件对 unsupported 如实呈现；不虚构 |
| SCENARIO-016 / AC-NFR-004-01（AssessmentResult 到期删除） | **blocked（CCR-001 pending）** | 提交侧删除链路已验证可用，但 CT-012 消费者仍冻结为 [MOD-02, MOD-05]；评分记录未纳入删除，完整性不可宣称 |
| 真实模型供应商评估 | **未接入（需用户合规批准）** | 仅 FakeModelProvider/FakeVendorAdapter；DD-009 要求接入前合规确认 |
| NFR-001/002/003 正式压力验收（100 学生/20–50 组、5 分钟窗口 ≥95%、30s/10min 目标率） | **未执行正式压测** | 仅有 30 并发探针证据（单进程 TestClient 口径）；正式压测需部署环境执行 |
| SM-001/002/003 达标率统计报表 | **组件就绪、未做课程期统计** | ScoringMetrics 单测通过；真实统计需课程期数据 |
| 学生侧真实宿主分发（Codex 插件安装形态） | **未验证** | 依赖 TD-01；插件仅经组装测试与 stub transport 验证 |

## 3. 已知风险

- received→processing 的生产接线点（CT-004 confirmed 后置钩子）未落地——当前由组合根/运维手工驱动（e2e-report §接线注记）；上线前必须接线，否则提交停在 received。
- ACL 预算守卫为事后判定；真实供应商接入需强制超时层。
- ScoringMetrics 为进程内统计（重启清零）；SM 报表需持久化或外部聚合（后续）。
- SI-STORE `_unassigned` 路径的课程键重组织（D-P5-01 登记的后续细化）。
- IC-PQ-004 清理需冷态执行（L11 envelope 单写约束，已明示）。
- 读模型 material_refs 空投影（CT-006 载荷事实；教师材料明细浏览需未来契约扩展）。
- L14 授权适配对不存在 submission 仅认证即放行（v1 单教师可接受，T-B03a 登记）。

## 4. 环境与依赖

- Python 3.14.3 · Node v24.14.0 · ruff 0.15.21 · Docker/Compose 29.1.3/v2.40.3 · PostgreSQL 16（docker postgres:16-alpine）。
- server/requirements.txt：fastapi 0.135.3 · uvicorn · SQLAlchemy 2.0.50 · alembic 1.18.4 · psycopg 3.3.4 · pydantic 2.13.4 · jinja2（本阶段补充）。
- worker/requirements.txt：SQLAlchemy · psycopg · httpx（未使用，留待真实供应商适配）。
- plugin：零依赖（Node ≥20）。
- pip check：仅环境级无关冲突（langchain-openai vs openai，非本项目依赖）。

## 5. Phase 6 硬化修复（本阶段发现并修复）

1. SI-STORE 相对 data_dir 前缀校验缺陷（并发探针发现）→ 根目录 resolve 归一 + 回归测试。
2. db.engine 连接池过小（30 并发 QueuePool 耗尽）→ pool_size=20/max_overflow=30（仅 PG；SQLite 不传参）。
3. server/requirements.txt 缺 jinja2（镜像构建发现）→ 已补声明。
4. Dockerfile.server CMD 为 Phase 1 占位 → 切换为 `uvicorn course_app.main:create_app --factory`。
5. 四个脚本误用 `file:NAME` URI（实为磁盘文件，跨运行累积）→ 改 `mode=memory` 真内存库 + 锚定连接保活；删除散落文件。
6. hardening 脚本学生令牌明文检查悬空引用（F821）→ 修正为真实换领后断言。
7. docker 基础镜像拉取遇镜像站 403 → 直接 pull 后构建通过（环境插曲，非代码问题）。

## 6. 验证命令汇总（可复跑）

```bash
python -m unittest discover -s server/tests        # 327 OK
python -m unittest discover -s worker/tests        # 104 OK
cd plugin && npm test                              # 102 pass
python scripts/smoke_wave1.py / smoke_wave2.py / smoke_wave3.py
python scripts/e2e_scenario_001.py / e2e_scenario_012.py
python scripts/hardening_check.py
python scripts/retention_drill.py
DATABASE_URL=postgresql://tutor:tutor@localhost:5432/tutor python scripts/concurrency_probe.py
cd server && python -m alembic upgrade head / downgrade base / current
docker compose -f deploy/docker-compose.yml build / config --quiet
ruff check server worker shared scripts
```

## 7. Runbook

- `docs/runbook/deploy-runbook.md`（部署/升级/配置复核清单）
- `docs/runbook/disaster-recovery-runbook.md`（备份/恢复/故障处置/审计保全）
- `docs/runbook/rollback-runbook.md`（回退流程与验证清单）
- `docs/operations.md`（日常运维基线，T-B03d 已更新组合根启动说明）

## 8. 最终门禁建议

- 可进入发布候选评审：**是**（批准范围内）。
- 发布前必须人工确认：① TD-01 处置（REQ-003 是否接受首版无对话采集或解除阻塞）；② CCR-001 裁决（SCENARIO-016 完整性）；③ received→processing 生产接线点落地；④ 正式压测与部署环境验收计划；⑤ 真实供应商合规批准（如需真实评估）。
- 最终决定（human gate: final）由用户作出。
