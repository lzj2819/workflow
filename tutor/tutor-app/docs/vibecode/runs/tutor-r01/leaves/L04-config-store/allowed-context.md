# Allowed Context — L04 CONFIG-STORE

## 可写路径（仅这些）

- `plugin/src/config_store/**`
- `plugin/test/config-store.test.js`

## 只读输入

- `plugin/src/config/**`、`plugin/src/ports/**`、`plugin/src/host/**`、`plugin/package.json`
- `contracts/**`、`server/**`、`worker/**`、`shared/**`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- Node 24；零运行时依赖；**禁止 npm install / pip install**。
- 测试运行目录：`plugin/`（worktree 内）。
