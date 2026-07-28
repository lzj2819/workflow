# T-B01d 完成记录 — CT-001 真实 multipart 接入

- 任务：T-B01d（Phase 5 / B-01，依赖 T-B01a 已在 main）
- 分支/SHA：`tutor-r01/B01d-multipart` @ `93d5a78`（基线 main `604d365`，merge 为 fast-forward，无冲突）
- 状态：done（无 CCR）

## 协议事实来源核对（无契约冲突）

`plugin/src/upload_client/session-driver.js` 实际协议：单端点
`POST /api/v1/submissions`，以 `phase` 字段区分子协议步骤
（`create_session` / `chunk` / `merge`）+ `GET /api/v1/submissions/{uuid}`（CT-002）。
与冻结 CT-001（单端点 + endpoint 注记「先创建上传会话，逐分片上传，最后提交合并」+
versioning 注记「分片协议字段向后兼容追加」）一致，**非分端点协议，无需 CCR、未新增端点**。
应答形状：create_session → `{upload_session_id}`；chunk → `{acked: true, chunk_index}`；
merge → CT-001 received/rejected schema（服务端实现已对齐，插件测试 85/85 通过）。

## 改动（仅允许路径）

- 新增 `server/course_app/submission_intake/api/multipart.py`（约 480 行）：
  - `create_multipart_router(...)`：注入 session_factory / L08 UploadTransferService /
    L09 IntakeOrchestrator；Bearer 认证复用 L09 TokenService。
  - multipart/form-data 解析（stdlib only，不引入 python-multipart 等新依赖；
    requirements.txt 未改）：`metadata` JSON part + 二进制分片 parts；
    流式读取（request.stream 累积 + Content-Length 预检），单次请求 500MB 守卫 → 413。
  - 分片协议三阶段：create_session（submission_uuid 幂等建会话、登记身份与分片元数据）、
    chunk（直传字节 append_chunk；JSON 通道 content/content_ref 字面编码兼容）、
    merge（分片齐套校验 → 既有编排：IC-SI-01 适配器幂等短路 + 实时归属校验 + IC-SI-04）。
  - 单次 multipart 上传（无 phase）：建会话→逐分片→编排确认；已 merged 会话跳过 append，
    幂等重放安全。
  - 无 phase JSON 请求委托既有 L09 行为（复用 router.py 的 SubmissionRequest/应答整形），
    JSON/content_ref 通道不回归。
  - 错误映射与 L09 错误码表一致：413 PAYLOAD_TOO_LARGE（请求守卫与会话累计超限）、
    415 UNSUPPORTED_MEDIA_TYPE（类别/类型白名单，KD-004）、401 AUTH_INVALID、
    400 VALIDATION_FAILED（缺 metadata/未知 phase/分片未齐 merge/会话协议错误）、
    存储暂态 → 503 无公共码。未改 L09 router.py/orchestrator.py，未改契约文件。
- 新增 `server/tests/test_b01d_multipart.py`（13 用例）：TestClient + 真实 L08 +
  SI-STORE 内存 fake + 真实 L02/L01；multipart router 先挂载 + L09 router
  （auth/token、CT-002）的自装配（正式挂载归 T-B03d）。

## 验证（worktree 根，全绿）

- `python -m unittest discover -s server/tests -p "test_b01d_*.py" -v`：13/13 OK。
- `python -m unittest discover -s server/tests`：237 个测试，6 失败 ——
  全部为 main 基线既有失败（test_b01b_relay：基线 224 测试同样 6 失败，见风险 1），
  本任务 0 回归。
- worker：45/45 OK；plugin：85 pass / 0 fail。
- `ruff check` 两改动文件：All checks passed；`py_compile` 通过。
- 单测 SQLite + StaticPool；无新迁移（alembic 无需执行）。

## 契约影响

无。未新增端点、未改 schema；phase 字段属冻结 versioning 注记的向后兼容追加范围。
应答字段与 ct-001/ct-002/auth-token 冻结 schema 一致（测试断言 additionalProperties 封闭集）。

## 风险

1. **main 基线既有失败（非本任务引入，超出允许路径未修）**：`test_b01b_relay` 6 个用例
   在 main `604d365` 上即失败（retry/backoff/confirm 相关断言为 0），建议协调者回退
   T-B01b 负责人核查。
2. 分片会话身份（invite_code/姓名/小组/作业）按 upload_session_id 进程内登记：
   进程重启后 merge 应答 400，客户端清本地 checkpoint 重发 create_session 可幂等恢复
   （L08 会话与已确认分片在库，重放 duplicate 去重）。持久化身份表需新迁移，超出本
   任务允许路径；建议 T-B03d 组合根或后续 backfill 评估。
3. session-driver 对 `media_type` 为透传（`?? null`），L08 白名单按 CT-001
   file_type_whitelist 标签校验；若上游（L06/L07 采集器）最终传 MIME 字符串将被 415
   拒绝。插件测试夹具用 MIME 值，实际取值归 T-B04 组装时确认，建议联调时核对。
4. 组合提示（T-B03d）：Starlette 路由按注册序匹配，multipart router 须先于（或替代）
   L09 router 挂载 `POST /api/v1/submissions`；无 phase JSON 请求由 multipart router
   内部委托既有 L09 行为，语义一致（测试已验证两 router 共存装配）。
