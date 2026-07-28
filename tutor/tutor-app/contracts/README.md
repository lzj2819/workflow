# contracts/ — tutor-r01 冻结契约（机器可读）

**维护者：仅 Integration Owner。** 叶子只读；任何变更走 `contract-change-request.md` 流程。

- 语义权威来源：`tutor/L0-root/architecture/04-interface-contracts.md`（SHA-256 `4599918536e46ca90f566919dc3e1e9f42c59d6da034d771ca44a98bae3efb9f`）各契约 `contract_fields` YAML 块；本目录为其逐字段落地，不得反向修改设计语义。
- 冻结状态：正式冻结（matrix gate 2026-07-19 批准）。例外：CCR-001 pending —— 批准前 CT-012/CT-014 不得修改。
- 内部契约（IC-M01/IC-SI/ICT/CP/M05-IC）索引见 `internal-contracts.json`；其字段级语义以各 L1 包 `04-contracts-and-runtime.md` 为准。

## 文件约定

- 每契约一个 JSON 文件：元数据（provider/consumer/端点/幂等/超时重试/版本/错误码/副作用）+ `schemas`（JSON Schema draft 2020-12，内联展开，不用 `$ref`，便于零依赖校验）。
- 事件契约：`schemas.event` 含 `v`（const 1）字段；消费方幂等要求写入 `idempotency`。
- CT-001 的分片协议（建会话/追分片/合并）为传输层细节，由 L08 SI-XFER 详细设计承载；本文件固定逻辑契约（幂等键、类别标注、限制与应答）。
- CT-007 为视图族（课程/小组/学生/提交详情/删除批次），`schemas.response` 为按视图层级取用的出参超集，具体端点拆分由 L15 详细设计承载。
- CT-010 为外部契约（MOD-04 ACL ↔ 模型供应商）；数据最小化：禁发 `submission_id`、学生姓名等业务标识。
- FLOW-011 为 internal_read 描述符，无网络 schema。

## 清单

| 文件 | 契约 | 类型 |
|---|---|---|
| ct-001.json | 提交材料包上传 | api |
| ct-002.json | 提交状态查询 | api (query) |
| ct-003.json | 课程归属校验 | api |
| ct-004.json | SubmissionReceived | event |
| ct-005.json | SubmissionScored / ScoringFailed | event |
| ct-006.json | SubmissionReceived（读模型派生） | event |
| ct-007.json | 教师课程数据查询 | api (query) |
| ct-008.json | 教师批注与最终等级调整 | api |
| ct-009.json | 展示视图生成 | api |
| ct-010.json | 模型评估推理（外部） | external_api |
| ct-011.json | 删除确认 | api |
| ct-012.json | RecordsDeleted | event（CCR-001 pending，冻结不改） |
| ct-013.json | 名单导入 | api |
| ct-014.json | PurgeCompleted | event（CCR-001 关联，冻结不改） |
| auth-token.json | POST /api/v1/auth/token（CT-001 契约族附属） | api |
| flow-011.json | 课程结束时间只读引用 | internal_read |
