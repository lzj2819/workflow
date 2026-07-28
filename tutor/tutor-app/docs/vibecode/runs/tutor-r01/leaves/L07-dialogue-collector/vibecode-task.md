# VibeCode Task — L07 CMP-DIALOGUE-COLLECTOR（17/17 最后一叶）

- run：tutor-r01；leaf：L07；波次：W1（迟发）；分支：`tutor-r01/L07-dialogue-collector`
- 模块：MOD-01 codex-plugin / CMP-DIALOGUE-COLLECTOR 完整 Codex 对话导出（DU-1，Node ESM 零依赖）。
- **TD-01 已解除（D-1 选 A，2026-07-22）**：宿主机制已核实——读取 `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`（codex resume 同一数据源；codex-cli 0.144.1 实测存在）。

## 目标

实现采集侧 ACL：从 Codex 会话回放文件导出完整对话为 DialogueExport 形状（REQ-003；INV-4 快照重传不重采）。

## 交付物

1. `exportDialogue({ sessionsRoot?, sessionSelector, fs? })`：
   - sessionsRoot 可配置（默认 `~/.codex/sessions`）；**只读该根以内路径，越界即拒绝**；
   - sessionSelector：`{ sessionId?: string, since?: ISO8601, until?: ISO8601 }`（按文件名时间戳/uuid 选择最近匹配；多候选取最新并记录 candidates）；
   - 解析 JSONL 行为 DialogueExport：`format_version`、`source_host: "codex-cli"`、`exported_at`、`turns[]`（role ∈ user/assistant/system/tool，content 非空、顺序保持、**不得截断**）；
   - 完整性校验：会话元数据行存在；turns 非空；sha256 快照标识（INV-4）。
2. `createDialogueCollector(deps)`：L11 编排可注入的端口实现（与 Phase 1 `src/host/dialogue-export-port.js` 的 validateDialogueExport 形状兼容）；导出物经其校验通过。
3. 失败显式化：会话不存在/不可读/为空 → 稳定错误码（不可静默转为「对话缺失」，由 L11 按任务书语义处理）。
4. 测试：`plugin/test/dialogue-collector.test.js`（**全部使用合成 rollout fixture，禁止读取任何真实用户会话文件**）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-dialogue-collector/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（03-state-and-data.md 的 ST-02/INV-4）
- 验收：根 PRD REQ-003、AC-REQ-003-01 MOD-01 slice
- 仓库：`plugin/src/host/dialogue-export-port.js`（形状与校验）、`plugin/src/ports/index.js`

## 禁止

- 读取真实用户会话文件（含本机 ~/.codex 下任何真实 rollout 内容）；虚构/改写导出物；改其他叶子/契约；npm 依赖。
- 禁止把会话内容写入日志。

## 验证（worktree 的 plugin/ 目录）

- `node --test test/dialogue-collector.test.js` 全绿（含：完整导出、turns 顺序与角色映射、快照 sha 稳定、选择器歧义显式报告、越界路径拒绝、空会话显式失败）
- `npm test` 全绿（既有 102 项不得回归）
- `node --check` 全部新增/改动 .js

## 完成包

写入主仓任务包目录 completion-report.md（SHA/改动/验证/契约影响=预期无/风险/范围自检）。
