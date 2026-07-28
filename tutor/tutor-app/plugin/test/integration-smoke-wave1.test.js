import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { createConfigStore } from "../src/config_store/config-store.js";
import { parseSubmissionIntent } from "../src/intent_parser/index.js";
import { collectMaterials } from "../src/material_collector/index.js";

// Wave 1 插件侧跨叶子冒烟：L04 配置保存/读取 → L05 意图解析闸门 → L06 材料收集。
test("L04+L05+L06 链路：配置 → 意图 → 材料清单", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "tutor-smoke-"));
  const codeDir = path.join(root, "code");
  const shotsDir = path.join(root, "shots");
  const resultDir = path.join(root, "result");
  await mkdir(codeDir, { recursive: true });
  await mkdir(shotsDir, { recursive: true }); // 空目录：配置完整，但 L06 标记 screenshot 缺失
  await mkdir(resultDir, { recursive: true });
  await writeFile(path.join(codeDir, "main.py"), "print('hw')\n");
  await writeFile(path.join(codeDir, "virus.exe"), "MZ", "latin1"); // 白名单外
  await writeFile(path.join(resultDir, "README.md"), "# result\n");

  // L04：保存完整配置并重读一致
  const store = createConfigStore({ filePath: path.join(root, "config.json") });
  const config = {
    invite_code: "INV-01",
    student_name: "张三",
    group_name: "第7组",
    code_dir: codeDir,
    screenshots_dir: shotsDir,
    results_dir: resultDir,
  };
  const saved = await store.save(config);
  assert.equal(saved.ok, true, JSON.stringify(saved));
  const loaded = await store.getRequired();
  assert.equal(loaded.invite_code, "INV-01");
  assert.equal(loaded.code_dir, codeDir);

  // L05：完整指令（标签式）→ complete；缺小组 → complete=false + missing
  const intent = parseSubmissionIntent("提交作业：hw-01，姓名：张三，小组：第7组");
  assert.equal(intent.complete, true, JSON.stringify(intent));
  assert.equal(intent.assignment, "hw-01");
  assert.equal(intent.student_name, "张三");
  assert.equal(intent.group_name, "第7组");
  const incomplete = parseSubmissionIntent("作业：hw-01，姓名：张三");
  assert.equal(incomplete.complete, false);
  assert.ok(incomplete.missing.includes("group_name"));

  // L06：L04 配置 + L05 意图组装采集任务输入（此组装归 L11 PENDING-QUEUE，冒烟预演）→
  // 代码/结果入库，截图缺失显式标记，白名单外跳过
  const manifest = await collectMaterials({
    submission_uuid: "00000000-0000-4000-8000-000000000001",
    identity_snapshot: {
      assignment: intent.assignment,
      student_name: intent.student_name,
      group_name: intent.group_name,
    },
    config_snapshot: {
      code_dir: loaded.code_dir,
      screenshot_dir: loaded.screenshots_dir,
      result_dir: loaded.results_dir,
    },
    snapshot_at: "2026-07-20T08:00:00.000Z",
  });
  const categories = new Set(manifest.items.map((i) => i.category));
  assert.ok(categories.has("code") && categories.has("result"));
  assert.ok(manifest.missing_items.includes("screenshot"));
  assert.ok(!manifest.items.some((i) => i.path.endsWith(".exe")));
  assert.ok(manifest.total_bytes > 0);
});
