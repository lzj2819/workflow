/**
 * T-B04 / IC-PQ-004 — 终态任务保留期清理协调（L11 同叶子新增模块）。
 *
 * 语义（IC-PQ-004）：
 * - completed / failed_terminal 任务超过保留期（retentionDays，默认 30 天可配）
 *   从持久化 envelope（ST-PQ-05 StateStoreEnvelope）移除；
 * - 审计先行：移除前先落终态摘要到 archive/（每任务一文件，原子写），
 *   摘要只含 submission_uuid / terminal_state / terminal_at / archived_at，
 *   绝不包含材料快照 / bundle_ref / 对话内容；
 * - 进行中任务（created/collecting/queued/uploading/failed_retryable/
 *   confirm_required）绝不删除；未超期终态保留；
 * - 清理计数可观测：onEvent 发出结构化事件 + 返回清理摘要；
 * - 只消费 L11 公开形状（state-store envelope / task-machine 终态枚举），
 *   不改动 L11 既有实现。
 *
 * 协调约束（重要）：envelope 由 L11 队列单写。本函数读写同一 envelope，
 * 必须在队列冷态执行（进程启动后、queue.init() 之前，或队列 dispose 之后），
 * 否则存活队列的下一次 persist 会用内存态覆盖清理结果。
 */

import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import { TERMINAL_STATES } from "./task-machine.js";

export const DEFAULT_RETENTION_DAYS = 30;
const DAY_MS = 86_400_000;

export const CLEANUP_ERROR_CODES = Object.freeze([
  "CLEANUP_STORE_MISSING",
  "CLEANUP_ARCHIVE_FAILED",
  "CLEANUP_PERSIST_FAILED",
]);

/** 清理协调可诊断错误（code 定位原因；不静默降级）。 */
export class CleanupError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "CleanupError";
    this.code = code;
    this.reason = reason;
  }
}

let tmpSeq = 0;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** 任务记录进入终态的时刻：history 最后一项 at，回退 updated_at。 */
function terminalAtOf(record) {
  if (Array.isArray(record?.history) && record.history.length > 0) {
    const last = record.history[record.history.length - 1];
    if (typeof last?.at === "string" && !Number.isNaN(Date.parse(last.at))) return last.at;
  }
  if (typeof record?.updated_at === "string" && !Number.isNaN(Date.parse(record.updated_at))) {
    return record.updated_at;
  }
  return null;
}

/** 原子写一个终态摘要文件（tmp + rename；摘要绝不含材料快照）。 */
async function writeArchiveSummary(archiveDir, summary) {
  const filePath = path.join(archiveDir, `${summary.submission_uuid}.json`);
  const tmpPath = `${filePath}.tmp-${process.pid}-${++tmpSeq}`;
  try {
    await mkdir(archiveDir, { recursive: true });
    await writeFile(tmpPath, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
    await rename(tmpPath, filePath);
  } catch (err) {
    throw new CleanupError(
      "CLEANUP_ARCHIVE_FAILED",
      `cannot write archive summary ${filePath}: ${err?.message ?? String(err)}`,
    );
  }
  return filePath;
}

/**
 * 执行 IC-PQ-004 终态清理。
 *
 * @param {Object} deps
 * @param {Object} deps.store          L11 envelope 存储（createStateStore 形状 {load, save}）
 * @param {string} deps.archiveDir     终态摘要归档目录（archive/）
 * @param {number} deps.now            当前时刻（epoch ms，注入时钟）
 * @param {number} [deps.retentionDays] 终态保留天数（默认 30，可配）
 * @param {Object} [deps.queue]        可选存活队列实例（仅作防御性交叉核对；
 *   清理以 envelope 为权威，须冷态执行，见文件头注释）
 * @param {(event: Object) => void} [deps.onEvent] 结构化事件（清理计数可观测）
 * @returns {Promise<{scanned: number, terminal_total: number, removed_count: number,
 *   retained_terminal_count: number, removed: Object[], archive_files: string[]}>}
 */
export async function runCleanup({
  store,
  archiveDir,
  now,
  retentionDays = DEFAULT_RETENTION_DAYS,
  queue = null,
  onEvent = () => {},
} = {}) {
  if (!isPlainObject(store) || typeof store.load !== "function" || typeof store.save !== "function") {
    throw new CleanupError("CLEANUP_STORE_MISSING", "store with {load, save} is required");
  }
  if (typeof archiveDir !== "string" || archiveDir.trim() === "") {
    throw new CleanupError("CLEANUP_STORE_MISSING", "archiveDir must be a non-empty string");
  }
  if (typeof now !== "number" || !Number.isFinite(now)) {
    throw new CleanupError("CLEANUP_STORE_MISSING", "now must be a finite epoch-ms number");
  }
  if (typeof retentionDays !== "number" || !(retentionDays > 0)) {
    throw new CleanupError("CLEANUP_STORE_MISSING", "retentionDays must be a positive number");
  }
  const retentionMs = retentionDays * DAY_MS;

  const envelope = await store.load(); // 损坏 → StateCorruptError 原样传播（可诊断）
  const tasks = isPlainObject(envelope.tasks) ? envelope.tasks : {};
  const commandIndex = isPlainObject(envelope.command_index) ? envelope.command_index : {};
  const triggers = Array.isArray(envelope.triggers) ? envelope.triggers : [];

  const entries = Object.entries(tasks);
  const expired = [];
  let terminalTotal = 0;

  for (const [uuid, record] of entries) {
    if (!isPlainObject(record) || !TERMINAL_STATES.includes(record.state)) continue; // 进行中绝不删
    terminalTotal += 1;
    const terminalAt = terminalAtOf(record);
    if (terminalAt === null) continue; // 时间不可判定：保守保留，不猜
    if (now - Date.parse(terminalAt) > retentionMs) {
      expired.push({ uuid, record, terminal_at: terminalAt });
    }
  }

  // 防御性交叉核对：存活队列内存态仍视该任务为非终态时不得移除。
  if (queue !== null && typeof queue.getTask === "function") {
    for (let i = expired.length - 1; i >= 0; i -= 1) {
      const live = queue.getTask(expired[i].uuid);
      if (live && !TERMINAL_STATES.includes(live.state)) expired.splice(i, 1);
    }
  }

  // 审计先行：先落全部终态摘要（uuid/终态/时间，无材料快照），再改 envelope。
  const removed = [];
  const archiveFiles = [];
  const archivedAt = new Date(now).toISOString();
  for (const { uuid, record, terminal_at } of expired) {
    const summary = {
      submission_uuid: uuid,
      terminal_state: record.state,
      terminal_at,
      archived_at: archivedAt,
    };
    archiveFiles.push(await writeArchiveSummary(archiveDir, summary));
    removed.push(summary);
  }

  if (removed.length > 0) {
    const removedUuids = new Set(removed.map((s) => s.submission_uuid));
    const nextTasks = {};
    for (const [uuid, record] of entries) {
      if (!removedUuids.has(uuid)) nextTasks[uuid] = record;
    }
    const nextCommandIndex = {};
    for (const [commandId, uuid] of Object.entries(commandIndex)) {
      if (!removedUuids.has(uuid)) nextCommandIndex[commandId] = uuid;
    }
    try {
      await store.save({ tasks: nextTasks, command_index: nextCommandIndex, triggers });
    } catch (err) {
      throw new CleanupError(
        "CLEANUP_PERSIST_FAILED",
        `cannot persist cleaned envelope: ${err?.message ?? String(err)}`,
      );
    }
  }

  const summary = {
    scanned: entries.length,
    terminal_total: terminalTotal,
    removed_count: removed.length,
    retained_terminal_count: terminalTotal - removed.length,
    removed,
    archive_files: archiveFiles,
  };
  // 可观测：清理计数（不含任何材料/配置明文）。
  onEvent({
    event: "PendingQueueCleanupCompleted",
    scanned: summary.scanned,
    terminal_total: summary.terminal_total,
    removed_count: summary.removed_count,
    retained_terminal_count: summary.retained_terminal_count,
    retention_days: retentionDays,
  });
  return summary;
}
