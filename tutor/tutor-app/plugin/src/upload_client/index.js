/**
 * L10 CMP-UPLOAD-CLIENT — 上传客户端 facade（IC-M01-04 consumer 实现）。
 *
 * 组成（L2 02 分解，DU-1 进程内，无独立部署单元）：
 * - CMP-UPLOAD-AUTH-ADAPTER     auth/token 换领 + 内存令牌租约（ST-L2-01）
 * - CMP-UPLOAD-SESSION-DRIVER   CT-001 创建会话→逐分片→合并；CT-002 查询；ST-05 单写
 * - CMP-UPLOAD-OUTCOME-RESOLVER 观察收敛 + unknown→CT-002 指数退避
 * - CMP-UPLOAD-ORCHESTRATOR     IC-M01-04 入口 + 单任务执行保护（ST-L2-02）
 *
 * 基线（KD-005）：Bearer token、submission_uuid 幂等键、分片断点续传、/api/v1。
 * 网络层全部经注入 transport（本叶子不发真实网络请求）；零运行时依赖。
 *
 * 不实现：意图（L05）、采集（L06/L07）、配置（L04）、队列编排（L11）、展示（L13）。
 */

import { createAuthAdapter } from "./auth-adapter.js";
import { createMemoryCheckpointStore } from "./checkpoint-store.js";
import { createOutcomeResolver } from "./outcome-resolver.js";
import { createUploadOrchestrator } from "./orchestrator.js";
import { createSessionDriver } from "./session-driver.js";

export {
  CATEGORY_ID_TO_CT001,
  INTERNAL_CATEGORY_IDS,
  toCt001Category,
} from "./categories.js";
export { createMemoryCheckpointStore } from "./checkpoint-store.js";
export { UPLOAD_CLIENT_ERROR_CODES, UploadClientError } from "./errors.js";
export { DEFAULT_CONFIRM_TIMEOUT_MS } from "./session-driver.js";
export { DEFAULT_QUERY_BACKOFF_MS } from "./outcome-resolver.js";

/**
 * 创建上传客户端（IC-M01-04 上传执行端口实现）。
 *
 * @param {Object} deps
 * @param {(req: {method: string, path: string, headers?: Object, body?: Object}) => Promise<{status: number, body?: any}>} deps.transport
 *        传输注入（HTTPS 出口的唯一适配点；测试用 stub）
 * @param {{load: Function, save: Function, clear: Function}} [deps.checkpointStore]
 *        ST-05 持久化适配（默认内存实现；A-007 具体机制为 implementation_detail）
 * @param {() => number} [deps.clock]        毫秒时钟
 * @param {number} [deps.confirmTimeoutMs]   合并确认超时（默认 30000，NFR-003）
 * @param {(ms: number) => Promise<void>} [deps.sleep]  CT-002 退避睡眠（测试注入）
 * @param {number[]} [deps.backoffMs]        CT-002 指数退避序列
 * @param {(event: Object) => void} [deps.onEvent]  结构化本地事件（绝不含 token/材料正文）
 *
 * @returns {{
 *   startOrResumeUpload: (job: Object) => Promise<Object>,
 *   discardCheckpoint: (uuid: string) => Promise<void>,
 *   loadCheckpoint: (uuid: string) => Promise<Object|null>,
 * }}
 */
export function createUploadClient({
  transport,
  checkpointStore,
  clock,
  confirmTimeoutMs,
  sleep,
  backoffMs,
  onEvent = () => {},
}) {
  const store = checkpointStore ?? createMemoryCheckpointStore();
  const authAdapter = createAuthAdapter({ transport, clock, onEvent });
  const sessionDriver = createSessionDriver({
    transport,
    authAdapter,
    checkpointStore: store,
    clock,
    confirmTimeoutMs,
    onEvent,
  });
  const outcomeResolver = createOutcomeResolver({
    sessionDriver,
    sleep,
    backoffMs,
    onEvent,
  });
  const orchestrator = createUploadOrchestrator({
    sessionDriver,
    outcomeResolver,
    checkpointStore: store,
    onEvent,
  });

  return {
    startOrResumeUpload: orchestrator.startOrResumeUpload,
    discardCheckpoint: orchestrator.discardCheckpoint,
    loadCheckpoint: (uuid) => store.load(uuid),
  };
}
