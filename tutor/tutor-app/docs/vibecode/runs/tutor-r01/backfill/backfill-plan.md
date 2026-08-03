# Backfill Plan — tutor-r01 / Phase 5（受限回填）

- 批准：用户 2026-07-21（仅限本计划范围）。
- 执行：Integration Owner 主导；实施委托 Claude Code 子代理在隔离 worktree 完成，协调者定义范围、核验与集成。
- 严格边界：L07/TD-01 blocked；CCR-001 pending（SCENARIO-016 blocked，不得声称 AssessmentResult 删除链路完成）；不接真实供应商/密钥/外发；契约语义变更即停并 CCR；不改 tutor 设计包；不发布。

## 集成任务与允许修改范围

| task | 内容 | 允许路径（相对仓库根） | 依赖 |
|---|---|---|---|
| T-B01a | SI-STORE：材料存储真实实现（MaterialStorePort + MaterialMetadataReader + 课程配额 200GB；目录布局 DD-005；暂存/正式区；PG 登记） | `server/course_app/submission_intake/store/**`、`server/migrations/versions/0009_material_store.py`（down=11a22f91f4b3）、`server/tests/test_b01a_*.py` | — |
| T-B01b | SI-RELAY：PG Outbox 绑定（SqlaOutboxStore 同事务入队）+ 投递器（轮询/退避/确认）+ 入站去重（ST-04/05） | `server/course_app/submission_intake/relay/**`、`shared/tutor_shared/outbox.py`（仅追加 SQL 实现，不改既有语义）、`server/migrations/versions/0010_outbox.py`（down=11a22f91f4b3）、`server/tests/test_b01b_*.py` | T-B01a（共享迁移头） |
| T-B01c | SI-PURGE：CT-012 消费 → 材料+提交记录清除 → CT-014 回传（失败项保留重跑；审计不受影响） | `server/course_app/submission_intake/purge/**`、`server/tests/test_b01c_*.py` | T-B01a/b |
| T-B01d | CT-001 真实 multipart：multipart/form-data 二进制接入与分片会话协议端点（对齐 L10 session-driver 期望），保留 JSON/content_ref 兼容 | `server/course_app/submission_intake/api/multipart.py`（新增模块）、`server/tests/test_b01d_*.py` | T-B01a |
| T-B02a | MODEL-SERVICE-ACL（可替换接口 + fake 实现；CT-010 出站最小化校验 + 入站 schema 校验 + ≤3min 预算 + 三分类错误）+ RESULT-PUBLISHER（CT-005 经 SQL Outbox 发布与投递确认语义） | `worker/assessment_worker/model_acl/**`、`worker/assessment_worker/result_publisher/**`、`worker/tests/test_b02a_*.py` | T-B01b（SQL Outbox 抽象） |
| T-B02b | RUBRIC-PROMPT-COMPOSER（RubricPolicy 版本化存证 + ICT-002 实现 + 三桶预算编排）+ SCORING-METRICS（SM-002/003 度量 + ICT-008 查询端口） | `worker/assessment_worker/rubric/**`、`worker/assessment_worker/scoring_metrics/**`、`server/migrations/versions/0011_rubric_policies.py`（down=11a22f91f4b3）、`worker/tests/test_b02b_*.py` | T-B02a |
| T-B03a | ACCESS-GATE：教师账号（v1 运维预置）+ 会话签发/校验（不透明令牌、HttpOnly、12h 滑动）+ 课程授权（TeacherAccessGrant）+ AccessDeniedLogged 追加审计 | `server/course_app/teacher_web/access_gate/**`、`server/migrations/versions/0012_access_gate.py`（down=11a22f91f4b3）、`server/tests/test_b03a_*.py` | — |
| T-B03b | READMODEL-PROJECTOR：消费 CT-005/CT-006/CT-014(+M05-IC-05/CT-012 自消费) → 读模型表 + 投影位点同事务 + 重放守卫；M05-IC-02 双侧面实现；CT-005 scored 时经 M05-IC-01 建复核记录 | `server/course_app/teacher_web/projector/**`、`server/migrations/versions/0013_read_model.py`（down=11a22f91f4b3）、`server/tests/test_b03b_*.py` | T-B01b、T-B03a（接线在组合根） |
| T-B03c | RETENTION-GOVERNANCE：DeletionBatch 聚合 + 到期批处理（FLOW-011 读 L01 课程结束时间）+ CT-011 端点接线 + 审计先行 + CT-012 发布 + CT-014 消费回写批次（**不声称 SCENARIO-016**） | `server/course_app/teacher_web/retention/**`、`server/migrations/versions/0014_retention.py`（down=11a22f91f4b3）、`server/tests/test_b03c_*.py` | T-B01b/c、T-B03a |
| T-B03d | SSR 路由挂载 + 组合根（main.py：全部 router 挂载 + 真实组件装配 + 健康/指标） | `server/course_app/main.py`、`server/course_app/composition.py`（新增）、`server/tests/test_b03d_*.py` | 全部 B-01/B-03 |
| T-B04 | 插件组装（入口装配 L04~L07/L10/L11/L13）+ checkpoint 文件持久化（L10 接口）+ IC-PQ-004 终态清理协调 | `plugin/src/app/**`、`plugin/src/upload_client/file-checkpoint-store.js`、`plugin/src/pending_queue/cleanup.js`、`plugin/test/b04-*.test.js` | — |
| T-B05 | E2E 联调：SCENARIO-001（主链路）、SCENARIO-012（模型失败重试）；SCENARIO-016 保持 blocked 并留可观测证据 | `scripts/e2e_scenario_001.py`、`scripts/e2e_scenario_012.py`、`docs/vibecode/runs/tutor-r01/e2e-report.md` | 全部 |

## 纪律

- 迁移全部以 `11a22f91f4b3` 为 down_revision（并行多头），集成时 alembic merge heads。
- 每个任务：completion note（SHA/改动/验证/契约影响/风险）写入 `docs/vibecode/runs/tutor-r01/backfill/<task>-completion.md`。
- 每个任务完成后跑全量回归（server/worker/plugin + 既有冒烟）。
- SCENARIO-016 与 AssessmentResult 删除链路：**不实现、不声称**；保留 blocked 可观测状态。
