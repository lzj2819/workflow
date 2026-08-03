# VibeCode Task — L10 CMP-UPLOAD-CLIENT（W2）

- run：tutor-r01；leaf：L10；波次：W2；分支：`tutor-r01/L10-upload-client`
- 模块：MOD-01 codex-plugin / CMP-UPLOAD-CLIENT 上传客户端（DU-1，Node ESM 零依赖）。

## 目标

实现 CT-001/CT-002 consumer：分片上传、断点续传、checkpoint 对账、令牌缓存（KD-005、LCD-006）。

## 交付物

1. 上传执行端口（IC-M01-04）：createUpload(submission_uuid, payload) → 建会话/逐分片/合并；状态查询（CT-002 结果未知时）；断点续传（ST-05 UploadCheckpoint：只记已确认分片，INV-5）。
2. 幂等：submission_uuid 全程作为幂等键；重试不产生重复提交；30 秒未确认 → CT-002 查询真实状态（不重复上传）。
3. 令牌缓存（LCD-006，implementation_detail）：auth/token 换领与内存缓存，过期重领；令牌不得写日志。
4. **类别映射**：内部类别 id（dialogue/code/screenshot/result，与 L06 一致）→ CT-001 中文类别（对话/代码/截图/结果）的**叶子内常量映射表**。注意：这是内部映射，不改任何共享契约；若实现中发现需要改变线上 schema 或类别集合 → **立即停止并提交 contract-change-request**（用户指令）。
5. 网络层注入：fetch/transport 以依赖注入（测试用 stub），本叶子不发真实网络请求；错误分类（网络中断→保留待上传；30s 超时→CT-002；4xx/5xx→按错误码呈现）。
6. 测试：`plugin/test/upload-client.test.js`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-upload-client/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（03-state-and-data.md 的 ST-05/INV-5、04-contracts-and-runtime.md 的 IC-M01-04、05-local-decisions.md 的 LCD-006）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-001/CT-002、KD-005）
- 验收：根 PRD AC-REQ-001-01 及 exceptions；NFR-003
- 仓库：`contracts/ct-001.json`、`ct-002.json`、`auth-token.json`、`plugin/src/ports/index.js`、L06 的 `plugin/src/material_collector/index.js`（类别 id 来源，只读）

## 关键语义

- checkpoint 只记已确认分片；服务端为权威（客户端预检不改变服务端校验结果）。
- 不实现：意图（L05）、采集（L06/L07）、配置（L04）、队列编排（L11）、展示（L13）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
