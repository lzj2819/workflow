# Forbidden Changes — L09

- 修改 `contracts/`、`shared/`、`server/course_app/`（api 之外）、既有迁移、兄弟目录。
- 修改 L01/L02/L08 实现（只能经冻结端口注入使用）；做跨叶子真实接线（归集成）。
- 实现教师端端点、SI-XFER 会话细节（用其端口）、SI-CORE 聚合细节（用其端口）。
- 令牌明文入库或入日志；改变 CT-001/CT-002/auth-token 冻结字段与错误码。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
