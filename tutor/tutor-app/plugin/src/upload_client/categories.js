/**
 * L10 CMP-UPLOAD-CLIENT — 类别映射（叶子内常量表）。
 *
 * 内部类别 id（与 L06 CMP-MATERIAL-COLLECTOR 的 code/screenshot/result 及
 * L07 对话导出物 dialogue 一致）→ CT-001 material_chunks.category 中文枚举
 * （对话/代码/截图/结果，contracts/ct-001.json 线上 schema）。
 *
 * 这是内部映射，不改变 CT-001 schema 或类别集合；新增/变更类别属于
 * 契约变更（return_to_parent），不得在本叶子内扩展。
 */

import { UploadClientError } from "./errors.js";

/** 内部类别 id → CT-001 中文类别（一一对应，冻结）。 */
export const CATEGORY_ID_TO_CT001 = Object.freeze({
  dialogue: "对话",
  code: "代码",
  screenshot: "截图",
  result: "结果",
});

/** 受支持的内部类别 id（与映射表键集合一致）。 */
export const INTERNAL_CATEGORY_IDS = Object.freeze(Object.keys(CATEGORY_ID_TO_CT001));

/**
 * 内部类别 id 映射为 CT-001 中文类别。
 * 未知 id 是调用方缺陷：本地显式失败，不发任何网络请求。
 * @param {string} internalId
 * @returns {"对话"|"代码"|"截图"|"结果"}
 */
export function toCt001Category(internalId) {
  const mapped = CATEGORY_ID_TO_CT001[internalId];
  if (mapped === undefined) {
    throw new UploadClientError(
      "UP-ERR-CATEGORY-UNKNOWN",
      `unknown internal category id: ${String(internalId)}（支持的 id 见 CATEGORY_ID_TO_CT001）`,
    );
  }
  return mapped;
}
