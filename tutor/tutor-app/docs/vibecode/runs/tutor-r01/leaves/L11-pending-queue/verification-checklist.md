# Verification Checklist — L11

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/pending-queue.test.js` 全绿
- [ ] `npm test` 全绿（既有测试不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] 意图完整 → 建任务（uuid 生成一次后不变）→ 快照（创建即快照）→ 编排采集 → 交上传端口；意图缺项 → 不建任务、零网络调用（spy 断言）
- [ ] 断网/上传失败 → 任务保留 failed_retryable + 失败原因；重启扫描后可恢复（LCD-005 触发，注入时钟）
- [ ] 重传不重采：恢复任务复用原采集快照（采集端口 spy 只被调一次）
- [ ] 对话端口抛 HostUnsupportedError → 任务显式失败且原因含 unsupported（不静默、不伪造）
- [ ] 状态机非法迁移拒绝；failed_terminal 不可恢复
- [ ] IC-M01-05 输出 StatusView 形状与 ports/index.js 一致
