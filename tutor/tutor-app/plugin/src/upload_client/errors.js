/**
 * L10 CMP-UPLOAD-CLIENT — 稳定错误类型（不改任何父契约错误码）。
 *
 * 本模块内部错误仅用于本地编程/配置类失败（不发网络请求即可判定）；
 * 线上 CT-001/CT-002/auth-token 的错误码（AUTH_INVALID、VALIDATION_FAILED、
 * PAYLOAD_TOO_LARGE、UNSUPPORTED_MEDIA_TYPE、REJECTED_MEMBERSHIP、NOT_FOUND）
 * 原样透传到 UploadOutcome，不在此重定义。
 */

/** 本叶子本地错误码（非线上契约错误码）。 */
export const UPLOAD_CLIENT_ERROR_CODES = Object.freeze([
  "UP-ERR-JOB-INVALID",
  "UP-ERR-CATEGORY-UNKNOWN",
  "UP-ERR-TRANSPORT-INVALID",
]);

/** 可解释的本地失败（code 定位原因；消息不含令牌与材料正文）。 */
export class UploadClientError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "UploadClientError";
    this.code = code;
    this.reason = reason;
  }
}
