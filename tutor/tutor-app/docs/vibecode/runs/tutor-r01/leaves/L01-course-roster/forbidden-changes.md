# Forbidden Changes — L01

- 修改 `contracts/`（含 ct-003/ct-013/flow-011）任一内容；契约如需变更 → 停止并写 contract-change-request。
- 修改 `shared/`、`server/course_app/`（含 main.py、db.py、settings.py、health.py、contracts_registry.py）。
- 修改 `server/migrations/` 既有文件（alembic.ini、env.py、0001_baseline.py）；不得改 `down_revision` 链上他人文件。
- 修改兄弟模块目录（submission_intake、teacher_web）与 plugin/worker/deploy。
- 给 CT-003 增加字段（如 submission_id，MOD-03 LCD-003 明确拒绝）；引入名单缓存；发布/订阅事件。
- 实现归属校验之外的任何提交/评分/教师端逻辑。
- 无法在允许范围内解决的问题：停止，写 contract-change-request 或阻塞说明到完成包，**不得跨边界自行修复**。
