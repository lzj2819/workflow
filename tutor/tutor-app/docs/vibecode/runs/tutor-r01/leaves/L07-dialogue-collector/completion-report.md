# Completion Report — L07 CMP-DIALOGUE-COLLECTOR（17/17）

- run：tutor-r01；leaf：L07；分支：`tutor-r01/L07-dialogue-collector`（worktree，基线 main 9687a73）
- 状态：**done**；TD-01 已按 D-1 选 A 解除（宿主机制：codex rollout JSONL）

## SHA

`81c506d607a04c77bf6701bb0ae8316867d27e15`
`feat(l07): CMP-DIALOGUE-COLLECTOR codex rollout jsonl export (TD-01 resolved)`

## 改动（仅 allowed-context 内）

| 文件 | 说明 |
|---|---|
| `plugin/src/dialogue_collector/index.js`（新增，451 行） | `exportDialogue({sessionsRoot?, sessionSelector, fs?, now?})` + `createDialogueCollector(deps)`；10 个稳定错误码（`DIALOGUE_COLLECTOR_ERROR_CODES`，冻结）；`DialogueCollectorError` |
| `plugin/test/dialogue-collector.test.js`（新增，15 项） | 全部合成 rollout fixture（临时目录自建 JSONL），零真实会话读取 |

未触碰 `plugin/` 其他目录、package.json、contracts/、server/、worker/、shared/、deploy/、docs/、tutor 设计包。

## 语义要点

- 数据源：`~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`（codex resume 同一数据源；sessionsRoot 可配置，调用时求值默认值）。
- 选择器 `{sessionId?, since?, until?}`：按文件名 ts/uuid 过滤；多候选取最新，全部候选记入 `source.candidates`（歧义显式报告）。
- 解析：message（user/assistant/system；developer→system）+ function_call/_output（→tool，name/arguments/output 完整 JSON 保真）；多 content 分片无损拼接（不插字符）；reasoning/turn_context 等协议记录跳过并计数（`records_skipped`，不计截断）。
- 完整性：session_meta 必需；turns 非空；`snapshot_sha256` = 源文件字节哈希（INV-4，重导稳定）；放行前经 `validateDialogueExport` 复检（fail closed）。
- 安全：只读 sessionsRoot 以内（词法守卫 `DIALOGUE_PATH_OUTSIDE_ROOT`）；不跟随符号链接；sessionId 强制 uuid 形（路径穿越拒绝）；错误消息只含路径/行号，不含会话正文；无日志。
- 失败显式化：不存在/不可读/为空/缺元数据/解析损坏/不可映射角色/空消息 → 稳定错误码抛出，绝不静默转为「对话缺失」、绝不伪造（L11 按任务书映射为 DIALOGUE_EXPORT_FAILED 原因）。

## 验证（worktree `plugin/`，Node 24）

- `node --test test/dialogue-collector.test.js`：**15/15 通过**（覆盖任务书全部语义断言：完整导出、顺序与角色映射、sha 稳定、歧义显式报告、越界拒绝、空会话显式失败，及元数据缺失/损坏行不含正文/INV-DLG-1 无 uuid 不采集/端口形状兼容）。
- `npm test`：**117/117 通过**（既有 102 项零回归 + 新增 15）。
- `node --check`：2 个新增 .js 全部通过。

## 契约影响

预期无，实际无。`DialogueExport` 形状与 `src/host/dialogue-export-port.js` 的 `validateDialogueExport` 完全兼容（`source_host: "codex-cli"` 落定 TD-01 占位）；导出物仅追加 `snapshot_sha256`/`source` 可选字段（校验器忽略额外字段；L11/L10 经 JSON 序列化透传，CT-001 字段不变）。L11 注入形状 `(taskRef) => Promise<artifact>` 未变；`app/index.js` 的 `hostDialoguePort` 注入点可直接换接 `createDialogueCollector(...).collectDialogue`（属集成 Owner 后续工作，本叶未改 app 层）。

## 风险

1. rollout JSONL 记录类型映射基于 codex-cli 0.144.1 布局；未来宿主新增对话型记录类型将被跳过计数而非导出——属显式设计（协议记录非对话正文），但若宿主把真实对话移到新类型，会以 records_skipped 形式可观测，需随宿主升级复验。
2. 文件名时间戳按 UTC 解释用于排序/区间过滤（仅影响候选排序，不进 turns）。
3. 真实宿主首接时建议用一条真实会话做人工抽查（本叶遵守授权纪律未读真实会话）。

## 范围自检

- 可写路径：仅 `plugin/src/dialogue_collector/**` 与 `plugin/test/dialogue-collector.test.js` —— 符合。
- 零 npm 依赖、未 npm install、未读真实会话、会话内容未写日志、未批准任何 gate、未改 tutor 设计包 —— 符合。
