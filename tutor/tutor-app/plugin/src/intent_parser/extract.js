/**
 * UNIT-INTENT-PARSER-FIELD-EXTRACTOR（IC-IP-02）：候选字段提取。
 *
 * 纯函数：无副作用、无网络、无模型调用、无跨请求状态（INV-IP-02/04）。
 * 无法确定的候选交由闸门按缺项处理，本单元绝不猜测（LCD-IP-002）。
 */

import { FIELD_IDS } from "./rules.js";
import { normalizeValue } from "./normalize.js";

/**
 * 按规则表从指令文本中提取各字段的候选值。
 *
 * @param {string} text 当前指令文本（非空字符串，由调用方保证）
 * @param {Readonly<Object>} rules 规则表（形状同 DEFAULT_RULES）
 * @returns {Object<string, {values: string[], spans: Array<{rule: string, index: number}>}>}
 *   每个字段给出「去重后的规范化候选值」与「来源片段位置」（可追溯，仅进程内瞬态）。
 */
export function extractSlots(text, rules) {
  const slots = {};
  for (const field of FIELD_IDS) {
    const values = [];
    const spans = [];
    for (const rule of rules[field] ?? []) {
      // 每次调用克隆正则，避免共享 lastIndex 造成跨调用不确定性。
      const flags = rule.pattern.flags.includes("g")
        ? rule.pattern.flags
        : rule.pattern.flags + "g";
      const re = new RegExp(rule.pattern.source, flags);
      for (const match of text.matchAll(re)) {
        const raw = match[1];
        if (typeof raw !== "string") continue;
        const value = normalizeValue(raw);
        if (value === "") continue; // EMPTY_FIELD：空捕获视为未提取
        if (!values.includes(value)) values.push(value);
        spans.push({ rule: rule.id, index: match.index ?? -1 });
      }
    }
    slots[field] = { values, spans };
  }
  return slots;
}
