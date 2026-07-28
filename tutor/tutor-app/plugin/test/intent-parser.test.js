/**
 * L05 CMP-INTENT-PARSER 验证（IC-M01-01 / F1-1 / AC-REQ-001-01 boundaries）。
 *
 * testcases.json（tutor/L2/mod-01/L2-mod-01-cmp-intent-parser）场景覆盖说明：
 * - 正场景（TC-001/TC-003 的本叶子切片：指令 → 身份+作业正确提取）→「完整指令」各用例。
 * - 反场景（TC-004/TC-005：缺任一必填项不产出可提交意图，返回具体缺失字段）
 *   →「缺项闸门」各用例；complete=false 即 INV-1 闸门语义（队列据此不创建任务、
 *   不产生网络调用），「信息不完整」展示标签由 L11/L13 负责。
 * - TC-002（唯一提交编号）归 CMP-PENDING-QUEUE（L11）、TC-006（断网保留）归
 *   CMP-UPLOAD-CLIENT（L10），均非本叶子职责，不在此断言。
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  parseSubmissionIntent,
  createIntentParser,
  DEFAULT_RULES,
  FIELD_IDS,
} from "../src/intent_parser/index.js";

test("完整指令（标签式中文）→ complete=true 且三值正确提取", () => {
  const r = parseSubmissionIntent("提交作业：第一次作业，姓名：张三，小组：第 3 组");
  assert.equal(r.complete, true);
  assert.equal(r.assignment, "第一次作业");
  assert.equal(r.student_name, "张三");
  assert.equal(r.group_name, "第 3 组");
  assert.deepEqual(r.missing, []);
});

test("完整指令（自然形态：作业是/我叫/第 X 组）", () => {
  const r = parseSubmissionIntent("作业是《需求分析》，我叫李四，第 5 组");
  assert.equal(r.complete, true);
  assert.equal(r.assignment, "《需求分析》");
  assert.equal(r.student_name, "李四");
  assert.equal(r.group_name, "第 5 组");
  assert.deepEqual(r.missing, []);
});

test("完整指令（提交 X 作业 + 无空格序数组名）", () => {
  const r = parseSubmissionIntent("提交第二次作业，姓名：王五，小组：第二组");
  assert.equal(r.complete, true);
  assert.equal(r.assignment, "第二次");
  assert.equal(r.student_name, "王五");
  assert.equal(r.group_name, "第二组");
});

test("完整指令（英文标签）", () => {
  const r = parseSubmissionIntent("submit assignment: hw-01, name: Tom, group: 7");
  assert.equal(r.complete, true);
  assert.equal(r.assignment, "hw-01");
  assert.equal(r.student_name, "Tom");
  assert.equal(r.group_name, "7");
});

test("缺作业 → complete=false 且 missing 精确列出 assignment（TC-004/005）", () => {
  const r = parseSubmissionIntent("姓名：张三，小组：第 3 组");
  assert.equal(r.complete, false);
  assert.deepEqual(r.missing, ["assignment"]);
  assert.equal(r.assignment, undefined);
  // 已确定字段仍随结果返回，供展示层诊断；missing[] 为闸门唯一权威
  assert.equal(r.student_name, "张三");
  assert.equal(r.group_name, "第 3 组");
});

test("缺姓名 → complete=false 且 missing 精确列出 student_name（TC-004/005）", () => {
  const r = parseSubmissionIntent("作业：第一次作业，小组：第 3 组");
  assert.equal(r.complete, false);
  assert.deepEqual(r.missing, ["student_name"]);
  assert.equal(r.student_name, undefined);
  assert.equal(r.assignment, "第一次作业");
});

test("缺小组 → complete=false 且 missing 精确列出 group_name（TC-004/005）", () => {
  const r = parseSubmissionIntent("作业：第一次作业，姓名：张三");
  assert.equal(r.complete, false);
  assert.deepEqual(r.missing, ["group_name"]);
  assert.equal(r.group_name, undefined);
});

test("全缺（空文本/空白/非字符串）→ missing 三项全列（EMPTY_COMMAND 失败闭合）", () => {
  for (const input of ["", "   ", "\n\t ", null, undefined, 42, {}]) {
    const r = parseSubmissionIntent(input);
    assert.equal(r.complete, false, `input=${String(input)}`);
    assert.deepEqual(r.missing, ["assignment", "student_name", "group_name"]);
    assert.equal(r.assignment, undefined);
    assert.equal(r.student_name, undefined);
    assert.equal(r.group_name, undefined);
  }
});

test("确定性：同一输入重复解析输出完全一致（INV-IP-04 / IDEM-IP-01）", () => {
  const text = "提交作业：第一次作业，姓名：张三，小组：第 3 组";
  const first = parseSubmissionIntent(text);
  assert.deepEqual(parseSubmissionIntent(text), first);
  assert.deepEqual(parseSubmissionIntent(text), first);
  // 新建解析器实例对同一输入亦给出一致结果（无跨请求共享状态）
  assert.deepEqual(createIntentParser().parseSubmissionIntent(text), first);
});

test("中文姓名含空格与「第 X 组」形态正确提取（空白折叠无损）", () => {
  const r = parseSubmissionIntent("作业：实验一，姓名：张 三，小组：第 12 组");
  assert.equal(r.complete, true);
  assert.equal(r.student_name, "张 三");
  assert.equal(r.group_name, "第 12 组");
});

test("R-05：指令与配置不一致时以当次指令为准（LCD-001/LCD-IP-003）", () => {
  const config = { student_name: "张三", group_name: "第 9 组", assignment: "旧作业" };
  const r = parseSubmissionIntent("提交作业：第一次作业，姓名：李四，小组：第 3 组", { config });
  assert.equal(r.complete, true);
  assert.equal(r.assignment, "第一次作业");
  assert.equal(r.student_name, "李四");
  assert.equal(r.group_name, "第 3 组");
});

test("R-05：配置不得静默补齐当前指令缺失的必填字段（INV-IP-03）", () => {
  const config = { student_name: "张三", group_name: "第 3 组" };
  const r = parseSubmissionIntent("作业：第一次作业，小组：第 3 组", { config });
  assert.equal(r.complete, false);
  assert.deepEqual(r.missing, ["student_name"]);
  assert.equal(r.student_name, undefined);
});

test("歧义/冲突字段按缺项处理，不猜测放行（LCD-IP-002 fail-closed）", () => {
  const r = parseSubmissionIntent("作业：第一次作业，姓名：张三，姓名：李四，小组：第 3 组");
  assert.equal(r.complete, false);
  assert.deepEqual(r.missing, ["student_name"]);
  assert.equal(r.student_name, undefined); // 冲突值不得进入结果
});

test("缺项结果只含具体字段名且不产生提交意图（AC-REQ-001-01 boundaries 汇总）", () => {
  const scenarios = [
    ["姓名：张三，小组：第 3 组", ["assignment"]],
    ["作业：第一次作业，小组：第 3 组", ["student_name"]],
    ["作业：第一次作业，姓名：张三", ["group_name"]],
    ["随便聊聊", ["assignment", "student_name", "group_name"]],
  ];
  for (const [text, expected] of scenarios) {
    const r = parseSubmissionIntent(text);
    assert.equal(r.complete, false, text);
    assert.deepEqual(r.missing, expected, text);
    for (const field of r.missing) {
      assert.ok(FIELD_IDS.includes(field), `missing 字段名须为契约字段：${field}`);
    }
  }
});

test("可配置规则表：自定义关键词生效，内置表不受影响（LCD-IP-001 提取可替换）", () => {
  const custom = createIntentParser({
    ...DEFAULT_RULES,
    assignment: [
      ...DEFAULT_RULES.assignment,
      { id: "assignment.custom.gongke", pattern: /功课\s*[:：]\s*([^，。；;,：:\n]+)/g },
    ],
  });
  const text = "功课：习题三，姓名：张三，小组：第 3 组";
  const rc = custom.parseSubmissionIntent(text);
  assert.equal(rc.complete, true);
  assert.equal(rc.assignment, "习题三");
  // 内置表不含「功课」关键词 → 同一文本按缺项失败闭合（规则表驱动，确定性）
  const rd = parseSubmissionIntent(text);
  assert.equal(rd.complete, false);
  assert.deepEqual(rd.missing, ["assignment"]);
});
