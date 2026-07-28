/**
 * L11 CMP-PENDING-QUEUE — PendingTask 状态机（ST-04 / ST-PQ-01）。
 *
 * 合法迁移表是本地唯一权威；任何状态推进必须经 assertTransition，
 * 非法迁移以 InvalidTransitionError 拒绝（IC-PQ-001 INVALID_TRANSITION）。
 *
 * 主线（vibecode-task）：created → collecting → queued → uploading
 *   →（completed | failed_retryable | failed_terminal）
 * 附加保持 L1/L2 语义：
 * - uploading → confirm_required：CT-001 30 秒未确认（结果未知，保留不伪造结论）；
 * - failed_retryable → collecting：采集失败保留待恢复，恢复时重采（尚无快照，不违反 INV-4）；
 * - failed_retryable / confirm_required → uploading：恢复续传（同一 uuid + checkpoint）。
 * 终态 completed / failed_terminal 不可恢复（PQ-INV-005 保留边界）。
 */

export const TASK_STATES = Object.freeze([
  "created",
  "collecting",
  "queued",
  "uploading",
  "completed",
  "failed_retryable",
  "failed_terminal",
  "confirm_required",
]);

/** 终态：仅来自上传端口应答（confirmed/rejected），本地绝不自行判定服务端语义。 */
export const TERMINAL_STATES = Object.freeze(["completed", "failed_terminal"]);

/** 可恢复保留态：断网/中断/结果未知时任务与上传状态必须保留（D-AC exceptions）。 */
export const RECOVERABLE_STATES = Object.freeze(["failed_retryable", "confirm_required"]);

const TRANSITIONS = Object.freeze({
  created: Object.freeze(["collecting"]),
  collecting: Object.freeze(["queued", "failed_retryable"]),
  queued: Object.freeze(["uploading", "failed_retryable"]),
  uploading: Object.freeze([
    "completed",
    "failed_retryable",
    "failed_terminal",
    "confirm_required",
  ]),
  failed_retryable: Object.freeze(["collecting", "uploading"]),
  confirm_required: Object.freeze(["uploading"]),
  completed: Object.freeze([]),
  failed_terminal: Object.freeze([]),
});

/** 非法状态迁移（可观测拒绝；不静默改写状态）。 */
export class InvalidTransitionError extends Error {
  constructor(from, to) {
    super(`INVALID_TRANSITION: ${from} -> ${to} is not allowed`);
    this.name = "InvalidTransitionError";
    this.code = "INVALID_TRANSITION";
    this.from = from;
    this.to = to;
  }
}

export function isTerminalState(state) {
  return TERMINAL_STATES.includes(state);
}

export function isRecoverableState(state) {
  return RECOVERABLE_STATES.includes(state);
}

export function canTransition(from, to) {
  return Array.isArray(TRANSITIONS[from]) && TRANSITIONS[from].includes(to);
}

/**
 * 校验一次状态迁移；非法即抛 InvalidTransitionError。
 * @param {string} from
 * @param {string} to
 * @returns {void}
 */
export function assertTransition(from, to) {
  if (!TASK_STATES.includes(from)) {
    throw new InvalidTransitionError(from, to);
  }
  if (!canTransition(from, to)) {
    throw new InvalidTransitionError(from, to);
  }
}
