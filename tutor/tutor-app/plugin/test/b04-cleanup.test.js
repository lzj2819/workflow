/**
 * T-B04 / IC-PQ-004 — pending_queue/cleanup.js 终态清理协调测试。
 *
 * 断言：
 * - completed / failed_terminal 超期（retentionDays 可配，默认 30 天）被移除；
 * - 进行中任务（failed_retryable 等）绝不误删；未超期终态保留；
 * - 审计先行：终态摘要落 archive/（uuid/终态/时间，绝不含材料快照）；
 * - command_index 同步清理；清理计数可观测（onEvent + 返回摘要）。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { createPendingQueue } from "../src/pending_queue/index.js";
import { createStateStore } from "../src/pending_queue/state-store.js";
import { DEFAULT_RETENTION_DAYS, runCleanup } from "../src/pending_queue/cleanup.js";

const DAY_MS = 86_400_000;

function makeClock(startMs = 1_700_000_000_000) {
  let now = startMs;
  return {
    now: () => now,
    advance(ms) {
      now += ms;
    },
  };
}

function makeIntent(assignment) {
  return {
    complete: true,
    assignment,
    student_name: "张三",
    group_name: "G1",
    missing: [],
  };
}

function makePorts(uploadByAssignment) {
  return {
    readConfig: async () => ({
      invite_code: "INV-001",
      code_dir: "C:/m/code",
      screenshot_dir: "C:/m/shots",
      result_dir: "C:/m/results",
    }),
    collectDialogue: async () => ({
      format_version: "1",
      source_host: "test-host",
      exported_at: "2026-07-21T00:00:00.000Z",
      turns: [{ role: "user", content: "提交作业" }],
    }),
    collectMaterials: async (taskRef) => ({
      submission_uuid: taskRef.submission_uuid,
      identity: taskRef.intent,
      items: [
        {
          category: "code",
          path: "C:/m/code/main.py",
          size_bytes: 10,
          sha256: "a".repeat(64),
          modified_at: "2026-07-21T00:00:00.000Z",
        },
      ],
      missing_items: [],
      total_bytes: 10,
      over_budget: false,
      warnings: [],
      snapshot_at: "2026-07-21T00:00:00.000Z",
    }),
    upload: async (job) => uploadByAssignment(job.identity.assignment),
  };
}

/** 建三个任务：completed / failed_terminal / failed_retryable（进行中）。 */
async function seedQueue(t, clock) {
  const dir = await mkdtemp(path.join(tmpdir(), "b04-cleanup-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const storagePath = path.join(dir, "queue.json");
  let seq = 0;
  const queue = createPendingQueue({
    storagePath,
    ports: makePorts((assignment) => {
      if (assignment === "hw-ok") {
        return { status: "confirmed", submission_id: "sub-1", received_at: new Date(clock.now()).toISOString(), missing_items: [] };
      }
      if (assignment === "hw-reject") {
        return { status: "rejected", rejection_reason: "REJECTED_MEMBERSHIP" };
      }
      return { status: "interrupted", cause: "NETWORK_INTERRUPTED" };
    }),
    clock,
    uuidgen: () => `uuid-${++seq}`,
  });
  const r1 = await queue.submitIntent(makeIntent("hw-ok"), { command_id: "cmd-1" });
  const r2 = await queue.submitIntent(makeIntent("hw-reject"), { command_id: "cmd-2" });
  const r3 = await queue.submitIntent(makeIntent("hw-retry"), { command_id: "cmd-3" });
  assert.equal(queue.getTask(r1.task_ref.submission_uuid).state, "completed");
  assert.equal(queue.getTask(r2.task_ref.submission_uuid).state, "failed_terminal");
  assert.equal(queue.getTask(r3.task_ref.submission_uuid).state, "failed_retryable");
  await queue.dispose(); // 冷态：避免存活队列 persist 覆盖清理结果
  return { dir, storagePath, uuids: [r1, r2, r3].map((r) => r.task_ref.submission_uuid) };
}

test("超期终态移除 + 归档摘要 + 计数可观测；进行中不误删", async (t) => {
  const clock = makeClock();
  const { dir, storagePath, uuids } = await seedQueue(t, clock);
  const archiveDir = path.join(dir, "archive");
  const events = [];
  clock.advance(31 * DAY_MS);

  const summary = await runCleanup({
    store: createStateStore({ storagePath }),
    archiveDir,
    now: clock.now(),
    onEvent: (e) => events.push(e),
  });

  assert.equal(summary.scanned, 3);
  assert.equal(summary.terminal_total, 2);
  assert.equal(summary.removed_count, 2);
  assert.equal(summary.retained_terminal_count, 0);
  assert.deepEqual(
    summary.removed.map((s) => s.submission_uuid).sort(),
    [uuids[0], uuids[1]].sort(),
  );

  // 归档摘要：uuid/终态/时间齐全，绝不含材料快照。
  const files = (await readdir(archiveDir)).sort();
  assert.deepEqual(files, [`${uuids[0]}.json`, `${uuids[1]}.json`].sort());
  const archived = JSON.parse(await readFile(path.join(archiveDir, `${uuids[0]}.json`), "utf8"));
  assert.equal(archived.submission_uuid, uuids[0]);
  assert.equal(archived.terminal_state, "completed");
  assert.equal(typeof archived.terminal_at, "string");
  assert.equal(typeof archived.archived_at, "string");
  const raw = await readFile(path.join(archiveDir, `${uuids[0]}.json`), "utf8");
  for (const forbidden of ["bundle_ref", "dialogue_artifact", "material_manifest", "sha256", "turns"]) {
    assert.ok(!raw.includes(forbidden), `archive must not contain material snapshot (${forbidden})`);
  }
  const archivedRejected = JSON.parse(await readFile(path.join(archiveDir, `${uuids[1]}.json`), "utf8"));
  assert.equal(archivedRejected.terminal_state, "failed_terminal");

  // envelope：仅剩进行中任务；command_index 同步清理。
  const envelope = await createStateStore({ storagePath }).load();
  assert.deepEqual(Object.keys(envelope.tasks), [uuids[2]]);
  assert.equal(envelope.tasks[uuids[2]].state, "failed_retryable");
  assert.deepEqual(envelope.command_index, { "cmd-3": uuids[2] });

  // 可观测：清理计数事件。
  const evt = events.find((e) => e.event === "PendingQueueCleanupCompleted");
  assert.ok(evt);
  assert.equal(evt.removed_count, 2);
  assert.equal(evt.terminal_total, 2);
});

test("未超期终态保留；retentionDays 可配", async (t) => {
  const clock = makeClock();
  const { dir, storagePath, uuids } = await seedQueue(t, clock);
  const archiveDir = path.join(dir, "archive");

  clock.advance(29 * DAY_MS); // 默认 30 天内
  let summary = await runCleanup({
    store: createStateStore({ storagePath }),
    archiveDir,
    now: clock.now(),
  });
  assert.equal(summary.removed_count, 0);
  assert.equal(summary.retained_terminal_count, 2);

  clock.advance(2 * DAY_MS); // 共 31 天；但 retentionDays=60 → 仍保留
  summary = await runCleanup({
    store: createStateStore({ storagePath }),
    archiveDir,
    now: clock.now(),
    retentionDays: 60,
  });
  assert.equal(summary.removed_count, 0);

  summary = await runCleanup({
    store: createStateStore({ storagePath }),
    archiveDir,
    now: clock.now(),
    retentionDays: 30,
  });
  assert.equal(summary.removed_count, 2);
  const envelope = await createStateStore({ storagePath }).load();
  assert.deepEqual(Object.keys(envelope.tasks), [uuids[2]]);
});

test("默认保留期为 30 天", () => {
  assert.equal(DEFAULT_RETENTION_DAYS, 30);
});

test("缺 store/now → 可诊断拒绝", async () => {
  await assert.rejects(() => runCleanup({ now: 0 }), /CLEANUP_STORE_MISSING/);
  await assert.rejects(
    () => runCleanup({ store: { load: async () => ({}), save: async () => {} }, archiveDir: "x" }),
    /CLEANUP_STORE_MISSING/,
  );
});
