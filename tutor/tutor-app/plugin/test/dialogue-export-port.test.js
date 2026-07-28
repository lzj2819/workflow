import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import {
  validateDialogueExport,
  exportDialogueFromHost,
  HostUnsupportedError,
} from "../src/host/dialogue-export-port.js";

const here = path.dirname(fileURLToPath(import.meta.url));

test("fixture 满足 DialogueExport 端口形状", async () => {
  const raw = await readFile(
    path.join(here, "../src/host/fixtures/dialogue-export.sample.json"),
    "utf-8",
  );
  const result = validateDialogueExport(JSON.parse(raw));
  assert.deepEqual(result.errors, []);
  assert.equal(result.ok, true);
});

test("非法导出物逐项报错", () => {
  assert.equal(validateDialogueExport(null).ok, false);
  const bad = validateDialogueExport({ format_version: "", turns: [{ role: "ghost", content: "" }] });
  assert.equal(bad.ok, false);
  assert.ok(bad.errors.some((e) => e.includes("format_version")));
  assert.ok(bad.errors.some((e) => e.includes("source_host")));
  assert.ok(bad.errors.some((e) => e.includes("role")));
});

test("宿主导出入口为显式 unsupported 失败（可观测，不虚构 API）", async () => {
  await assert.rejects(exportDialogueFromHost(), (err) => {
    assert.ok(err instanceof HostUnsupportedError);
    assert.equal(err.code, "HOST_EXPORT_UNSUPPORTED");
    assert.ok(err.detail.includes("TD-01"));
    return true;
  });
});
