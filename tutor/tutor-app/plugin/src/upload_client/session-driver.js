/**
 * L10 CMP-UPLOAD-SESSION-DRIVER — CT-001 会话/分片/合并与 CT-002 查询执行。
 *
 * 语义（L2 04 IC-UP-003 / IC-UP-004；L2-UP-INV-001/003/004；L2-UP-IDEM-001）：
 * - 分片协议：创建会话 → 逐分片 → 提交合并（POST /api/v1/submissions，
 *   phase 区分子协议步骤；路径/字段沿用 CT-001，未新增线上端点）；
 * - checkpoint（ST-05）只在服务端 ack 后写入；恢复时复用同一 uuid + session +
 *   checkpoint，跳过已确认分片，不新建重复 Submission；
 * - 任一请求 401/AUTH_INVALID → 失效租约、重取一次、只重放当前未确认请求；
 * - 合并请求 confirmTimeoutMs（默认 30s，NFR-003）无确认 → unknown 观察，
 *   绝不重发整包；
 * - CT-002 只读查询（GET /api/v1/submissions/{uuid}），无副作用；
 * - transport 依赖注入，本模块不发真实网络请求。
 */

import { toCt001Category } from "./categories.js";
import { UploadClientError } from "./errors.js";

export const DEFAULT_CONFIRM_TIMEOUT_MS = 30_000;

/** 默认计时器：unref 避免挂起进程。 */
const defaultTimers = {
  setTimeout: (fn, ms) => {
    const h = setTimeout(fn, ms);
    h.unref?.();
    return h;
  },
  clearTimeout: (h) => clearTimeout(h),
};

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/**
 * 创建会话驱动器。
 * @param {Object} deps
 * @param {(req: Object) => Promise<{status: number, body?: any}>} deps.transport
 * @param {{getLease: Function, invalidate: Function}} deps.authAdapter
 * @param {{load: Function, save: Function, clear: Function}} deps.checkpointStore
 * @param {() => number} [deps.clock]
 * @param {number} [deps.confirmTimeoutMs]  合并确认超时（默认 30s）
 * @param {{setTimeout: Function, clearTimeout: Function}} [deps.timers]
 * @param {(event: Object) => void} [deps.onEvent]
 */
export function createSessionDriver({
  transport,
  authAdapter,
  checkpointStore,
  clock = () => Date.now(),
  confirmTimeoutMs = DEFAULT_CONFIRM_TIMEOUT_MS,
  timers = defaultTimers,
  onEvent = () => {},
}) {
  if (typeof transport !== "function") {
    throw new UploadClientError("UP-ERR-TRANSPORT-INVALID", "transport must be a function");
  }

  /**
   * 带授权的传输调用；401/AUTH_INVALID → 失效租约并重取后重放当前请求一次
   * （L2-UP-INV-004 / IC-UP-003：只重放当前未确认请求）。
   * @returns {Promise<{kind: "ok", status: number, body: any} | {kind: "interrupted", cause: string} | {kind: "auth_failed"}>}
   */
  async function sendWithAuth(identity, buildRequest, { allowAuthRetry = true } = {}) {
    let lease;
    try {
      lease = await authAdapter.getLease(identity);
    } catch (err) {
      if (err?.code === "UP-ERR-AUTH") return { kind: "auth_failed" };
      return { kind: "interrupted", cause: "NETWORK_INTERRUPTED" };
    }

    const attempt = async () => {
      const req = buildRequest();
      req.headers = { ...(req.headers ?? {}), authorization: `Bearer ${lease.token}` };
      try {
        const res = await transport(req);
        return { kind: "ok", status: res?.status, body: res?.body ?? {} };
      } catch {
        return { kind: "interrupted", cause: "NETWORK_INTERRUPTED" };
      }
    };

    let res = await attempt();
    if (
      res.kind === "ok" &&
      (res.status === 401 || res.body?.error_code === "AUTH_INVALID")
    ) {
      authAdapter.invalidate();
      if (!allowAuthRetry) return { kind: "auth_failed" };
      try {
        lease = await authAdapter.getLease(identity, { forceRefresh: true });
      } catch (err) {
        if (err?.code === "UP-ERR-AUTH") return { kind: "auth_failed" };
        return { kind: "interrupted", cause: "NETWORK_INTERRUPTED" };
      }
      res = await attempt(); // 只重放当前请求一次
      if (
        res.kind === "ok" &&
        (res.status === 401 || res.body?.error_code === "AUTH_INVALID")
      ) {
        authAdapter.invalidate();
        return { kind: "auth_failed" };
      }
    }
    return res;
  }

  /** 4xx/5xx 按线上错误码原样呈现为 interrupted（不伪造服务端终态）。 */
  function httpErrorObservation(status, body) {
    const code = body?.error_code;
    return {
      type: "interrupted",
      interruption_cause: typeof code === "string" ? code : `HTTP_${status}`,
    };
  }

  function mergeOutcomeFromBody(status, body) {
    if (body?.status === "received" && typeof body.submission_id === "string") {
      return {
        type: "received",
        submission_id: body.submission_id,
        received_at: body.received_at ?? null,
        missing_items: Array.isArray(body.missing_items) ? body.missing_items : [],
      };
    }
    if (body?.status === "rejected") {
      return {
        type: "rejected",
        rejection_reason: body.rejection_reason ?? "rejected",
      };
    }
    return httpErrorObservation(status, body);
  }

  function chunkMeta(chunk) {
    return {
      category: toCt001Category(chunk.category),
      filename: chunk.filename ?? null,
      media_type: chunk.media_type ?? null,
      size_bytes: chunk.size_bytes ?? null,
    };
  }

  /**
   * 执行 StartUpload/ResumeUpload（IC-UP-003）。
   * @param {Object} command
   * @param {string} command.submission_uuid
   * @param {{chunks: Array}} command.bundle_ref
   * @param {Object} command.identity
   * @param {Object|null} [command.checkpoint]  既有 ST-05（ResumeUpload）
   * @returns {Promise<Object>} TransferObservation：
   *   {type:"received"|"rejected"|"interrupted"|"unknown", ...}
   */
  async function execute({ submission_uuid, bundle_ref, identity, checkpoint = null }) {
    const chunks = bundle_ref.chunks;
    const confirmed = new Set(checkpoint?.confirmed_chunks ?? []);
    let sessionId = checkpoint?.upload_session_id ?? null;

    // 1) 创建上传会话（uuid 幂等；有 checkpoint 会话则复用，不发第二次创建）
    if (sessionId === null) {
      const res = await sendWithAuth(identity, () => ({
        method: "POST",
        path: "/api/v1/submissions",
        body: {
          phase: "create_session",
          submission_uuid,
          invite_code: identity.invite_code,
          student_name: identity.student_name,
          group_name: identity.group_name,
          assignment: identity.assignment,
          material_chunks: chunks.map(chunkMeta),
          total_chunks: chunks.length,
        },
      }));
      if (res.kind === "interrupted") {
        return { type: "interrupted", interruption_cause: res.cause };
      }
      if (res.kind === "auth_failed") {
        return { type: "interrupted", interruption_cause: "AUTH_INVALID" };
      }
      if (res.status < 200 || res.status >= 300) {
        return httpErrorObservation(res.status, res.body);
      }
      sessionId = res.body?.upload_session_id;
      if (typeof sessionId !== "string" || sessionId === "") {
        throw new UploadClientError(
          "UP-ERR-TRANSPORT-INVALID",
          "create_session response missing upload_session_id",
        );
      }
      onEvent({ event: "UploadSessionCreated", submission_uuid });
    }

    // 初始/恢复 checkpoint：会话与总分片数元数据（不含任何未确认分片）
    let cp = {
      submission_uuid,
      upload_session_id: sessionId,
      confirmed_chunks: [...confirmed].sort((a, b) => a - b),
      total_chunks: chunks.length,
      last_ack_at: checkpoint?.last_ack_at ?? null,
    };
    await checkpointStore.save(cp);

    // 2) 逐分片：跳过已确认（INV-5），ack 后单写 checkpoint（L2-UP-CON-001）
    for (let i = 0; i < chunks.length; i += 1) {
      if (confirmed.has(i)) continue;
      const chunk = chunks[i];
      const res = await sendWithAuth(identity, () => ({
        method: "POST",
        path: "/api/v1/submissions",
        body: {
          phase: "chunk",
          submission_uuid,
          upload_session_id: sessionId,
          chunk_index: i,
          chunk: {
            ...chunkMeta(chunk),
            content_ref: chunk.content_ref ?? null,
            content: chunk.content ?? null,
          },
        },
      }));
      if (res.kind === "interrupted") {
        onEvent({ event: "UploadInterrupted", submission_uuid, chunk_index: i });
        return { type: "interrupted", interruption_cause: res.cause };
      }
      if (res.kind === "auth_failed") {
        return { type: "interrupted", interruption_cause: "AUTH_INVALID" };
      }
      if (res.status < 200 || res.status >= 300 || res.body?.acked !== true) {
        if (res.body?.status === "rejected") return mergeOutcomeFromBody(res.status, res.body);
        return httpErrorObservation(res.status, res.body);
      }
      confirmed.add(i);
      cp = {
        ...cp,
        confirmed_chunks: [...confirmed].sort((a, b) => a - b),
        last_ack_at: new Date(clock()).toISOString(),
      };
      await checkpointStore.save(cp); // ack 后写（INV-5）
      onEvent({ event: "ChunkAcknowledged", submission_uuid, chunk_index: i });
    }

    // 3) 提交合并；confirmTimeoutMs 无确认 → unknown（L2-UP-INV-003，不重发整包）
    const mergeCall = sendWithAuth(identity, () => ({
      method: "POST",
      path: "/api/v1/submissions",
      body: { phase: "merge", submission_uuid, upload_session_id: sessionId },
    }));
    const winner = await Promise.race([
      mergeCall.then((r) => ({ tag: "response", r })),
      new Promise((resolve) =>
        timers.setTimeout(() => resolve({ tag: "timeout" }), confirmTimeoutMs),
      ),
    ]);
    if (winner.tag === "timeout") {
      onEvent({ event: "UploadConfirmationTimedOut", submission_uuid });
      return { type: "unknown", unknown_reason: "CONFIRM_TIMEOUT" };
    }
    const res = winner.r;
    if (res.kind === "interrupted") {
      return { type: "interrupted", interruption_cause: res.cause };
    }
    if (res.kind === "auth_failed") {
      return { type: "interrupted", interruption_cause: "AUTH_INVALID" };
    }
    if (res.status < 200 || res.status >= 300) {
      return httpErrorObservation(res.status, res.body);
    }
    return mergeOutcomeFromBody(res.status, res.body);
  }

  /**
   * CT-002 只读状态查询（IC-UP-004；无副作用，天然幂等）。
   * @returns {Promise<{kind: "snapshot", body: Object} | {kind: "not_found"} | {kind: "unreachable"} | {kind: "auth_failed"}>}
   */
  async function queryStatus(identity, submission_uuid) {
    const res = await sendWithAuth(identity, () => ({
      method: "GET",
      path: `/api/v1/submissions/${encodeURIComponent(submission_uuid)}`,
    }));
    if (res.kind === "interrupted") return { kind: "unreachable" };
    if (res.kind === "auth_failed") return { kind: "auth_failed" };
    if (res.status === 404 || res.body?.error_code === "NOT_FOUND") return { kind: "not_found" };
    if (typeof res.status !== "number" || res.status < 200 || res.status >= 300) {
      return { kind: "unreachable" };
    }
    return { kind: "snapshot", body: res.body ?? {} };
  }

  return { execute, queryStatus };
}
