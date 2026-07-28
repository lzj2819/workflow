# Allowed Context — L06 MATERIAL-COLLECTOR

## 可写路径（仅这些）

- `plugin/src/material_collector/**`
- `plugin/test/material-collector.test.js`

## 只读输入

- `plugin/`（其余全部）、`contracts/`、`server/`、`worker/`、`shared/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- Node 24；零运行时依赖（sha256 用 node:crypto）；**禁止 npm install**。
- 测试运行目录：`plugin/`（worktree 内）。
