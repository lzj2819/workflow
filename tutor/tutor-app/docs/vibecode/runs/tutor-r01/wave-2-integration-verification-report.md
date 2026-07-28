# Wave 2 Integration Verification Report — tutor-r01

- 日期：2026-07-20；执行：Integration Owner / Workflow Coordinator
- 范围：integration/wave-2（L08~L13 已审查提交）；集成批准：用户 2026-07-20（仅限 Wave 2 集成）
- 结论：**集成验证全部通过，可合入 main。**

## 1. 集成对象与合并顺序

按序合并（`--no-ff` 保留历史，**零冲突**；每次合并后核对变更路径 ⊆ 对应 allowed-context）：

| # | 叶子 | 叶子提交 | 变更路径核对 |
|---|---|---|---|
| 1 | L08 SI-XFER | `a59c906` | ✅ 7 文件全部允许路径内 |
| 2 | L09 SI-API | `1e715be` | ✅ 9 文件 |
| 3 | L10 UPLOAD-CLIENT | `4ec5ac0` | ✅ 9 文件 |
| 4 | L11 PENDING-QUEUE | `f061ed9` | ✅ 5 文件 |
| 5 | L12 ASSESSMENT-ENGINE | `3e560c0` | ✅ 7 文件 |
| 6 | L13 STATUS-PRESENTER | `848cb86` | ✅ 2 文件 |

无冲突、无解决动作、无叶子提交被改写。

## 2. Alembic merge-head 证据

- 合并前两头：`0005_upload_sessions`、`0006_auth_tokens`（均 down_revision=9c99fa53f9f8）。
- 命令：`python -m alembic merge -m "wave-2 merge heads (L08/L09)" 0005_upload_sessions 0006_auth_tokens` → `b9c6e3d6276a_wave_2_merge_heads_l08_l09.py`。
- 合并后 `python -m alembic heads` → 唯一 `b9c6e3d6276a (head)`。
- 真实 PostgreSQL（docker postgres:16-alpine，健康检查通过）：`upgrade head` → 全部迁移 + mergepoint 应用；`current` → `b9c6e3d6276a (head) (mergepoint)`；**14 表**齐备（W1 8 表 + upload_sessions/upload_chunk_receipts/upload_finalize_attempts（L08）+ auth_token_grants（L09））。

## 3. 六项集成接线事项处置

| # | 事项 | 处置 | 证据 |
|---|---|---|---|
| 1 | L09 ↔ L08 IC-SI-01 真实接线 | **完成**：新增 `server/course_app/submission_intake/wiring.py`（XferTransferAdapter：ingest → create_session/append_chunk（断点跳过已确认分片）/finalize；SIZE_LIMIT_EXCEEDED/TYPE_NOT_ALLOWED 透传，存储暂态失败按可重试失败表达） | smoke_wave2 全链路通过（真实 HTTP + 真实 L08 会话） |
| 2 | L11 / L13 状态枚举映射对齐 | **完成**：L13 状态语义表追加 `created/collecting/completed/failed_retryable/failed_terminal`（追加键、不改既有键语义；failed_* 两态纳入真实原因展示）；同步修正 success 档注释 | plugin/test/integration-smoke-wave2.test.js 4 用例通过；npm 85/85 |
| 3 | L10 checkpoint 持久化注入边界 | **登记**：注入点为 `createMemoryCheckpointStore` 工厂（plugin/src/upload_client/checkpoint-store.js，orchestrator 构造参数）；跨进程文件实现归 B-04（MOD-01 集成，A-007 implementation_detail），本期不落代码 | 报告 §5 遗留 |
| 4 | L12 三桶映射集成口径 | **登记**：现行口径 = 对话→dialogue_summary、代码→code、结果/结果描述→result_description、其余类别（含截图）折叠进 result_description 并带类别标签（L12 engine.py `_CT010_CATEGORY_BUCKETS`）；RUBRIC-PROMPT-COMPOSER 细化（LCD-005）归 B-02 | 报告 §5 遗留 |
| 5 | IC-PQ-004 终态清理协调 | **登记**：归 B-04/Phase 5 决定（L11 完成包已标注不在本叶交付）；本期不实现 | 报告 §5 遗留 |
| 6 | L08 abort 映射区分 | **登记**：约定 `failure_reason` 前缀 `aborted:` = 用户/管理中止；TTL/重试窗口耗尽为不同 reason；区分在展示/映射层消费（UI 与 B-01），不改 L08/L09 代码、无契约变更 | 报告 §5 遗留 |

## 4. 全量验证结果（integration/wave-2）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python -m unittest discover -s server/tests` | **119 tests OK**（76 W1 + L08 25 + L09 18） |
| 2 | `python -m unittest discover -s worker/tests` | **45 tests OK**（32 + L12 13） |
| 3 | `cd plugin && npm test` | **85/85 pass**（43 W1 + L10 12 + L11 10 + L13 16 + 集成冒烟 4） |
| 4 | `python scripts/smoke_wave1.py` | SMOKE_OK（W1 链路无回归） |
| 5 | `python scripts/smoke_wave2.py` | **SMOKE_OK**（L01+L02+L08+L09+L03+L12 全链路 21 断言；真实 TestClient HTTP） |
| 6 | `ruff check server worker shared scripts` | All checks passed（修复 3 处未用导入/变量） |
| 7 | `python -m py_compile`（全部 .py） | OK |
| 8 | `node --check`（全部 plugin .js） | OK |
| 9 | `docker compose -f deploy/docker-compose.yml config --quiet` | OK |
| 10 | alembic upgrade/current/heads（真实 PG） | 见 §2，全部通过 |

环境：Python 3.14.3 · Node v24.14.0 · ruff 0.15.21 · Docker/Compose 29.1.3/v2.40.3。
冒烟修正（非叶子缺陷）：SQLite 内存库跨线程共享（StaticPool，TestClient 独立线程）、ICT-003 material_refs 为对象形状、L12 payload 的 attempt_no 去重、测试替身元数据登记。

## 5. 遗留风险与 Phase 5 事项

- PG 会话绑定 OutboxStore（SI-RELAY/RESULT-PUBLISHER，B-01/B-02）——W1 遗留继续有效。
- SI-STORE 真实实现（加密暂存/配额/目录布局，B-01）——本期冒烟以内存替身验证端口形状。
- L10 checkpoint 文件持久化（B-04，§3.3）；CT-010 三桶映射细化（B-02，§3.4）；IC-PQ-004（B-04，§3.5）；abort 前缀展示映射（B-01/UI，§3.6）。
- CT-001 真实 multipart 二进制接入（契约 content_ref 占位 → 真实分片协议，B-01/L09 后续）。
- L07 保持 blocked（TD-01）；CCR-001 保持 pending（CT-012/CT-014 未动）；tutor 设计包未动；未批准 Wave 3/Phase 5/release。

## 6. Wave 3 前置条件评估

**已满足**：W1+W2 全部集成入 main 且全量绿；W3 叶子（L14~L17）依赖的事件流（CT-004/005/006 真实载荷已由冒烟锁定）与读模型输入就绪；迁移链单头（b9c6e3d6276a）可续。**未放行**——等用户批准。

## 7. 结论

integration/wave-2（HEAD `e47ded5`）满足合入 main 的全部条件。
