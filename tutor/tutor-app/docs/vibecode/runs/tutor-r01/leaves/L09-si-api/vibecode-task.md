# VibeCode Task — L09 SI-API（W2）

- run：tutor-r01；leaf：L09；波次：W2；分支：`tutor-r01/L09-si-api`
- 模块：MOD-02 submission-intake / SI-API 接入层（DU-2）。

## 目标

实现 CT-001/CT-002 与 `POST /api/v1/auth/token` 端点、学生令牌认证、幂等接入与 30 秒编排（KD-005、NFR-003）。

## 交付物

1. FastAPI `APIRouter`（不挂载，挂载归 backfill/平台）：
   - `POST /api/v1/auth/token`：邀请码+姓名+小组 → 名单核对（语义同 CT-003，经 IC-SI-03 注入）→ 不透明令牌签发（服务端存哈希；ST-06 AuthTokenGrant 审计；TTL 30 天，DD-004）。
   - `POST /api/v1/submissions`：Bearer 认证 → 幂等（submission_uuid）→ 归属校验（IC-SI-03）→ 分片会话与材料接收（IC-SI-01，注入 L08 端口或 stub）→ 聚合确认（IC-SI-04，注入 L02 实现或 stub）→ 30 秒内应答 received + missing_items；拒绝路径 rejected + rejection_reason。
   - `GET /api/v1/submissions/{submission_uuid}`：状态查询（CT-002 字段；404 未知 UUID）。
2. 认证/幂等中间件或依赖注入件：AUTH_INVALID 映射；错误码映射表（contracts/ct-001.json、ct-002.json、auth-token.json 的 error_codes）。
3. 迁移：`server/migrations/versions/0006_auth_tokens.py`（ST-06；`down_revision="9c99fa53f9f8"`，多头由协调者合并）。
4. 测试：`server/tests/test_l09_si_api.py`（用 fastapi TestClient；CT-003 注入可用 L01 的 `course_roster.verifier.verify_membership` 进程内调用，DD-004）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-02/L2-mod-02-si-api/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-02/architecture/`（04-contracts-and-runtime.md 的 IC-SI-01/03/04 与错误码映射、05-local-decisions.md 的 LCD-001/004）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-001/CT-002/auth-token、错误码汇总）
- 验收：根 PRD AC-REQ-001-01、AC-REQ-003-01、AC-REQ-007-01；NFR-002/003
- 仓库：`contracts/ct-001.json`、`ct-002.json`、`ct-003.json`、`auth-token.json`；L01/L02/L08 实现（main 上 L01/L02 已在，L08 同波次——按冻结端口注入，不做跨叶子真实接线，集成时由协调者完成）

## 关键语义

- 30 秒接收确认目标：同步路径只做校验+持久化+应答；评分触发经事件（不阻塞应答）。
- 令牌不得明文入库/入日志；REJECTED_MEMBERSHIP 为业务终态（status=rejected，非 HTTP 错误）。
- 教师端端点（CT-007 等）与本叶子无关。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
