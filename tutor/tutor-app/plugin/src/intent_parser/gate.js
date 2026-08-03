/**
 * UNIT-INTENT-PARSER-REQUIRED-FIELD-GATE（IC-IP-04）：必填字段确定性闸门。
 *
 * 唯一放行点（L1 LCD-001 / F1-1 / INV-1）：
 * - 三字段各恰有一个确定值 → SubmissionIntent（complete=true）。
 * - 任一字段缺失（0 个候选）或冲突（>1 个不同候选，CONFLICTING_FIELD）
 *   → MissingFields（complete=false + 具体缺失字段），绝不猜测放行
 *   （LCD-IP-002，fail-closed）。
 *
 * 输出形状对齐 plugin/src/ports/index.js 的 IC-M01-01 IntentResult：
 * { complete, assignment?, student_name?, group_name?, missing[] }。
 * complete=false 时仍附带已确定的字段值供展示层诊断；missing[] 为闸门判定的
 * 唯一权威，消费方（CMP-PENDING-QUEUE）据此不创建任务、不产生网络调用。
 */

import { FIELD_IDS } from "./rules.js";

/**
 * @param {Object<string, {values: string[]}>} slots 规范化后的候选槽位
 * @returns {{complete: boolean, missing: string[]}} IntentResult（互斥语义由 complete 保证）
 */
export function decide(slots) {
  const result = { complete: true, missing: [] };
  for (const field of FIELD_IDS) {
    const values = slots[field]?.values ?? [];
    if (values.length === 1) {
      result[field] = values[0];
    } else {
      // 0 = MISSING_REQUIRED_FIELD；>1 = 冲突，fail-closed 按缺项处理
      result.complete = false;
      result.missing.push(field);
    }
  }
  return result;
}
