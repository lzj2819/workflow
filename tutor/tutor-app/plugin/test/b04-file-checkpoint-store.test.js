/**
 * T-B04 — file-checkpoint-store（ST-05 文件持久化）测试。
 *
 * 断言：
 * - 接口形状与 createMemoryCheckpointStore 一致（load/save/clear）；
 * - 原子写（tmp + rename，提交后无 tmp 残留）；save 串行化；
 * - 只持久化已确认分片形状的记录（INV-5 fail-closed 校验）；
 * - 损坏文件 → CHECKPOINT_CORRUPT 可诊断报错，不覆盖不删除原文件；
 * - load 返回副本（调用方改写不影响已存记录）。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import {
  CheckpointStoreError,
  createFileCheckpointStore,
} from "../src/upload_client/file-checkpoint-store.js";
import { createMemoryCheckpointStore } from "../src/upload_client/checkpoint-store.js";

const UUID = "11111111-2222-3333-4444-555555555555";

function makeCp(overrides = {}) {
  return {
    submission_uuid: UUID,
    upload_session_id: "sess-1",
    confirmed_chunks: [0, 1],
    total_chunks: 4,
    last_ack_at: "2026-07-21T00:00:00.000Z",
    ...overrides,
  };
}

async function makeStore(t) {
  const dir = await mkdtemp(path.join(tmpdir(), "b04-cp-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return { store: createFileCheckpointStore({ dir }), dir };
}

test("接口形状与内存版一致（load/save/clear 均为函数）", async (t) => {
  const { store } = await makeStore(t);
  const mem = createMemoryCheckpointStore();
  for (const key of ["load", "save", "clear"]) {
    assert.equal(typeof store[key], typeof mem[key]);
  }
});

test("save/load 往返；不存在 → null；load 返回副本", async (t) => {
  const { store } = await makeStore(t);
  assert.equal(await store.load(UUID), null);
  await store.save(makeCp());
  const loaded = await store.load(UUID);
  assert.deepEqual(loaded, makeCp());
  loaded.confirmed_chunks.push(99); // 改副本不影响已存记录
  assert.deepEqual((await store.load(UUID)).confirmed_chunks, [0, 1]);
});

test("原子写：提交后目录无 tmp 残留", async (t) => {
  const { store, dir } = await makeStore(t);
  await store.save(makeCp());
  await store.save(makeCp({ confirmed_chunks: [0, 1, 2] }));
  const names = await readdir(dir);
  assert.deepEqual(names, [`checkpoint-${UUID}.json`]);
});

test("clear 移除；重复 clear 不报错", async (t) => {
  const { store } = await makeStore(t);
  await store.save(makeCp());
  await store.clear(UUID);
  assert.equal(await store.load(UUID), null);
  await store.clear(UUID); // ENOENT 容忍
});

test("损坏文件 → CHECKPOINT_CORRUPT，原文件保留不被覆盖", async (t) => {
  const { store, dir } = await makeStore(t);
  const filePath = path.join(dir, `checkpoint-${UUID}.json`);
  await writeFile(filePath, "{not-json", "utf8");
  await assert.rejects(() => store.load(UUID), (err) => {
    assert.ok(err instanceof CheckpointStoreError);
    assert.equal(err.code, "CHECKPOINT_CORRUPT");
    return true;
  });
  // 原文件未被删除/改写
  assert.equal(await readFile(filePath, "utf8"), "{not-json");
});

test("形状/uuid 不符的记录 → CHECKPOINT_CORRUPT", async (t) => {
  const { store, dir } = await makeStore(t);
  const filePath = path.join(dir, `checkpoint-${UUID}.json`);
  await writeFile(
    filePath,
    JSON.stringify({ submission_uuid: "other-uuid", upload_session_id: "s", confirmed_chunks: [], total_chunks: 0, last_ack_at: null }),
    "utf8",
  );
  await assert.rejects(() => store.load(UUID), /CHECKPOINT_CORRUPT/);
});

test("INV-5 fail-closed：拒绝形状不符的 save（未确认分片不得入 checkpoint）", async (t) => {
  const { store } = await makeStore(t);
  await assert.rejects(() => store.save({ ...makeCp(), confirmed_chunks: "0" }), /CHECKPOINT_INVALID/);
  await assert.rejects(() => store.save({ ...makeCp(), confirmed_chunks: [-1] }), /CHECKPOINT_INVALID/);
  await assert.rejects(() => store.save({ ...makeCp(), upload_session_id: "" }), /CHECKPOINT_INVALID/);
  await assert.rejects(() => store.save({ ...makeCp(), submission_uuid: "../escape" }), /CHECKPOINT_INVALID/);
  assert.equal(await store.load(UUID), null); // 拒绝写入，无残留
});
