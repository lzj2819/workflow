/**
 * UNIT-INTENT-PARSER-NORMALIZER 的规范化规则（IC-IP-03）。
 *
 * 只做无损清理：去除外围空白、折叠连续空白为单个空格。
 * 不补齐必填字段、不猜测值、不改写语义（INV-IP-03）。
 * 幂等：normalizeValue(normalizeValue(x)) === normalizeValue(x)。
 */

/**
 * @param {string} raw 提取器给出的原始捕获值
 * @returns {string} 规范化后的值；空白-only 输入归一为空字符串（EMPTY_FIELD）
 */
export function normalizeValue(raw) {
  return String(raw).replace(/\s+/g, " ").trim();
}
