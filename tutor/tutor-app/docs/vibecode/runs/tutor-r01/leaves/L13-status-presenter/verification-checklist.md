# Verification Checklist — L13

## 命令（worktree 的 plugin/ 目录下）

- [ ] `node --test test/status-presenter.test.js` 全绿
- [ ] `npm test` 全绿（既有测试不得回归）
- [ ] `node --check` 全部新增/改动 .js

## 语义断言（测试必须覆盖）

- [ ] received → 展示提交编号 + received_at + missing_items（中文类别名）
- [ ] upload_failed / rejected / scoring_failed → 展示真实失败原因，不显示任何等级
- [ ] 配置不完整 → 列出缺失字段清单（AC-REQ-002-01 展示面）
- [ ] 断网待上传 → 明确的本地保留与恢复提示
- [ ] 输出不含内部错误码原文；不含令牌/secret；输入 StatusView 形状与 ports/index.js 一致
