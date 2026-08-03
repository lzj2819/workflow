# tutor-app Task Plan

- 运行 ID：`tutor-r01`
- 目标：按 tutor 设计包实施完整产品（DU-1 插件 + DU-2 服务端 + DU-3 评估 worker），17 个叶子全部落地并通过验收契约。
- 协调者：Integration Owner / Workflow Coordinator（本会话）。
- 当前阶段：**Phase 6 发布准备与硬化验证完成（2026-07-22）**。报告：`docs/vibecode/runs/tutor-r01/release-readiness-report.md`（可发布能力/证据/风险/不可发布项）。**正式发布未批准，等待用户最终产品范围与发布门禁决定**。

## 阶段计划

| 阶段 | 内容 | 状态 | 出口条件 |
|---|---|---|---|
| Phase 0 | 设计包阅读 + 控制面 + 矩阵 | completed | matrix approved 2026-07-19 |
| Phase 1 | 契约 schema + monorepo 骨架 + 工程基线 + MOD-02 复核 | completed | 验证报告已出（35+8+8 绿） |
| Phase 2 | Wave 1 叶子实现（**仅 L01~L06 已放行**；L07 blocked by TD-01） | completed | 六个完成包核验通过 + 集成验证通过并合入 main（2026-07-20） |
| Phase 3 | Wave 2 叶子实现（L08~L13） | completed | 六个完成包核验 + 集成验证通过并合入 main（2026-07-20） |
| Phase 4 | Wave 3 叶子实现（L14~L17） | completed | 四个完成包核验 + 集成验证通过并合入 main（2026-07-20） |
| Phase 5 | 受限回填 B-01~B-05（支撑组件与接线；SCENARIO-001/012 联调；016 blocked） | completed | B-01~B-04 组件测试通过 + SCENARIO-001/012 E2E 通过 + Phase 5 verification report（2026-07-21） |
| Phase 6 | 发布准备与硬化验证 | completed | release-readiness-report（2026-07-22）；正式发布待用户最终门禁 |

## Human Gates（不得自动批准）

1. **matrix 批准** — approved（2026-07-19，用户对话批准）。
2. 契约变更 — **CCR-001 已提交，pending**（TD-08，AssessmentResult 删除接线；批准前 CT-012/CT-014 保持冻结，不得实施）。
3. 高风险失败（如数据丢失、验收连续失败）。
4. 最终发布决策（Phase 6 出口）。
5. Phase 1 → Phase 2 放行：Phase 1 验证结果向用户汇报并由用户确认。

## 范围基线

- 17 个叶子 = 16 个 L2 STOP_LAYERING 节点 + MOD-03（L1 终端叶子）。
- 父级内部支撑组件不作为叶子，由 Integration Owner 在 Phase 5 backfill：SI-STORE/SI-RELAY/SI-VERIFY/SI-PURGE（MOD-02）；CMP-MODEL-SERVICE-ACL/CMP-RESULT-PUBLISHER/CMP-RUBRIC-PROMPT-COMPOSER/CMP-SCORING-METRICS（MOD-04）；CMP-ACCESS-GATE/CMP-READMODEL-PROJECTOR/CMP-RETENTION-GOVERNANCE（MOD-05）。
- Non-goals 严格执行：学生查看评分、百分制、自动触发提交均不实现。
