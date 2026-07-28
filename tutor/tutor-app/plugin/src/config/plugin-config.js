/**
 * 插件配置校验（L04 CMP-CONFIG-STORE 端口形状；REQ-002 / AC-REQ-002-01）。
 *
 * 规则（冻结）：
 * - 必填：invite_code、student_name、group_name、code_dir、screenshots_dir、results_dir；
 * - 任一目录为空/不可读 → 配置为不完整并列出缺失项；
 * - 格式无效 → 拒绝保存并保留上一次有效配置（INV-3，由 L04 落地保存语义）。
 *
 * @typedef {Object} PluginConfig
 * @property {string} invite_code
 * @property {string} student_name
 * @property {string} group_name
 * @property {string} code_dir
 * @property {string} screenshots_dir
 * @property {string} results_dir
 */

export const REQUIRED_CONFIG_FIELDS = Object.freeze([
  "invite_code",
  "student_name",
  "group_name",
  "code_dir",
  "screenshots_dir",
  "results_dir",
]);

const DIR_FIELDS = Object.freeze(["code_dir", "screenshots_dir", "results_dir"]);

/**
 * 校验配置。目录可读性经注入的 dirCheck 检查（默认 node:fs access）。
 * @param {unknown} cfg
 * @param {{dirCheck?: (p: string) => Promise<boolean>}} [deps]
 * @returns {Promise<{ok: boolean, missing: string[], errors: string[]}>}
 */
export async function validatePluginConfig(cfg, deps = {}) {
  const dirCheck =
    deps.dirCheck ??
    (async (p) => {
      const { access } = await import("node:fs/promises");
      try {
        await access(p);
        return true;
      } catch {
        return false;
      }
    });

  const missing = [];
  const errors = [];
  if (cfg === null || typeof cfg !== "object" || Array.isArray(cfg)) {
    return { ok: false, missing: [...REQUIRED_CONFIG_FIELDS], errors: ["config must be an object"] };
  }
  for (const field of REQUIRED_CONFIG_FIELDS) {
    if (typeof cfg[field] !== "string" || cfg[field].trim() === "") {
      missing.push(field);
    }
  }
  for (const field of DIR_FIELDS) {
    if (!missing.includes(field) && !(await dirCheck(cfg[field]))) {
      errors.push(`directory not readable: ${field}=${cfg[field]}`);
    }
  }
  return { ok: missing.length === 0 && errors.length === 0, missing, errors };
}
