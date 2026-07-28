# tutor-app — Agent Instructions

本仓库是 tutor（Vibe Coding 课程评估系统）设计包的**唯一实现仓库**，由 Integration Owner / Workflow Coordinator 按 Layered Vibe Coding 流程驱动。

## 设计输入（只读）

- 设计包根：`E:\pythonproject\完整流程\代码设计\完整代码开发工作流\tutor\`（**只读，任何 agent 不得修改**）。
- 权威契约源：`tutor/L0-root/architecture/04-interface-contracts.md`（CT-001~CT-014 + auth/token）。
- 终端边界：`tutor/L2/leaf-gate.L2-terminal.md`（16 个 L2 全部 STOP_LAYERING）+ `tutor/L1/L1-mod-03/architecture/06-leaf-decision.md`（MOD-03 在 L1 即终端叶子）。
- **实现范围 = 17 个叶子**（16 个 L2 叶子 + MOD-03 L1 叶子），见 `docs/vibecode/runs/tutor-r01/execution-matrix.md`。legacy 扫描到的 16 个 L2 节点不是全部范围。

## 硬性规则

1. 代码只写入本仓库（tutor-app）；不得写入 tutor 设计包或工作流仓库其他任何目录。
2. 当前活跃运行：`docs/vibecode/runs/tutor-r01/`。运行真相 = run-manifest + execution-matrix + contract-freeze + task-registry 四份文件共同构成。
3. 不得自动批准任何 human gate：矩阵批准、契约变更、高风险失败、最终发布决策，均由用户显式确认。
4. Leaf Owner 只能修改 execution-matrix 中该叶子 `allowed_paths` 列出的路径；不得修改父接线、兄弟内部、共享契约、根级 DTO/事件 schema。
5. Integration Owner 只能修改当前 backfill 计划列出的父集成层文件（含各父模块的内部支撑组件：SI-STORE/SI-RELAY/SI-VERIFY/SI-PURGE、CMP-ACCESS-GATE/CMP-READMODEL-PROJECTOR/CMP-RETENTION-GOVERNANCE、CMP-MODEL-SERVICE-ACL/CMP-RESULT-PUBLISHER/CMP-RUBRIC-PROMPT-COMPOSER/CMP-SCORING-METRICS）。
6. 契约冻结后以 `docs/vibecode/runs/tutor-r01/contract-freeze.md` 为准；任何共享契约变更必须停止并产出 `contract-change-request.md` 交用户决策。
7. 继承设计决策 KD-001~KD-005 不可推翻；各模块 LCD 决策在其模块边界内不可推翻。设计包中 `defer_to_detail_design` / `implementation_detail` 项可在实现时落地，但必须登记到 findings.md。
8. 状态机、幂等、重试语义以设计为准：Submission 六态 + deleted；CT-003 每次重新校验不缓存；评分失败自动重试一次；Outbox 事件消费幂等；不得伪造等级。
9. 工作流仓库根 `vibecode/state.json`（legacy 状态）不由本运行使用；本运行不调用 `advance-state`，恢复仅以 tutor-r01 manifest 与任务注册表为准。

## 目录约定（草案，Phase 1 脚手架时固化）

```
plugin/     DU-1 MOD-01 codex-plugin（学生侧）
server/     DU-2 course-app（MOD-02 submission-intake + MOD-03 course-roster + MOD-05 teacher-web）
worker/     DU-3 assessment-worker（MOD-04 assessment）
contracts/  冻结契约的机器可读 schema（Integration Owner 维护，叶子只读）
docs/vibecode/runs/tutor-r01/  本运行全部控制文件
```
