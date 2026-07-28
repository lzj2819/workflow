import { test } from "node:test";
import assert from "node:assert/strict";

import { validatePluginConfig, REQUIRED_CONFIG_FIELDS } from "../src/config/plugin-config.js";

const valid = {
  invite_code: "COURSE-2026",
  student_name: "张三",
  group_name: "第 7 组",
  code_dir: "D:/work/hw1",
  screenshots_dir: "D:/work/hw1/shots",
  results_dir: "D:/work/hw1/result",
};

test("完整配置通过（目录可读）", async () => {
  const result = await validatePluginConfig(valid, { dirCheck: async () => true });
  assert.equal(result.ok, true);
  assert.deepEqual(result.missing, []);
  assert.deepEqual(result.errors, []);
});

test("缺字段逐项列入 missing", async () => {
  const result = await validatePluginConfig({ invite_code: "X" }, { dirCheck: async () => true });
  assert.equal(result.ok, false);
  for (const field of REQUIRED_CONFIG_FIELDS.filter((f) => f !== "invite_code")) {
    assert.ok(result.missing.includes(field), `missing ${field}`);
  }
});

test("目录不可读给出具体目录错误", async () => {
  const result = await validatePluginConfig(valid, {
    dirCheck: async (p) => !p.includes("shots"),
  });
  assert.equal(result.ok, false);
  assert.deepEqual(result.missing, []);
  assert.ok(result.errors.some((e) => e.includes("screenshots_dir")));
});

test("非对象配置拒绝", async () => {
  const result = await validatePluginConfig("nope", { dirCheck: async () => true });
  assert.equal(result.ok, false);
  assert.equal(result.missing.length, REQUIRED_CONFIG_FIELDS.length);
});
