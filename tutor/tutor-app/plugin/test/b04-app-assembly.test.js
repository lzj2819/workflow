/**
 * T-B04 — plugin/src/app 组装层测试（MOD-01 真实接线）。
 *
 * 覆盖：
 * - 主流程全链（stub transport）：配置 → 意图 → L06/L07 采集 → L11 编排 →
 *   L10 上传 → L13 呈现；对话 chunk 内容为注入 host port 的真实导出物；
 * - INV-1：意图缺项/配置不完整 → L13 呈现并中止，不建任务、零网络调用；
 * - TD-01：host unsupported 显式呈现真实原因（HOST_EXPORT_UNSUPPORTED），
 *   不伪造对话导出物、不静默转为「对话缺失」；
 * - 断网恢复：checkpoint 文件跨进程复用（同会话、跳过已确认分片）、
 *   采集不重做（INV-4）、uuid 全程不变（INV-2）；
 * - IC-PQ-004：cleanupTerminal 超期终态清理 + 归档，冷态执行后 recover 无残留。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { createPlugin } from "../src/app/index.js";
import { HostUnsupportedError } from "../src/host/dialogue-export-port.js";

const DAY_MS = 86_400_000;
const COMMAND = "提交第一次作业，姓名：张三，小组：第 3 组";

function makeClock(startMs = 1_700_000_000_000) {
  let now = startMs;
  return {
    now: () => now,
    advance(ms) {
      now += ms;
    },
  };
}

function createSpy(impl) {
  const spy = async (...args) => {
    spy.calls.push(args);
    return impl(...args);
  };
  spy.calls = [];
  return spy;
}

function dialogueExport() {
  return {
    format_version: "1",
    source_host: "test-host",
    exported_at: "2026-07-21T00:00:00.000Z",
    turns: [{ role: "user", content: "请提交第一次作业" }],
  };
}

/** MOD-02 stub server（多 epoch 共享 submissions，模拟服务端状态持续）。 */
function createStubServer(hooks = {}) {
  const requests = [];
  const submissions = new Map();
  let tokenSeq = 0;

  const defaultHandle = (req) => {
    if (req.path === "/api/v1/auth/token") {
      tokenSeq += 1;
      return { status: 200, body: { access_token: `tok-${tokenSeq}`, token_type: "Bearer", expires_in: 3600 } };
    }
    if (req.path.startsWith("/api/v1/submissions/") && req.method === "GET") {
      const uuid = decodeURIComponent(req.path.slice("/api/v1/submissions/".length));
      const sub = submissions.get(uuid);
      if (!sub) return { status: 404, body: { error_code: "NOT_FOUND" } };
      return {
        status: 200,
        body: { submission_id: sub.submission_id, status: sub.merged ? "received" : "upload_failed", missing_items: [] },
      };
    }
    const phase = req.body?.phase;
    if (phase === "create_session") {
      const uuid = req.body.submission_uuid;
      let sub = submissions.get(uuid);
      if (!sub) {
        sub = { session_id: `sess-${uuid}`, submission_id: `sub-${uuid}`, acked: new Set(), merged: false };
        submissions.set(uuid, sub);
      }
      return { status: 200, body: { upload_session_id: sub.session_id } };
    }
    if (phase === "chunk") {
      const sub = submissions.get(req.body.submission_uuid);
      sub.acked.add(req.body.chunk_index);
      return { status: 200, body: { acked: true, chunk_index: req.body.chunk_index } };
    }
    if (phase === "merge") {
      const sub = submissions.get(req.body.submission_uuid);
      sub.merged = true;
      return {
        status: 200,
        body: { submission_id: sub.submission_id, received_at: "2026-07-21T01:00:00.000Z", status: "received", missing_items: [] },
      };
    }
    throw new Error(`unexpected request: ${req.method} ${req.path}`);
  };

  const transport = async (req) => {
    requests.push(req);
    if (hooks.override) {
      const r = hooks.override(req);
      if (r !== undefined) return r;
    }
    return defaultHandle(req);
  };
  return { transport, requests, submissions };
}

async function makeEnv(t) {
  const root = await mkdtemp(path.join(tmpdir(), "b04-app-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const dirs = {
    code_dir: path.join(root, "code"),
    screenshots_dir: path.join(root, "shots"),
    results_dir: path.join(root, "results"),
  };
  for (const d of Object.values(dirs)) await mkdir(d, { recursive: true });
  await writeFile(path.join(dirs.code_dir, "main.py"), "print('hi')\n", "utf8");
  await writeFile(path.join(dirs.screenshots_dir, "shot.png"), "PNG", "utf8");
  await writeFile(path.join(dirs.results_dir, "out.csv"), "a,b\n", "utf8");
  const storageRoot = path.join(root, "state");
  return { root, storageRoot, dirs };
}

async function saveFullConfig(plugin, dirs) {
  const res = await plugin.config.save({
    invite_code: "INV-2026",
    student_name: "张三",
    group_name: "第 3 组",
    code_dir: dirs.code_dir,
    screenshots_dir: dirs.screenshots_dir,
    results_dir: dirs.results_dir,
  });
  assert.equal(res.status, "complete");
}

function makePlugin(env, server, { clock = makeClock(), hostDialoguePort, uuidgen, onEvent } = {}) {
  let seq = 0;
  return createPlugin({
    storageRoot: env.storageRoot,
    transport: server.transport,
    hostDialoguePort: hostDialoguePort ?? createSpy(async () => dialogueExport()),
    clock,
    uuidgen: uuidgen ?? (() => `uuid-${++seq}`),
    ...(onEvent ? { onEvent } : {}),
  });
}

test("主流程全链：意图→采集→上传→呈现；对话 chunk 为真实导出物；终态清 checkpoint", async (t) => {
  const env = await makeEnv(t);
  const server = createStubServer();
  const dialoguePort = createSpy(async () => dialogueExport());
  const plugin = makePlugin(env, server, { hostDialoguePort: dialoguePort });
  t.after(() => plugin.dispose());
  await saveFullConfig(plugin, env.dirs);

  const result = await plugin.submit(COMMAND);
  assert.equal(result.intake_result, "created");
  const uuid = result.task_ref.submission_uuid;

  const status = plugin.getStatus(uuid);
  assert.equal(status.presentation.status, "completed");
  assert.equal(status.presentation.severity, "success");
  assert.equal(status.presentation.submission_id, `sub-${uuid}`);

  // L10 真实接线：会话 → 分片（对话 + 三材料）→ 合并。
  const phases = server.requests.map((r) => r.body?.phase).filter(Boolean);
  assert.deepEqual(phases, ["create_session", "chunk", "chunk", "chunk", "chunk", "merge"]);
  const dialogueChunk = server.requests.find((r) => r.body?.phase === "chunk" && r.body.chunk?.category === "对话");
  assert.ok(dialogueChunk, "dialogue chunk uploaded");
  assert.deepEqual(JSON.parse(dialogueChunk.body.chunk.content), dialogueExport());
  assert.equal(dialoguePort.calls.length, 1);

  // 终态后 ST-05 checkpoint 已清理。
  const cpNames = await readdir(plugin.paths.checkpoints);
  assert.deepEqual(cpNames, []);
});

test("INV-1：意图缺项 → L13 呈现并中止，不建任务、零网络调用", async (t) => {
  const env = await makeEnv(t);
  const server = createStubServer();
  const plugin = makePlugin(env, server);
  t.after(() => plugin.dispose());
  await saveFullConfig(plugin, env.dirs);

  const result = await plugin.submit("帮我提交一下");
  assert.equal(result.intake_result, "info_incomplete");
  assert.equal(result.task_ref, null);
  assert.deepEqual(result.missing_fields.sort(), ["assignment", "group_name", "student_name"]);
  assert.equal(result.presentation.status, "info_incomplete");
  assert.equal(server.requests.length, 0, "zero network calls");
  assert.deepEqual(plugin.listStatus(), []);
});

test("配置不完整 → L13 配置面呈现并中止，零网络调用", async (t) => {
  const env = await makeEnv(t);
  const server = createStubServer();
  const plugin = makePlugin(env, server);
  t.after(() => plugin.dispose());
  const res = await plugin.config.save({
    invite_code: "INV-2026",
    student_name: "张三",
    group_name: "第 3 组",
    code_dir: "",
    screenshots_dir: env.dirs.screenshots_dir,
    results_dir: env.dirs.results_dir,
  });
  assert.equal(res.status, "incomplete");

  const result = await plugin.submit(COMMAND);
  assert.equal(result.intake_result, "config_unavailable");
  assert.equal(result.presentation.view_type, "config");
  assert.equal(server.requests.length, 0);
});

test("TD-01：host unsupported 显式呈现真实原因，不伪造对话导出物", async (t) => {
  const env = await makeEnv(t);
  const server = createStubServer();
  const unsupported = createSpy(async () => {
    throw new HostUnsupportedError("TD-01: Codex host export mechanism not confirmed");
  });
  const plugin = makePlugin(env, server, { hostDialoguePort: unsupported });
  t.after(() => plugin.dispose());
  await saveFullConfig(plugin, env.dirs);

  const result = await plugin.submit(COMMAND);
  assert.equal(result.intake_result, "created");
  const status = plugin.getStatus(result.task_ref.submission_uuid);
  assert.equal(status.presentation.status, "failed_retryable");
  // 真实原因原样透传（含 HOST_EXPORT_UNSUPPORTED），经 L13 展示。
  assert.ok(status.presentation.failure_reason.includes("HOST_EXPORT_UNSUPPORTED"));
  assert.ok(status.presentation.failure_reason.includes("dialogue export unsupported"));
  assert.ok(status.text.includes("unsupported"));
  // 不伪造：没有任何上传请求（无对话 chunk、无导出物）。
  assert.equal(server.requests.length, 0);
  // missing_items 不得被静默改写为「对话缺失」类别。
  assert.ok(!status.presentation.missing_items.includes("dialogue"));
});

test("断网恢复：checkpoint 文件跨进程复用，采集不重做（INV-4），uuid 不变（INV-2）", async (t) => {
  const env = await makeEnv(t);
  const clock = makeClock();
  let epoch = 1;
  const server = createStubServer({
    override: (req) => {
      if (epoch === 1 && req.body?.phase === "chunk" && req.body.chunk_index === 1) {
        throw new Error("network down"); // 断网：chunk 0 已 ack，chunk 1 失败
      }
      return undefined;
    },
  });

  // epoch 1：首次提交，上传中断。
  const uuid = "uuid-recover-1";
  const dialogue1 = createSpy(async () => dialogueExport());
  const plugin1 = makePlugin(env, server, { clock, hostDialoguePort: dialogue1, uuidgen: () => uuid });
  await saveFullConfig(plugin1, env.dirs);
  const r1 = await plugin1.submit(COMMAND);
  assert.equal(r1.task_ref.submission_uuid, uuid);
  assert.equal(plugin1.getStatus(uuid).presentation.status, "failed_retryable");

  // checkpoint 文件已落盘：chunk 0 已确认。
  const cp = await plugin1.checkpointStore.load(uuid);
  assert.equal(cp.upload_session_id, `sess-${uuid}`);
  assert.deepEqual(cp.confirmed_chunks, [0]);
  await plugin1.dispose();
  const epoch1Requests = server.requests.length;

  // epoch 2：模拟进程重启（新实例、同 storageRoot），恢复。
  epoch = 2;
  clock.advance(31_000); // 越过退避（30s）
  const dialogue2 = createSpy(async () => dialogueExport());
  const plugin2 = makePlugin(env, server, { clock, hostDialoguePort: dialogue2, uuidgen: () => uuid });
  t.after(() => plugin2.dispose());
  await plugin2.recover();

  const status = plugin2.getStatus(uuid);
  assert.equal(status.presentation.status, "completed");
  assert.equal(status.presentation.submission_id, `sub-${uuid}`);

  const epoch2Requests = server.requests.slice(epoch1Requests);
  // 会话复用（不重复 create_session）；已确认分片不重传。
  assert.equal(epoch2Requests.filter((r) => r.body?.phase === "create_session").length, 0);
  assert.deepEqual(
    epoch2Requests.filter((r) => r.body?.phase === "chunk").map((r) => r.body.chunk_index),
    [1, 2, 3],
  );
  assert.equal(epoch2Requests.filter((r) => r.body?.phase === "merge").length, 1);
  // INV-4：采集快照重传不重采（对话/材料端口零调用）。
  assert.equal(dialogue2.calls.length, 0);
  assert.equal(dialogue1.calls.length, 1);
  // 完成后 checkpoint 文件已清理。
  assert.equal(await plugin2.checkpointStore.load(uuid), null);
});

test("IC-PQ-004：cleanupTerminal 清理超期终态 + 归档；recover 后无残留", async (t) => {
  const env = await makeEnv(t);
  const server = createStubServer();
  const clock = makeClock();
  const events = [];
  const uuid = "uuid-cleanup-1";

  const plugin1 = makePlugin(env, server, {
    clock,
    uuidgen: () => uuid,
    onEvent: (e) => events.push(e),
  });
  await saveFullConfig(plugin1, env.dirs);
  await plugin1.submit(COMMAND);
  assert.equal(plugin1.getStatus(uuid).presentation.status, "completed");
  await plugin1.dispose();

  // 冷态（init 之前）执行清理：31 天后超期。
  clock.advance(31 * DAY_MS);
  const plugin2 = makePlugin(env, server, { clock, uuidgen: () => uuid, onEvent: (e) => events.push(e) });
  t.after(() => plugin2.dispose());
  const summary = await plugin2.cleanupTerminal();
  assert.equal(summary.removed_count, 1);
  assert.deepEqual(summary.removed[0].submission_uuid, uuid);
  assert.equal(summary.removed[0].terminal_state, "completed");

  const archived = JSON.parse(await readFile(path.join(plugin2.paths.archive, `${uuid}.json`), "utf8"));
  assert.equal(archived.submission_uuid, uuid);
  assert.equal(archived.terminal_state, "completed");
  assert.ok(events.some((e) => e.event === "PendingQueueCleanupCompleted" && e.removed_count === 1));

  await plugin2.recover();
  assert.deepEqual(plugin2.listStatus(), []);
});
