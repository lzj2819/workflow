# Wave 1 Integration Verification Report — tutor-r01

- 日期：2026-07-20；执行：Integration Owner / Workflow Coordinator
- 范围：integration/wave-1（L01~L06 已审查提交）；集成批准：用户 2026-07-20（仅限 Wave 1 集成）
- 结论：**集成验证全部通过，可合入 main。**

## 1. 集成对象与合并顺序

按序合并（`--no-ff` 保留历史，**零冲突**；每次合并后核对变更路径 ⊆ 对应 allowed-context）：

| # | 叶子 | 叶子提交 | 合并提交 | 变更路径核对 |
|---|---|---|---|---|
| 1 | L01 course-roster | `972e1f9` | （合并链） | ✅ 9 文件全部允许路径内 |
| 2 | L02 SI-CORE | `2970b01` | （合并链） | ✅ 9 文件 |
| 3 | L03 SCORING-ORCHESTRATOR | `066e516` | （合并链） | ✅ 7 文件 |
| 4 | L04 CONFIG-STORE | `12927a5` | （合并链） | ✅ 3 文件 |
| 5 | L05 INTENT-PARSER | `8610326` | （合并链） | ✅ 6 文件 |
| 6 | L06 MATERIAL-COLLECTOR | `f7f4dc2` | （合并链） | ✅ 2 文件 |

无冲突、无解决动作、无叶子提交被改写（rebase/squash 未使用）。

## 2. Alembic merge-head 证据

- 合并前三头：`0002_course_roster`、`0003_submission_core`、`0004_scoring_tasks`（均 down_revision=0001_baseline）。
- 命令：`python -m alembic merge -m "wave-1 merge heads (L01/L02/L03)" 0002_course_roster 0003_submission_core 0004_scoring_tasks` → 生成 `9c99fa53f9f8_wave_1_merge_heads_l01_l02_l03.py`（不改任何既有迁移语义，仅合并谱系）。
- 合并后：`python -m alembic heads` → 唯一 `9c99fa53f9f8 (head)`。
- 环境注记：系统 PATH 上 Anaconda 的 alembic 与 Python 3.14 不兼容，统一用 `python -m alembic`；`alembic.ini` 注释改 ASCII（alembic 按 locale 读取，中文 Windows 下 GBK 解码失败）。
- 真实 PostgreSQL 验证（docker postgres:16-alpine，容器健康）：
  - `DATABASE_URL=postgresql://tutor:tutor@localhost:5432/tutor python -m alembic upgrade head` → 全部迁移 + mergepoint 应用；
  - `python -m alembic current` → `9c99fa53f9f8 (head) (mergepoint)`；
  - 建表核对：`courses, invite_codes, roster_entries, verification_records`（L01）、`submissions, submission_materials, submission_integrity_reports`（L02）、`scoring_tasks, scoring_results`（L03）+ `alembic_version`；
  - `downgrade base` → 仅剩 alembic_version；再 `upgrade head` → 重放成功。

## 3. 全量验证结果（integration/wave-1）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python -m unittest discover -s server/tests` | **76 tests OK**（36 Phase-1 基线（含契约）+ L01 18 + L02 22） |
| 2 | `python -m unittest discover -s worker/tests` | **32 tests OK**（8 基线 + L03 24） |
| 3 | `cd plugin && npm test` | **43/43 pass**（8 基线 + L04 10 + L05 15 + L06 9 + 集成冒烟 1） |
| 4 | `python scripts/smoke_wave1.py` | **SMOKE_OK**（L01+L02+L03 跨叶子链路 20 项断言全过） |
| 5 | `ruff check server worker shared scripts` | All checks passed |
| 6 | `python -m py_compile`（全部 .py） | OK |
| 7 | `node --check`（全部 plugin .js） | OK |
| 8 | `docker compose -f deploy/docker-compose.yml config --quiet` | OK |
| 9 | alembic upgrade/downgrade/current/heads（真实 PG） | 见 §2，全部通过 |

环境版本：Python 3.14.3 · Node v24.14.0 · ruff 0.15.21 · Docker/Compose 29.1.3/v2.40.3 · fastapi 0.135.3 · SQLAlchemy 2.0.50 · alembic 1.18.4 · pydantic 2.13.4 · psycopg 3.3.4。

## 4. 跨叶子集成冒烟（用户要求的 ≥1 条，实际 2 条）

1. **服务端链路（scripts/smoke_wave1.py，SQLite 单库）**：L01 预置课程/导入名单/归属校验 → L02 幂等创建（received + 同事务 CT-004/CT-006 入队）→ received→processing（task_persisted）→ L03 消费 CT-004（跨叶子 payload 保真、重复事件幂等）→ 认领（SqlaTaskLeaseStore）→ 完成（CT-005 scored 四件套入队）→ L02 应用终态（scored，重复应用幂等）。20 项断言全过。
2. **插件链路（plugin/test/integration-smoke-wave1.test.js）**：L04 保存/重读配置 → L05 标签式指令解析（完整 + 缺项 fail-closed）→ L04 配置 × L05 意图组装采集输入（该组装正式归 L11）→ L06 收集（代码/结果入库、screenshot 缺失显式、白名单外跳过）。

冒烟过程暴露并修正 3 处冒烟脚本自身接线错误（非叶子缺陷）：consumer_ack 字面量、L03 应使用其 SqlaTaskLeaseStore（行级租约）而非内存租约、L06 采集输入为任务快照形状。叶子实现均未改动。

## 5. 边界确认

- L07 保持 blocked（TD-01）；CCR-001 保持 pending（CT-012/CT-014 未动）；tutor 设计包未动；未启动任何 Wave 2 任务；未批准任何后续 gate。
- 契约影响：无（六个叶子）+ 协调者既有落地修正（ct-003 条件化，`80ace9f`，已在 wave-1-readiness-review 登记）。

## 6. Phase 5 遗留项（登记，不属本次集成范围）

- SI-RELAY / RESULT-PUBLISHER：真实 PG 会话绑定的 OutboxStore 实现（L02/L03 完成包登记）。
- SI-STORE / SI-VERIFY / SI-PURGE；CT-013 教师会话鉴权注入；MOD-05 全部 backfill 组件。
- L06 类别映射（内部 id → CT-001 中文类别）在 L10 集成时确认。
- 迁移合并纪律：后续叶子迁移继续以单头（当前 9c99fa53f9f8）为 down_revision。

## 7. 结论

integration/wave-1（HEAD `cbef93a`）满足合入 main 的全部条件。
