/**
 * T-B04 — ST-05 UploadCheckpoint 文件持久化实现（A-007 跨进程持久）。
 *
 * 接口形状与 L10 默认内存实现 createMemoryCheckpointStore 完全一致：
 * {load, save, clear}，可直接注入 createUploadClient({checkpointStore})。
 *
 * 语义承诺（不随介质改变）：
 * - 按 submission_uuid 一文件（checkpoint-<uuid>.json），JSON 序列化；
 * - 原子写：同目录临时文件 + rename（同卷原子），写失败不破坏既有文件；
 * - 损坏文件（非法 JSON / 形状不符）→ 可诊断 CheckpointStoreError
 *   （CHECKPOINT_CORRUPT），不覆盖、不删除原文件（参照 L04 state-store 模式）；
 * - INV-5 / L2-UP-INV-001：confirmed_chunks 只含服务端已确认分片索引；
 *   写入时机由 SESSION-DRIVER 在 ack 后决定，本模块只持久化收到的记录，
 *   并拒绝形状不符的记录（fail-closed，不静默改写）；
 * - 记录不含令牌、identity、材料内容（仅会话/偏移元数据，同内存版口径）。
 *
 * 零网络、零 npm 依赖；仅学生本机 DU-1。
 */

import { mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import path from "node:path";

export const CHECKPOINT_STORE_ERROR_CODES = Object.freeze([
  "CHECKPOINT_CORRUPT",
  "CHECKPOINT_INVALID",
  "CHECKPOINT_PERSIST_FAILED",
]);

/** checkpoint 存储可诊断错误（code 定位原因；不静默降级）。 */
export class CheckpointStoreError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "CheckpointStoreError";
    this.code = code;
    this.reason = reason;
  }
}

let tmpSeq = 0;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** uuid 只允许安全文件名字符（防路径穿越；不改变 uuid 本身）。 */
const SAFE_UUID_RE = /^[A-Za-z0-9_-]+$/;

function assertUuid(uuid) {
  if (typeof uuid !== "string" || !SAFE_UUID_RE.test(uuid)) {
    throw new CheckpointStoreError(
      "CHECKPOINT_INVALID",
      `submission_uuid must be a non-empty safe string: ${String(uuid)}`,
    );
  }
}

/**
 * 校验 ST-05 记录形状（fail-closed：形状不符拒绝写入，不静默修正）。
 * confirmed_chunks 必须是非负整数数组（INV-5：只含已确认分片索引）。
 */
function validateCheckpoint(cp) {
  if (!isPlainObject(cp)) {
    throw new CheckpointStoreError("CHECKPOINT_INVALID", "checkpoint must be an object");
  }
  assertUuid(cp.submission_uuid);
  if (typeof cp.upload_session_id !== "string" || cp.upload_session_id === "") {
    throw new CheckpointStoreError(
      "CHECKPOINT_INVALID",
      "upload_session_id must be a non-empty string",
    );
  }
  if (
    !Array.isArray(cp.confirmed_chunks) ||
    cp.confirmed_chunks.some((i) => !Number.isInteger(i) || i < 0)
  ) {
    throw new CheckpointStoreError(
      "CHECKPOINT_INVALID",
      "confirmed_chunks must be an array of non-negative integers (acked chunks only, INV-5)",
    );
  }
  if (!Number.isInteger(cp.total_chunks) || cp.total_chunks < 0) {
    throw new CheckpointStoreError(
      "CHECKPOINT_INVALID",
      "total_chunks must be a non-negative integer",
    );
  }
  if (cp.last_ack_at !== null && typeof cp.last_ack_at !== "string") {
    throw new CheckpointStoreError(
      "CHECKPOINT_INVALID",
      "last_ack_at must be a string or null",
    );
  }
}

function normalizeCheckpoint(raw) {
  if (!isPlainObject(raw)) return null;
  try {
    validateCheckpoint(raw);
  } catch {
    return null;
  }
  return {
    submission_uuid: raw.submission_uuid,
    upload_session_id: raw.upload_session_id,
    confirmed_chunks: [...raw.confirmed_chunks],
    total_chunks: raw.total_chunks,
    last_ack_at: raw.last_ack_at ?? null,
  };
}

/**
 * 创建文件版 checkpoint store（与 createMemoryCheckpointStore 同形状）。
 * @param {Object} deps
 * @param {string} deps.dir checkpoint 文件目录（不存在时按需创建）
 * @returns {{load: (uuid: string) => Promise<Object|null>,
 *   save: (cp: Object) => Promise<void>, clear: (uuid: string) => Promise<void>}}
 */
export function createFileCheckpointStore({ dir } = {}) {
  if (typeof dir !== "string" || dir.trim() === "") {
    throw new CheckpointStoreError("CHECKPOINT_INVALID", "dir must be a non-empty string");
  }
  /** 单写方串行化：同一进程内并发 save 按序提交。 */
  let writeChain = Promise.resolve();

  function pathFor(uuid) {
    assertUuid(uuid);
    return path.join(dir, `checkpoint-${uuid}.json`);
  }

  /**
   * 读取 checkpoint；不存在 → null；损坏 → CHECKPOINT_CORRUPT（保留原文件）。
   * @returns {Promise<Object|null>} ST-05 记录副本
   */
  async function load(uuid) {
    const filePath = pathFor(uuid);
    let raw;
    try {
      raw = await readFile(filePath, "utf8");
    } catch (err) {
      if (err?.code === "ENOENT") return null;
      throw new CheckpointStoreError(
        "CHECKPOINT_CORRUPT",
        `cannot read checkpoint: ${filePath} (${err?.code ?? err?.message ?? "unknown"})`,
      );
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      throw new CheckpointStoreError(
        "CHECKPOINT_CORRUPT",
        `checkpoint file is not valid JSON: ${filePath} (${err.message}); file preserved`,
      );
    }
    const cp = normalizeCheckpoint(parsed);
    if (cp === null || cp.submission_uuid !== uuid) {
      throw new CheckpointStoreError(
        "CHECKPOINT_CORRUPT",
        `checkpoint record shape invalid or uuid mismatch: ${filePath}; file preserved`,
      );
    }
    return cp;
  }

  async function saveNow(cp) {
    const filePath = pathFor(cp.submission_uuid);
    const tmpPath = `${filePath}.tmp-${process.pid}-${++tmpSeq}`;
    try {
      await mkdir(dir, { recursive: true });
      await writeFile(tmpPath, `${JSON.stringify(cp, null, 2)}\n`, "utf8");
      // rename 前失败：既有文件不受影响；tmp 清理为尽力而为。
      await rename(tmpPath, filePath);
    } catch (err) {
      try {
        await unlink(tmpPath);
      } catch {
        /* tmp 可能不存在；忽略 */
      }
      throw new CheckpointStoreError(
        "CHECKPOINT_PERSIST_FAILED",
        `atomic commit failed for ${filePath}: ${err?.message ?? String(err)}`,
      );
    }
  }

  /**
   * 原子提交一份 ST-05 记录（tmp + rename）。只接受形状合法的已确认分片记录。
   * @param {Object} cp ST-05 UploadCheckpoint
   */
  function save(cp) {
    // 与内存版一致的异步接口：校验失败以 Promise 拒绝呈现（不同步抛出）。
    try {
      validateCheckpoint(cp);
    } catch (err) {
      return Promise.reject(err);
    }
    const snapshot = {
      submission_uuid: cp.submission_uuid,
      upload_session_id: cp.upload_session_id,
      confirmed_chunks: [...cp.confirmed_chunks],
      total_chunks: cp.total_chunks,
      last_ack_at: cp.last_ack_at ?? null,
    };
    const result = writeChain.then(() => saveNow(snapshot));
    writeChain = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }

  /** 终态清理（L2 03 cleanup_trigger：confirmed/rejected 后由父队列触发）。 */
  async function clear(uuid) {
    const filePath = pathFor(uuid);
    try {
      await unlink(filePath);
    } catch (err) {
      if (err?.code !== "ENOENT") {
        throw new CheckpointStoreError(
          "CHECKPOINT_PERSIST_FAILED",
          `cannot remove checkpoint: ${filePath} (${err?.code ?? err?.message ?? "unknown"})`,
        );
      }
    }
  }

  return Object.freeze({ load, save, clear });
}
