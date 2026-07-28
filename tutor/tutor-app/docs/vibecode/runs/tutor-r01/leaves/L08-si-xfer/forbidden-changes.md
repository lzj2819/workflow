# Forbidden Changes — L08

- 修改 `contracts/`、`shared/`、`server/course_app/`（xfer 之外）、既有迁移文件、兄弟目录。
- 实现 SI-API（HTTP 端点/认证）、SI-CORE（提交聚合）、SI-STORE（正式材料写入，抽象注入即可）、SI-RELAY/SI-PURGE。
- 改变 CT-001 冻结语义（幂等键、类别枚举、500MB/白名单）。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
