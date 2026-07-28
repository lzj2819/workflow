/**
 * T-B04 — MOD-01 插件组装层（plugin composition root）。
 *
 * 装配 L04 config → L05 intent → L06/L07 采集 → L11 queue → L10 upload →
 * L13 presenter（IC-M01-01~05 真实接线）。只消费各叶子公开接口，不改叶子实现。
 *
 * 适配点（冻结契约间的命名/形状差，仅在本层桥接）：
 * - L04 配置字段 screenshots_dir/results_dir → L06/L11 快照字段
 *   screenshot_dir/result_dir（readConfig / config_snapshot 双向同口径）；
 * - L11 taskRef{submission_uuid, intent, config_ref} → L06 collectMaterials
 *   入参{submission_uuid, identity_snapshot, config_snapshot, snapshot_at}；
 * - L11 bundle_ref{dialogue_artifact, material_manifest} → L10 UploadJob
 *   bundle_ref.chunks（对话 artifact 序列化为 dialogue chunk；材料项以
 *   content_ref 引用，不在本层读材料正文）；
 * - L10 UploadOutcome.outcome_type → L11 期望的 status 词汇
 *   （confirmed/rejected/unknown/interrupted）。
 *
 * 硬性语义：
 * - TD-01：host dialogue port 必须注入；缺省为 host/dialogue-export-port 的
 *   exportDialogueFromHost（立即抛 HostUnsupportedError）。本层绝不虚构宿主
 *   导出能力、绝不把 unsupported 静默转为「对话缺失」；失败经 L11 记录真实
 *   原因并经 L13 原样透传展示；
 * - INV-1：意图缺项或配置不完整 → 经 L13 呈现并中止，不建任务、零网络调用；
 * - INV-2：submission_uuid 由 L11 生成一次全程不变，本层不重新生成；
 * - INV-4：采集快照由 L11 持久化，重传复用不重采（本层不重发采集）；
 * - checkpoint 文件持久化：createFileCheckpointStore 注入 L10（替代内存默认）；
 *   终态（confirmed/rejected）后 discardCheckpoint（L2 03 cleanup_trigger）；
 * - IC-PQ-004：cleanupTerminal 协调终态清理（默认 30 天可配），冷态执行
 *   （recover/init 之前，见 pending_queue/cleanup.js 头注释）。
 *
 * 零 npm 依赖；transport 注入，本层不发真实网络请求。
 */

import path from "node:path";

import { createConfigStore } from "../config_store/config-store.js";
import { createIntentParser } from "../intent_parser/index.js";
import { collectMaterials } from "../material_collector/index.js";
import { createPendingQueue } from "../pending_queue/index.js";
import { createStateStore as createQueueStateStore } from "../pending_queue/state-store.js";
import { runCleanup, DEFAULT_RETENTION_DAYS } from "../pending_queue/cleanup.js";
import { createUploadClient } from "../upload_client/index.js";
import { createFileCheckpointStore } from "../upload_client/file-checkpoint-store.js";
import { exportDialogueFromHost } from "../host/dialogue-export-port.js";
import {
  presentConfigView,
  presentTaskView,
  renderPresentationView,
} from "../status_presenter/index.js";

export class PluginAssemblyError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "PluginAssemblyError";
    this.code = code;
    this.reason = reason;
  }
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/**
 * L11 bundle_ref{dialogue_artifact, material_manifest} → L10 chunks。
 * 对话导出物序列化为单个 dialogue chunk；材料项以 content_ref 引用本地路径
 * （正文读取由服务端协议侧决定，本层不读材料内容、不伪造字节）。
 */
export function bundleRefToChunks(bundleRef) {
  const chunks = [];
  const dialogue = bundleRef?.dialogue_artifact;
  if (isPlainObject(dialogue)) {
    const content = JSON.stringify(dialogue);
    chunks.push({
      category: "dialogue",
      filename: "dialogue.json",
      media_type: "application/json",
      size_bytes: Buffer.byteLength(content, "utf8"),
      content,
    });
  }
  const items = bundleRef?.material_manifest?.items;
  for (const item of Array.isArray(items) ? items : []) {
    chunks.push({
      category: item.category,
      filename: typeof item.path === "string" ? item.path.split("/").pop() : null,
      media_type: null,
      size_bytes: item.size_bytes ?? null,
      content_ref: item.path ?? null,
    });
  }
  return chunks;
}

/**
 * 创建装配完成的插件实例。
 *
 * @param {Object} deps
 * @param {string} deps.storageRoot   本地状态根目录（config/queue/checkpoints/archive）
 * @param {(req: Object) => Promise<{status: number, body?: any}>} deps.transport
 *        HTTPS 出口唯一适配点（测试用 stub；本层不发真实网络请求）
 * @param {(taskRef: Object) => Promise<Object>} [deps.hostDialoguePort]
 *        宿主导出端口（TD-01 真实适配注入点）；缺省 = exportDialogueFromHost，
 *        调用即抛 HostUnsupportedError（显式可观测，绝不虚构导出物）
 * @param {{now: () => number}} [deps.clock]   注入时钟（epoch ms）
 * @param {() => string} [deps.uuidgen]        注入 uuid 生成（测试确定性）
 * @param {(p: string) => Promise<boolean>} [deps.dirCheck] 目录可读性探测（测试注入）
 * @param {(event: Object) => void} [deps.onEvent] 结构化本地事件（不含 token/材料正文）
 */
export function createPlugin(deps = {}) {
  if (typeof deps.storageRoot !== "string" || deps.storageRoot.trim() === "") {
    throw new PluginAssemblyError("ASSEMBLY_INVALID", "storageRoot must be a non-empty string");
  }
  if (typeof deps.transport !== "function") {
    throw new PluginAssemblyError("ASSEMBLY_INVALID", "transport must be an injected function");
  }
  const clock = deps.clock ?? { now: () => Date.now() };
  const onEvent = deps.onEvent ?? (() => {});
  const hostDialoguePort = deps.hostDialoguePort ?? exportDialogueFromHost;
  if (typeof hostDialoguePort !== "function") {
    throw new PluginAssemblyError("ASSEMBLY_INVALID", "hostDialoguePort must be a function");
  }

  const paths = {
    config: path.join(deps.storageRoot, "plugin-config.json"),
    queue: path.join(deps.storageRoot, "pending-queue.json"),
    checkpoints: path.join(deps.storageRoot, "checkpoints"),
    archive: path.join(deps.storageRoot, "archive"),
  };

  // L04 配置端口（IC-M01-02）。
  const configStore = createConfigStore({
    filePath: paths.config,
    ...(deps.dirCheck ? { dirCheck: deps.dirCheck } : {}),
  });
  // L05 意图解析端口（IC-M01-01；纯函数确定性闸门）。
  const intentParser = createIntentParser();
  // ST-05 文件版 checkpoint（A-007 跨进程持久；接口同内存默认）。
  const checkpointStore = createFileCheckpointStore({ dir: paths.checkpoints });
  // L10 上传执行端口（IC-M01-04）。
  const uploadClient = createUploadClient({
    transport: deps.transport,
    checkpointStore,
    clock: () => clock.now(),
    onEvent,
  });

  /** L04 EffectiveConfig → L11 只读配置快照（字段命名桥接）。 */
  async function readConfig() {
    const eff = await configStore.get();
    if (!eff.ok) return null;
    return {
      invite_code: eff.invite_code,
      code_dir: eff.code_dir,
      screenshot_dir: eff.screenshots_dir,
      result_dir: eff.results_dir,
    };
  }

  /** L07 对话采集端口：host port 注入；unsupported/失败原样传播（TD-01）。 */
  async function collectDialogue(taskRef) {
    return hostDialoguePort(taskRef);
  }

  /** L06 材料采集端口（taskRef → collectMaterials 入参桥接）。 */
  async function collectMaterialsPort(taskRef) {
    return collectMaterials({
      submission_uuid: taskRef.submission_uuid,
      identity_snapshot: taskRef.intent,
      config_snapshot: {
        code_dir: taskRef.config_ref?.code_dir,
        screenshot_dir: taskRef.config_ref?.screenshot_dir,
        result_dir: taskRef.config_ref?.result_dir,
      },
      snapshot_at: new Date(clock.now()).toISOString(),
    });
  }

  /** L10 上传端口（UploadJob/UploadOutcome 词汇桥接 + 终态 checkpoint 清理）。 */
  async function upload(job) {
    const outcome = await uploadClient.startOrResumeUpload({
      submission_uuid: job.submission_uuid,
      bundle_ref: { chunks: bundleRefToChunks(job.bundle_ref) },
      identity: job.identity,
      ...(job.checkpoint != null ? { checkpoint: job.checkpoint } : {}),
    });
    switch (outcome?.outcome_type) {
      case "confirmed":
        await uploadClient.discardCheckpoint(job.submission_uuid); // 终态清理 ST-05
        return {
          status: "confirmed",
          submission_id: outcome.submission_id ?? null,
          received_at: outcome.received_at ?? null,
          missing_items: Array.isArray(outcome.missing_items) ? outcome.missing_items : [],
        };
      case "rejected":
        await uploadClient.discardCheckpoint(job.submission_uuid); // 终态不再续传
        return { status: "rejected", rejection_reason: outcome.rejection_reason ?? "rejected" };
      case "unknown":
        return { status: "unknown" };
      default:
        return {
          status: "interrupted",
          cause: outcome?.interruption_cause ?? "UNKNOWN_INTERRUPT",
        };
    }
  }

  // L11 队列编排枢纽（IC-M01-01/03/04 消费侧；IC-M01-05 数据源）。
  const queue = createPendingQueue({
    storagePath: paths.queue,
    ports: { readConfig, collectDialogue, collectMaterials: collectMaterialsPort, upload },
    clock,
    ...(deps.uuidgen ? { uuidgen: deps.uuidgen } : {}),
  });
  // IC-PQ-004 清理用的 envelope 存储（与队列同路径；冷态使用，见 cleanup.js）。
  const queueStore = createQueueStateStore({ storagePath: paths.queue });

  function presentTask(taskView) {
    const presentation = presentTaskView(taskView);
    return { presentation, text: renderPresentationView(presentation) };
  }

  /**
   * 主流程（MOD-01 submit）：配置读取 → 意图解析 → 缺项经 L13 呈现并中止
   * （INV-1 零网络）→ L11 编排采集/上传 → L13 呈现真实结果。
   * @param {string} commandText 学生自然语言提交指令
   * @param {Object} [options]
   * @param {string} [options.command_id] 指令级幂等键
   */
  async function submit(commandText, options = {}) {
    // 1) 配置读取（L04）；不可读/不完整 → L13 呈现并中止，不建任务零网络。
    const eff = await configStore.get();
    if (!eff.ok) {
      const view = presentConfigView({
        completeness: eff.completeness ?? [],
        dir_errors: [...(eff.dir_errors ?? []), `config unreadable: ${eff.error_code}`],
      });
      return {
        intake_result: "config_unavailable",
        task_ref: null,
        missing_fields: [],
        presentation: view,
        text: renderPresentationView(view),
      };
    }
    if (eff.status !== "complete") {
      const view = presentConfigView({
        completeness: eff.completeness ?? [],
        dir_errors: eff.dir_errors ?? [],
      });
      return {
        intake_result: "config_unavailable",
        task_ref: null,
        missing_fields: eff.completeness ?? [],
        presentation: view,
        text: renderPresentationView(view),
      };
    }

    // 2) 意图解析（L05；配置仅作只读上下文，不补齐缺项）。
    const intent = intentParser.parseSubmissionIntent(commandText, {
      config: eff,
      config_version: eff.config_version,
    });
    if (!intent.complete) {
      // INV-1：缺项经 L13 呈现并中止，不建任务、零网络调用。
      const view = presentTaskView({
        status: "info_incomplete",
        missing_items: intent.missing ?? [],
      });
      return {
        intake_result: "info_incomplete",
        task_ref: null,
        missing_fields: intent.missing ?? [],
        presentation: view,
        text: renderPresentationView(view),
      };
    }

    // 3) L11 编排：建任务（uuid 一次生成）→ 采集（快照）→ 上传。
    const result = await queue.submitIntent(intent, {
      ...(options.command_id != null ? { command_id: options.command_id } : {}),
    });

    // 4) L13 呈现真实状态/原因（HostUnsupported 等失败原样透传，不伪造）。
    if (result.task_ref) {
      const { presentation, text } = presentTask(
        queue.getTaskView(result.task_ref.submission_uuid),
      );
      return { ...result, presentation, text };
    }
    // config_unavailable（竞态：提交间配置被改坏）→ 配置展示面。
    const view = presentConfigView({ completeness: result.missing_fields ?? [], dir_errors: [] });
    return { ...result, presentation: view, text: renderPresentationView(view) };
  }

  /**
   * 恢复扫描入口（LCD-005 process_start）：加载最近一致 envelope、归一化
   * 崩溃窗口、重放未完成任务（同一 uuid + 既有采集快照 + checkpoint，INV-2/4）。
   * @returns {Promise<{tasks: Object[]}>} 恢复后全部任务的 StatusView
   */
  async function recover() {
    await queue.init();
    return { tasks: queue.listTaskViews() };
  }

  /**
   * IC-PQ-004 终态清理：completed/failed_terminal 超期（默认 30 天可配）
   * 移除 + 终态摘要归档（archive/）+ 清理计数可观测。进行中任务不误删。
   * 冷态执行约束：须在 recover()/init 之前或 dispose 之后调用（envelope 单写）。
   * @param {Object} [opts]
   * @param {number} [opts.retentionDays] 默认 30
   * @param {number} [opts.now] 默认注入时钟当前值（epoch ms）
   */
  async function cleanupTerminal(opts = {}) {
    return runCleanup({
      store: queueStore,
      archiveDir: paths.archive,
      now: opts.now ?? clock.now(),
      retentionDays: opts.retentionDays ?? DEFAULT_RETENTION_DAYS,
      queue,
      onEvent,
    });
  }

  /** IC-M01-05：单任务状态展示（真实状态/原因，经 L13）。 */
  function getStatus(submissionUuid) {
    return presentTask(queue.getTaskView(submissionUuid));
  }

  /** IC-M01-05：全部任务状态视图（原始 StatusView，供宿主列表渲染）。 */
  function listStatus() {
    return queue.listTaskViews();
  }

  return Object.freeze({
    submit,
    recover,
    cleanupTerminal,
    getStatus,
    listStatus,
    config: configStore,
    queue,
    checkpointStore,
    paths,
    dispose: () => queue.dispose(),
  });
}
