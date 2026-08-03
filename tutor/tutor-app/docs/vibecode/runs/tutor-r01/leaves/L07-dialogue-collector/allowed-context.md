# Allowed Context — L07

## 可写路径（仅这些）

- `plugin/src/dialogue_collector/**`
- `plugin/test/dialogue-collector.test.js`

## 只读输入

- `plugin/`（其余全部）、`contracts/`、`server/`、`worker/`、`shared/`、`deploy/`、`docs/`
- tutor 设计包（只读）

## 环境

- Node 24；零运行时依赖；**禁止 npm install**。
- 测试运行目录：`plugin/`（worktree 内）。
- 授权纪律：测试只用合成 fixture；禁止读取真实用户会话文件；会话内容禁止写日志。

# Forbidden Changes — L07

- 修改 `plugin/` 内其他目录与 package.json；修改 contracts/、server/、worker/、shared/、deploy/、docs/。
- 读取真实用户会话内容；虚构/篡改对话导出物；静默降级为「对话缺失」。
- 引入 npm 依赖；跨边界自行修复（停止 + contract-change-request 或阻塞说明）。
