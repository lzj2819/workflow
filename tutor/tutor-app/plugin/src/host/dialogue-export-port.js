/**
 * Host adapter 端口：完整 Codex 对话导出（采集侧 ACL，L07 CMP-DIALOGUE-COLLECTOR）。
 *
 * TD-01（真实阻塞）：宿主 Codex 环境的对话导出机制未确认。本文件只定义：
 *   1) 我们需要的导出物形状（DialogueExport）与校验；
 *   2) 显式 unsupported 失败（可观测）；
 * 不定义、不猜测任何宿主 API。真实适配待 TD-01 确认后在 L07 实现。
 *
 * @typedef {Object} DialogueTurn
 * @property {"user"|"assistant"|"system"|"tool"} role
 * @property {string} content
 * @property {string} [timestamp] ISO8601
 *
 * @typedef {Object} DialogueExport
 * @property {string} format_version  导出物格式版本（如 "1"）
 * @property {string} source_host     宿主标识（确认 TD-01 后填真实值）
 * @property {string} exported_at     ISO8601 导出时间
 * @property {DialogueTurn[]} turns   完整对话轮次（不得截断）
 */

export const DIALOGUE_EXPORT_ROLES = Object.freeze(["user", "assistant", "system", "tool"]);

/** 宿主导出能力未确认/不可用时的显式失败（失败可观测，禁止静默降级）。 */
export class HostUnsupportedError extends Error {
  constructor(detail) {
    super(`host dialogue export unsupported: ${detail}`);
    this.name = "HostUnsupportedError";
    this.code = "HOST_EXPORT_UNSUPPORTED";
    this.detail = detail;
    this.host_detected = null; // TD-01 确认后由适配器填充
  }
}

/**
 * 校验一个对话导出物是否满足端口形状。
 * @param {unknown} doc
 * @returns {{ok: boolean, errors: string[]}}
 */
export function validateDialogueExport(doc) {
  const errors = [];
  if (doc === null || typeof doc !== "object" || Array.isArray(doc)) {
    return { ok: false, errors: ["export must be an object"] };
  }
  if (typeof doc.format_version !== "string" || doc.format_version.length === 0) {
    errors.push("format_version must be a non-empty string");
  }
  if (typeof doc.source_host !== "string" || doc.source_host.length === 0) {
    errors.push("source_host must be a non-empty string");
  }
  if (typeof doc.exported_at !== "string" || Number.isNaN(Date.parse(doc.exported_at))) {
    errors.push("exported_at must be an ISO8601 timestamp");
  }
  if (!Array.isArray(doc.turns) || doc.turns.length === 0) {
    errors.push("turns must be a non-empty array");
  } else {
    doc.turns.forEach((turn, i) => {
      if (!DIALOGUE_EXPORT_ROLES.includes(turn?.role)) {
        errors.push(`turns[${i}].role must be one of ${DIALOGUE_EXPORT_ROLES.join("/")}`);
      }
      if (typeof turn?.content !== "string" || turn.content.length === 0) {
        errors.push(`turns[${i}].content must be a non-empty string`);
      }
      if (turn?.timestamp !== undefined && Number.isNaN(Date.parse(turn.timestamp))) {
        errors.push(`turns[${i}].timestamp must be ISO8601 when present`);
      }
    });
  }
  return { ok: errors.length === 0, errors };
}

/**
 * 宿主导出入口（未实现——TD-01）。
 * 任何调用立即以可观测的 HostUnsupportedError 失败；不得在此虚构宿主 API。
 * @returns {Promise<DialogueExport>}
 */
export async function exportDialogueFromHost() {
  throw new HostUnsupportedError(
    "TD-01: Codex host export mechanism not confirmed; real adapter lands in L07 after confirmation",
  );
}
