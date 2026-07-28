# Forbidden Changes — L04

- 修改 `plugin/src/config/plugin-config.js`（复用，需变更 → 记入完成包）；修改 ports/host 与 package.json。
- 修改 contracts/、server/、worker/、shared/、deploy/、docs/ 及其他叶子目录。
- 引入 npm 依赖（保持零依赖基线）；实现其他叶子职责。
- 跨边界自行修复问题：停止 + contract-change-request 或阻塞说明。
