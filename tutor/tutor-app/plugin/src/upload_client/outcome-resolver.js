/**
 * L10 CMP-UPLOAD-OUTCOME-RESOLVER — TransferObservation/CT-002 快照 → UploadOutcome。
 *
 * 语义（L2 04 IC-UP-005/006；LCD-UP-004；NFR-003）：
 * - received → confirmed；rejected → rejected（原因原样）；
 *   interrupted → interrupted（保留待上传语义）；
 * - unknown（30 秒未确认）不是终态：先 CT-002 指数退避查询，收敛前绝不重发整包；
 * - CT-002 received/processing/scored → confirmed（服务端已持有提交）；
 *   rejected → rejected；upload_failed/scoring_failed/deleted → interrupted；
 * - NOT_FOUND → interrupted（服务端无此 uuid，父队列可从 checkpoint 恢复）；
 * - 查询仍不可达（退避耗尽）→ unknown（不伪造服务端终态）。
 */

export const DEFAULT_QUERY_BACKOFF_MS = Object.freeze([1_000, 2_000, 4_000]);

const defaultSleep = (ms) =>
  new Promise((resolve) => {
    const h = setTimeout(resolve, ms);
    h.unref?.();
  });

/**
 * @param {Object} deps
 * @param {{queryStatus: Function}} deps.sessionDriver
 * @param {(ms: number) => Promise<void>} [deps.sleep]
 * @param {number[]} [deps.backoffMs]  指数退避序列（LCD-UP-006 参数）
 * @param {(event: Object) => void} [deps.onEvent]
 */
export function createOutcomeResolver({
  sessionDriver,
  sleep = defaultSleep,
  backoffMs = DEFAULT_QUERY_BACKOFF_MS,
  onEvent = () => {},
}) {
  /** CT-001 直接观察 → UploadOutcome（不含 unknown；unknown 走 resolveUnknown）。 */
  function outcomeFromObservation(submission_uuid, obs) {
    switch (obs.type) {
      case "received":
        return {
          submission_uuid,
          outcome_type: "confirmed",
          submission_id: obs.submission_id,
          received_at: obs.received_at,
          missing_items: obs.missing_items ?? [],
        };
      case "rejected":
        return {
          submission_uuid,
          outcome_type: "rejected",
          rejection_reason: obs.rejection_reason,
        };
      default:
        return {
          submission_uuid,
          outcome_type: "interrupted",
          interruption_cause: obs.interruption_cause ?? "UNKNOWN_INTERRUPT",
        };
    }
  }

  /** CT-002 快照 → 收敛结果；不可收敛返回 null（继续退避）。 */
  function outcomeFromSnapshot(submission_uuid, body) {
    switch (body?.status) {
      case "received":
      case "processing":
      case "scored":
        return {
          submission_uuid,
          outcome_type: "confirmed",
          submission_id: body.submission_id,
          received_at: body.received_at ?? null,
          missing_items: Array.isArray(body.missing_items) ? body.missing_items : [],
        };
      case "rejected":
        return {
          submission_uuid,
          outcome_type: "rejected",
          rejection_reason: body.failure_reason ?? "rejected",
        };
      case "upload_failed":
      case "scoring_failed":
      case "deleted":
        return {
          submission_uuid,
          outcome_type: "interrupted",
          interruption_cause: body.status,
          failure_reason: body.failure_reason ?? null,
        };
      default:
        return null;
    }
  }

  /**
   * unknown → CT-002 指数退避查询直至收敛或耗尽（IC-UP-006 / R-UP-03）。
   * @returns {Promise<Object>} UploadOutcome
   */
  async function resolveUnknown(identity, submission_uuid) {
    for (let attempt = 1; attempt <= backoffMs.length; attempt += 1) {
      await sleep(backoffMs[attempt - 1]);
      onEvent({ event: "RemoteStatusQuery", submission_uuid, query_attempt: attempt });
      const res = await sessionDriver.queryStatus(identity, submission_uuid);
      if (res.kind === "snapshot") {
        const outcome = outcomeFromSnapshot(submission_uuid, res.body);
        if (outcome !== null) {
          onEvent({ event: "RemoteStatusResolved", submission_uuid, outcome_type: outcome.outcome_type });
          return outcome;
        }
        // 快照语义不明：保守按仍不可达继续退避（不伪造终态）
        continue;
      }
      if (res.kind === "not_found") {
        onEvent({ event: "RemoteStatusResolved", submission_uuid, outcome_type: "interrupted" });
        return {
          submission_uuid,
          outcome_type: "interrupted",
          interruption_cause: "NOT_FOUND",
        };
      }
      if (res.kind === "auth_failed") {
        return {
          submission_uuid,
          outcome_type: "interrupted",
          interruption_cause: "AUTH_INVALID",
        };
      }
      // unreachable：继续退避
    }
    onEvent({ event: "RemoteStatusUnresolved", submission_uuid });
    return {
      submission_uuid,
      outcome_type: "unknown",
      unknown_reason: "UNREACHABLE",
    };
  }

  return { outcomeFromObservation, resolveUnknown };
}
