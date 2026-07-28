/**
 * L04 CMP-CONFIG-STORE 测试（REQ-002 / AC-REQ-002-01 / INV-3）。
 *
 * 覆盖 verification-checklist 语义断言：
 * 保存→重读一致（含中文）、原子保存中断不破坏旧配置、无效拒绝且旧值可读、
 * 必填缺失→不完整+缺失项、目录不可读→具体目录错误、损坏文件可诊断且不覆盖、
 * IC-M01-02 端口形状与订阅事件、schema_version 演进。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, readFile, writeFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createConfigStore } from "../src/config_store/config-store.js";
import { REQUIRED_CONFIG_FIELDS } from "../src/config/plugin-config.js";
import { IC_M01_IDS } from "../src/ports/index.js";

const VALID = {
  invite_code: "COURSE-2026",
  student_name: "张三",
  group_name: "第 7 组",
  code_dir: "D:/work/hw1",
  screenshots_dir: "D:/work/hw1/shots",
  results_dir: "D:/work/hw1/result",
};

const okDir = async () => true;

async function freshDir(t) {
  const dir = await mkdtemp(join(tmpdir(), "l04-config-store-"));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}

test("保存后重开值一致（含中文字段），config_version 重开延续", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  const saved = await store.save(VALID);
  assert.equal(saved.ok, true);
  assert.equal(saved.saved, true);
  assert.equal(saved.status, "complete");
  assert.equal(saved.config_version, 1);

  // 模拟「重新打开」：新实例读同一文件，值逐项一致
  const reopened = createConfigStore({ filePath: file, dirCheck: okDir });
  const eff = await reopened.get();
  assert.equal(eff.ok, true);
  assert.equal(eff.status, "complete");
  for (const f of REQUIRED_CONFIG_FIELDS) assert.equal(eff[f], VALID[f], f);
  assert.deepEqual(eff.completeness, []);
  assert.deepEqual(eff.dir_errors, []);

  // schema v1：磁盘记录携带 schema_version 供演进
  const onDisk = JSON.parse(await readFile(file, "utf8"));
  assert.equal(onDisk.schema_version, 1);
  assert.equal(onDisk.config_version, 1);

  // 重开后再次保存：版本延续不回退
  const again = await reopened.save({ ...VALID, group_name: "第 8 组" });
  assert.equal(again.config_version, 2);
});

test("原子保存：rename 前写入失败不破坏旧配置", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  let failWrites = false;
  const fsDeps = {
    writeFile: async (...args) => {
      if (failWrites) throw new Error("simulated disk full");
      return writeFile(...args);
    },
  };
  const store = createConfigStore({ filePath: file, dirCheck: okDir, fs: fsDeps });
  const first = await store.save(VALID);
  assert.equal(first.ok, true);
  const before = await readFile(file, "utf8");

  failWrites = true;
  const second = await store.save({ ...VALID, student_name: "李四" });
  assert.equal(second.ok, false);
  assert.equal(second.saved, false);
  assert.equal(second.error_code, "PERSISTENCE_FAILED");
  failWrites = false;

  // 旧配置文件字节不变；旧有效配置保持可读；临时文件已清理
  assert.equal(await readFile(file, "utf8"), before);
  const eff = await store.get();
  assert.equal(eff.student_name, "张三");
  assert.equal(eff.config_version, 1);
  const leftovers = (await readdir(dir)).filter((f) => f.includes(".tmp-"));
  assert.deepEqual(leftovers, []);
});

test("格式无效拒绝保存，上一次有效配置保持可读（INV-3）", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  await store.save(VALID);
  const before = await readFile(file, "utf8");

  for (const bad of ["nope", null, [1, 2], { ...VALID, invite_code: 42 }]) {
    const res = await store.save(bad);
    assert.equal(res.ok, false);
    assert.equal(res.saved, false);
    assert.equal(res.error_code, "INVALID_CONFIG");
    assert.ok(res.field_errors.length > 0);
  }

  // 旧值未被覆盖且保持可读
  assert.equal(await readFile(file, "utf8"), before);
  const eff = await store.get();
  assert.equal(eff.status, "complete");
  assert.equal(eff.invite_code, "COURSE-2026");
  assert.equal(eff.config_version, 1);
});

test("必填缺失保存为「不完整」并列出缺失项", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  const res = await store.save({ invite_code: "COURSE-2026" });
  assert.equal(res.ok, true);
  assert.equal(res.saved, true);
  assert.equal(res.status, "incomplete");

  // 缺失项覆盖 student_name/group_name/三个目录
  const expectedMissing = REQUIRED_CONFIG_FIELDS.filter((f) => f !== "invite_code");
  assert.deepEqual(res.missing, expectedMissing);
  for (const f of expectedMissing) assert.ok(res.completeness.includes(f), f);

  // 已填值持久化，重开后缺失项仍在
  const reopened = createConfigStore({ filePath: file, dirCheck: okDir });
  const eff = await reopened.get();
  assert.equal(eff.status, "incomplete");
  assert.equal(eff.invite_code, "COURSE-2026");
  assert.deepEqual(eff.missing, expectedMissing);

  await assert.rejects(
    () => reopened.getRequired(),
    (err) => {
      assert.equal(err.code, "CONFIG_INCOMPLETE");
      assert.deepEqual(err.missing, expectedMissing);
      return true;
    },
  );
});

test("目录不可读保存为不完整并给出具体目录错误（注入 dirCheck）", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const dirCheck = async (p) => !p.includes("shots");
  const store = createConfigStore({ filePath: file, dirCheck });
  const res = await store.save(VALID);
  assert.equal(res.ok, true);
  assert.equal(res.saved, true);
  assert.equal(res.status, "incomplete");
  assert.deepEqual(res.missing, []);
  assert.ok(
    res.dir_errors.some((e) => e.includes("screenshots_dir") && e.includes("not readable")),
    "具体目录错误",
  );
  assert.ok(res.completeness.includes("screenshots_dir"));

  // 读取时重新探测：当前目录错误只影响派生视图
  const eff = await store.get();
  assert.ok(eff.dir_errors.some((e) => e.includes("screenshots_dir")));

  await assert.rejects(
    () => store.getRequired(),
    (err) => {
      assert.equal(err.code, "CONFIG_INCOMPLETE");
      assert.ok(err.dir_errors.some((e) => e.includes("screenshots_dir")));
      return true;
    },
  );
});

test("损坏配置文件（非法 JSON）：可诊断错误，读取不覆盖旧值", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  await store.save(VALID);

  // 外部损坏文件
  await writeFile(file, "{ not json !!!", "utf8");
  const corruptBytes = await readFile(file, "utf8");

  // 进程内保留上一次有效配置（INV-3），显式 stale，不伪造结论
  const stale = await store.get();
  assert.equal(stale.ok, true);
  assert.equal(stale.stale, true);
  assert.equal(stale.read_error.error_code, "CONFIG_CORRUPT");
  assert.equal(stale.student_name, "张三");

  // 重开（无 lastGood）：可诊断错误
  const fresh = createConfigStore({ filePath: file, dirCheck: okDir });
  const res = await fresh.get();
  assert.equal(res.ok, false);
  assert.equal(res.error_code, "CONFIG_CORRUPT");
  assert.ok(res.error_detail.includes("not valid JSON"));

  // 读取无任何写副作用：损坏文件保持原样
  assert.equal(await readFile(file, "utf8"), corruptBytes);
});

test("从未保存：状态 missing，getRequired 拒绝", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  const eff = await store.get();
  assert.equal(eff.ok, true);
  assert.equal(eff.status, "missing");
  assert.deepEqual(eff.completeness, [...REQUIRED_CONFIG_FIELDS]);
  assert.equal(eff.config_version, null);
  await assert.rejects(() => store.getRequired(), /incomplete/);
});

test("getRequired 完整时返回六字段配置", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  await store.save(VALID);
  const cfg = await store.getRequired();
  assert.deepEqual(cfg, VALID);
});

test("IC-M01-02 端口形状与变更订阅事件", async (t) => {
  assert.ok(IC_M01_IDS.includes("IC-M01-02"));
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  for (const fn of ["save", "get", "getRequired", "onChange"]) {
    assert.equal(typeof store[fn], "function", fn);
  }

  const events = [];
  const unsubscribe = store.onChange((e) => events.push(e));
  await store.save(VALID);
  await store.save("garbage");
  unsubscribe();
  await store.save({ ...VALID, student_name: "李四" }); // 退订后不再收到

  assert.equal(events.length, 2);
  assert.equal(events[0].type, "ConfigSaved");
  assert.equal(events[0].config_version, 1);
  assert.deepEqual(events[0].completeness, []);
  assert.equal(events[1].type, "ConfigRejected");
  assert.equal(events[1].error_code, "INVALID_CONFIG");

  // EffectiveConfig 形状：六字段 + completeness[] + dir_errors[]
  const eff = await store.get();
  for (const f of REQUIRED_CONFIG_FIELDS) assert.equal(typeof eff[f], "string", f);
  assert.ok(Array.isArray(eff.completeness));
  assert.ok(Array.isArray(eff.dir_errors));
});

test("不支持的 schema_version 读取报错且保留原记录", async (t) => {
  const dir = await freshDir(t);
  const file = join(dir, "config.json");
  const future = JSON.stringify({ schema_version: 999, config_version: 7, config: VALID });
  await writeFile(file, future, "utf8");

  const store = createConfigStore({ filePath: file, dirCheck: okDir });
  const res = await store.get();
  assert.equal(res.ok, false);
  assert.equal(res.error_code, "UNSUPPORTED_SCHEMA_VERSION");
  assert.ok(res.error_detail.includes("999"));
  // 不得以默认值覆盖旧配置
  assert.equal(await readFile(file, "utf8"), future);
});
