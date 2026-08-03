# Run Manifest — tutor-r01

| 条目 | 值 |
|---|---|
| run_id | `tutor-r01` |
| project_id | `tutor-app` |
| 创建时间 | 2026-07-19（Asia/Shanghai） |
| 协调者 | Integration Owner / Workflow Coordinator |
| 目标仓库 | `E:\pythonproject\完整流程\代码设计\完整代码开发工作流\tutor-app`（独立 Git 仓库，main） |
| 设计输入（只读） | `E:\pythonproject\完整流程\代码设计\完整代码开发工作流\tutor\` |
| 运行类型 | 新 root run（root-to-integration，分层 vibe coding） |
| 范围 | 17 个叶子（16 个 L2 STOP_LAYERING + MOD-03 L1 终端叶子）+ 父级 backfill |
| 状态 | **Wave 3 已集成入 main（2026-07-20）**；16/17 叶子完成（L07 blocked）；等待用户放行 Phase 5 |

## 输入身份（SHA-256，恢复时逐一核对；任一不匹配即视为不同运行，不得 resume）

| 设计文件 | SHA-256 |
|---|---|
| tutor/L0-root/vibe-coding-course-prd.md | a3d61ac93d25a2d66aa02f098f208bc0a01b08dde0ccb46871e51426ddf8ae5c |
| tutor/L0-root/architecture/01-system-overview.md | 928e5a4c1de6369bae17b2d1985c99263a9c784219c76131b574baf6dcd50913 |
| tutor/L0-root/architecture/02-runtime-architecture.md | a5d9d3652cf3b638d0fa6c4790c19641893689ff06bea891603c6734e6193dbe |
| tutor/L0-root/architecture/03-data-and-consistency.md | 73fdd729ad2bc277d3f5d854a265238dc04bd2cc41507d95efa97d25a71a6e8c |
| tutor/L0-root/architecture/04-interface-contracts.md | 4599918536e46ca90f566919dc3e1e9f42c59d6da034d771ca44a98bae3efb9f |
| tutor/L0-root/architecture/05-decisions-and-technology.md | 96b5b4006e16139f71fc95e7c374f54b606f99d00739b3b91acdc17bae86fc27 |
| tutor/L0-root/architecture/06-deployment.md | b3efc7ea6a0e80c0780207504d7be00e62014b10aa99ac29f7cc72e95ac3af70 |
| tutor/L2/leaf-gate.L2-terminal.md | 1dcb210f2e08a1f4ddf7e2da052c4002fedcb90864b2f9c884839274609e1328 |
| tutor/L1/L1-mod-03/architecture/06-leaf-decision.md | 7d37e7161d8f7168b50fca275e71fd844544bf4991b4e1b0b5c278961c100014 |

L1/L2 各节点包（prd、architecture/*、leaf_gate_decision.json）为叶子级输入，按 execution-matrix 的 `design_refs` 列逐叶子引用；其哈希在 Phase 2 生成各叶子任务包时登记。

## 运行配置

| 项 | 值 |
|---|---|
| mode | 手动协调（协调者驱动；不调用 legacy `advance-state` / `run-workflow` 自动执行） |
| 真相文件 | 本 manifest + execution-matrix.md + contract-freeze.md + task-registry.md |
| 事件日志 | `docs/vibecode/runs/tutor-r01/execution-log.jsonl`（Phase 1 起追加，append-only） |
| 恢复规则 | 仅以本 run 目录文件恢复；核对上表输入哈希；禁止使用任何 Fixture 批准充当真实批准 |

## Human Gates 状态

| Gate | 状态 | 批准记录 |
|---|---|---|
| matrix（执行矩阵 + 决策清单） | **approved** | 用户对话批准，2026-07-19 |
| wave_1（仅 L01~L06 开工） | **approved** | 用户对话批准，2026-07-20；L07 保持 blocked（TD-01） |
| wave_1_integration | **approved + done** | 用户对话批准，2026-07-20；integration/wave-1 验证通过后合入 main |
| wave_2（L08~L13 开工） | **approved** | 用户对话批准，2026-07-20 |
| wave_2_integration | **approved + done** | 用户对话批准，2026-07-20；integration/wave-2 验证通过后合入 main |
| wave_3（L14~L17 开工） | **approved** | 用户对话批准，2026-07-20 |
| wave_3_integration | **approved + done** | 用户对话批准，2026-07-20；integration/wave-3 验证通过后合入 main |
| contract_change | **pending（CCR-001 已提交，待用户批准）** | — |
| high_risk_failure | pending（无触发） | — |
| wave_2 / wave_3 / integration | **not approved** | — |
| final（发布决策） | pending | — |

## 范围声明

- 实现：PRD「Current Release」全部 REQ-001~012、NFR-001~004；三条 scenario chain（SCENARIO-001 主链路、SCENARIO-012 评分失败重试、SCENARIO-016 保留删除）。
- 不实现（PRD Non-goals）：学生查看评分/建议/历史、百分制评分、自动触发提交。
- 继承不可推翻：KD-001~KD-005；各模块 LCD（MOD-01 LCD-001~006、MOD-02 LCD-001~009、MOD-03 LCD-001~005、MOD-04 LCD-001~006、MOD-05 LCD-001~009 中标记 decide_now/inherited 者）。
