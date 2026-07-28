# Allowed Context — L10 UPLOAD-CLIENT

## 可写路径（仅这些）

- `plugin/src/upload_client/**`
- `plugin/test/upload-client.test.js`

## 只读输入

- `plugin/`（其余全部）、`contracts/`、`server/`、`worker/`、`shared/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- Node 24；零运行时依赖；**禁止 npm install**；不发真实网络请求（transport 注入）。
- 测试运行目录：`plugin/`（worktree 内）。
