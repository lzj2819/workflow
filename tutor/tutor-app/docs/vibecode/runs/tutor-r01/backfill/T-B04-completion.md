# T-B04 完成记录 — 插件组装 + checkpoint 持久化 + IC-PQ-004

- SHA：`3bdf36d03a12edeb53aa60e1c5aedf8c184ff280`（分支 tutor-r01/B04-plugin-assembly，worktree `.worktrees/B04-plugin-assembly`）
- 日期：2026-07-21
- 前置：`git merge main` fast-forward 无冲突（55e19d5）。

## 改动（全部在允许路径内）

1. `plugin/src/app/index.js`（新增）：`createPlugin(deps)` 装配 L04 config → L05 intent → L06/L07 采集 → L11 queue → L10 upload → L13 presenter。
   - 适配桥接（不改叶子）：L04 `screenshots_dir/results_dir` ↔ L06/L11 `screenshot_dir/result_dir`；L11 `taskRef` → L06 `collectMaterials` 入参；L11 `bundle_ref{dialogue_artifact, material_manifest}` → L10 `bundle_ref.chunks`；L10 `outcome_type` → L11 `status` 词汇。
   - `submit(commandText)`：配置读取 → 不完整经 L13 配置面呈现并中止 → 意图解析 → 缺项经 L13 呈现并中止（INV-1 零网络）→ L11 编排 → L13 呈现真实状态。
   - `recover()`（启动恢复扫描）、`cleanupTerminal()`、`getStatus/listStatus`、`dispose()`。
   - TD-01：host dialogue port 必须注入；缺省为 `exportDialogueFromHost`（抛 HostUnsupportedError）；不虚构导出能力、不静默转为「对话缺失」，失败原因经 L13 原样透传。
   - 终态（confirmed/rejected）后 `discardCheckpoint`（L2 03 cleanup_trigger）。
2. `plugin/src/upload_client/file-checkpoint-store.js`（新增）：`createFileCheckpointStore({dir})`，接口与 `createMemoryCheckpointStore` 同形状；按 `checkpoint-<uuid>.json` 一文件；原子写（tmp+rename）+ 串行化；损坏文件 → `CHECKPOINT_CORRUPT` 可诊断报错且保留原文件；INV-5 fail-closed 形状校验（只收已确认分片索引记录）；校验失败以 Promise 拒绝（与内存版异步形状一致）。
3. `plugin/src/pending_queue/cleanup.js`（新增）：`runCleanup({store, archiveDir, now, retentionDays=30, queue?, onEvent})`。审计先行（终态摘要先落 `archive/<uuid>.json`：uuid/terminal_state/terminal_at/archived_at，绝无材料快照）→ envelope 原子移除 + command_index 同步清理；进行中任务不误删；时间不可判定保守保留；存活队列非终态交叉核对否决；清理计数经 onEvent + 返回摘要可观测。
4. 测试（新增）：`plugin/test/b04-app-assembly.test.js`（6）、`b04-cleanup.test.js`（4）、`b04-file-checkpoint-store.test.js`（7）。

## 验证

- `node --test test/b04-*.test.js`：17/17 通过。
- `npm test`：102/102 通过（既有 85 项无回归）。
- `node --check`：全部 6 个新增 .js 通过。

## 契约影响

- 无契约语义变更。只消费 L04~L13 冻结公开接口；未改任何叶子实现文件。
- 命名差桥接（`screenshots_dir` vs `screenshot_dir`）仅在组装层适配，未改冻结字段。
- 无 npm 依赖；transport/host port 注入，测试零真实网络。

## 风险 / 注意

- IC-PQ-004 清理与 L11 envelope 单写约束：`cleanupTerminal` 必须冷态执行（`recover()`/init 之前或 dispose 之后），否则存活队列的 persist 会用内存态覆盖清理结果（已在 cleanup.js 与 app 头注释明示；测试按冷态路径验证）。
- 清理为双写者时 revision 计数按顺序使用保持单调；并发运行清理与队列不在本任务范围（编排层纪律）。
