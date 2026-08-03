# Forbidden Changes — L10

- 修改 `plugin/` 内其他目录（含 material_collector 的类别定义）与 package.json。
- 修改 contracts/、server/、worker/、shared/、deploy/、docs/。
- 引入 npm 依赖；发真实网络请求；令牌写日志或明文持久化。
- 改变 CT-001/CT-002 线上 schema 或类别集合（需要时停止 + contract-change-request）。
- 实现其他叶子职责；跨边界自行修复。
