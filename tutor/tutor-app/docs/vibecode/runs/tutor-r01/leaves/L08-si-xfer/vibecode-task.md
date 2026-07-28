# VibeCode Task — L08 SI-XFER（W2）

- run：tutor-r01；leaf：L08；波次：W2；分支：`tutor-r01/L08-si-xfer`
- 模块：MOD-02 submission-intake / SI-XFER 分片上传会话（DU-2）。

## 目标

实现 CT-001 分片协议承载：上传会话、分片追加、断点续传、合并完成、中止（KD-005），500MB 与类型白名单预检（KD-004）。

## 交付物

1. UploadSession 持久化（ST-02）：会话/分片清单/续传进度；状态 interrupted_retryable / failed_terminal 等（MOD-02 03-state-and-data）；会话 TTL 与归档（LCD-006 implementation_detail）。
2. IC-SI-01 上传会话命令/查询端口实现（建会话/追分片/合并/中止；供 L09 SI-API 消费）。
3. 分片完整性：只确认已落盘分片（INV-5 同类语义）；重复分片幂等；乱序容忍；合并时校验总大小 ≤500MB 与类别白名单（材料类别枚举对齐 contracts/ct-001.json）。
4. 迁移：`server/migrations/versions/0005_upload_sessions.py`（`down_revision="9c99fa53f9f8"`，多头由协调者集成时合并）。
5. 测试：`server/tests/test_l08_si_xfer.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-02/L2-mod-02-si-xfer/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-02/architecture/`（03-state-and-data.md 的 ST-02、04-contracts-and-runtime.md 的 IC-SI-01、05-local-decisions.md 的 LCD-006）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-001 分片协议、KD-004/005）
- 验收：根 PRD AC-REQ-001-01 exceptions（断点续传）、AC-REQ-003-01（upload_failed 标记）
- 仓库：`contracts/ct-001.json`、`internal-contracts.json`；`server/course_app/db.py`；材料写入端口以抽象注入（SI-STORE 归 backfill，本叶子只写会话与暂存元数据）

## 关键语义

- checkpoint 只记已确认分片；合并前不产生材料正式引用；中断可恢复。
- 超限/白名单外 → 明确错误（映射 PAYLOAD_TOO_LARGE / UNSUPPORTED_MEDIA_TYPE 语义，HTTP 映射归 L09）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
