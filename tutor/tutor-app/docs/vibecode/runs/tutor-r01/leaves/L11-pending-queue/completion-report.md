# Completion Report — L11 CMP-PENDING-QUEUE（tutor-r01 / W2）

- leaf：L11 CMP-PENDING-QUEUE（MOD-01 本地任务队列与状态机）
- 分支：`tutor-r01/L11-pending-queue`（worktree `.worktrees/L11-pending-queue`，基线 main a4d373f）
- 状态：**done**
- 提交 SHA：**f061ed9a789a837bd7e9beb23f20ebc7531f6639**

## 改动清单（全部在 allowed-context 内）

- `plugin/src/pending_queue/index.js` — 编排枢纽：意图入口闸门（INV-1/PQ-INV-001）、任务创建+创建即快照（LCD-002/INV-2）、采集编排（IC-M01-03，端口注入）、上传驱动（IC-M01-04）、恢复触发（IC-PQ-002/LCD-005）、StatusView 数据源（IC-M01-05）、command_id 幂等（PQ-IDEM-001）、单任务租约（PQ-INV-003）。
- `plugin/src/pending_queue/task-machine.js` — 状态机迁移表与非法迁移拒绝（created→collecting→queued→uploading→completed/failed_retryable/failed_terminal，外加 confirm_required 保留态）。
- `plugin/src/pending_queue/state-store.js` — ST-PQ-05 envelope：JSON 文件、revision 单调、sha256 checksum、tmp+rename 原子写；损坏拒绝加载不覆盖最近有效状态（PQ-INV-004，LCD-004 implementation_detail）。
- `plugin/src/pending_queue/recovery.js` — 指数退避与可选定时器，注入时钟/调度器（LCD-PQ-004 下沉）。
- `plugin/test/pending-queue.test.js` — 10 个测试，端口全部注入 stub/spy。

## 验证命令与结果（worktree `plugin/` 目录）

- `node --test test/pending-queue.test.js` → **pass 10 / fail 0**（尾部：`ℹ pass 10`、`ℹ fail 0`）
- `npm test` → **pass 53 / fail 0**（既有 43 测试无回归）
- `node --check` 对全部 5 个新增 .js → 全部 OK

checklist 语义断言映射：意图缺项零端口调用（测试 2/3）；断网保留+重启扫描恢复+重传不重采+uuid 不变（测试 4，采集 spy 重启后 0 次调用）；HostUnsupportedError 显式失败含 "unsupported"（测试 5，bundle_ref=null、missing_items 不含 dialogue、upload 未调用）；非法迁移拒绝+failed_terminal 不可恢复（测试 6）；StatusView 形状（测试 10）；另有 confirm_required 不伪造结论（测试 7）、command_id 幂等（测试 8）、材料采集失败可观测（测试 9）。

## 契约影响

无。未修改 contracts/、`ports/index.js`、其他叶子目录或 package.json；仅经冻结端口注入消费 L04（readConfig）/L06（collectMaterials 形状）/L07（collectDialogue + HostUnsupportedError instanceof 只读引用）/L10（upload job/outcome 形状）。零运行时依赖，未 npm install。

## 风险 / 说明

1. **confirm_required 状态**：叶任务状态机主线未列出，但 L1 03/04 明确要求 30s unknown 期间保持 confirm_required 且不伪造结论；作为 uploading 的附加保留态实现（迁移表显式固定），集成时如与其他 Wave-2 叶子的状态枚举口径不一致需在集成层对齐。
2. **TD-01 阻塞保留**：HostUnsupportedError → failed_retryable + 可观测原因；每次启动扫描会重试采集（尚无快照，不违反 INV-4），TD-01 确认后由 L07 真实适配器自动解除。
3. 上传端口抛异常按 `interrupted` 归一（网络中断语义）；upload 端口真实形状以 L10 交付为准，集成时核对 outcome.status 枚举（confirmed/rejected/interrupted/unknown）。
4. 清理协调（IC-PQ-004/006~009，received/rejected 后的本地 artifact 清理）未在本叶范围（任务包交付物 1–5 未含 CLEANUP 子节点）；终态记录保留在队列中，留待后续波次或集成回填决定。
5. 损坏存储拒绝加载并抛 STATE_CORRUPT（保护最近有效状态）；迁移/修复策略按 LCD-PQ-005 属下一层。

## 范围自检

`git diff --name-only main...HEAD`：

```
plugin/src/pending_queue/index.js
plugin/src/pending_queue/recovery.js
plugin/src/pending_queue/state-store.js
plugin/src/pending_queue/task-machine.js
plugin/test/pending-queue.test.js
```

全部位于 `plugin/src/pending_queue/**` 与 `plugin/test/pending-queue.test.js`，无越界改动。
