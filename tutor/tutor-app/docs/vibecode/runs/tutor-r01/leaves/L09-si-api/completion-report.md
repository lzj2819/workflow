# Completion Report — L09 SI-API（tutor-r01，W2）

- leaf：L09 SI-API（MOD-02 接入层）
- 分支：`tutor-r01/L09-si-api`（worktree `.worktrees/L09-si-api`，基线 main a4d373f）
- 提交 SHA：**1e715be2fc29592f9fac0eb65db732b276551d61**
- 状态：done

## 改动清单（9 文件，全部在允许路径内）

| 文件 | 内容 |
|---|---|
| `server/course_app/submission_intake/api/__init__.py` | 包公共入口导出（`create_router` 等） |
| `.../api/errors.py` | 冻结错误码与 HTTP 映射表（AUTH_INVALID→401、VALIDATION_FAILED→400、NOT_FOUND→404、PAYLOAD_TOO_LARGE→413、UNSUPPORTED_MEDIA_TYPE→415；REJECTED_MEMBERSHIP 业务终态无 HTTP 映射） |
| `.../api/models.py` | ST-06 AuthTokenGrant 模型（自有 Base；只存 token 哈希 + 主体指纹） |
| `.../api/ports.py` | IC-SI-03 名单核对端口与 IC-SI-01 上传会话冻结端口 Protocol（L08 stub 注入面） |
| `.../api/tokens.py` | SI-API-AUTH：不透明令牌签发/认证（secrets.token_urlsafe，服务端存 sha256，TTL 30 天 = 2592000s，DD-004），ST-06 签发/拒绝审计 |
| `.../api/orchestrator.py` | 30 秒同步编排（NFR-003）：幂等预查 → IC-SI-01 材料接收 → IC-SI-03 实时归属校验（有限快速重试，LCD-001）→ IC-SI-04 ConfirmReceived/MarkRejected/MarkUploadFailed |
| `.../api/router.py` | APIRouter（不挂载）：POST /api/v1/auth/token、POST /api/v1/submissions、GET /api/v1/submissions/{uuid}；Bearer 认证依赖；契约字段严格映射 |
| `server/migrations/versions/0006_auth_tokens.py` | ST-06 建表迁移；revision=`0006_auth_tokens`，down_revision=`9c99fa53f9f8` |
| `server/tests/test_l09_si_api.py` | 18 项测试（TestClient + SQLite；L01 verifier / L02 SubmissionCoreService 进程内注入，IC-SI-01 冻结端口 stub） |

## 验证命令与结果（worktree 根执行）

- `python -m unittest discover -s server/tests -p "test_l09_*.py" -v` → **Ran 18 tests … OK**
- `python -m unittest discover -s server/tests` → **Ran 94 tests … OK**（既有 76 项零回归 + 新增 18）
- `ruff check server/course_app/submission_intake/api server/tests/test_l09_si_api.py server/migrations/versions/0006_auth_tokens.py` → **All checks passed!**
- `python -m py_compile`（全部 9 个新增/改动 .py）→ **PY_COMPILE_OK**
- 迁移可导入、revision/down_revision 正确 → 由 `test_migration_importable_with_correct_revisions` 覆盖（通过）

语义断言覆盖：auth/token 200/401 + 审计不含明文；CT-001 received（30s 内）/400/401；rejected 业务终态（HTTP 200）；submission_uuid 幂等（同一 submission_id、无重复记录/事件、不重复合并）；CT-002 已知/未知 uuid（404）；413/415 映射；名单不可用 503 且不建提交（LCD-001）；应答字段与 contracts/ct-001.json、ct-002.json、auth-token.json 逐项一致（required ⊆ keys 且 additionalProperties=false 时无多余键）。

## 契约影响

无。CT-001/CT-002/auth-token 字段、错误码、幂等与版本均未改动；ST-06 为父包已登记的 API 自有状态；未新增公共契约。

## 实现注记（不越界的局部决定）

1. **expected_categories 基线**：ConfirmReceived 的 expected_categories 取材料类别全集（CT-004 冻结枚举 对话/代码/截图/结果），与 L02 测试口径一致；客户端声明类别仅传给 IC-SI-01 会话。missing_items 由 SI-CORE 完整性报告计算（缺失显式标记、不阻断 received）。
2. **暂态失败映射**：名单不可用（ROSTER_UNAVAILABLE 有限重试耗尽）与上传终态失败映射为 503/500 暂态应答，**不携带新公共错误码**（应答体仅 `detail`），不暴露内部细节、不伪造 received；客户端按 CT-001 既有约定以同一幂等键重发或经 CT-002 查询（LCD-001 选项 C 的同步应答形态）。
3. **重复换领令牌**：每次签发新不透明令牌并独立审计（满足「重复换领返回有效令牌」）。
4. **挂载/平台面**：路由不挂载；uvicorn 目标、/metrics 接入、挂载点归 backfill/平台（同 L01 口径）。

## 风险/阻塞

- 无阻塞。
- 残余风险（低）：IC-SI-01 为消费方定义的冻结端口面（ingest 单请求编排形态），与 L08 真实实现的接线归集成；若 L08 端口形态不同，由集成方适配（本叶子测试全部经 stub 注入，无跨叶子真实接线）。

## 范围自检

`git diff --name-only main...HEAD` 输出 9 个文件，全部位于允许路径
（`server/course_app/submission_intake/api/**`、`server/migrations/versions/0006_auth_tokens.py`、`server/tests/test_l09_si_api.py`）；未触碰 contracts/、shared/、L01/L02/L08、既有迁移与兄弟目录。
