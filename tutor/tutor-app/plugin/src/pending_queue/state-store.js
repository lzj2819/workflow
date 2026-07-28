/**
 * L11 CMP-PENDING-QUEUE — STATE-STORE（ST-PQ-05 StateStoreEnvelope）。
 *
 * LCD-004 / A-007 implementation_detail：本机 JSON 文件持久化。
 * 语义承诺（LCD-PQ-003 / PQ-INV-006，不随实现介质改变）：
 * - revision 单调递增，随每次提交 +1；
 * - checksum（sha256，稳定序列化）校验 envelope 完整性；
 * - 原子写：先写同目录临时文件，再 rename 替换（同卷原子）；
 * - 校验失败 / 解析失败 → StateCorruptError（STATE_CORRUPT）拒绝加载，
 *   不覆盖磁盘上最近一份有效状态（PQ-INV-004）。
 *
 * 零网络、零依赖；仅学生本机 DU-1。
 */

import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

export const STATE_STORE_SCHEMA_VERSION = 1;

/** 持久化状态损坏 / 校验失败（拒绝加载并保留磁盘上最近有效状态）。 */
export class StateCorruptError extends Error {
  constructor(reason) {
    super(`STATE_CORRUPT: ${reason}`);
    this.name = "StateCorruptError";
    this.code = "STATE_CORRUPT";
    this.reason = reason;
  }
}

/** 稳定序列化（键排序；undefined 对象属性跳过，与 JSON.stringify 口径一致）。 */
function stableStringify(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value) ?? "null";
  }
  if (Array.isArray(value)) {
    return `[${value.map((v) => (v === undefined ? "null" : stableStringify(v))).join(",")}]`;
  }
  const keys = Object.keys(value)
    .filter((k) => value[k] !== undefined)
    .sort();
  return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(",")}}`;
}

function checksumOf(payload) {
  return createHash("sha256").update(stableStringify(payload), "utf8").digest("hex");
}

function emptyRecords() {
  return { tasks: {}, command_index: {}, triggers: [] };
}

/**
 * 创建本机 StateStore。
 * @param {Object} opts
 * @param {string} opts.storagePath envelope JSON 文件路径
 */
export function createStateStore({ storagePath }) {
  if (typeof storagePath !== "string" || storagePath.trim() === "") {
    throw new StateCorruptError("storagePath must be a non-empty string");
  }
  let revision = 0;

  /**
   * 加载 envelope；文件不存在 → 空状态（revision 0）。
   * 损坏 / schema 不兼容 / checksum 不匹配 → StateCorruptError，不写盘。
   * @returns {Promise<{tasks: Object, command_index: Object, triggers: string[]}>}
   */
  async function load() {
    let raw;
    try {
      raw = await readFile(storagePath, "utf8");
    } catch (err) {
      if (err?.code === "ENOENT") {
        revision = 0;
        return emptyRecords();
      }
      throw new StateCorruptError(
        `cannot read store: ${storagePath} (${err?.code ?? err?.message ?? "unknown"})`,
      );
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new StateCorruptError(`store is not valid JSON: ${storagePath}`);
    }
    if (parsed?.schema_version !== STATE_STORE_SCHEMA_VERSION) {
      throw new StateCorruptError(
        `unsupported schema_version: ${String(parsed?.schema_version)} (expected ${STATE_STORE_SCHEMA_VERSION})`,
      );
    }
    const { checksum, ...payload } = parsed;
    if (typeof checksum !== "string" || checksum !== checksumOf(payload)) {
      throw new StateCorruptError("checksum mismatch; refusing to load or overwrite");
    }
    if (typeof payload.revision !== "number" || payload.revision < 0) {
      throw new StateCorruptError("revision must be a non-negative number");
    }
    revision = payload.revision;
    return {
      tasks: payload.tasks ?? {},
      command_index: payload.command_index ?? {},
      triggers: Array.isArray(payload.triggers) ? payload.triggers : [],
    };
  }

  /**
   * 原子提交一份完整记录集（revision +1，重写 envelope）。
   * @param {{tasks: Object, command_index: Object, triggers: string[]}} records
   * @returns {Promise<{revision: number}>}
   */
  async function save(records) {
    revision += 1;
    const payload = {
      schema_version: STATE_STORE_SCHEMA_VERSION,
      revision,
      tasks: records.tasks ?? {},
      command_index: records.command_index ?? {},
      triggers: Array.isArray(records.triggers) ? records.triggers : [],
    };
    const envelope = { ...payload, checksum: checksumOf(payload) };
    await mkdir(path.dirname(storagePath), { recursive: true });
    const tmpPath = `${storagePath}.tmp-${process.pid}`;
    await writeFile(tmpPath, `${JSON.stringify(envelope, null, 2)}\n`, "utf8");
    await rename(tmpPath, storagePath);
    return { revision };
  }

  return Object.freeze({ load, save });
}
