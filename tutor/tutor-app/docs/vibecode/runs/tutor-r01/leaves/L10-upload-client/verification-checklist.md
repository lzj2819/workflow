# Verification Checklist — L10

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/upload-client.test.js` 全绿
- [ ] `npm test` 全绿（既有 43 项不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] 建会话 → 逐分片 → 合并全流程（stub transport 断言请求形状含 submission_uuid/类别中文枚举）
- [ ] 中断后续传：已确认分片不重传（checkpoint 只记已确认），未确认分片重发
- [ ] 同一 submission_uuid 重试 → 服务端返回同一 submission_id（幂等，不产生第二次创建语义）
- [ ] 30 秒未确认 → 自动转 CT-002 查询真实状态（不重复上传）
- [ ] 类别映射表：dialogue/code/screenshot/result → 对话/代码/截图/结果 一一对应
- [ ] 令牌：缓存命中不重复换领；过期/401 后重领一次；令牌不出现在日志/错误消息
- [ ] 网络中断 → 返回可恢复失败（保留待上传语义），不丢 checkpoint
