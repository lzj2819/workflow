# T-B01d — CT-001 真实 multipart 接入（Phase 5 / B-01）

- worktree：`tutor-app/.worktrees/B01d-multipart`（分支 tutor-r01/B01d-multipart，基线 main 917f8d1）
- 允许路径（仅这些）：
  - `server/course_app/submission_intake/api/multipart.py`（新模块）
  - `server/tests/test_b01d_multipart.py`（及 `server/tests/b01d_*.py` 辅助）

## 目标

在既有 CT-001 端点族上接入真实 multipart/form-data 二进制上传（KD-005 分片断点续传），与 L10 session-driver 的客户端协议对齐；保留既有 JSON/content_ref 通道兼容（测试与本地工具）。

## 交付物

1. 先读取 `plugin/src/upload_client/session-driver.js`，提取客户端实际调用的端点/载荷形状（建会话/追分片/合并/状态查询），以其为协议事实来源；**若其期望与冻结 CT-001（单端点 + 分片协议注记）冲突，停止并在完成记录中给出 contract-change-request 草案**。
2. `multipart.py`：multipart/form-data 解析（元数据 JSON part + 二进制分片 parts；流式读取，单次请求 500MB 上限守卫）；类别校验（对白名单 KD-004）；接入既有 TransferSessionPort/XferTransferAdapter（内容以字节直传，不经 content_ref 占位）。
3. 分片会话协议端点（若 session-driver 为分端点协议）：`POST /api/v1/submissions/upload-sessions`、`POST .../chunks`、`POST .../complete`（形状以 session-driver 为准；鉴权复用 L09 Bearer 依赖）。
4. 测试（TestClient + 真实 L08 + SI-STORE fake/内存）：multipart 二进制上传 → received；分片协议三阶段 → received；断点续传（已确认分片不重传）；超限 413、白名单外 415、未知令牌 401；JSON 兼容通道不回归。

## 禁止

- 改 L09 router.py/orchestrator.py 既有行为（只新增 multipart.py 并在测试中自装配验证；挂载归 T-B03d 组合根）；改契约文件；引入新依赖。

## 验证

- `python -m unittest discover -s server/tests -p "test_b01d_*.py" -v` 全绿
- `python -m unittest discover -s server/tests` 全绿（无回归）
- `ruff check <改动路径>`、`py_compile`

## 完成记录

写 `docs/vibecode/runs/tutor-r01/backfill/T-B01d-completion.md`。
