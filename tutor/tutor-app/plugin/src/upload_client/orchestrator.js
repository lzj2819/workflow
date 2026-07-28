/**
 * L10 CMP-UPLOAD-ORCHESTRATOR — IC-M01-04 上传执行入口（UploadJob → UploadOutcome）。
 *
 * 语义（L2 04 IC-UP-001；LCD-UP-003；ST-L2-02 ActiveUploadGuard）：
 * - 同一 submission_uuid 至多一个 active execution；重复 Start/Resume 归并到
 *   既有执行句柄（L2-UP-INV-002），不开第二个活跃会话；
 * - 编排 AUTH-ADAPTER / SESSION-DRIVER / OUTCOME-RESOLVER；不直接拼装
 *   CT-001 字段、不写 checkpoint、不决定服务端终态；
 * - unknown 观察一律转 CT-002 查询收敛（LCD-UP-004），不重发整包。
 */

import { toCt001Category } from "./categories.js";
import { UploadClientError } from "./errors.js";

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function validateJob(job) {
  if (!isPlainObject(job)) {
    throw new UploadClientError("UP-ERR-JOB-INVALID", "UploadJob must be an object");
  }
  if (typeof job.submission_uuid !== "string" || job.submission_uuid.trim() === "") {
    throw new UploadClientError("UP-ERR-JOB-INVALID", "submission_uuid must be a non-empty string");
  }
  const identity = job.identity;
  if (!isPlainObject(identity)) {
    throw new UploadClientError("UP-ERR-JOB-INVALID", "identity must be an object");
  }
  for (const f of ["invite_code", "student_name", "group_name", "assignment"]) {
    if (typeof identity[f] !== "string" || identity[f].trim() === "") {
      throw new UploadClientError("UP-ERR-JOB-INVALID", `identity.${f} must be a non-empty string`);
    }
  }
  const chunks = job.bundle_ref?.chunks;
  if (!Array.isArray(chunks)) {
    throw new UploadClientError("UP-ERR-JOB-INVALID", "bundle_ref.chunks must be an array");
  }
  for (const [i, chunk] of chunks.entries()) {
    if (!isPlainObject(chunk) || typeof chunk.category !== "string") {
      throw new UploadClientError(
        "UP-ERR-JOB-INVALID",
        `bundle_ref.chunks[${i}] must be an object with string category`,
      );
    }
    // 类别 id 本地预校验：未知类别在任何网络请求之前显式失败
    toCt001Category(chunk.category);
  }
}

/**
 * @param {Object} deps
 * @param {{execute: Function}} deps.sessionDriver
 * @param {{outcomeFromObservation: Function, resolveUnknown: Function}} deps.outcomeResolver
 * @param {{load: Function, save: Function, clear: Function}} deps.checkpointStore
 * @param {(event: Object) => void} [deps.onEvent]
 */
export function createUploadOrchestrator({
  sessionDriver,
  outcomeResolver,
  checkpointStore,
  onEvent = () => {},
}) {
  /** ST-L2-02：uuid → 执行中的 UploadOutcome Promise（仅内存）。 */
  const activeByUuid = new Map();

  /**
   * StartOrResumeUpload（IC-M01-04）。同一 uuid 重复调用归并到既有执行。
   * @param {Object} job  UploadJob{submission_uuid, bundle_ref, identity, checkpoint?}
   * @returns {Promise<Object>} UploadOutcome{outcome_type, ...}
   */
  function startOrResumeUpload(job) {
    try {
      validateJob(job);
    } catch (err) {
      // 校验失败统一走 Promise 拒绝（不同步抛出），与异步执行路径一致
      return Promise.reject(err);
    }
    const uuid = job.submission_uuid;

    const active = activeByUuid.get(uuid);
    if (active !== undefined) {
      onEvent({ event: "UploadExecutionMerged", submission_uuid: uuid });
      return active;
    }

    const execution = (async () => {
      const checkpoint = job.checkpoint ?? (await checkpointStore.load(uuid));
      const obs = await sessionDriver.execute({
        submission_uuid: uuid,
        bundle_ref: job.bundle_ref,
        identity: job.identity,
        checkpoint,
      });
      const outcome =
        obs.type === "unknown"
          ? await outcomeResolver.resolveUnknown(job.identity, uuid)
          : outcomeResolver.outcomeFromObservation(uuid, obs);
      onEvent({
        event: "UploadOutcomeProduced",
        submission_uuid: uuid,
        outcome_type: outcome.outcome_type,
      });
      return outcome;
    })();

    activeByUuid.set(uuid, execution);
    // 终态/取消后释放执行保护；保持同一 Promise 实例供归并方 await
    execution.finally(() => {
      if (activeByUuid.get(uuid) === execution) activeByUuid.delete(uuid);
    }).catch(() => {});
    return execution;
  }

  /** 终态（confirmed/rejected）后由父队列触发清理 ST-05（L2 03 cleanup_trigger）。 */
  async function discardCheckpoint(submission_uuid) {
    await checkpointStore.clear(submission_uuid);
  }

  return { startOrResumeUpload, discardCheckpoint };
}
