import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("Phase 1 骨架文件齐备", () => {
  const expected = [
    "src/host/dialogue-export-port.js",
    "src/host/fixtures/dialogue-export.sample.json",
    "src/config/plugin-config.js",
    "src/ports/index.js",
    "package.json",
  ];
  for (const rel of expected) {
    assert.ok(existsSync(path.join(root, rel)), `missing ${rel}`);
  }
});
