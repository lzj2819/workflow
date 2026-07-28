# Task Registry — tutor-r01

- 每行一个可派发任务。状态机：`pending → ready → in_progress → verify → done`；`blocked` 可任意态进入，解除后回到原态。
- matrix gate：approved 2026-07-19。**Wave 1/2/3 开工+集成、Phase 5 受限回填：approved + done（用户批准范围内）**；SCENARIO-016（CCR-001）与最终发布未批准。
- L07：TD-01 已由 D-1（选 A）关闭——宿主导出机制核实（codex rollout jsonl 只读导出，HostUnsupportedError 可观测），已合入 main（merge 5420657）。
- 派发时由协调者生成对应叶子任务包（vibecode-task.md / allowed-context.md / forbidden-changes.md / verification-checklist.md）并登记任务包路径。

## 叶子任务（17）

| task_id | leaf_id | 标题 | 波次 | 状态 | 阻塞 | 任务包路径 | 完成证据 |
|---|---|---|---|---|---|---|---|
| T-01 | L01 | MOD-03 course-roster 整模块实现（VERIFIER + ROSTER-ADMIN + 运维预置工具） | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L01-course-roster/ | 972e1f9；18 新增绿；完成包已核验 |
| T-02 | L02 | SI-CORE 提交聚合与状态机 | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L02-si-core/ | 2970b01；22 新增绿；完成包已核验 |
| T-03 | L03 | CMP-SCORING-ORCHESTRATOR 评分任务编排 | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L03-scoring-orchestrator/ | 066e516；24 新增绿；完成包已核验 |
| T-04 | L04 | CMP-CONFIG-STORE 插件配置 | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L04-config-store/ | 12927a5；10 新增绿；完成包已核验 |
| T-05 | L05 | CMP-INTENT-PARSER 意图解析与缺项闸门 | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L05-intent-parser/ | 8610326；15 新增绿；完成包已核验 |
| T-06 | L06 | CMP-MATERIAL-COLLECTOR 材料收集 | W1 | done | — | docs/vibecode/runs/tutor-r01/leaves/L06-material-collector/ | f7f4dc2；9 新增绿；完成包已核验 |
| T-07 | L07 | CMP-DIALOGUE-COLLECTOR 对话导出 | W1 | done | —（D-1 选 A 已批准并实施） | docs/vibecode/runs/tutor-r01/leaves/L07-dialogue-collector/ | 81c506d + merge 5420657；plugin 15/15 绿；HostUnsupportedError 可观测 |
| T-08 | L08 | SI-XFER 分片上传会话 | W2 | done | — | docs/vibecode/runs/tutor-r01/leaves/L08-si-xfer/ | a59c906；25 新增绿；完成包已核验 |
| T-09 | L09 | SI-API 接入端点与令牌 | W2 | done | — | docs/vibecode/runs/tutor-r01/leaves/L09-si-api/ | 1e715be；18 新增绿；完成包已核验 |
| T-10 | L10 | CMP-UPLOAD-CLIENT 上传客户端 | W2 | done | — | docs/vibecode/runs/tutor-r01/leaves/L10-upload-client/ | 4ec5ac0；12 新增绿；完成包已核验 |
| T-11 | L11 | CMP-PENDING-QUEUE 本地待上传队列 | W2 | done | — | docs/vibecode/runs/tutor-r01/leaves/L11-pending-queue/ | f061ed9；10 新增绿；完成包已核验 |
| T-12 | L12 | CMP-ASSESSMENT-ENGINE 五维评估装配 | W2 | done | —（fake provider 约束已遵守） | docs/vibecode/runs/tutor-r01/leaves/L12-assessment-engine/ | 3e560c0；13 新增绿；完成包已核验 |
| T-13 | L13 | CMP-STATUS-PRESENTER 状态展示 | W2 | done | — | docs/vibecode/runs/tutor-r01/leaves/L13-status-presenter/ | 848cb86；16 新增绿；完成包已核验 |
| T-14 | L14 | CMP-REVIEW-COMMAND 复核写侧 | W3 | done | —（理由保持可选，遵守） | docs/vibecode/runs/tutor-r01/leaves/L14-review-command/ | 58b6ee9；17 新增绿；完成包已核验 |
| T-15 | L15 | CMP-REVIEW-QUERY 教师查询读装配 | W3 | done | — | docs/vibecode/runs/tutor-r01/leaves/L15-review-query/ | c846a36；15 新增绿；完成包已核验 |
| T-16 | L16 | CMP-PRESENTATION 展示视图 | W3 | done | — | docs/vibecode/runs/tutor-r01/leaves/L16-presentation/ | 34bb13b；13 新增绿；完成包已核验 |
| T-17 | L17 | CMP-TEACHER-UI 教师前端 | W3 | done | —（仅消费已定义 API，遵守） | docs/vibecode/runs/tutor-r01/leaves/L17-teacher-ui/ | 70119ae；19 新增绿；完成包已核验 |

## 集成/ backfill 任务（Phase 5，Integration Owner）

| task_id | 范围 | 状态 | 备注 |
|---|---|---|---|
| B-01 | MOD-02 backfill：SI-STORE / SI-RELAY / SI-VERIFY / SI-PURGE 与 L02/L08/L09 接线 | done | store 47c3b67 / relay 4ea8b68 / purge fd44fd6(+0015) / multipart 93d5a78；PG SKIP LOCKED 验证通过 |
| B-02 | MOD-04 backfill：MODEL-SERVICE-ACL / RESULT-PUBLISHER / RUBRIC-PROMPT-COMPOSER / SCORING-METRICS 与 L03/L12 接线 | done | 3dbf9fa / 458121c；仅 fake 实现（遵守禁令） |
| B-03 | MOD-05 backfill：ACCESS-GATE / READMODEL-PROJECTOR / RETENTION-GOVERNANCE 与 L14~L17 接线 | done | e013713 / d392956 / 3373e48 / c694746+1ab6da9；SCENARIO-016 未声称 |
| B-04 | MOD-01 集成：L04~L07、L10、L11、L13 插件内接线 | done | 3bdf36d；TD-01 unsupported 如实透传 |
| B-05 | 端到端联调：SCENARIO-001 / SCENARIO-012 | done | 双 E2E_OK；SCENARIO-016 blocked 留证（e2e-report.md） |

## 阶段任务（协调者）

| task_id | 内容 | 状态 |
|---|---|---|
| P-00 | Phase 0：控制文件 + 矩阵 + 决策清单 | done（matrix gate approved 2026-07-19） |
| P-01 | Phase 1：契约 schema 落地、脚手架、测试骨架、详细设计记录 | done（2026-07-20，验证报告已出） |
| P-02I | Wave 1 集成（六分支合并 + merge-head + 全量验证 + 合入 main） | done（2026-07-20，报告已出） |
| P-03I | Wave 2 集成（六分支合并 + merge-head + 六项接线 + 全量验证 + 合入 main） | done（2026-07-20，报告已出） |
| P-04I | Wave 3 集成（四分支合并 + merge-head + 指定核验 + 全量验证 + 合入 main） | done（2026-07-20，报告已出） |
| P-05 | Phase 5：受限回填 B-01~B-05 + E2E | done（2026-07-21，报告已出） |
| P-06 | Phase 6：发布准备与硬化验证 | done（2026-07-22，release-readiness-report 已出；**正式发布未批准**） |
| G-01 | 最终门禁决策包（五项） | 决策已收到（2026-07-22）：D-1=A、D-2=批准方案A、D-3=批准推荐、D-4=建立 staging、D-5=只读调研；对应实施进行中 |
| C-01 | CCR-001 AssessmentResult 删除接线（TD-08） | **approved（2026-07-22，方案 A）** → in_progress（契约变更 + MOD-04 清除接线 + CT-015 + 双回流 + 迁移 + SCENARIO-016 验收） |
