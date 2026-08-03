/**
 * L07 CMP-DIALOGUE-COLLECTOR 测试 — 全部使用合成 rollout fixture。
 *
 * 授权纪律：本文件只读写测试自建临时目录中的合成 JSONL；
 * 绝不读取任何真实用户会话文件（含本机 ~/.codex）。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";

import {
  DIALOGUE_COLLECTOR_ERROR_CODES,
  DialogueCollectorError,
  createDialogueCollector,
  exportDialogue,
} from "../src/dialogue_collector/index.js";
import { validateDialogueExport } from "../src/host/dialogue-export-port.js";

const SESSION_UUID_A = "11111111-2222-3333-4444-555555555555";
const SESSION_UUID_B = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

async function makeTempRoot(t) {
  const dir = await mkdtemp(path.join(os.tmpdir(), "l07-dialogue-test-"));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  return dir;
}

/** 在 <root>/YYYY/MM/DD/ 下写一个合成 rollout 文件，返回绝对路径。 */
async function writeRollout(root, { dateDirs = ["2026", "07", "20"], ts = "2026-07-20T09-15-30", uuid = SESSION_UUID_A, lines }) {
  const dir = path.join(root, ...dateDirs);
  await mkdir(dir, { recursive: true });
  const file = path.join(dir, `rollout-${ts}-${uuid}.jsonl`);
  await writeFile(file, lines.join("\n") + "\n", "utf-8");
  return file;
}

function metaLine(uuid = SESSION_UUID_A) {
  return JSON.stringify({
    timestamp: "2026-07-20T09:15:30.000Z",
    type: "session_meta",
    payload: { id: uuid, timestamp: "2026-07-20T09:15:30.000Z", cli_version: "0.144.1-test" },
  });
}

function messageLine(role, text, { partType, timestamp = "2026-07-20T09:16:00.000Z" } = {}) {
  const type = partType ?? (role === "assistant" ? "output_text" : "input_text");
  return JSON.stringify({
    timestamp,
    type: "response_item",
    payload: { type: "message", role, content: [{ type, text }] },
  });
}

const FIXED_NOW = "2026-07-22T00:00:00.000Z";
const fixedClock = () => FIXED_NOW;

function standardLines() {
  return [
    metaLine(),
    messageLine("user", "请帮我完成本次作业的第一题"),
    messageLine("assistant", "好的，先看一下题目要求。"),
    JSON.stringify({
      timestamp: "2026-07-20T09:17:00.000Z",
      type: "response_item",
      payload: { type: "function_call", name: "shell", arguments: "{\"cmd\":\"ls\"}" },
    }),
    JSON.stringify({
      timestamp: "2026-07-20T09:17:05.000Z",
      type: "response_item",
      payload: { type: "function_call_output", call_id: "call-1", output: "src\ntest" },
    }),
  ];
}

test("完整导出：标准会话导出为合法 DialogueExport，内容不截断不虚构", async (t) => {
  const root = await makeTempRoot(t);
  const file = await writeRollout(root, { lines: standardLines() });

  const doc = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });

  const verdict = validateDialogueExport(doc);
  assert.deepEqual(verdict.errors, []);
  assert.equal(doc.format_version, "1");
  assert.equal(doc.source_host, "codex-cli");
  assert.equal(doc.exported_at, FIXED_NOW);
  assert.equal(doc.turns.length, 4);
  assert.deepEqual(
    doc.turns.map((x) => x.role),
    ["user", "assistant", "tool", "tool"],
  );
  assert.equal(doc.turns[0].content, "请帮我完成本次作业的第一题");
  assert.equal(doc.turns[1].content, "好的，先看一下题目要求。");
  // 工具轮次完整保留 name/arguments 与 output（可解析即未截断未改写）。
  assert.deepEqual(JSON.parse(doc.turns[2].content), { name: "shell", arguments: "{\"cmd\":\"ls\"}" });
  assert.deepEqual(JSON.parse(doc.turns[3].content), { call_id: "call-1", output: "src\ntest" });
  assert.equal(doc.source.session_id, SESSION_UUID_A);
  assert.equal(doc.source.rollout_file, path.relative(root, file).split(path.sep).join("/"));
  assert.deepEqual(doc.source.candidates, [doc.source.selected]);
  assert.equal(doc.source.cli_version, "0.144.1-test");
});

test("turns 顺序保持与角色映射（developer→system；协议记录跳过不计截断）", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, {
    lines: [
      metaLine(),
      messageLine("developer", "你是编程助教", { partType: "input_text" }),
      messageLine("system", "环境已就绪", { partType: "input_text" }),
      messageLine("user", "第一问"),
      JSON.stringify({
        timestamp: "2026-07-20T09:16:30.000Z",
        type: "response_item",
        payload: { type: "reasoning", summary: [] },
      }),
      messageLine("assistant", "第一答"),
      JSON.stringify({ timestamp: "2026-07-20T09:16:45.000Z", type: "turn_context", payload: {} }),
    ],
  });

  const doc = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });
  assert.deepEqual(
    doc.turns.map((x) => [x.role, x.content]),
    [
      ["system", "你是编程助教"],
      ["system", "环境已就绪"],
      ["user", "第一问"],
      ["assistant", "第一答"],
    ],
  );
  assert.equal(doc.source.records_skipped, 2); // reasoning + turn_context
  assert.equal(doc.turns[0].timestamp, "2026-07-20T09:16:00.000Z");
});

test("多 content 分片无损拼接（不插字符、不丢分片）", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, {
    lines: [
      metaLine(),
      JSON.stringify({
        timestamp: "2026-07-20T09:16:00.000Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [
            { type: "output_text", text: "片段一：" },
            { type: "output_text", text: "片段二" },
          ],
        },
      }),
    ],
  });
  const doc = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });
  assert.equal(doc.turns[0].content, "片段一：片段二");
});

test("快照 sha256 稳定（INV-4）：同一源文件重导哈希一致且等于文件内容哈希", async (t) => {
  const root = await makeTempRoot(t);
  const file = await writeRollout(root, { lines: standardLines() });

  const first = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });
  const second = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });
  assert.equal(first.snapshot_sha256, second.snapshot_sha256);

  const raw = await readFile(file, "utf-8");
  const expected = createHash("sha256").update(raw, "utf-8").digest("hex");
  assert.equal(first.snapshot_sha256, expected);
});

test("选择器歧义显式报告：多候选取最新，candidates 全量记录", async (t) => {
  const root = await makeTempRoot(t);
  const older = await writeRollout(root, {
    ts: "2026-07-19T08-00-00",
    uuid: SESSION_UUID_A,
    dateDirs: ["2026", "07", "19"],
    lines: [metaLine(SESSION_UUID_A), messageLine("user", "旧会话")],
  });
  await writeRollout(root, {
    ts: "2026-07-20T09-15-30",
    uuid: SESSION_UUID_B,
    dateDirs: ["2026", "07", "20"],
    lines: [metaLine(SESSION_UUID_B), messageLine("user", "新会话")],
  });

  const doc = await exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock });
  assert.equal(doc.source.session_id, SESSION_UUID_B);
  assert.equal(doc.turns[0].content, "新会话");
  assert.equal(doc.source.candidates.length, 2);
  assert.ok(doc.source.candidates.includes(doc.source.selected));
  assert.ok(
    doc.source.candidates.includes(path.relative(root, older).split(path.sep).join("/")),
  );

  // sessionId 精确过滤可命中旧会话。
  const byId = await exportDialogue({
    sessionsRoot: root,
    sessionSelector: { sessionId: SESSION_UUID_A },
    now: fixedClock,
  });
  assert.equal(byId.source.session_id, SESSION_UUID_A);
  assert.equal(byId.turns[0].content, "旧会话");
  assert.deepEqual(byId.source.candidates, [byId.source.selected]);
});

test("since/until 区间过滤；区间外无匹配 → DIALOGUE_SESSION_NOT_FOUND", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, { lines: standardLines() });

  const inRange = await exportDialogue({
    sessionsRoot: root,
    sessionSelector: { since: "2026-07-20T00:00:00Z", until: "2026-07-21T00:00:00Z" },
    now: fixedClock,
  });
  assert.equal(inRange.turns.length, 4);

  await assert.rejects(
    exportDialogue({
      sessionsRoot: root,
      sessionSelector: { since: "2026-07-21T00:00:00Z" },
      now: fixedClock,
    }),
    (err) => {
      assert.ok(err instanceof DialogueCollectorError);
      assert.equal(err.code, "DIALOGUE_SESSION_NOT_FOUND");
      return true;
    },
  );
});

test("越界路径拒绝：sessionId 路径穿越被拒绝；符号链接目录不跟随", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, { lines: standardLines() });

  for (const evil of ["../../etc/passwd", "..\\..\\secret", "not-a-uuid"]) {
    await assert.rejects(
      exportDialogue({ sessionsRoot: root, sessionSelector: { sessionId: evil }, now: fixedClock }),
      (err) => {
        assert.equal(err.code, "DIALOGUE_SELECTOR_INVALID");
        return true;
      },
    );
  }

  // 根内符号链接目录（fs 注入模拟 Dirent）：不跟随、不进入，绝不越界读取。
  const fakeDirent = (name, kind) => ({
    name,
    isSymbolicLink: () => kind === "symlink",
    isDirectory: () => kind === "dir",
    isFile: () => kind === "file",
  });
  let symlinkEntered = false;
  const fakeFs = {
    readdir: async (dir) => {
      if (dir === path.resolve(root)) return [fakeDirent("linked-outside", "symlink")];
      symlinkEntered = true; // 跟随符号链接才会走到这里
      return [];
    },
    readFile: async () => {
      throw new Error("must never read outside sessionsRoot");
    },
  };
  await assert.rejects(
    exportDialogue({
      sessionsRoot: root,
      sessionSelector: { sessionId: SESSION_UUID_B },
      fs: fakeFs,
      now: fixedClock,
    }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SESSION_NOT_FOUND");
      return true;
    },
  );
  assert.equal(symlinkEntered, false);
});

test("空会话显式失败：零字节文件与无对话轮次均 DIALOGUE_SESSION_EMPTY", async (t) => {
  const root = await makeTempRoot(t);
  const dir = path.join(root, "2026", "07", "20");
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, `rollout-2026-07-20T09-15-30-${SESSION_UUID_A}.jsonl`), "", "utf-8");

  await assert.rejects(
    exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SESSION_EMPTY");
      return true;
    },
  );

  const root2 = await makeTempRoot(t);
  await writeRollout(root2, { lines: [metaLine()] }); // 只有元数据、无对话轮次
  await assert.rejects(
    exportDialogue({ sessionsRoot: root2, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SESSION_EMPTY");
      return true;
    },
  );
});

test("会话元数据缺失显式失败：DIALOGUE_METADATA_MISSING", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, { lines: [messageLine("user", "没有 meta 的会话")] });
  await assert.rejects(
    exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_METADATA_MISSING");
      return true;
    },
  );
});

test("会话根不存在显式失败：DIALOGUE_SESSION_NOT_FOUND", async (t) => {
  const root = await makeTempRoot(t);
  await assert.rejects(
    exportDialogue({
      sessionsRoot: path.join(root, "no-such-dir"),
      sessionSelector: {},
      now: fixedClock,
    }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SESSION_NOT_FOUND");
      return true;
    },
  );
});

test("JSONL 损坏显式失败：DIALOGUE_EXPORT_FAILED，错误消息不含会话正文", async (t) => {
  const root = await makeTempRoot(t);
  const secret = "这行正文绝不能出现在错误消息里";
  await writeRollout(root, { lines: [metaLine(), messageLine("user", "ok"), `{"broken": ${secret}`] });
  await assert.rejects(
    exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_EXPORT_FAILED");
      assert.ok(!err.message.includes(secret));
      assert.ok(err.message.includes("line 3"));
      return true;
    },
  );
});

test("不可映射角色/空消息 fail closed：DIALOGUE_SNAPSHOT_INVALID（不虚构、不静默跳过）", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, { lines: [metaLine(), messageLine("ghost", "未知角色")] });
  await assert.rejects(
    exportDialogue({ sessionsRoot: root, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SNAPSHOT_INVALID");
      return true;
    },
  );

  const root2 = await makeTempRoot(t);
  await writeRollout(root2, { lines: [metaLine(), messageLine("user", "")] });
  await assert.rejects(
    exportDialogue({ sessionsRoot: root2, sessionSelector: {}, now: fixedClock }),
    (err) => {
      assert.equal(err.code, "DIALOGUE_SNAPSHOT_INVALID");
      return true;
    },
  );
});

test("createDialogueCollector：L11 端口形状，产物过 validateDialogueExport", async (t) => {
  const root = await makeTempRoot(t);
  await writeRollout(root, { lines: standardLines() });

  const collector = createDialogueCollector({ sessionsRoot: root, now: fixedClock });
  const artifact = await collector.collectDialogue({
    submission_uuid: "sub-uuid-1",
    intent: { assignment: "A1", student_name: "s", group_name: "g" },
    config_ref: {},
  });
  const verdict = validateDialogueExport(artifact);
  assert.deepEqual(verdict.errors, []);
  assert.equal(artifact.source_host, "codex-cli");
  assert.equal(typeof artifact.snapshot_sha256, "string");

  // selectSession 按任务推导选择器。
  const scoped = createDialogueCollector({
    sessionsRoot: root,
    selectSession: (taskRef) => ({ sessionId: taskRef.intent.session_uuid }),
    now: fixedClock,
  });
  const scopedArtifact = await scoped.collectDialogue({
    submission_uuid: "sub-uuid-2",
    intent: { session_uuid: SESSION_UUID_A },
  });
  assert.equal(scopedArtifact.source.session_id, SESSION_UUID_A);
});

test("createDialogueCollector：缺 submission_uuid 拒绝采集（INV-DLG-1）；失败显式传播不静默", async (t) => {
  const root = await makeTempRoot(t);
  const collector = createDialogueCollector({ sessionsRoot: root, now: fixedClock });

  await assert.rejects(collector.collectDialogue({}), (err) => {
    assert.equal(err.code, "DIALOGUE_TASK_REF_INVALID");
    return true;
  });

  // 无匹配会话：稳定错误码抛出（L11 据此记 DIALOGUE_EXPORT_FAILED，绝不转为「对话缺失」）。
  await assert.rejects(
    collector.collectDialogue({ submission_uuid: "sub-uuid-3" }),
    (err) => {
      assert.ok(err instanceof DialogueCollectorError);
      assert.equal(err.code, "DIALOGUE_SESSION_NOT_FOUND");
      assert.ok(DIALOGUE_COLLECTOR_ERROR_CODES.includes(err.code));
      return true;
    },
  );
});

test("错误码稳定性：全部导出错误码冻结且去重", () => {
  assert.equal(Object.isFrozen(DIALOGUE_COLLECTOR_ERROR_CODES), true);
  assert.equal(new Set(DIALOGUE_COLLECTOR_ERROR_CODES).size, DIALOGUE_COLLECTOR_ERROR_CODES.length);
});
