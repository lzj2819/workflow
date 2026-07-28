/**
 * L11 CMP-PENDING-QUEUE — 本地任务队列与采集编排枢纽（MOD-01 / DU-1）。
 *
 * 职责（IC-M01-01/03/04/05 编排侧；IC-PQ-000/002/003/005）：
 * - 意图入口闸门：缺作业/姓名/小组或配置前置失败 → 不建任务、零网络调用
 *   （INV-1 / PQ-INV-001）；
 * - 任务创建：submission_uuid 生成一次且全程不变（INV-2 / PQ-INV-002）；
 *   创建即快照意图与配置（LCD-002），落盘后才开始采集；
 * - 采集编排（IC-M01-03）：对话采集端口（L07，TD-01 unsupported 状态）与
 *   材料采集端口（L06 形状）均经注入消费；一次性快照，重传不重采（INV-4）。
 *   HostUnsupportedError 显式传播为可观测失败原因——不得静默转为「对话缺失」、
 *   不得伪造对话导出物；
 * - 上传驱动（IC-M01-04 / IC-PQ-003）：组装 UploadJob 交注入的上传端口（L10）；
 *   confirmed → completed；rejected → failed_terminal（不自动重试）；
 *   interrupted → failed_retryable 保留 + 失败原因 + 退避恢复计划；
 *   unknown → confirm_required 保留（结果未知，不伪造结论）；
 * - 恢复调度（LCD-005 / LCD-PQ-001）：启动扫描 + triggerRecovery 事件触发，
 *   trigger_id 去重，单任务租约（PQ-INV-003），failed_terminal 不可恢复；
 * - 状态展示数据源（IC-M01-05）：StatusView 真实状态/原因，不伪造结论。
 *
 * 零运行时依赖；所有兄弟叶子能力（L04/L05/L06/L07/L10/L13）只经冻结端口注入消费。
 */

import { randomUUID } from "node:crypto";
import { HostUnsupportedError } from "../host/dialogue-export-port.js";
import {
  assertTransition,
  isRecoverableState,
  isTerminalState,
  TASK_STATES,
} from "./task-machine.js";
import { createStateStore } from "./state-store.js";
import { createRecoveryScheduler } from "./recovery.js";

export const QUEUE_ERROR_CODES = Object.freeze([
  "INTENT_INCOMPLETE",
  "CONFIG_UNAVAILABLE",
  "INVALID_TRANSITION",
  "STATE_CORRUPT",
  "VIEW_NOT_AVAILABLE",
  "TRIGGER_INVALID",
  "PORT_MISSING",
  "HOST_EXPORT_UNSUPPORTED",
  "DIALOGUE_EXPORT_FAILED",
  "MATERIAL_COLLECTION_FAILED",
  "UPLOAD_REJECTED",
  "NETWORK_INTERRUPTED",
  "REMOTE_STATUS_UNKNOWN",
]);

/** 队列层可观测错误（code 定位原因）。 */
export class PendingQueueError extends Error {
  constructor(code, message) {
    super(`${code}: ${message}`);
    this.name = "PendingQueueError";
    this.code = code;
  }
}

const REQUIRED_INTENT_FIELDS = Object.freeze(["assignment", "student_name", "group_name"]);

/** 单任务租约时长（implementation_detail；只保证单飞不变量 PQ-INV-003）。 */
const LEASE_MS = 120_000;

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function intentMissingFields(intent) {
  if (!isPlainObject(intent) || intent.complete !== true) {
    const declared = Array.isArray(intent?.missing) ? intent.missing : [];
    const missing = [...declared];
    for (const f of REQUIRED_INTENT_FIELDS) {
      if (!missing.includes(f) && (typeof intent?.[f] !== "string" || intent[f].trim() === "")) {
        missing.push(f);
      }
    }
    return missing.length > 0 ? missing : [...REQUIRED_INTENT_FIELDS];
  }
  return REQUIRED_INTENT_FIELDS.filter(
    (f) => typeof intent[f] !== "string" || intent[f].trim() === "",
  );
}

/** 配置前置检查（PQ-INV-001）：上传身份需要 invite_code；缺则不建任务。 */
function configPreconditionMissing(config) {
  if (!isPlainObject(config)) return ["invite_code"];
  const missing = [];
  if (typeof config.invite_code !== "string" || config.invite_code.trim() === "") {
    missing.push("invite_code");
  }
  return missing;
}

function pickConfigSnapshot(config) {
  const snapshot = {};
  for (const f of ["invite_code", "code_dir", "screenshot_dir", "result_dir"]) {
    if (typeof config?.[f] === "string") snapshot[f] = config[f];
  }
  return snapshot;
}

/**
 * 创建本地待上传任务队列。
 * @param {Object} deps
 * @param {string} deps.storagePath  StateStoreEnvelope JSON 文件路径（LCD-004）
 * @param {Object} deps.ports        冻结端口注入（全部为函数）
 * @param {() => (Object|null|Promise<Object|null>)} [deps.ports.readConfig]
 *        IC-M01-02 只读配置端口（L04）；返回 EffectiveConfig 或 null
 * @param {(taskRef: Object) => Promise<Object>} deps.ports.collectDialogue
 *        IC-M01-03 对话采集端口（L07；TD-01 下抛 HostUnsupportedError）
 * @param {(taskRef: Object) => Promise<Object>} deps.ports.collectMaterials
 *        IC-M01-03 材料采集端口（L06 形状，返回 MaterialManifest）
 * @param {(job: Object) => Promise<Object>} deps.ports.upload
 *        IC-M01-04 上传端口（L10）；返回 UploadOutcome{status, ...}
 * @param {{now: () => number}} [deps.clock]        注入时钟（epoch ms；默认 Date.now）
 * @param {() => string} [deps.uuidgen]             注入 uuid 生成（默认 crypto.randomUUID）
 * @param {number} [deps.backoffMs]                 恢复基础退避（默认 30000）
 * @param {Object} [deps.scheduler]                 可选定时器端口 {setTimer, clearTimer}
 */
export function createPendingQueue(deps = {}) {
  const ports = deps.ports ?? {};
  for (const name of ["collectDialogue", "collectMaterials", "upload"]) {
    if (typeof ports[name] !== "function") {
      throw new PendingQueueError("PORT_MISSING", `ports.${name} must be an injected function`);
    }
  }
  const store = createStateStore({ storagePath: deps.storagePath });
  const clock = deps.clock ?? { now: () => Date.now() };
  const uuidgen = deps.uuidgen ?? (() => randomUUID());

  const tasks = new Map(); // submission_uuid -> task record
  const commandIndex = new Map(); // command_id -> submission_uuid
  const seenTriggers = new Set(); // trigger_id 去重（IC-PQ-002）
  let mutex = Promise.resolve();

  const recovery = createRecoveryScheduler({
    clock,
    baseBackoffMs: deps.backoffMs ?? 30_000,
    scheduler: deps.scheduler ?? null,
    onDue: (taskUuid, attemptCount) => {
      void triggerRecovery({
        trigger_id: `backoff_due:${taskUuid}:${attemptCount}`,
        trigger_type: "backoff_due",
        task_uuid: taskUuid,
      });
    },
  });

  function nowIso() {
    return new Date(clock.now()).toISOString();
  }

  function withLock(fn) {
    const run = mutex.then(fn, fn);
    mutex = run.catch(() => {});
    return run;
  }

  async function persist() {
    await store.save({
      tasks: Object.fromEntries(tasks),
      command_index: Object.fromEntries(commandIndex),
      triggers: [...seenTriggers],
    });
  }

  function transition(task, to, reason = null) {
    assertTransition(task.state, to);
    task.history.push({ from: task.state, to, at: nowIso(), reason });
    task.state = to;
    task.updated_at = nowIso();
  }

  function taskRefOf(task) {
    return { submission_uuid: task.submission_uuid, state: task.state };
  }

  function isDue(task, nowMs) {
    return task.next_attempt_at == null || Date.parse(task.next_attempt_at) <= nowMs;
  }

  function hasActiveLease(task, nowMs) {
    return task.lease != null && Date.parse(task.lease.expires_at) > nowMs;
  }

  function scheduleRetry(task, triggerLabel) {
    task.attempt_count += 1;
    const { nextAttemptAt } = recovery.schedule(task.submission_uuid, task.attempt_count);
    task.next_attempt_at = nextAttemptAt;
    task.last_trigger = triggerLabel;
  }

  function clearSchedule(task) {
    task.next_attempt_at = null;
    recovery.cancel(task.submission_uuid);
  }

  function markCollectionFailure(task, kind, err) {
    if (kind === "dialogue" && (err instanceof HostUnsupportedError || err?.code === "HOST_EXPORT_UNSUPPORTED")) {
      // TD-01：显式传播 unsupported，绝不静默转为「对话缺失」、绝不伪造导出物
      task.failure_code = "HOST_EXPORT_UNSUPPORTED";
      task.failure_reason = `dialogue export unsupported (HOST_EXPORT_UNSUPPORTED): ${err?.detail ?? err?.message ?? "host export unavailable"}`;
    } else if (kind === "dialogue") {
      task.failure_code = "DIALOGUE_EXPORT_FAILED";
      task.failure_reason = `dialogue export failed: ${err?.message ?? String(err)}`;
    } else {
      task.failure_code = typeof err?.code === "string" ? err.code : "MATERIAL_COLLECTION_FAILED";
      task.failure_reason = `material collection failed: ${err?.message ?? String(err)}`;
    }
    if (task.state === "created") transition(task, "collecting");
    transition(task, "failed_retryable", task.failure_code);
    task.lease = null;
  }

  /**
   * 采集编排（IC-M01-03）：仅当任务尚无 bundle 快照时执行（INV-4 重传不重采）。
   * @returns {Promise<boolean>} true = 快照就绪并已推进 queued
   */
  async function runCollection(task) {
    if (task.bundle_ref != null) return true; // 已有创建时快照：恢复路径绝不重采
    if (task.state === "created") transition(task, "collecting");
    const taskRef = {
      submission_uuid: task.submission_uuid,
      intent: task.intent_snapshot,
      config_ref: task.config_snapshot,
    };

    let dialogueArtifact = null;
    try {
      dialogueArtifact = await ports.collectDialogue(taskRef);
    } catch (err) {
      markCollectionFailure(task, "dialogue", err);
      await persist();
      return false;
    }
    if (!isPlainObject(dialogueArtifact)) {
      // 端口返回空/非法产物同样不得伪造：显式失败
      markCollectionFailure(
        task,
        "dialogue",
        new Error("dialogue export returned no artifact; nothing fabricated"),
      );
      await persist();
      return false;
    }

    let materialManifest = null;
    try {
      materialManifest = await ports.collectMaterials(taskRef);
    } catch (err) {
      markCollectionFailure(task, "material", err);
      await persist();
      return false;
    }

    task.bundle_ref = {
      dialogue_artifact: dialogueArtifact,
      material_manifest: materialManifest,
      warnings: Array.isArray(materialManifest?.warnings) ? [...materialManifest.warnings] : [],
    };
    task.missing_items = Array.isArray(materialManifest?.missing_items)
      ? [...materialManifest.missing_items]
      : [];
    task.failure_code = null;
    task.failure_reason = null;
    transition(task, "queued");
    await persist();
    return true;
  }

  /** 上传驱动（IC-M01-04 / IC-PQ-003）：同一 uuid + 既有快照 + 可选 checkpoint。 */
  async function runDispatch(task) {
    if (isTerminalState(task.state)) return; // 终态不可恢复（PQ-INV-005）
    transition(task, "uploading", task.last_trigger ?? "dispatch");

    const nowMs = clock.now();
    if (hasActiveLease(task, nowMs)) {
      return; // LEASE_CONFLICT：另一执行进行中，本次触发归并（PQ-INV-003）
    }
    task.lease = {
      lease_id: uuidgen(),
      owner: "cmp-pending-queue",
      expires_at: new Date(nowMs + LEASE_MS).toISOString(),
    };
    await persist();

    const job = {
      submission_uuid: task.submission_uuid, // INV-2：全程不变
      bundle_ref: task.bundle_ref,
      identity: {
        invite_code: task.config_snapshot.invite_code,
        student_name: task.intent_snapshot.student_name,
        group_name: task.intent_snapshot.group_name,
        assignment: task.intent_snapshot.assignment,
      },
      dispatch_id: uuidgen(),
    };
    if (task.checkpoint_ref != null) job.checkpoint = task.checkpoint_ref;

    let outcome;
    try {
      outcome = await ports.upload(job);
    } catch (err) {
      outcome = { status: "interrupted", cause: `upload port threw: ${err?.message ?? String(err)}` };
    }
    task.lease = null;

    switch (outcome?.status) {
      case "confirmed":
        task.submission_id = outcome.submission_id ?? null;
        task.received_at = outcome.received_at ?? null;
        if (Array.isArray(outcome.missing_items)) task.missing_items = [...outcome.missing_items];
        task.failure_code = null;
        task.failure_reason = null;
        clearSchedule(task);
        transition(task, "completed");
        break;
      case "rejected":
        // 认证/校验/归属拒绝：终态，不自动重试（L2 04 §4）
        task.failure_code = "UPLOAD_REJECTED";
        task.failure_reason = `upload rejected: ${outcome.rejection_reason ?? "rejected by server"}`;
        clearSchedule(task);
        transition(task, "failed_terminal", task.failure_code);
        break;
      case "unknown":
        // 30 秒未确认：结果未知，保留任务，不伪造成功/失败结论
        task.failure_code = "REMOTE_STATUS_UNKNOWN";
        task.failure_reason =
          "remote status unknown: upload unconfirmed within 30s; result pending confirmation (no fabricated conclusion)";
        transition(task, "confirm_required", task.failure_code);
        scheduleRetry(task, "confirm_required");
        break;
      case "interrupted":
      default:
        task.failure_code = "NETWORK_INTERRUPTED";
        task.failure_reason = `upload interrupted: ${outcome?.cause ?? "network interrupted"}`;
        transition(task, "failed_retryable", task.failure_code);
        scheduleRetry(task, "interrupted");
        break;
    }
    await persist();
  }

  /**
   * 初始化：加载持久化状态（PQ-INV-004 只从最近一致 revision 恢复），
   * 归一化崩溃窗口状态，然后执行启动扫描（LCD-005 process_start 触发）。
   */
  async function init() {
    await withLock(async () => {
      const data = await store.load();
      tasks.clear();
      for (const [uuid, record] of Object.entries(data.tasks)) tasks.set(uuid, record);
      commandIndex.clear();
      for (const [cid, uuid] of Object.entries(data.command_index)) commandIndex.set(cid, uuid);
      seenTriggers.clear();
      for (const id of data.triggers) seenTriggers.add(id);

      const now = nowIso();
      for (const task of tasks.values()) {
        if (!Array.isArray(task.history)) task.history = [];
        if (task.state === "queued" || task.state === "uploading") {
          // 崩溃窗口：结果未持久化，保守转为 failed_retryable 并立即可恢复
          task.lease = null;
          task.failure_code = "NETWORK_INTERRUPTED";
          task.failure_reason =
            "process restarted before upload outcome persisted; resume scheduled from last consistent revision";
          transition(task, "failed_retryable", "process_restart");
          task.next_attempt_at = now;
        }
      }
      await persist();
    });
    await triggerRecovery({
      trigger_id: `process_start:${nowIso()}`,
      trigger_type: "process_start",
    });
  }

  /**
   * 意图入口（IC-PQ-000 / IC-M01-01 消费侧）。
   * @param {Object} intent IntentResult（complete + assignment/student_name/group_name）
   * @param {Object} [options]
   * @param {string} [options.command_id] 指令级幂等键（同键返回既有任务，PQ-IDEM-001）
   * @returns {Promise<{intake_result: string, task_ref: Object|null, missing_fields: string[], error?: string}>}
   */
  async function submitIntent(intent, options = {}) {
    return withLock(async () => {
      const missing = intentMissingFields(intent);
      if (missing.length > 0) {
        // INV-1：缺项不建任务、零网络调用
        return { intake_result: "info_incomplete", task_ref: null, missing_fields: missing };
      }
      const commandId = options.command_id ?? intent.command_id ?? null;
      if (commandId != null && commandIndex.has(commandId)) {
        const existing = tasks.get(commandIndex.get(commandId));
        if (existing) {
          return { intake_result: "duplicate", task_ref: taskRefOf(existing), missing_fields: [] };
        }
      }
      const config = typeof ports.readConfig === "function" ? await ports.readConfig() : null;
      const configMissing = configPreconditionMissing(config);
      if (configMissing.length > 0) {
        // PQ-INV-001：配置前置失败不建任务、不调用上传端口
        return {
          intake_result: "config_unavailable",
          error: "CONFIG_UNAVAILABLE",
          task_ref: null,
          missing_fields: configMissing,
        };
      }

      const now = nowIso();
      const task = {
        submission_uuid: uuidgen(), // INV-2：仅此处生成一次
        command_id: commandId,
        state: "created",
        intent_snapshot: {
          assignment: intent.assignment,
          student_name: intent.student_name,
          group_name: intent.group_name,
        },
        config_snapshot: pickConfigSnapshot(config), // LCD-002：创建即快照
        bundle_ref: null,
        checkpoint_ref: null,
        submission_id: null,
        received_at: null,
        missing_items: [],
        failure_code: null,
        failure_reason: null,
        attempt_count: 0,
        next_attempt_at: null,
        last_trigger: null,
        lease: null,
        created_at: now,
        updated_at: now,
        history: [{ from: null, to: "created", at: now, reason: "intent_complete" }],
      };
      tasks.set(task.submission_uuid, task);
      if (commandId != null) commandIndex.set(commandId, task.submission_uuid);
      await persist(); // 快照先落盘，再开始采集

      const collected = await runCollection(task);
      if (collected) await runDispatch(task);
      await persist();
      return { intake_result: "created", task_ref: taskRefOf(task), missing_fields: [] };
    });
  }

  /**
   * 恢复触发（IC-PQ-002 / LCD-005）：启动扫描、可达性提示、退避到期、手动重试。
   * trigger_id 去重；failed_terminal / completed 永不恢复；到期且无活跃租约才执行。
   * @param {{trigger_id: string, trigger_type: string, task_uuid?: string}} trigger
   * @returns {Promise<{recovery_request_id: string|null, candidate_task_uuids: string[], deduplicated?: boolean}>}
   */
  async function triggerRecovery(trigger) {
    return withLock(async () => {
      if (!isPlainObject(trigger) || typeof trigger.trigger_id !== "string" || trigger.trigger_id === "") {
        throw new PendingQueueError("TRIGGER_INVALID", "trigger_id must be a non-empty string");
      }
      if (seenTriggers.has(trigger.trigger_id)) {
        return { recovery_request_id: null, candidate_task_uuids: [], deduplicated: true };
      }
      seenTriggers.add(trigger.trigger_id);

      const nowMs = clock.now();
      const candidates = [];
      for (const task of tasks.values()) {
        if (trigger.task_uuid != null && task.submission_uuid !== trigger.task_uuid) continue;
        if (isTerminalState(task.state)) continue; // 终态不可恢复
        if (hasActiveLease(task, nowMs)) continue; // 单飞（PQ-INV-003）
        if (task.state === "created" || task.state === "collecting") {
          if (task.bundle_ref == null) candidates.push(task); // 崩溃/采集失败：尚无快照，可重采
          continue;
        }
        if (task.state === "queued") {
          candidates.push(task);
          continue;
        }
        if (isRecoverableState(task.state) && isDue(task, nowMs)) {
          candidates.push(task);
        }
      }

      for (const task of candidates) {
        task.last_trigger = trigger.trigger_type;
        const ready = await runCollection(task); // 有快照则短路（INV-4）
        if (ready) await runDispatch(task);
      }
      await persist();
      return {
        recovery_request_id: `rec-${trigger.trigger_id}`,
        candidate_task_uuids: candidates.map((t) => t.submission_uuid),
      };
    });
  }

  /**
   * 状态展示数据源（IC-M01-05 / IC-PQ-005）：真实状态与原因，不伪造结论。
   * @param {string} submissionUuid
   * @returns {Object} StatusView（形状对齐 plugin/src/ports/index.js）
   */
  function getTaskView(submissionUuid) {
    const task = tasks.get(submissionUuid);
    if (!task) {
      throw new PendingQueueError("VIEW_NOT_AVAILABLE", `no task for uuid ${String(submissionUuid)}`);
    }
    const view = {
      submission_uuid: task.submission_uuid,
      status: task.state,
      missing_items: [...task.missing_items],
    };
    if (task.submission_id != null) view.submission_id = task.submission_id;
    if (task.failure_reason != null) view.failure_reason = task.failure_reason;
    if (task.next_attempt_at != null) view.retry_at = task.next_attempt_at;
    if (task.attempt_count > 0) view.progress = { attempt_count: task.attempt_count };
    return view;
  }

  /** @returns {Object[]} 全部任务的 StatusView（IC-M01-05，read-only） */
  function listTaskViews() {
    return [...tasks.keys()].map((uuid) => getTaskView(uuid));
  }

  /** 测试/诊断用：读取任务记录副本（不暴露写路径）。 */
  function getTask(submissionUuid) {
    const task = tasks.get(submissionUuid);
    return task ? structuredClone(task) : null;
  }

  async function dispose() {
    recovery.dispose();
    await mutex;
  }

  return Object.freeze({
    init,
    submitIntent,
    triggerRecovery,
    getTaskView,
    listTaskViews,
    getTask,
    dispose,
  });
}

export { TASK_STATES };
