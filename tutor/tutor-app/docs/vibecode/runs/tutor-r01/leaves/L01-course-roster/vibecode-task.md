# VibeCode Task — L01 MOD-03 course-roster（W1）

- run：tutor-r01；leaf：L01；波次：W1；分支：`tutor-r01/L01-course-roster`
- 模块：MOD-03 course-roster（L1 终端叶子，DU-2）。内部组件：CMP-MEMBERSHIP-VERIFIER、CMP-COURSE-ROSTER-ADMIN。

## 目标

实现课程/邀请码/名单聚合与每次提交的归属校验（REQ-005/006），不含任何兄弟模块逻辑。

## 交付物

1. Course 聚合持久化（PostgreSQL 目标、单测用 SQLite）：课程、邀请码（唯一，P1）、名单条目（姓名+小组，去重键 course_id+姓名+小组）、课程结束时间。
2. CMP-MEMBERSHIP-VERIFIER：CT-003 校验逻辑——每次调用直读当前名单（P3 禁缓存）、逐条写 VerificationRecord（P4，append-only）、拒绝原因至少区分「邀请码无效 / 名单未命中」（P5）、名单不可用映射 ROSTER_UNAVAILABLE。
3. CMP-COURSE-ROSTER-ADMIN：CT-013 名单导入（逐项错误报告 + conflicts[]、部分成功可见、幂等去重）；课程/邀请码运维预置工具（LCD-004，CLI 入口）。
4. 内部端口：CP-ROSTER-QUERY（ADMIN→VERIFIER 只读）、CP-COURSE-ENDTIME（供 MOD-05 FLOW-011 只读引用）。
5. FastAPI `APIRouter`（不挂载）：`POST /api/v1/courses/verify-membership`、`POST /api/v1/courses/{course_id}/roster`，应答字段与 contracts/ct-003.json、ct-013.json 一致。
6. 迁移：`server/migrations/versions/0002_course_roster.py`（`down_revision="0001_baseline"`；多头由协调者集成时合并）。
7. 测试：`server/tests/test_l01_course_roster.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L1/L1-mod-03/`（prd.md、architecture/01~06、child-handoff.md）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-003、CT-013）、`02-runtime-architecture.md`（FLOW-003、FLOW-011）、`03-data-and-consistency.md`（Course 行）
- 验收：根 PRD AC-REQ-003-01（shared slice）、AC-REQ-006-01（每次重新校验、独立校验记录、名单不可用 → identity_validation_failed 由调用方决定）
- 仓库：`contracts/ct-003.json`、`ct-013.json`、`flow-011.json`、`internal-contracts.json`（CP-*）；`server/course_app/db.py`（事务边界）、`shared/tutor_shared/`

## 关键语义（不得违背）

- 每次校验必须重新执行，禁止任何形式的通过结论缓存（REQ-006 / LCD-002）。
- 校验记录与校验结论同一事务；记录不携带 submission_id（LCD-003）。
- 不消费/不发布任何事件；不建独立服务；FLOW-011 不升级为网络契约（LCD 禁止项）。
- 「课程已结束的提交是否拒绝」**不实现**（findings R-02，父层未定义）。

## 完成包（写入主仓任务包目录 completion-report.md）

提交 SHA、改动文件清单、验证命令与原始输出尾部、契约影响（预期：无）、风险/阻塞、范围自检（git diff --name-only main...HEAD 与允许路径比对）。
