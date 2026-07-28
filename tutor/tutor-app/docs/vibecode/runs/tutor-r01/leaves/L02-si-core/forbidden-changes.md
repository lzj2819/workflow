# Forbidden Changes — L02

- 修改 `contracts/`、`shared/`、`server/course_app/`；修改兄弟目录（api/xfer/course_roster/teacher_web/plugin/worker/deploy）。
- 修改 `server/migrations/` 既有文件。
- 实现 SI-XFER（分片会话）、SI-API（HTTP 端点）、SI-STORE（磁盘写入）、SI-VERIFY（CT-003 客户端）、SI-RELAY（投递器）、SI-PURGE（清除执行）——这些属其他叶子或 backfill。
- 改变 Submission 状态机外部值域或终态语义；绕过幂等键；让 Outbox 行与业务写入分事务。
- 跨边界自行修复问题：无法解决 → 停止 + contract-change-request 或阻塞说明。
