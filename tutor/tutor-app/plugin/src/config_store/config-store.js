/**
 * CMP-CS-CONFIG-PORT — IC-M01-02 配置端口实现（REQ-002 / AC-REQ-002-01）。
 *
 * 编排：SaveConfig → validatePluginConfig（SCHEMA-VALIDATOR，复用
 * plugin/src/config/plugin-config.js，只读）→ 目录探测（DIRECTORY-PROBE，
 * 经注入 dirCheck）→ STATE-STORE 原子提交 → ConfigSaved/ConfigRejected。
 *
 * 语义（冻结自 L1 IC-M01-02 / L2 04-contracts-and-runtime / INV-3）：
 * - 格式无效（非对象、字段类型错误）→ 拒绝保存，不写 ST-01，保留上一次有效配置；
 * - 必填为空 / 目录不可读 → 保存值并标记「不完整」，completeness[]/dir_errors[] 显式列出；
 * - 读取 = 最近有效快照 + 当前目录重探测（LCD-CS-003），读取无写副作用（INV-CS-05）；
 * - 事件与错误载荷不含配置值明文（可观测只含操作类型/结果/config_version）。
 */

import {
  validatePluginConfig,
  REQUIRED_CONFIG_FIELDS,
} from "../config/plugin-config.js";
import {
  createStateStore,
  CURRENT_SCHEMA_VERSION,
} from "./state-store.js";

export const CONFIG_STORE_ERROR_CODES = Object.freeze([
  "INVALID_CONFIG",
  "DIRECTORY_UNREADABLE",
  "PERSISTENCE_FAILED",
  "CONFIG_CORRUPT",
  "UNSUPPORTED_SCHEMA_VERSION",
  "PERSISTENCE_READ_FAILED",
  "CONFIG_INCOMPLETE",
]);

const DIR_ERROR_FIELD = /^directory not readable: (\w+)=/;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** 从 validatePluginConfig 的 errors 文本提取目录字段名（冻结格式同源）。 */
function dirErrorFields(errors) {
  const fields = [];
  for (const e of errors) {
    const m = DIR_ERROR_FIELD.exec(e);
    if (m && !fields.includes(m[1])) fields.push(m[1]);
  }
  return fields;
}

function unionMissing(missing, dirFields) {
  const out = [...missing];
  for (const f of dirFields) if (!out.includes(f)) out.push(f);
  return out;
}

/**
 * 区分「格式无效」（拒绝）与「必填为空」（保存为不完整）：
 * 非对象 / 已出现字段类型非 string → 格式无效；缺失或空白字符串 → 不完整。
 * @returns {null | {field_errors: string[], missing: string[]}}
 */
function classifyInvalid(candidate) {
  if (!isPlainObject(candidate)) {
    return {
      field_errors: ["config must be an object"],
      missing: [...REQUIRED_CONFIG_FIELDS],
    };
  }
  const fieldErrors = [];
  const missing = [];
  for (const field of REQUIRED_CONFIG_FIELDS) {
    if (field in candidate && typeof candidate[field] !== "string") {
      fieldErrors.push(`field ${field} must be a string`);
      missing.push(field);
    }
  }
  if (fieldErrors.length > 0) {
    return { field_errors: fieldErrors, missing };
  }
  return null;
}

function emptyFields() {
  const fields = {};
  for (const f of REQUIRED_CONFIG_FIELDS) fields[f] = "";
  return fields;
}

/**
 * 创建 IC-M01-02 配置端口实例。
 * @param {{filePath: string,
 *          dirCheck?: (p: string) => Promise<boolean>,
 *          fs?: Object}} deps
 *   dirCheck 注入目录可读性探测（默认 node:fs access，同 validatePluginConfig）；
 *   fs 注入持久化原语（测试模拟故障）。
 * @returns {{save: Function, get: Function, getRequired: Function, onChange: Function}}
 */
export function createConfigStore({ filePath, dirCheck, fs } = {}) {
  if (!filePath || typeof filePath !== "string") {
    throw new Error("config-store: filePath is required");
  }
  const store = createStateStore({ filePath, fs });
  const listeners = new Set();
  const validateDeps = dirCheck ? { dirCheck } : {};

  function emit(event) {
    for (const listener of [...listeners]) {
      try {
        listener(event);
      } catch {
        /* 监听者故障不影响保存语义 */
      }
    }
  }

  function rejected(errorCode, extra) {
    const result = {
      ok: false,
      saved: false,
      error_code: errorCode,
      field_errors: [],
      missing: [],
      dir_errors: [],
      ...extra,
    };
    emit({
      type: "ConfigRejected",
      error_code: result.error_code,
      missing: result.missing,
      dir_errors: result.dir_errors,
    });
    return result;
  }

  /**
   * SaveConfig：写全量 PluginConfig（schema v1 持久化记录附加 schema_version）。
   * @param {unknown} candidate
   */
  async function save(candidate) {
    const invalid = classifyInvalid(candidate);
    if (invalid) {
      return rejected("INVALID_CONFIG", {
        field_errors: invalid.field_errors,
        missing: invalid.missing,
      });
    }

    // schema 校验 + 保存时目录探测（R-CS-01；目录问题不阻断提交）。
    const v = await validatePluginConfig(candidate, validateDeps);
    const dirFields = dirErrorFields(v.errors);
    const completeness = unionMissing(v.missing, dirFields);

    const config = emptyFields();
    for (const field of REQUIRED_CONFIG_FIELDS) {
      if (typeof candidate[field] === "string") config[field] = candidate[field];
    }

    // 版本延续：先读当前快照（含磁盘已有记录/lastGood），避免重开进程后版本回退。
    const snap = await store.readSnapshot();
    const record = {
      schema_version: CURRENT_SCHEMA_VERSION,
      config_version: (snap.record ? snap.record.config_version : 0) + 1,
      config,
      completeness,
      dir_errors: v.errors,
      saved_at: new Date().toISOString(),
    };

    const committed = await store.commit(record);
    if (!committed.ok) {
      return rejected(committed.error_code, {
        error_detail: committed.error_detail,
      });
    }

    const status = completeness.length === 0 ? "complete" : "incomplete";
    const result = {
      ok: true,
      saved: true,
      status,
      complete: status === "complete",
      missing: v.missing,
      completeness,
      dir_errors: v.errors,
      config_version: committed.config_version,
      schema_version: CURRENT_SCHEMA_VERSION,
    };
    emit({
      type: "ConfigSaved",
      config_version: result.config_version,
      status,
      completeness,
      dir_errors: v.errors,
    });
    return result;
  }

  function effectiveFromRecord(record, validation, extra = {}) {
    const dirFields = dirErrorFields(validation.errors);
    const completeness = unionMissing(validation.missing, dirFields);
    return {
      ok: true,
      status: completeness.length === 0 ? "complete" : "incomplete",
      ...emptyFields(),
      ...record.config,
      missing: validation.missing,
      completeness,
      dir_errors: validation.errors,
      config_version: record.config_version,
      schema_version: record.schema_version,
      saved_at: record.saved_at,
      ...extra,
    };
  }

  /**
   * ReadEffectiveConfig：最近有效快照 + 当前目录重探测；无写副作用。
   * @returns {Promise<Object>} EffectiveConfig{fields..., completeness[], dir_errors[]}
   */
  async function get() {
    const snap = await store.readSnapshot();
    if (!snap.ok) {
      if (snap.record) {
        // INV-3：磁盘损坏/版本不支持时保留上一次有效配置，显式标记 stale。
        const v = await validatePluginConfig(snap.record.config, validateDeps);
        return effectiveFromRecord(snap.record, v, {
          stale: true,
          read_error: { error_code: snap.error_code, error_detail: snap.error_detail },
        });
      }
      return {
        ok: false,
        status: "unreadable",
        ...emptyFields(),
        missing: [],
        completeness: [],
        dir_errors: [],
        config_version: null,
        schema_version: CURRENT_SCHEMA_VERSION,
        saved_at: null,
        error_code: snap.error_code,
        error_detail: snap.error_detail,
      };
    }
    if (!snap.record) {
      return {
        ok: true,
        status: "missing",
        ...emptyFields(),
        missing: [...REQUIRED_CONFIG_FIELDS],
        completeness: [...REQUIRED_CONFIG_FIELDS],
        dir_errors: [],
        config_version: null,
        schema_version: CURRENT_SCHEMA_VERSION,
        saved_at: null,
      };
    }
    const v = await validatePluginConfig(snap.record.config, validateDeps);
    return effectiveFromRecord(snap.record, v);
  }

  /**
   * 提交前置读取：仅在配置存在且完整时返回值，否则抛 CONFIG_INCOMPLETE。
   * @returns {Promise<Object>} PluginConfig 六字段
   */
  async function getRequired() {
    const eff = await get();
    if (!eff.ok) {
      const err = new Error(`config unreadable: ${eff.error_code}`);
      err.code = eff.error_code;
      err.error_detail = eff.error_detail;
      throw err;
    }
    if (eff.status !== "complete") {
      const err = new Error("config incomplete");
      err.code = "CONFIG_INCOMPLETE";
      err.missing = eff.missing;
      err.completeness = eff.completeness;
      err.dir_errors = eff.dir_errors;
      throw err;
    }
    const config = {};
    for (const field of REQUIRED_CONFIG_FIELDS) config[field] = eff[field];
    return config;
  }

  /**
   * 变更订阅：ConfigSaved / ConfigRejected（载荷不含配置值明文）。
   * @param {(event: Object) => void} listener
   * @returns {() => void} 取消订阅
   */
  function onChange(listener) {
    if (typeof listener !== "function") {
      throw new TypeError("onChange: listener must be a function");
    }
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  return { save, get, getRequired, onChange };
}
