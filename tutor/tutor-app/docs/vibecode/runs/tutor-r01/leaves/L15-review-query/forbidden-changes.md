# Forbidden Changes — L15

- 修改 `contracts/`、`shared/`、`server/course_app/`（review_query 之外）、迁移目录、兄弟目录、W1/W2 已有实现。
- 自建读模型表或投影逻辑（PROJECTOR 职责，backfill）；做跨模块同步读。
- 伪造等级或隐藏失败原因；实现 ACCESS-GATE（注入调用即可）。
- 跨边界自行修复：停止 + contract-change-request 或阻塞说明。
