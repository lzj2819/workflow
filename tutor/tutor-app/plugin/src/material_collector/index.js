/**
 * L06 CMP-MATERIAL-COLLECTOR — 三类目录材料收集与清单（REQ-DD004 / KD-004 / LCD-003）。
 *
 * 按配置快照从代码/截图/结果三个目录收集材料，产出 MaterialManifest：
 * - 只读取配置给出的三个目录（不递归子目录、不跟随符号链接、不读隐藏文件）；
 * - KD-004 文件类型白名单（代码/文本/图片/常见文档/压缩包，可配置覆盖）；
 *   白名单外文件跳过并按类别计数（不进 items）；
 * - 目录不存在或为空 → 对应类别显式进入 missing_items（不报错、不隐藏缺口，
 *   AC-REQ-003-01 MOD-01 slice / INV-L2-MC-03）；
 * - total_bytes 只累计白名单通过项（LCD-L2-MC-002）；超过 500MB 单次上限时
 *   置 over_budget=true 并追加预检警告（客户端预检，服务端权威不变，LCD-003）；
 * - 条目确定性排序（category → path），同一目录两次收集 manifest 一致（INV-L2-MC-04）。
 *
 * 清单形状对齐 IC-M01-03 材料侧端口（plugin/src/ports/index.js
 * CollectionBatch.material_refs / missing_items）：items 可直接作为
 * material_refs，missing_items 语义一致；缺失/预检警告经 warnings 供
 * CMP-STATUS-PRESENTER 展示。
 *
 * 不实现：对话采集（L07）、配置校验与保存（L04）、上传（L10）、队列（L11）；
 * 幂等复用与并发守卫由 CMP-PENDING-QUEUE 按 submission_uuid 编排（INV-L2-MC-05/06）。
 */

import { createHash } from "node:crypto";
import { lstat, readdir, readFile } from "node:fs/promises";
import path from "node:path";

/** 三类材料：类别 → 配置目录字段（INV-L2-MC-01）。 */
export const MATERIAL_CATEGORIES = Object.freeze([
  { category: "code", config_field: "code_dir" },
  { category: "screenshot", config_field: "screenshot_dir" },
  { category: "result", config_field: "result_dir" },
]);

/** KD-004 单次提交上限：500MB（客户端预检口径；服务端权威不变）。 */
export const MAX_SUBMISSION_BYTES = 524_288_000;

/**
 * KD-004 默认白名单（代码/文本/图片/常见文档/压缩包，扩展名小写、含点）。
 * 可通过 collectMaterials(config, { whitelist }) 整体覆盖。
 */
export const DEFAULT_WHITELIST = Object.freeze([
  // 代码
  ".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx", ".py", ".java", ".c", ".h",
  ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt",
  ".kts", ".scala", ".sql", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
  ".html", ".htm", ".css", ".scss", ".less", ".vue", ".svelte", ".lua", ".r",
  ".pl", ".pm", ".ex", ".exs", ".erl", ".hrl", ".clj", ".fs", ".dart", ".asm",
  // 文本
  ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl",
  ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".log", ".xml", ".env",
  ".gitignore", ".editorconfig",
  // 图片
  ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tif", ".tiff",
  ".heic",
  // 常见文档
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods",
  ".odp", ".rtf", ".epub",
  // 压缩包
  ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
]);

/** 材料收集失败的稳定错误码（L2 04-contracts-and-runtime §3.1）。 */
export const MC_ERROR_CODES = Object.freeze([
  "MC-ERR-CONFIG-INVALID",
  "MC-ERR-DIR-UNREADABLE",
  "MC-ERR-COLLECT-BUSY",
]);

/** 可解释的材料收集失败（code 定位原因；不静默降级）。 */
export class MaterialCollectionError extends Error {
  constructor(code, reason, category = null) {
    super(`${code}: ${reason}`);
    this.name = "MaterialCollectionError";
    this.code = code;
    this.category = category;
    this.reason = reason;
  }
}

function failConfig(reason) {
  throw new MaterialCollectionError("MC-ERR-CONFIG-INVALID", reason);
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function normalizeWhitelist(whitelist) {
  const list = whitelist ?? DEFAULT_WHITELIST;
  if (!Array.isArray(list) || list.length === 0) {
    failConfig("whitelist must be a non-empty array of extensions");
  }
  const normalized = new Set();
  for (const ext of list) {
    if (typeof ext !== "string" || !ext.startsWith(".")) {
      failConfig(`whitelist entry must be an extension starting with '.': ${String(ext)}`);
    }
    normalized.add(ext.toLowerCase());
  }
  return normalized;
}

function toPosixPath(p) {
  return p.split(path.sep).join("/");
}

async function sha256File(absPath) {
  const buf = await readFile(absPath);
  return createHash("sha256").update(buf).digest("hex");
}

/**
 * 扫描单个类别目录（CMP-MC-DIRECTORY-SCANNER 职责边界）。
 * 只读配置目录本身；不递归、不跟随符号链接、不读隐藏文件。
 * @returns {Promise<{candidates: Array, scan_diag: string[], empty: boolean, reason: string|null}>}
 */
async function scanCategoryDir(dir, { entryReader, statFn }) {
  let names;
  try {
    names = await entryReader(dir);
  } catch (err) {
    if (err?.code === "ENOENT" || err?.code === "ENOTDIR") {
      return { candidates: [], scan_diag: [], empty: true, reason: "not_found" };
    }
    throw new MaterialCollectionError(
      "MC-ERR-DIR-UNREADABLE",
      `directory unreadable: ${dir} (${err?.code ?? err?.message ?? "unknown"})`,
    );
  }

  const candidates = [];
  const scan_diag = [];
  for (const name of [...names].sort()) {
    const abs = path.join(dir, name);
    let lst;
    try {
      lst = await statFn(abs, { lstat: true });
    } catch (err) {
      scan_diag.push(`entry metadata unreadable: ${toPosixPath(abs)} (${err?.code ?? "unknown"})`);
      continue;
    }
    if (lst.isSymbolicLink()) {
      scan_diag.push(`symlink skipped: ${toPosixPath(abs)}`);
      continue;
    }
    if (!lst.isFile()) continue; // 子目录等不递归（L2 LCD-L2-MC-005 委托语义：不扩大遍历行为）
    if (name.startsWith(".")) continue; // 隐藏文件不进材料集合
    candidates.push({
      abs,
      rel_path: toPosixPath(path.join(dir, name)),
      size: lst.size,
      modified_at: lst.mtime.toISOString(),
    });
  }
  return { candidates, scan_diag, empty: candidates.length === 0, reason: null };
}

/**
 * 按配置收集三类材料并产出 MaterialManifest（CMP-MC-MANIFEST-BUILDER facade，
 * 实现 IC-M01-03 材料侧端口）。
 *
 * @param {Object} config
 * @param {string} config.submission_uuid   任务/提交 UUID（幂等关联键，本层不重新生成）
 * @param {{assignment: string, student_name: string, group_name: string}} config.identity_snapshot
 * @param {{code_dir: string, screenshot_dir: string, result_dir: string}} config.config_snapshot
 * @param {string} [config.snapshot_at]     ISO8601 采集时刻；缺省由本层取当前时间
 * @param {Object} [deps]
 * @param {string[]} [deps.whitelist]       覆盖 KD-004 默认白名单（扩展名表，小写含点）
 * @param {number} [deps.max_total_bytes]   覆盖 500MB 预检预算（默认 524288000）
 * @param {(dir: string) => Promise<string[]>} [deps.entryReader]  目录项读取（默认 readdir）
 * @param {(p: string, opts?: Object) => Promise<import("node:fs").Stats>} [deps.statFn]
 * @returns {Promise<MaterialManifest>}
 *
 * @typedef {Object} MaterialManifestItem
 * @property {string} category   "code" | "screenshot" | "result"
 * @property {string} path       绝对路径（POSIX 分隔符，确定性）
 * @property {number} size_bytes
 * @property {string} sha256     内容哈希（node:crypto）
 * @property {string} modified_at ISO8601
 *
 * @typedef {Object} MaterialManifest
 * @property {string} submission_uuid
 * @property {{assignment: string, student_name: string, group_name: string}} identity
 * @property {MaterialManifestItem[]} items        确定性排序（category → path）
 * @property {string[]} missing_items              缺失类别（code/screenshot/result，显式不隐藏）
 * @property {number} total_bytes                  仅白名单通过项累计（LCD-L2-MC-002）
 * @property {boolean} over_budget                 超过 500MB 预检上限
 * @property {string[]} warnings                   预检告警（供 STATUS-PRESENTER 展示）
 * @property {Object} skipped_by_category          白名单外文件计数 {code, screenshot, result}
 * @property {string[]} diagnostics                扫描/过滤诊断（不含材料正文）
 * @property {string} snapshot_at                  ISO8601 快照时刻
 */
export async function collectMaterials(config, deps = {}) {
  if (!isPlainObject(config)) failConfig("config must be an object");
  if (typeof config.submission_uuid !== "string" || config.submission_uuid.trim() === "") {
    failConfig("submission_uuid must be a non-empty string");
  }
  const identity = config.identity_snapshot;
  if (!isPlainObject(identity)) failConfig("identity_snapshot must be an object");
  for (const f of ["assignment", "student_name", "group_name"]) {
    if (typeof identity[f] !== "string" || identity[f].trim() === "") {
      failConfig(`identity_snapshot.${f} must be a non-empty string`);
    }
  }
  const snapshot = config.config_snapshot;
  if (!isPlainObject(snapshot)) failConfig("config_snapshot must be an object");

  const whitelist = normalizeWhitelist(deps.whitelist);
  const budget = deps.max_total_bytes ?? MAX_SUBMISSION_BYTES;
  if (!Number.isInteger(budget) || budget <= 0) {
    failConfig("max_total_bytes must be a positive integer");
  }
  const entryReader = deps.entryReader ?? ((dir) => readdir(dir));
  const statFn = deps.statFn ?? ((p) => lstat(p));
  const snapshotAt = config.snapshot_at ?? new Date().toISOString();
  if (Number.isNaN(Date.parse(snapshotAt))) {
    failConfig(`snapshot_at must be ISO8601: ${String(snapshotAt)}`);
  }

  const items = [];
  const missing_items = [];
  const warnings = [];
  const diagnostics = [];
  const skipped_by_category = {};
  let total_bytes = 0;

  for (const { category, config_field } of MATERIAL_CATEGORIES) {
    const dir = snapshot[config_field];
    if (typeof dir !== "string" || dir.trim() === "") {
      failConfig(`config_snapshot.${config_field} must be a non-empty directory path`);
    }
    skipped_by_category[category] = 0;

    const { candidates, scan_diag, empty, reason } = await scanCategoryDir(dir, { entryReader, statFn });
    diagnostics.push(...scan_diag);
    if (empty) {
      missing_items.push(category);
      warnings.push(
        reason === "not_found"
          ? `material category missing: ${category} directory not found (${dir})`
          : `material category missing: ${category} directory empty (${dir})`,
      );
      continue;
    }

    for (const cand of candidates) {
      const ext = path.extname(cand.abs).toLowerCase();
      if (!whitelist.has(ext)) {
        skipped_by_category[category] += 1;
        diagnostics.push(`filtered by whitelist: ${cand.rel_path} (${ext || "no extension"})`);
        continue;
      }
      let sha256;
      try {
        sha256 = await sha256File(cand.abs);
      } catch (err) {
        throw new MaterialCollectionError(
          "MC-ERR-DIR-UNREADABLE",
          `file unreadable during hashing: ${cand.rel_path} (${err?.code ?? "unknown"})`,
          category,
        );
      }
      total_bytes += cand.size;
      items.push({
        category,
        path: cand.rel_path,
        size_bytes: cand.size,
        sha256,
        modified_at: cand.modified_at,
      });
    }
  }

  items.sort((a, b) =>
    a.category === b.category
      ? a.path < b.path
        ? -1
        : a.path > b.path
          ? 1
          : 0
      : a.category < b.category
        ? -1
        : 1,
  );

  const over_budget = total_bytes > budget;
  if (over_budget) {
    warnings.push(
      `precheck over budget: total_bytes=${total_bytes} exceeds ${budget} (500MB 单次上限；客户端预检，服务端权威不变)`,
    );
  }

  return {
    submission_uuid: config.submission_uuid,
    identity: {
      assignment: identity.assignment,
      student_name: identity.student_name,
      group_name: identity.group_name,
    },
    items,
    missing_items,
    total_bytes,
    over_budget,
    warnings,
    skipped_by_category,
    diagnostics,
    snapshot_at: snapshotAt,
  };
}
