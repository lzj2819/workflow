/**
 * CMP-CS-STATE-STORE — ST-01 持久化（IC-CS-003 原子提交端口）。
 *
 * 语义（冻结自 L2 03-state-and-data / 05-local-decisions）：
 * - 单写方；一次有效保存要么完整替换记录，要么不改变（INV-CS-03）；
 * - 原子提交：临时文件 + rename；提交失败旧值保持可读（PERSISTENCE_FAILED）；
 * - 记录携带 schema_version（LCD-CS-004）：已知版本归一化读取，
 *   不支持版本读取报错且保留原记录，不得以默认值覆盖；
 * - 损坏（非法 JSON / 形状不符）读取给出可诊断错误，不覆盖、不删除原文件；
 * - 进程内保留最近一次有效快照（lastGood），供 INV-3「保留上一次有效配置」。
 *
 * 可观测字段限：操作类型、结果、config_version（不含邀请码明文/目录内容）。
 */

import {
  writeFile as fsWriteFile,
  rename as fsRename,
  readFile as fsReadFile,
  mkdir as fsMkdir,
  unlink as fsUnlink,
} from "node:fs/promises";
import { dirname } from "node:path";

export const CURRENT_SCHEMA_VERSION = 1;

let tmpSeq = 0;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/**
 * 归一化并校验持久化记录形状；不合法返回 null（调用方按损坏处理）。
 * @param {unknown} raw
 * @returns {null | {schema_version:number, config_version:number, config:Object,
 *   completeness:string[], dir_errors:string[], saved_at:string|null}}
 */
export function normalizeRecord(raw) {
  if (!isPlainObject(raw)) return null;
  if (raw.schema_version !== CURRENT_SCHEMA_VERSION) return null;
  if (typeof raw.config_version !== "number" || !Number.isInteger(raw.config_version)) return null;
  if (!isPlainObject(raw.config)) return null;
  return {
    schema_version: raw.schema_version,
    config_version: raw.config_version,
    config: { ...raw.config },
    completeness: Array.isArray(raw.completeness) ? [...raw.completeness] : [],
    dir_errors: Array.isArray(raw.dir_errors) ? [...raw.dir_errors] : [],
    saved_at: typeof raw.saved_at === "string" ? raw.saved_at : null,
  };
}

/**
 * @param {{filePath: string, fs?: Object}} deps fs 可注入 writeFile/rename/readFile/mkdir/unlink 以模拟故障。
 */
export function createStateStore({ filePath, fs: fsDeps = {} }) {
  if (!filePath || typeof filePath !== "string") {
    throw new Error("state-store: filePath is required");
  }
  const io = {
    writeFile: fsDeps.writeFile ?? fsWriteFile,
    rename: fsDeps.rename ?? fsRename,
    readFile: fsDeps.readFile ?? fsReadFile,
    mkdir: fsDeps.mkdir ?? fsMkdir,
    unlink: fsDeps.unlink ?? fsUnlink,
  };

  /** 最近一次有效记录（进程内 INV-3 保留）；读取成功或提交成功时刷新。 */
  let lastGood = null;
  /** 单写方串行化：并发 save 按完成顺序成为新的最近有效配置。 */
  let writeChain = Promise.resolve();

  /**
   * 读取当前快照。只读：任何失败都不写、不删原文件。
   * @returns {Promise<{ok:true, record:Object|null}
   *   | {ok:false, error_code:string, error_detail:string, record:Object|null}>}
   */
  async function readSnapshot() {
    let text;
    try {
      text = await io.readFile(filePath, "utf8");
    } catch (err) {
      if (err && err.code === "ENOENT") {
        return { ok: true, record: lastGood };
      }
      return {
        ok: false,
        error_code: "PERSISTENCE_READ_FAILED",
        error_detail: `read failed: ${err && err.message ? err.message : String(err)}`,
        record: lastGood,
      };
    }
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (err) {
      return {
        ok: false,
        error_code: "CONFIG_CORRUPT",
        error_detail: `config file is not valid JSON: ${err.message}`,
        record: lastGood,
      };
    }
    if (isPlainObject(parsed) && parsed.schema_version !== CURRENT_SCHEMA_VERSION) {
      // LCD-CS-004：不支持的版本保留原记录，不得以默认值覆盖。
      return {
        ok: false,
        error_code: "UNSUPPORTED_SCHEMA_VERSION",
        error_detail: `unsupported schema_version: ${String(parsed.schema_version)} (supported: ${CURRENT_SCHEMA_VERSION})`,
        record: lastGood,
      };
    }
    const record = normalizeRecord(parsed);
    if (!record) {
      return {
        ok: false,
        error_code: "CONFIG_CORRUPT",
        error_detail: "config record shape invalid",
        record: lastGood,
      };
    }
    lastGood = record;
    return { ok: true, record };
  }

  async function commitNow(record) {
    const tmpPath = `${filePath}.tmp-${process.pid}-${++tmpSeq}`;
    try {
      await io.mkdir(dirname(filePath), { recursive: true });
      await io.writeFile(tmpPath, JSON.stringify(record, null, 2) + "\n", "utf8");
      // rename 前失败：旧文件不受影响；tmp 清理为尽力而为。
      await io.rename(tmpPath, filePath);
    } catch (err) {
      try {
        await io.unlink(tmpPath);
      } catch {
        /* tmp 可能不存在；忽略 */
      }
      return {
        ok: false,
        error_code: "PERSISTENCE_FAILED",
        error_detail: `atomic commit failed: ${err && err.message ? err.message : String(err)}`,
      };
    }
    lastGood = record;
    return { ok: true, config_version: record.config_version };
  }

  /**
   * 原子提交一条完整记录（临时文件 + rename）。串行化并发写入。
   * @param {Object} record normalizeRecord 兼容形状
   */
  function commit(record) {
    const result = writeChain.then(() => commitNow(record));
    writeChain = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }

  return {
    readSnapshot,
    commit,
    getLastGood: () => lastGood,
  };
}
