/**
 * CMP-INTENT-PARSER / IC-M01-01 意图解析端口实现（L05）。
 *
 * 内部链路（L2 02/04）：
 *   COMMAND-ADAPTER（本文件）→ FIELD-EXTRACTOR（extract.js）
 *   → NORMALIZER（normalize.js）→ REQUIRED-FIELD-GATE（gate.js）
 *
 * 语义承诺：
 * - 纯函数、零副作用：无网络、无模型调用、无持久化、无任务创建
 *   （INV-1 / INV-IP-02）；同一输入重复调用结果完全一致（INV-IP-04）。
 * - 确定性缺项闸门（L1 LCD-001 / F1-1）：assignment/student_name/group_name
 *   任一缺失或冲突 → complete=false + 具体缺失字段，绝不猜测放行（LCD-IP-002）。
 * - 当次指令优先（R-05 / LCD-IP-003 / INV-IP-03）：配置仅作只读上下文，
 *   绝不用于补齐或覆盖必填槽位。
 *
 * 输出形状对齐 plugin/src/ports/index.js 的 IntentResult typedef：
 * { complete, assignment?, student_name?, group_name?, missing[] }。
 */

import { DEFAULT_RULES, FIELD_IDS } from "./rules.js";
import { extractSlots } from "./extract.js";
import { decide } from "./gate.js";

export { DEFAULT_RULES, FIELD_IDS };

/**
 * 以指定规则表创建一个解析器（提取规则可配置/可替换，闸门语义不变）。
 *
 * @param {Readonly<Object>} [rules] 规则表（形状同 DEFAULT_RULES），缺省用内置表
 * @returns {{parseSubmissionIntent: (text: unknown, options?: Object) => Object}}
 */
export function createIntentParser(rules = DEFAULT_RULES) {
  const effectiveRules = rules ?? DEFAULT_RULES;

  /**
   * 解析学生的自然语言提交指令（IC-M01-01 入参 command_text）。
   *
   * @param {unknown} text 指令文本；非字符串或空白 → 三项全缺（EMPTY_COMMAND）
   * @param {Object} [options] 只读上下文
   * @param {Object} [options.config] EffectiveConfig 快照（IC-M01-02 只读）。
   *   仅作诊断上下文；绝不参与必填字段取值（R-05：指令与配置不一致时以当次指令为准）。
   * @param {string} [options.config_version] 配置版本（诊断用，可选）。
   * @returns {{complete: boolean, assignment?: string, student_name?: string,
   *   group_name?: string, missing: string[]}} IntentResult
   */
  function parseSubmissionIntent(text, options = {}) {
    void options; // 配置只读上下文不改变本端口的输入 schema，也不补齐缺项

    if (typeof text !== "string" || text.trim() === "") {
      // EMPTY_COMMAND：不进入提取器，直接失败闭合（IC-IP-01）
      return { complete: false, missing: [...FIELD_IDS] };
    }

    const slots = extractSlots(text, effectiveRules);
    return decide(slots);
  }

  return Object.freeze({ parseSubmissionIntent, rules: effectiveRules });
}

const defaultParser = createIntentParser();

/**
 * 使用内置规则表解析提交指令（签名与语义同 createIntentParser().parseSubmissionIntent）。
 *
 * @param {unknown} text
 * @param {Object} [options]
 * @returns {{complete: boolean, assignment?: string, student_name?: string,
 *   group_name?: string, missing: string[]}}
 */
export function parseSubmissionIntent(text, options = {}) {
  return defaultParser.parseSubmissionIntent(text, options);
}
