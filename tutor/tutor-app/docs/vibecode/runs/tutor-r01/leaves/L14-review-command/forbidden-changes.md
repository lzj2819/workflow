# Forbidden Changes — L14

- 修改 `contracts/`、`shared/`、`server/course_app/`（review_command 之外）、既有迁移、兄弟目录、W1/W2 已有实现。
- 把 adjustment_reason 改为必填（规则变更 → 停止 + contract-change-request）。
- 伪造等级或绕过 NO_ORIGINAL_GRADE；实现 ACCESS-GATE/PROJECTOR/RETENTION（backfill）。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
