/**
 * UNIT-INTENT-PARSER-FIELD-EXTRACTOR 的可配置提取规则表。
 *
 * 依据：L1 LCD-001（提取机制为 implementation_detail，可演进）、
 * L2 LCD-IP-001（可替换提取 + 确定性闸门）、LCD-IP-004（提取策略下沉）。
 *
 * 仅本地关键词/模式匹配：无网络、无模型调用；同一文本重复匹配结果一致
 * （INV-IP-04）。规则的增改只影响候选提取，不改变 IC-M01-01 输出语义。
 *
 * 每条规则：{ id, pattern }，pattern 必须含捕获组 1 = 字段原始值，
 * 并建议带 g 标志（缺省时提取器自动补上，保证 matchAll 可用）。
 */

export const FIELD_IDS = Object.freeze(["assignment", "student_name", "group_name"]);

/**
 * 字段值不允许跨越的边界：从句分隔符与冒号。
 * 排除冒号是为了在缺少分隔符的粘连文本（如「作业： 姓名：张三」）中
 * 不吞掉后续标签，保持 fail-closed 可诊断。
 */
const VALUE = "[^，。；;,：:\\n]";

export const DEFAULT_RULES = Object.freeze({
  assignment: Object.freeze([
    // 「作业：第一次作业」「作业是 实验一」「作业为 习题三」
    { id: "assignment.label.zh", pattern: new RegExp(`作业\\s*[:：是为]\\s*(${VALUE}+)`, "g") },
    // 「提交第一次作业」「提交 实验一 作业」
    { id: "assignment.submit.zh", pattern: new RegExp(`提交\\s*(${VALUE}+?)\\s*作业`, "g") },
    // "assignment: hw-01"
    { id: "assignment.label.en", pattern: /assignment\s*[:：=]\s*([^\s，。；;,]+)/gi },
  ]),
  student_name: Object.freeze([
    // 「姓名：张三」「名字是 李四」
    { id: "name.label.zh", pattern: new RegExp(`(?:姓名|名字)\\s*[:：是为]\\s*(${VALUE}+)`, "g") },
    // 「我叫王五」「我是张三」「名字叫李四」
    { id: "name.self.zh", pattern: new RegExp(`(?:我叫|我是|名字叫)\\s*(${VALUE}+)`, "g") },
    // "name: Tom"
    { id: "name.label.en", pattern: /name\s*[:：=]\s*([^\s，。；;,]+)/gi },
  ]),
  group_name: Object.freeze([
    // 「小组：第 3 组」「组别为 甲组」
    { id: "group.label.zh", pattern: new RegExp(`(?:小组|组别)\\s*[:：是为]\\s*(${VALUE}+)`, "g") },
    // 「第 3 组」「第二组」「第 十二 组」（含全角数字）
    { id: "group.ordinal.zh", pattern: /(第\s*[0-9０-９一二三四五六七八九十百零]+\s*组)/g },
    // "group: 7"
    { id: "group.label.en", pattern: /group\s*[:：=]\s*([^\s，。；;,]+)/gi },
  ]),
});
