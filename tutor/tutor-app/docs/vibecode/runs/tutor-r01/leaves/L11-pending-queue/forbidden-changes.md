# Forbidden Changes — L11

- 修改 `plugin/` 内其他目录与 package.json；修改 contracts/、server/、worker/、shared/、deploy/、docs/。
- 实现 L04/L05/L06/L07/L10/L13 的内部逻辑（只经冻结端口注入消费）。
- 伪造对话导出物；把 HostUnsupportedError 静默转为「对话缺失」；引入 npm 依赖。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
