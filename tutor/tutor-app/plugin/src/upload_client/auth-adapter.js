/**
 * L10 CMP-UPLOAD-AUTH-ADAPTER — auth/token 换领与内存令牌租约（ST-L2-01）。
 *
 * 语义（L2 04 IC-UP-002 / LCD-UP-002 / LCD-006 / KD-005）：
 * - 按 identity context（invite_code+student_name+group_name 摘要）复用未过期
 *   Bearer token；过期或显式失效后重新换领；
 * - 租约仅进程内存持有：不落盘、不进 checkpoint、不进材料包；
 * - 令牌绝不写入日志/错误消息（本模块事件与错误只含状态码与上下文摘要）；
 * - AUTH_INVALID 由调用方触发 invalidate() 后重取；本适配器不修改 identity、
 *   不做名单校验（归服务端 CT-003 语义）。
 */

import { createHash } from "node:crypto";

import { UploadClientError } from "./errors.js";

/** 提前续约余量：避免租约在飞行中请求期间过期。 */
export const DEFAULT_LEASE_SKEW_MS = 30_000;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function contextHashOf(identity) {
  return createHash("sha256")
    .update(
      `${identity.invite_code}\x00${identity.student_name}\x00${identity.group_name}`,
      "utf8",
    )
    .digest("hex");
}

function validateIdentity(identity) {
  if (!isPlainObject(identity)) {
    throw new UploadClientError("UP-ERR-JOB-INVALID", "identity must be an object");
  }
  for (const f of ["invite_code", "student_name", "group_name"]) {
    if (typeof identity[f] !== "string" || identity[f].trim() === "") {
      throw new UploadClientError(
        "UP-ERR-JOB-INVALID",
        `identity.${f} must be a non-empty string`,
      );
    }
  }
}

/**
 * 创建认证适配器。
 * @param {Object} deps
 * @param {(req: {method: string, path: string, headers?: Object, body?: Object}) => Promise<{status: number, body?: any}>} deps.transport
 * @param {() => number} [deps.clock]   毫秒时钟（默认 Date.now）
 * @param {number} [deps.leaseSkewMs]   过期判定余量（默认 30s）
 * @param {(event: Object) => void} [deps.onEvent]  结构化事件（绝不含 token）
 */
export function createAuthAdapter({
  transport,
  clock = () => Date.now(),
  leaseSkewMs = DEFAULT_LEASE_SKEW_MS,
  onEvent = () => {},
}) {
  if (typeof transport !== "function") {
    throw new UploadClientError("UP-ERR-TRANSPORT-INVALID", "transport must be a function");
  }

  /** ST-L2-01：内存唯一租约；{token, expires_at, context_hash}。 */
  let lease = null;

  function isUsable(candidate, contextHash) {
    return (
      candidate !== null &&
      candidate.context_hash === contextHash &&
      candidate.expires_at > clock() + leaseSkewMs
    );
  }

  /**
   * 获取当前有效租约；缓存命中不重复换领，未命中/过期时调用 auth/token。
   * @param {{invite_code: string, student_name: string, group_name: string}} identity
   * @param {{forceRefresh?: boolean}} [opts]  401/AUTH_INVALID 后强制重取
   * @returns {Promise<{token: string, expires_at: number, context_hash: string}>}
   */
  async function getLease(identity, { forceRefresh = false } = {}) {
    validateIdentity(identity);
    const contextHash = contextHashOf(identity);
    if (!forceRefresh && isUsable(lease, contextHash)) {
      onEvent({ event: "TokenLeaseReused", context_hash: contextHash });
      return lease;
    }

    let res;
    try {
      res = await transport({
        method: "POST",
        path: "/api/v1/auth/token",
        body: {
          invite_code: identity.invite_code,
          student_name: identity.student_name,
          group_name: identity.group_name,
        },
      });
    } catch (err) {
      // 网络层中断：不失效现有租约语义，由调用方按 interrupted 处理
      onEvent({ event: "AuthTokenRequestInterrupted", context_hash: contextHash });
      throw new UploadClientError(
        "UP-ERR-AUTH-UNREACHABLE",
        `auth/token request interrupted (${err?.code ?? err?.name ?? "network error"})`,
      );
    }

    const body = res?.body ?? {};
    if (res.status === 401 || body.error_code === "AUTH_INVALID") {
      lease = null;
      onEvent({ event: "TokenLeaseInvalidated", context_hash: contextHash, reason: "AUTH_INVALID" });
      throw new UploadClientError("UP-ERR-AUTH", "AUTH_INVALID: credentials rejected by auth/token");
    }
    if (typeof res.status !== "number" || res.status < 200 || res.status >= 300) {
      throw new UploadClientError(
        "UP-ERR-AUTH-UNREACHABLE",
        `auth/token unexpected status ${String(res?.status)}`,
      );
    }
    if (
      typeof body.access_token !== "string" ||
      body.access_token === "" ||
      !Number.isInteger(body.expires_in) ||
      body.expires_in < 1
    ) {
      throw new UploadClientError(
        "UP-ERR-TRANSPORT-INVALID",
        "auth/token response missing access_token/expires_in",
      );
    }

    // 替换而非复用旧租约（ST-L2-01 单写方）
    lease = {
      token: body.access_token,
      expires_at: clock() + body.expires_in * 1000,
      context_hash: contextHash,
    };
    onEvent({
      event: "TokenLeaseReady",
      context_hash: contextHash,
      expires_at: new Date(lease.expires_at).toISOString(),
    });
    return lease;
  }

  /** 使当前租约立即失效（401/AUTH_INVALID 后调用；L2-UP-INV-004）。 */
  function invalidate() {
    if (lease !== null) {
      onEvent({ event: "TokenLeaseInvalidated", context_hash: lease.context_hash, reason: "local" });
    }
    lease = null;
  }

  return { getLease, invalidate };
}
