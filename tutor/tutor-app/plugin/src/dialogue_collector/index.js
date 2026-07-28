/**
 * L07 CMP-DIALOGUE-COLLECTOR — 完整 Codex 对话导出（REQ-DD003 / REQ-003；DU-1）。
 *
 * TD-01 已解除（D-1 选 A，2026-07-22）：宿主机制为 Codex 会话回放文件
 *   ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl
 * （codex resume 同一数据源；codex-cli 0.144.1 实测存在）。本模块是该数据源的
 * 采集侧 ACL（CMP-DLG-HOST-ADAPTER + SNAPSHOT-VALIDATOR 的实现面）。
 *
 * 行为要点：
 * - sessionsRoot 可配置（默认 ~/.codex/sessions）；只读该根以内路径，
 *   不跟随符号链接，越界即显式拒绝（DIALOGUE_PATH_OUTSIDE_ROOT）；
 * - sessionSelector { sessionId?, since?, until? }：按 rollout 文件名
 *   时间戳/uuid 过滤；多候选取最新，全部候选记入 source.candidates（显式报告）；
 * - rollout JSONL → DialogueExport（对齐 src/host/dialogue-export-port.js）：
 *   message（user/assistant/system；developer→system）与 function_call /
 *   function_call_output（→tool）为对话轮次，顺序保持、内容不截断、不虚构；
 *   reasoning / turn_context / event_msg 等协议性记录不是对话正文，跳过并计数
 *   （source.records_skipped），不计为截断；
 * - 完整性：session_meta 行必须存在；turns 非空；导出物携带源文件
 *   snapshot_sha256（INV-4：同一源文件重导哈希稳定，快照重传不重采）；
 * - 失败显式化：会话不存在/不可读/为空/缺元数据/解析失败均以稳定错误码抛出，
 *   绝不静默转为「对话缺失」、绝不伪造导出物（LCD-DLG-003 fail closed）；
 * - 会话内容不写日志；错误消息只含路径/行号/类别，不含会话正文。
 *
 * 零运行时依赖；Node ESM。不实现：材料采集（L06）、队列编排（L11）、上传（L10）。
 */

import { createHash } from "node:crypto";
import os from "node:os";
import path from "node:path";
import { readdir, readFile } from "node:fs/promises";

import { validateDialogueExport } from "../host/dialogue-export-port.js";

/** 本层稳定错误码（失败显式化；L11 按任务书语义映射为采集失败原因）。 */
export const DIALOGUE_COLLECTOR_ERROR_CODES = Object.freeze([
  "DIALOGUE_ROOT_INVALID",
  "DIALOGUE_SELECTOR_INVALID",
  "DIALOGUE_TASK_REF_INVALID",
  "DIALOGUE_PATH_OUTSIDE_ROOT",
  "DIALOGUE_SESSION_NOT_FOUND",
  "DIALOGUE_SESSION_UNREADABLE",
  "DIALOGUE_SESSION_EMPTY",
  "DIALOGUE_METADATA_MISSING",
  "DIALOGUE_EXPORT_FAILED",
  "DIALOGUE_SNAPSHOT_INVALID",
]);

/** 对话采集失败（code 定位原因；reason 不含会话正文）。 */
export class DialogueCollectorError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "DialogueCollectorError";
    this.code = code;
    this.reason = reason;
  }
}

function fail(code, reason) {
  throw new DialogueCollectorError(code, reason);
}

/** codex rollout 文件名：rollout-YYYY-MM-DDTHH-MM-SS-<uuid>.jsonl */
export const ROLLOUT_FILENAME_RE =
  /^rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jsonl$/;

const UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

/** 遍历防御上限：正常布局为 root/YYYY/MM/DD（3 层）。 */
const MAX_WALK_DEPTH = 8;

/** 默认会话根（调用时求值，便于测试隔离；不读取任何真实会话内容）。 */
export function defaultSessionsRoot() {
  return path.join(os.homedir(), ".codex", "sessions");
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function toPosix(p) {
  return p.split(path.sep).join("/");
}

/** 只读 sessionsRoot 以内路径：每次读取前的词法越界守卫。 */
function assertWithinRoot(resolvedRoot, absPath) {
  const rel = path.relative(resolvedRoot, absPath);
  if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) {
    fail("DIALOGUE_PATH_OUTSIDE_ROOT", "refusing to read outside sessionsRoot");
  }
}

/** 文件名时间戳转可比较值（仅用于排序/区间过滤，不作为 turn 时间）。 */
function filenameTsToMs(ts) {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})$/.exec(ts);
  if (!m) return null;
  const ms = Date.parse(`${m[1]}T${m[2]}:${m[3]}:${m[4]}Z`);
  return Number.isNaN(ms) ? null : ms;
}

function validateSelector(selector) {
  if (!isPlainObject(selector)) {
    fail("DIALOGUE_SELECTOR_INVALID", "sessionSelector must be an object");
  }
  const { sessionId, since, until } = selector;
  if (sessionId !== undefined) {
    // sessionId 仅作为 uuid 过滤器，绝不允许被当作路径片段（防越界）。
    if (typeof sessionId !== "string" || !UUID_RE.test(sessionId)) {
      fail(
        "DIALOGUE_SELECTOR_INVALID",
        "sessionSelector.sessionId must be a session uuid (path fragments rejected)",
      );
    }
  }
  let sinceMs = null;
  let untilMs = null;
  if (since !== undefined) {
    sinceMs = Date.parse(since);
    if (typeof since !== "string" || Number.isNaN(sinceMs)) {
      fail("DIALOGUE_SELECTOR_INVALID", "sessionSelector.since must be an ISO8601 timestamp");
    }
  }
  if (until !== undefined) {
    untilMs = Date.parse(until);
    if (typeof until !== "string" || Number.isNaN(untilMs)) {
      fail("DIALOGUE_SELECTOR_INVALID", "sessionSelector.until must be an ISO8601 timestamp");
    }
  }
  if (sinceMs !== null && untilMs !== null && sinceMs > untilMs) {
    fail("DIALOGUE_SELECTOR_INVALID", "sessionSelector.since must not be after until");
  }
  return {
    sessionId: sessionId !== undefined ? sessionId.toLowerCase() : null,
    sinceMs,
    untilMs,
  };
}

/**
 * 在 sessionsRoot 内枚举 rollout 文件（只进目录、不跟随符号链接）。
 * @returns {Promise<Array<{abs: string, rel: string, ts: string, tsMs: number|null, uuid: string}>>}
 */
async function findRolloutFiles(resolvedRoot, fsImpl) {
  const found = [];
  async function walk(dir, depth) {
    if (depth > MAX_WALK_DEPTH) return;
    let entries;
    try {
      entries = await fsImpl.readdir(dir, { withFileTypes: true });
    } catch (err) {
      if (depth === 0 && (err?.code === "ENOENT" || err?.code === "ENOTDIR")) {
        fail("DIALOGUE_SESSION_NOT_FOUND", "sessions root not found or not a directory");
      }
      fail(
        "DIALOGUE_SESSION_UNREADABLE",
        `sessions directory unreadable (${err?.code ?? "unknown"})`,
      );
    }
    for (const entry of entries) {
      if (entry.isSymbolicLink()) continue; // 不跟随符号链接：防越出 sessionsRoot
      const abs = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(abs, depth + 1);
        continue;
      }
      if (!entry.isFile()) continue;
      const m = ROLLOUT_FILENAME_RE.exec(entry.name);
      if (m) {
        found.push({
          abs,
          rel: toPosix(path.relative(resolvedRoot, abs)),
          ts: m[1],
          tsMs: filenameTsToMs(m[1]),
          uuid: m[2].toLowerCase(),
        });
      }
    }
  }
  await walk(resolvedRoot, 0);
  return found;
}

/** 按选择器过滤；多候选按时间戳降序（并列按相对路径升序，确定性）。 */
function selectCandidate(files, sel) {
  const matched = files.filter((f) => {
    if (sel.sessionId !== null && f.uuid !== sel.sessionId) return false;
    if (sel.sinceMs !== null && (f.tsMs === null || f.tsMs < sel.sinceMs)) return false;
    if (sel.untilMs !== null && (f.tsMs === null || f.tsMs > sel.untilMs)) return false;
    return true;
  });
  matched.sort((a, b) => {
    if (a.ts !== b.ts) return a.ts < b.ts ? 1 : -1;
    return a.rel < b.rel ? -1 : a.rel > b.rel ? 1 : 0;
  });
  return matched;
}

function mapMessageRole(role) {
  switch (role) {
    case "user":
    case "assistant":
    case "system":
      return role;
    case "developer": // codex 指令消息；归入 system 槽位
      return "system";
    default:
      return null;
  }
}

/** message payload → 完整文本（content 分片按原序无损拼接，不插字符、不截断）。 */
function messageText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return null;
  const parts = [];
  for (const part of content) {
    if (typeof part?.text === "string") parts.push(part.text);
  }
  return parts.length > 0 ? parts.join("") : null;
}

/**
 * rollout JSONL → turns + session 元数据。
 * 协议性记录（reasoning/turn_context/event_msg/其他未知类型）跳过并计数。
 */
function parseRollout(raw) {
  const lines = raw.split(/\r?\n/);
  let meta = null;
  const turns = [];
  let recordsTotal = 0;
  let recordsSkipped = 0;

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (trimmed === "") return;
    recordsTotal += 1;
    let record;
    try {
      record = JSON.parse(trimmed);
    } catch {
      // 错误消息只带行号，不带行内容（会话正文不进日志/错误）。
      fail("DIALOGUE_EXPORT_FAILED", `rollout JSONL parse failed at line ${idx + 1}`);
    }
    if (!isPlainObject(record)) {
      fail("DIALOGUE_EXPORT_FAILED", `rollout record at line ${idx + 1} is not an object`);
    }

    const recordType = record.type;
    const payload = isPlainObject(record.payload) ? record.payload : null;
    if (recordType === "session_meta" || payload?.type === "session_meta") {
      meta = payload ?? record;
      return;
    }

    const timestamp =
      typeof record.timestamp === "string" && !Number.isNaN(Date.parse(record.timestamp))
        ? record.timestamp
        : null;

    if (recordType !== "response_item" || payload === null) {
      recordsSkipped += 1;
      return;
    }

    switch (payload.type) {
      case "message": {
        const role = mapMessageRole(payload.role);
        if (role === null) {
          fail(
            "DIALOGUE_SNAPSHOT_INVALID",
            `unmappable message role at line ${idx + 1} (refusing to fabricate)`,
          );
        }
        const text = messageText(payload.content);
        if (text === null || text === "") {
          fail(
            "DIALOGUE_SNAPSHOT_INVALID",
            `message turn at line ${idx + 1} has no text content (refusing to fabricate)`,
          );
        }
        const turn = { role, content: text };
        if (timestamp !== null) turn.timestamp = timestamp;
        turns.push(turn);
        return;
      }
      case "function_call":
      case "custom_tool_call": {
        if (typeof payload.name !== "string" || payload.name === "") {
          fail("DIALOGUE_SNAPSHOT_INVALID", `tool call at line ${idx + 1} missing name`);
        }
        const args =
          typeof payload.arguments === "string"
            ? payload.arguments
            : typeof payload.input === "string"
              ? payload.input
              : null;
        const turn = { role: "tool", content: JSON.stringify({ name: payload.name, arguments: args }) };
        if (timestamp !== null) turn.timestamp = timestamp;
        turns.push(turn);
        return;
      }
      case "function_call_output":
      case "custom_tool_call_output": {
        const output = payload.output;
        const body =
          typeof output === "string" ? output : output === undefined ? null : JSON.stringify(output);
        const turn = {
          role: "tool",
          content: JSON.stringify({
            call_id: typeof payload.call_id === "string" ? payload.call_id : null,
            output: body,
          }),
        };
        if (timestamp !== null) turn.timestamp = timestamp;
        turns.push(turn);
        return;
      }
      default:
        // reasoning 等非对话正文记录：跳过并计数，不计为截断。
        recordsSkipped += 1;
    }
  });

  return { meta, turns, recordsTotal, recordsSkipped };
}

/**
 * 从 Codex 会话回放文件导出完整对话（DialogueExport 形状）。
 *
 * @param {Object} options
 * @param {string} [options.sessionsRoot]  会话根（默认 ~/.codex/sessions）
 * @param {Object} [options.sessionSelector] { sessionId?, since?, until? }
 * @param {Object} [options.fs]            注入 { readdir, readFile }（测试用）
 * @param {() => string} [options.now]     注入 exported_at 时钟（ISO8601）
 * @returns {Promise<DialogueExport & {snapshot_sha256: string, source: Object}>}
 */
export async function exportDialogue(options = {}) {
  if (!isPlainObject(options)) fail("DIALOGUE_ROOT_INVALID", "options must be an object");
  const sessionsRoot = options.sessionsRoot ?? defaultSessionsRoot();
  if (typeof sessionsRoot !== "string" || sessionsRoot.trim() === "") {
    fail("DIALOGUE_ROOT_INVALID", "sessionsRoot must be a non-empty string");
  }
  const resolvedRoot = path.resolve(sessionsRoot);
  const sel = validateSelector(options.sessionSelector ?? {});
  const fsImpl = {
    readdir: options.fs?.readdir ?? readdir,
    readFile: options.fs?.readFile ?? readFile,
  };
  const now = options.now ?? (() => new Date().toISOString());

  const files = await findRolloutFiles(resolvedRoot, fsImpl);
  const candidates = selectCandidate(files, sel);
  if (candidates.length === 0) {
    fail(
      "DIALOGUE_SESSION_NOT_FOUND",
      "no rollout session matches the selector (nothing fabricated; not a missing-dialogue downgrade)",
    );
  }
  const selected = candidates[0];
  assertWithinRoot(resolvedRoot, selected.abs);

  let raw;
  try {
    raw = await fsImpl.readFile(selected.abs, "utf-8");
  } catch (err) {
    fail(
      "DIALOGUE_SESSION_UNREADABLE",
      `rollout file unreadable: ${selected.rel} (${err?.code ?? "unknown"})`,
    );
  }
  if (raw.trim() === "") {
    fail("DIALOGUE_SESSION_EMPTY", `rollout file is empty: ${selected.rel}`);
  }

  const { meta, turns, recordsTotal, recordsSkipped } = parseRollout(raw);
  if (meta === null) {
    fail("DIALOGUE_METADATA_MISSING", `session_meta record missing in ${selected.rel}`);
  }
  if (turns.length === 0) {
    fail("DIALOGUE_SESSION_EMPTY", `rollout session has no dialogue turns: ${selected.rel}`);
  }

  // INV-4：源文件字节级快照标识；同一文件重导哈希稳定。
  const snapshotSha256 = createHash("sha256").update(raw, "utf-8").digest("hex");

  const exportedAt = now();
  if (typeof exportedAt !== "string" || Number.isNaN(Date.parse(exportedAt))) {
    fail("DIALOGUE_EXPORT_FAILED", "injected clock did not return an ISO8601 timestamp");
  }

  const doc = {
    format_version: "1",
    source_host: "codex-cli",
    exported_at: exportedAt,
    turns,
    snapshot_sha256: snapshotSha256,
    source: {
      host_record_type: "codex-rollout-jsonl",
      session_id: typeof meta.id === "string" ? meta.id : selected.uuid,
      rollout_file: selected.rel,
      cli_version: typeof meta.cli_version === "string" ? meta.cli_version : null,
      candidates: candidates.map((c) => c.rel),
      selected: selected.rel,
      records_total: recordsTotal,
      records_skipped: recordsSkipped,
    },
  };

  // 放行前形状校验（与 host/dialogue-export-port.js 同一权威校验器；fail closed）。
  const verdict = validateDialogueExport(doc);
  if (!verdict.ok) {
    fail("DIALOGUE_SNAPSHOT_INVALID", `export failed port validation: ${verdict.errors.join("; ")}`);
  }
  return doc;
}

/**
 * L11 编排可注入的对话采集端口实现（IC-M01-03 dialogue 分支）。
 *
 * @param {Object} deps
 * @param {string} [deps.sessionsRoot]     会话根（默认 ~/.codex/sessions）
 * @param {Object} [deps.sessionSelector]  静态选择器
 * @param {(taskRef: Object) => Object} [deps.selectSession] 按任务推导选择器（覆盖静态值）
 * @param {Object} [deps.fs]               注入 { readdir, readFile }
 * @param {() => string} [deps.now]        注入时钟（ISO8601）
 * @returns {{collectDialogue: (taskRef: Object) => Promise<Object>}}
 */
export function createDialogueCollector(deps = {}) {
  if (!isPlainObject(deps)) fail("DIALOGUE_ROOT_INVALID", "deps must be an object");
  const selectSession = deps.selectSession ?? null;
  if (selectSession !== null && typeof selectSession !== "function") {
    fail("DIALOGUE_ROOT_INVALID", "deps.selectSession must be a function when provided");
  }

  async function collectDialogue(taskRef) {
    // INV-DLG-1：没有父层 submission_uuid 不得开始采集。
    if (!isPlainObject(taskRef) || typeof taskRef.submission_uuid !== "string" || taskRef.submission_uuid.trim() === "") {
      fail("DIALOGUE_TASK_REF_INVALID", "taskRef.submission_uuid must be a non-empty string");
    }
    const selector = selectSession !== null ? selectSession(taskRef) : (deps.sessionSelector ?? {});
    return exportDialogue({
      sessionsRoot: deps.sessionsRoot,
      sessionSelector: selector,
      ...(deps.fs ? { fs: deps.fs } : {}),
      ...(deps.now ? { now: deps.now } : {}),
    });
  }

  return Object.freeze({ collectDialogue });
}
