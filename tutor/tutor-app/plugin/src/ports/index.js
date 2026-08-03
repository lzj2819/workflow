/**
 * 核心端口类型（IC-M01-01..05，MOD-01 内部契约）。
 *
 * 仅类型形状（JSDoc），不含实现；字段级语义以
 * tutor/L1/L1-mod-01/architecture/04-contracts-and-runtime.md §3 为准。
 * 各端口实现属对应叶子（L04~L07、L10、L11、L13）。
 *
 * IC-M01-01 意图解析端口：INTENT-PARSER → PENDING-QUEUE
 * @typedef {Object} IntentResult
 * @property {boolean} complete        作业/姓名/小组三者齐全（F1-1 闸门；缺任一项不创建提交）
 * @property {string} [assignment]
 * @property {string} [student_name]
 * @property {string} [group_name]
 * @property {string[]} missing        缺失字段名列表
 *
 * IC-M01-03 采集编排端口：PENDING-QUEUE → DIALOGUE/MATERIAL-COLLECTOR
 * @typedef {Object} CollectionBatch
 * @property {string} submission_uuid  全程不变（INV-2）
 * @property {Object} dialogue_ref     对话导出物引用（ST-02，快照重传不重采 INV-4）
 * @property {Object[]} material_refs  MaterialManifest 条目（ST-03）
 * @property {string[]} missing_items  缺失类别（对话/代码/截图/结果）
 *
 * IC-M01-04 上传执行端口：UPLOAD-CLIENT ↔ PENDING-QUEUE
 * @typedef {Object} UploadHandle
 * @property {string} submission_uuid
 * @property {"queued"|"uploading"|"paused"|"completed"|"failed"} state
 * @property {number[]} confirmed_chunks  只记已确认分片（INV-5）
 *
 * IC-M01-05 状态展示端口：PENDING-QUEUE / CONFIG-STORE → STATUS-PRESENTER
 * @typedef {Object} StatusView
 * @property {string} [submission_id]
 * @property {string} status
 * @property {string[]} missing_items
 * @property {string} [failure_reason]   展示真实原因，不伪造结论
 */

export const IC_M01_IDS = Object.freeze([
  "IC-M01-01",
  "IC-M01-02",
  "IC-M01-03",
  "IC-M01-04",
  "IC-M01-05",
]);
