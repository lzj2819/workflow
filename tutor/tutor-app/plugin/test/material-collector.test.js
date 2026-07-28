import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  collectMaterials,
  MaterialCollectionError,
  MATERIAL_CATEGORIES,
  MAX_SUBMISSION_BYTES,
} from "../src/material_collector/index.js";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/** CT-001 材料类别枚举（只读契约输入）。 */
async function ct001CategoryEnum() {
  const raw = await readFile(path.join(REPO_ROOT, "contracts", "ct-001.json"), "utf8");
  const ct001 = JSON.parse(raw);
  return ct001.schemas.request.properties.material_chunks.items.properties.category.enum;
}

const CT001_CATEGORY_BY_MANIFEST = Object.freeze({
  code: "代码",
  screenshot: "截图",
  result: "结果",
});

async function withFixture(t, files) {
  const root = await mkdtemp(path.join(tmpdir(), "l06-mc-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const dirs = { code: "code", screenshot: "shots", result: "result" };
  for (const dir of Object.values(dirs)) {
    await mkdir(path.join(root, dir), { recursive: true });
  }
  for (const [rel, content] of Object.entries(files ?? {})) {
    const abs = path.join(root, rel);
    await mkdir(path.dirname(abs), { recursive: true });
    await writeFile(abs, content);
  }
  return {
    root,
    config: {
      submission_uuid: "11111111-2222-3333-4444-555555555555",
      identity_snapshot: { assignment: "作业一", student_name: "张三", group_name: "第 7 组" },
      config_snapshot: {
        code_dir: path.join(root, dirs.code),
        screenshot_dir: path.join(root, dirs.screenshot),
        result_dir: path.join(root, dirs.result),
      },
      snapshot_at: "2026-07-20T08:00:00.000Z",
    },
  };
}

const sha256Of = (s) => createHash("sha256").update(s).digest("hex");

test("三类目录收集为 manifest：category/path/size_bytes/sha256 齐全、确定性排序", async (t) => {
  const { config } = await withFixture(t, {
    "code/b.py": "print('b')\n",
    "code/a.js": "console.log('a');\n",
    "code/notes.txt": "notes\n",
    "shots/shot2.png": "PNG-2",
    "shots/shot1.png": "PNG-1",
    "result/out.csv": "x,y\n1,2\n",
  });

  const m = await collectMaterials(config);

  assert.equal(m.submission_uuid, config.submission_uuid);
  assert.deepEqual(m.identity, config.identity_snapshot);
  assert.equal(m.snapshot_at, "2026-07-20T08:00:00.000Z");
  assert.deepEqual(m.missing_items, []);
  assert.equal(m.over_budget, false);

  // 条目字段齐全
  for (const item of m.items) {
    assert.ok(["code", "screenshot", "result"].includes(item.category));
    assert.equal(typeof item.path, "string");
    assert.ok(!item.path.includes("\\"), "path 使用 POSIX 分隔符");
    assert.equal(typeof item.size_bytes, "number");
    assert.match(item.sha256, /^[0-9a-f]{64}$/);
    assert.ok(!Number.isNaN(Date.parse(item.modified_at)));
  }

  // 确定性排序：category → path
  const keys = m.items.map((i) => `${i.category}${i.path}`);
  assert.deepEqual(keys, [...keys].sort());
  assert.deepEqual(
    m.items.map((i) => i.category),
    ["code", "code", "code", "result", "screenshot", "screenshot"],
  );

  // sha256 与内容一致；size_bytes 正确
  const aJs = m.items.find((i) => i.path.endsWith("/a.js"));
  assert.equal(aJs.sha256, sha256Of("console.log('a');\n"));
  assert.equal(aJs.size_bytes, Buffer.byteLength("console.log('a');\n"));

  // total_bytes = 全部通过项之和
  const expectedTotal = m.items.reduce((acc, i) => acc + i.size_bytes, 0);
  assert.equal(m.total_bytes, expectedTotal);
  assert.ok(m.total_bytes > 0);
});

test("白名单外文件被跳过并计数（不产生 items），隐藏文件与子目录不进入", async (t) => {
  const { config } = await withFixture(t, {
    "code/main.py": "ok\n",
    "code/evil.exe": "MZ",
    "code/archive.bak": "bak",
    "code/.hidden.js": "hidden\n",
    "code/nested/inner.py": "print('nested')\n",
  });

  const m = await collectMaterials(config);

  assert.deepEqual(
    m.items.map((i) => path.basename(i.path)),
    ["main.py"],
  );
  assert.equal(m.skipped_by_category.code, 2); // evil.exe + archive.bak
  assert.equal(m.skipped_by_category.screenshot, 0);
  assert.equal(m.skipped_by_category.result, 0);
  assert.ok(m.diagnostics.some((d) => d.includes("evil.exe") && d.includes("whitelist")));
  assert.ok(m.diagnostics.some((d) => d.includes("archive.bak")));
  // 隐藏文件与子目录内容既不收集也不计过滤数
  assert.ok(!m.items.some((i) => i.path.includes(".hidden") || i.path.includes("nested")));
  assert.deepEqual(m.missing_items.sort(), ["result", "screenshot"]);
});

test("目录不存在与目录为空都显式入 missing_items，其余类别正常收集", async (t) => {
  const { root, config } = await withFixture(t, {
    "code/app.ts": "export {};\n",
    "result/report.md": "# report\n",
  });
  // shots 目录存在但为空（夹具默认创建）；额外把 result 指到不存在的目录
  await rm(path.join(root, "result"), { recursive: true, force: true });

  const m = await collectMaterials(config);

  assert.deepEqual(m.missing_items, ["screenshot", "result"]);
  assert.deepEqual(m.items.map((i) => i.category), ["code"]);
  assert.ok(m.warnings.some((w) => w.includes("screenshot") && w.includes("empty")));
  assert.ok(m.warnings.some((w) => w.includes("result") && w.includes("not found")));
  // 缺失被显式标记而不是隐藏：items 中没有 screenshot/result 条目，但类别出现在 missing_items
  assert.ok(!m.items.some((i) => i.category === "screenshot" || i.category === "result"));
});

test("total_bytes 汇总与超 500MB 预检警告（预算可注入验证口径）", async (t) => {
  const { config } = await withFixture(t, {
    "code/big.bin.py": "x".repeat(1024),
    "shots/pic.jpg": "y".repeat(2048),
  });

  const ok = await collectMaterials(config);
  assert.equal(ok.total_bytes, 1024 + 2048);
  assert.equal(ok.over_budget, false);
  assert.ok(!ok.warnings.some((w) => w.includes("over budget")));

  const over = await collectMaterials(config, { max_total_bytes: 1000 });
  assert.equal(over.total_bytes, 1024 + 2048);
  assert.equal(over.over_budget, true);
  assert.ok(over.warnings.some((w) => w.includes("over budget") && w.includes("500MB")));
  // 预检告警不阻断收集（服务端权威）：items 仍然完整
  assert.equal(over.items.length, 2);

  assert.equal(MAX_SUBMISSION_BYTES, 524_288_000);
});

test("同一目录两次收集 manifest 一致（快照稳定性）", async (t) => {
  const { config } = await withFixture(t, {
    "code/z.py": "z\n",
    "code/a.py": "a\n",
    "shots/s.png": "p",
  });

  const first = await collectMaterials(config);
  const second = await collectMaterials(config);
  assert.deepEqual(second, first);
});

test("端口形状：items/missing_items 可直接作为 IC-M01-03 material_refs/missing_items", async (t) => {
  const { config } = await withFixture(t, {
    "code/a.py": "a\n",
    "shots/s.png": "p",
    "result/r.csv": "c\n",
  });

  const m = await collectMaterials(config);

  // CollectionBatch.material_refs：对象数组，条目为 MaterialManifest 条目
  assert.ok(Array.isArray(m.items));
  for (const ref of m.items) {
    assert.equal(typeof ref, "object");
    for (const field of ["category", "path", "size_bytes", "sha256"]) {
      assert.ok(field in ref, `material_refs 条目缺字段 ${field}`);
    }
  }
  // CollectionBatch.missing_items：字符串数组
  assert.ok(Array.isArray(m.missing_items));
  for (const mi of m.missing_items) assert.equal(typeof mi, "string");

  // 类别语义与 CT-001 material_chunks[] 枚举一一对应（INV-L2-MC-01）
  const ctEnum = await ct001CategoryEnum();
  assert.deepEqual(
    MATERIAL_CATEGORIES.map((c) => c.category).sort(),
    ["code", "result", "screenshot"],
  );
  for (const item of m.items) {
    const ctCategory = CT001_CATEGORY_BY_MANIFEST[item.category];
    assert.ok(ctCategory, `未映射的 manifest 类别 ${item.category}`);
    assert.ok(ctEnum.includes(ctCategory), `${ctCategory} 不在 CT-001 类别枚举内`);
  }
});

test("配置快照失效显式失败（MC-ERR-CONFIG-INVALID），不静默降级", async (t) => {
  const { config } = await withFixture(t, { "code/a.py": "a\n" });

  await assert.rejects(
    collectMaterials({ ...config, config_snapshot: { ...config.config_snapshot, code_dir: "" } }),
    (err) => {
      assert.ok(err instanceof MaterialCollectionError);
      assert.equal(err.code, "MC-ERR-CONFIG-INVALID");
      return true;
    },
  );
  await assert.rejects(collectMaterials({}), /MC-ERR-CONFIG-INVALID/);
  await assert.rejects(
    collectMaterials({ ...config, submission_uuid: "" }),
    /MC-ERR-CONFIG-INVALID/,
  );
});

test("目录不可读（非缺失类错误）显式失败 MC-ERR-DIR-UNREADABLE", async (t) => {
  const { config } = await withFixture(t, { "code/a.py": "a\n" });
  const permErr = new Error("permission denied");
  permErr.code = "EACCES";

  await assert.rejects(
    collectMaterials(config, {
      entryReader: async (dir) => {
        if (dir === config.config_snapshot.screenshot_dir) throw permErr;
        const { readdir } = await import("node:fs/promises");
        return readdir(dir);
      },
    }),
    (err) => {
      assert.ok(err instanceof MaterialCollectionError);
      assert.equal(err.code, "MC-ERR-DIR-UNREADABLE");
      assert.match(err.reason, /screenshot|shots/);
      return true;
    },
  );
});

test("白名单可配置覆盖", async (t) => {
  const { config } = await withFixture(t, {
    "code/a.py": "a\n",
    "code/b.xyz": "custom\n",
  });

  const m = await collectMaterials(config, { whitelist: [".xyz"] });
  assert.deepEqual(
    m.items.map((i) => path.basename(i.path)),
    ["b.xyz"],
  );
  assert.equal(m.skipped_by_category.code, 1);
});
