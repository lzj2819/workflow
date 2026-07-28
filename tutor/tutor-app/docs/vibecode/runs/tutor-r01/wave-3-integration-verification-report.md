# Wave 3 Integration Verification Report — tutor-r01

- 日期：2026-07-20；执行：Integration Owner / Workflow Coordinator
- 范围：integration/wave-3（L14~L17 已审查提交）；集成批准：用户 2026-07-20（仅限 Wave 3 集成）
- 结论：**集成验证全部通过，可合入 main。**

## 1. 集成对象与合并顺序

按序合并（`--no-ff` 保留历史，**零冲突**；每次合并后核对变更路径 ⊆ 对应 allowed-context）：

| # | 叶子 | 叶子提交 | 变更路径核对 |
|---|---|---|---|
| 1 | L14 REVIEW-COMMAND | `58b6ee9` | ✅ 8 文件全部允许路径内 |
| 2 | L15 REVIEW-QUERY | `c846a36` | ✅ 7 文件 |
| 3 | L16 PRESENTATION | `34bb13b` | ✅ 12 文件 |
| 4 | L17 TEACHER-UI | `70119ae` | ✅ 16 文件 |

无冲突、无解决动作、无叶子提交被改写。

## 2. Alembic merge-head 证据

- 合并前两头：`0007_review_records`、`0008_presentation_views`（均 down_revision=b9c6e3d6276a）。
- 命令：`python -m alembic merge -m "wave-3 merge heads (L14/L16)" 0007_review_records 0008_presentation_views` → `11a22f91f4b3_wave_3_merge_heads_l14_l16.py`。
- 合并后 `python -m alembic heads` → 唯一 `11a22f91f4b3 (head)`。
- 真实 PostgreSQL（docker，健康）：`upgrade head` 通过；`current` → `11a22f91f4b3 (head) (mergepoint)`；**19 表**齐备（W2 14 表 + review_records/review_grade_adjustments/review_idempotency_keys（L14）+ presentation_views/presentation_idempotency（L16））。

## 3. 指定集成核验事项

| # | 事项 | 处置 | 证据 |
|---|---|---|---|
| 1 | L15/L16 与 M05-IC-02 注入端口兼容性 | **核验通过**：两叶子消费同一端口的两个侧面（L15 `query()` 扁平视图族 / L16 `group_view()` 小组视图）。冒烟以单一 StubReadModel 在同一数据集上同时实现两侧面，分别驱动 L15 facade 与 L16 coordinator 成功取数且数据一致（同一提交的 final_grade 两侧一致）。结论：PROJECTOR（B-03）单实现可服务两消费方，端口无冲突 | scripts/smoke_wave3.py（M05-IC-02 兼容段） |
| 2 | L14→L15/L16→L17 真实状态/错误/空结果展示 | **核验通过**：真实链路（L01 课程 → L02 两提交 → L03 scored(B)/scoring_failed(重试一次后失败) → L14 M05-IC-01 建复核记录 + CT-008 调整 final=B→A → L15 详情含 original/final/annotation、scoring_failed 含原因+重试记录无等级 → L16 快照+幂等命中+无提交小组 NO_AVAILABLE_SUBMISSION → L17 页面真实渲染：final=A+批注可见、scoring_failed 页展示 MODEL_TIMEOUT 且显式缺失标记（missing-value）、无 grade-value 等级值） | scripts/smoke_wave3.py 全链路段（21 断言） |
| 3 | 409 映射统一验证 | **核验通过**：L14 router 真实 HTTP——无原始等级设 final_grade → 409 + NO_ORIGINAL_GRADE；仅批注 → 200。契约错误码语义未改（行为核验，非契约变更） | scripts/smoke_wave3.py 409 段 |

冒烟断言修正记录（均非叶子缺陷）：L15 ReadModelView 顶层字段口径（装配器读取形状）、L03 任务内重试回调方式（同租约 attempt_no=2，无需重新认领）、RetentionStub 参数签名、L14 AccessGrant 字段、L17 会话 cookie 名（teacher_session）、断言口径对齐模板显式缺失标记（missing-value vs grade-value）。

## 4. 全量验证结果（integration/wave-3）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `python -m unittest discover -s server/tests` | **183 tests OK**（119 W2 + L14 17 + L15 15 + L16 13 + L17 19） |
| 2 | `python -m unittest discover -s worker/tests` | **45 tests OK** |
| 3 | `cd plugin && npm test` | **85/85 pass** |
| 4 | `python scripts/smoke_wave1.py` / `smoke_wave2.py` / `smoke_wave3.py` | 全部 SMOKE_OK（W1/W2 无回归） |
| 5 | `ruff check server worker shared scripts` | All checks passed |
| 6 | `python -m py_compile`（全部 .py） | OK |
| 7 | `node --check`（全部 plugin .js） | OK |
| 8 | `docker compose -f deploy/docker-compose.yml config --quiet` | OK |
| 9 | alembic upgrade/current/heads（真实 PG） | 见 §2，全部通过 |

环境：Python 3.14.3 · Node v24.14.0 · ruff 0.15.21 · Docker/Compose 29.1.3/v2.40.3。

## 5. 边界确认

- 未实现 MOD-05 backfill 三组件、CT-011 真实端点、SSR 路由挂载（归 B-03）；未启动 Phase 5。
- L07 保持 blocked（TD-01）；CCR-001 保持 pending（CT-012/CT-014 未动）；tutor 设计包未动；未发布。
- 契约影响：无（四叶子 + 集成核验均确认）。

## 6. 遗留项（Phase 5 B-01~B-05 输入）

- **B-01（MOD-02）**：SI-STORE 真实实现（加密暂存/配额/目录）、SI-RELAY（PG 会话绑定 OutboxStore + 投递器 + 入站去重）、SI-VERIFY（已在 L09 以进程内注入，需收口）、SI-PURGE（CT-012 清除执行 + CT-014 回传）、CT-001 真实 multipart 接入。
- **B-02（MOD-04）**：MODEL-SERVICE-ACL（真实供应商接入前需用户合规确认，DD-009）、RESULT-PUBLISHER、RUBRIC-PROMPT-COMPOSER（含 CT-010 三桶映射细化）、SCORING-METRICS。
- **B-03（MOD-05）**：ACCESS-GATE（教师会话认证+课程授权+AccessDeniedLogged 持久化）、READMODEL-PROJECTOR（M05-IC-02 双侧面单实现，兼容性已验证）、RETENTION-GOVERNANCE（CT-011 端点、到期批处理、CT-012 发布、FLOW-011 接线）、SSR 路由挂载（L17 + main.py）、教师会话 API。
- **B-04（MOD-01）**：插件内组装（L04~L07、L10、L11、L13）、checkpoint 文件持久化注入、IC-PQ-004 清理协调、L06→CT-001 类别映射确认（已由 L10 常量表承载，复核即可）。
- **B-05**：端到端联调 SCENARIO-001/012/016（016 删除链路受 CCR-001 pending 阻塞）。
- 其余登记：L16 幂等时间窗粒度（UTC 自然日，implementation_detail）；L14 NO_ORIGINAL_GRADE→409 已统一验证；L10 checkpoint 持久化注入点；abort 前缀展示映射。

## 7. Phase 5 前置条件评估

**已满足**：16/17 叶子（除 L07）全部集成入 main 且全量绿；三条 scenario chain 所需的事件载荷（CT-004/005/006）与教师端链路均已由冒烟锁定；迁移链单头（11a22f91f4b3）可续；backfill 端口边界全部以注入点形式存在且经测试锁定。**未放行**——等用户批准。Phase 5 唯一结构性阻塞：CCR-001 pending 影响 SCENARIO-016 删除链路完整性声明（TD-08）；L07（TD-01）影响 REQ-003 对话采集端到端。

## 8. 结论

integration/wave-3（HEAD `08eb884`）满足合入 main 的全部条件。
