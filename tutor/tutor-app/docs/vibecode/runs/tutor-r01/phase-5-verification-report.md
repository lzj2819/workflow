# Phase 5 Verification Report — tutor-r01（受限回填 B-01~B-05）

- 日期：2026-07-21；执行：Integration Owner / Workflow Coordinator
- 范围：用户批准的 Phase 5 受限回填（B-01~B-05 明确范围）
- 结论：**全部批准范围内工作完成并验证通过；具备进入最终发布准备阶段的条件（在 TD-01 与 CCR-001 两个既有阻塞解除前，REQ-003 与 SCENARIO-016/AC-NFR-004-01 不可宣称完成）。**

## 1. 已完成的 B-01~B-05 工作

### B-01（MOD-02）

| 任务 | 交付 | 验证 |
|---|---|---|
| T-B01a SI-STORE | FilesystemMaterialStore（原子暂存/幂等提升/配额前置/删除幂等）+ MaterialFile/CourseQuotaUsage + 迁移 0009 | 18 测试绿；提交 `47c3b67` |
| T-B01b SI-RELAY | SqlaOutboxStore（同事务入队、内部无 commit/rollback、PG SKIP LOCKED 认领）+ OutboxRelayer（轮询/退避/确认）+ InboundDedup + 迁移 0010 | 15 测试绿；**真实 PG 并发认领验证：5 记录两线程 0 重叠**；提交 `4ea8b68` |
| T-B01c SI-PURGE | PurgeExecutor（CT-012 逐项清除、失败重跑、CT-014 载荷契约一致、与登记同事务入队）+ ST-07 + 迁移 0015（协调者补） | 8 测试绿；提交 `fd44fd6` |
| T-B01d CT-001 multipart | multipart/form-data 二进制接入 + 分片会话协议端点（对齐 L10 session-driver，无 CCR） | 13 测试绿；提交 `93d5a78` |

### B-02（MOD-04）

| 任务 | 交付 | 验证 |
|---|---|---|
| T-B02a MODEL-SERVICE-ACL + RESULT-PUBLISHER | 出站最小化校验 + ≤3min 预算守卫 + CT-010 应答校验 + 三分类错误 + FakeVendorAdapter（标注 fake）；session 注入 SqlaOutboxStore 的 CT-005 发布端口 | 28 测试绿；提交 `3dbf9fa` |
| T-B02b RUBRIC-PROMPT-COMPOSER + SCORING-METRICS | RubricPolicy 版本化存证（种子 v1 五维）+ 确定性 compose + 三桶预算；SM-002/003 度量 + ICT-008 查询 + 迁移 0011 | 31 测试绿；提交 `458121c` |

### B-03（MOD-05）

| 任务 | 交付 | 验证 |
|---|---|---|
| T-B03a ACCESS-GATE | 教师账号/会话（不透明令牌、哈希存储、12h 滑动）+ 课程授权 + AccessDeniedLogged 追加审计 + 三形状适配 + 运维预置 CLI + 迁移 0012 | 32 测试绿；提交 `e013713` |
| T-B03b READMODEL-PROJECTOR | CT-005/006/014 投影 + 位点同事务 + 重放守卫（tombstone）+ M05-IC-02 双侧面 + M05-IC-01 接线 + 迁移 0013 | 25 测试绿；提交 `d392956` |
| T-B03c RETENTION-GOVERNANCE | 到期批处理（FLOW-011 同进程注入）+ CT-011（409/幂等/审计先行）+ CT-012 发布 + CT-014 回写 + M05-IC-06 读端口 + 迁移 0014 | 28 测试绿；提交 `3373e48` |
| T-B03d 组合根 | composition.py（全组件真实装配）+ main.py（全部 router 挂载 + health/metrics）+ relayer_tick 钩子 | 3 组合冒烟绿；提交 `c694746` + 缺陷修复 `1ab6da9` |

**跨组件缺陷修复（Integration Owner 范围）**：T-B03d 发现 L14 一次「批注+等级」调整两事件共用 adjustment_id，B03b projector 仅按 id 去重丢 final_grade → 去重键改为 (adjustment_id, event_type) + 回归测试（`1ab6da9`）。

### B-04（MOD-01 集成）

插件组装（createPlugin/submit/recover；TD-01 unsupported 如实透传）+ checkpoint 文件持久化（原子写、INV-5）+ IC-PQ-004 终态清理（30 天可配、审计摘要、冷态执行约束已明示）。17 测试绿 + npm 102 全绿；提交 `3bdf36d`。

### B-05（E2E 联调）

- `scripts/e2e_scenario_001.py`：SCENARIO-001 主链路 **E2E_OK**（18 断言）。
- `scripts/e2e_scenario_012.py`：SCENARIO-012 失败重试 **E2E_OK**（9 断言）。
- 详见 `docs/vibecode/runs/tutor-r01/e2e-report.md`（含接线注记：received→processing 的生产接线点建议）。

## 2. 仍被 TD-01 / CCR-001 阻塞的能力与场景

| 阻塞 | 受影响能力 | 现状 |
|---|---|---|
| TD-01 | REQ-003 完整 Codex 对话采集（L07）；SCENARIO-001 的「对话」材料真实来源 | L07 未启动；host port 显式 unsupported；不虚构、不降级 |
| CCR-001 | SCENARIO-016 端到端；AC-NFR-004-01 的 AssessmentResult 到期删除完整性 | 组件级就绪（B03c/B01c/B03b），**不声称端到端完成**；CT-012/CT-014 冻结未动（消费者仍 [MOD-02, MOD-05]） |

## 3. 测试 / 迁移 / 端到端验证结果

| 项 | 命令 | 结果 |
|---|---|---|
| server 全量 | `python -m unittest discover -s server/tests` | **326 OK**（183 W3 + B01a 18 + B01b 15 + B01c 8 + B01d 13 + B03a 32 + B03b 26 + B03c 28 + B03d 3 + projector 回归 1） |
| worker 全量 | `python -m unittest discover -s worker/tests` | **104 OK**（45 W2 + B02a 28 + B02b 31） |
| plugin 全量 | `cd plugin && npm test` | **102/102**（85 W2 + B04 17） |
| E2E | `scripts/e2e_scenario_001.py` / `e2e_scenario_012.py` | 均 E2E_OK |
| 既有冒烟 | `scripts/smoke_wave1/2/3.py` | 全部 SMOKE_OK（无回归） |
| ruff | `ruff check server worker shared scripts` | All checks passed |
| py_compile / node --check | 全部 .py / .js | OK |
| compose | `docker compose -f deploy/docker-compose.yml config --quiet` | OK |
| 迁移（真实 PG） | `alembic upgrade head` → `current` → `heads` | merge-head `27867c368f7e` 单一 head；**38 表**齐备（19 + 19 Phase 5）；复跑幂等干净 |
| PG 并发认领 | 两线程 fetch_due 同 5 记录 | 0 重叠（SKIP LOCKED 生效，关闭 T-B01b 风险注记） |

环境：Python 3.14.3 · Node v24.14.0 · ruff 0.15.21 · Docker/Compose 29.1.3/v2.40.3 · fastapi 0.135.3 · SQLAlchemy 2.0.50 · alembic 1.18.4 · pydantic 2.13.4 · psycopg 3.3.4。

## 4. 过程缺陷与修复（诚实登记）

1. relay 测试固定 NOW 时钟脆弱 → 动态 NOW（`b0710ea`）。
2. T-B01c ST-07 缺迁移（任务书疏漏）→ 协调者补 0015 并与模型约束对齐。
3. projector 复核事件去重丢 final_grade → (adjustment_id, event_type)（`1ab6da9`，T-B03d 缺陷见证驱动）。
4. E2E 脚本自身接线修正：worker 侧非 CT-004 记录释放、received→processing 显式 ack、Bearer/cookie 通道区分、shared-cache 内存库、Windows 文件锁规避。

## 5. 遗留项（不阻塞本阶段关闭；进入发布准备前的输入）

- received→processing 的生产接线点（CT-004 confirmed 后置钩子，见 e2e-report §接线注记 1）。
- SI-STORE `_unassigned` 路径的课程键重组织（D-P5-01 登记）。
- ACL 预算守卫为事后判定；真实供应商接入需强制超时层 + 用户合规确认（DD-009）。
- ScoringMetrics 为进程内统计；三桶预算上线前需样例回归（LCD-005）。
- IC-PQ-004 清理需冷态执行（L11 envelope 单写约束，已明示）。
- 读模型 material_refs 空投影为 CT-006 载荷事实（契约不含材料清单；教师材料明细浏览需未来契约扩展，登记为观察项）。

## 6. 是否具备进入最终发布准备阶段的条件

**具备**（就批准范围而言）：全部 16/17 叶子 + B-01~B-05 回填完成且全量绿；真实 PG 迁移与并发语义验证通过；两条可联调场景链 E2E 通过；组合根可启动（uvicorn course_app.main:create_app --factory，见 docs/operations.md）。
**不具备宣称产品完成的两点**：TD-01（REQ-003 对话采集）与 CCR-001（SCENARIO-016 / AC-NFR-004-01 完整性）——这两项的最终验收必须在阻塞解除后补做。最终发布决定（human gate: final）由用户作出。
