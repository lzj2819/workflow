# Forbidden Changes — L03

- 修改 `contracts/`、`shared/`、`server/`（除新迁移文件）、`worker/assessment_worker/`、`plugin/`、`deploy/`。
- 修改 `server/migrations/` 既有文件。
- 实现 CT-010 模型调用、五维评估装配（L12）、提示编排、CT-005 投递器、度量组件（均 backfill 或其他叶子）。
- 实现 CT-012 消费/删除接线（CCR-001 pending，用户明令禁止）。
- 突破 REQ-012「重试一次」；绕过 submission_id 幂等；让任务持久化先于事件确认的语义反转。
- 跨边界自行修复问题：停止 + contract-change-request 或阻塞说明。
