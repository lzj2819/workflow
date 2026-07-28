/**
 * L13 CMP-STATUS-PRESENTER — 学生侧状态与错误展示（REQ-004 / REQ-DD001/DD002；
 * AC-REQ-001-01 exceptions 展示面 / AC-REQ-002-01 不完整配置提示面）。
 *
 * 实现 IC-M01-05 消费端（plugin/src/ports/index.js StatusView；L1
 * 04-contracts-and-runtime.md §3.1）：
 * - 展示数据源唯一：只消费 IC-M01-05 的 task_view / config_view 输入快照，
 *   不新增数据源、不查询 MOD-02、不写回 ST-01/ST-04（INV-SP-001）；
 * - 不伪造结论：status / submission_id / failure_reason / missing_items 原样保留
 *   到视图（INV-SP-002/004）；失败状态展示真实原因，绝不显示等级或伪造成功；
 * - 内部错误码原文不暴露给学生：映射为学生可读文案但保留真实含义
 *   （原始 failure_reason 在视图中透传给宿主 renderer，派生文案不替代原值）；
 * - missing_items 用中文类别名（对话/代码/截图/结果，对齐 CT-001/CT-002 枚举）；
 * - 同一输入快照 → 确定性等价视图（INV-SP-005）；无网络、无持久化、无重试；
 * - 展示不可用仅抛 VIEW_NOT_AVAILABLE（INV-SP-006）。
 *
 * 子节点职责（L2 02-architecture-decomposition）在本文件内分段实现：
 * CMP-SP-TASK-VIEW-PROJECTOR → projectTaskView；
 * CMP-SP-CONFIG-VIEW-PROJECTOR → projectConfigView；
 * CMP-SP-STATUS-MESSAGE-MAPPER → mapTaskMessage / mapConfigMessage；
 * CMP-SP-RENDER-ADAPTER → renderPresentationView（纯文本宿主渲染，LCD-SP-006）。
 *
 * 不实现：L04/L05/L06/L10/L11 的内部逻辑；本层不持有任何持久状态。
 */

/** 展示失败的稳定错误码（IC-M01-05 error_codes；INV-SP-006）。 */
export const SP_ERROR_CODES = Object.freeze(["VIEW_NOT_AVAILABLE"]);

/** 展示不可用错误（code 定位原因；不静默降级、不触发重试）。 */
export class StatusPresenterError extends Error {
  constructor(code, reason) {
    super(`${code}: ${reason}`);
    this.name = "StatusPresenterError";
    this.code = code;
    this.reason = reason;
  }
}

function viewNotAvailable(reason) {
  throw new StatusPresenterError("VIEW_NOT_AVAILABLE", reason);
}

/** 缺失材料类别 → 学生可读中文名（CT-001/CT-002 枚举：对话/代码/截图/结果）。 */
export const CATEGORY_LABELS = Object.freeze({
  dialogue: "对话",
  code: "代码",
  screenshot: "截图",
  screenshots: "截图",
  result: "结果",
  results: "结果",
  对话: "对话",
  代码: "代码",
  截图: "截图",
  结果: "结果",
});

/** 配置必填字段 → 学生可读中文名（对齐 plugin/src/config/plugin-config.js）。 */
export const CONFIG_FIELD_LABELS = Object.freeze({
  invite_code: "课程邀请码",
  student_name: "姓名",
  group_name: "小组",
  code_dir: "代码目录",
  screenshots_dir: "截图目录",
  results_dir: "结果目录",
});

/**
 * 内部错误码 → 学生可读文案（保留真实含义，不暴露码原文）。
 * 覆盖 CT-001/CT-002 error_codes、L2 内部码与常见网络 errno。
 */
const ERROR_CODE_MESSAGES = Object.freeze({
  AUTH_INVALID: "身份验证未通过，请检查课程邀请码",
  VALIDATION_FAILED: "提交内容未通过服务器校验",
  PAYLOAD_TOO_LARGE: "提交内容超过大小限制",
  UNSUPPORTED_MEDIA_TYPE: "存在不支持的文件类型",
  REJECTED_MEMBERSHIP: "你不在本课程提交名单中，提交被服务器拒绝",
  NOT_FOUND: "服务器未找到对应的提交记录",
  VIEW_NOT_AVAILABLE: "状态暂时不可用，请稍后重试查看",
  ECONNREFUSED: "无法连接服务器",
  ECONNRESET: "网络连接被中断",
  ECONNABORTED: "网络连接被中断",
  ETIMEDOUT: "连接服务器超时",
  ENOTFOUND: "无法解析服务器地址",
  EAI_AGAIN: "网络暂时不可用",
});

/** 形如 MC-ERR-DIR-UNREADABLE 的内部错误码（不暴露原文）。 */
const INTERNAL_ERR_CODE_RE = /\b[A-Z]{2,}(?:-[A-Z0-9]+)*-ERR(?:-[A-Z0-9]+)+\b/g;
/** 形如 SCREAMING_SNAKE 的内部码（下划线连接的全大写 token）。 */
const SCREAMING_CODE_RE = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g;
/** 令牌/secret 泄漏面（防御性脱敏；正常路径不应出现）。 */
const SECRET_PATTERNS = Object.freeze([
  /Bearer\s+\S+/gi,
  /\b(?:token|secret|api[-_]?key|password|invite[-_]?code)\s*[=:]\s*\S+/gi,
]);

/**
 * 把内部失败原因映射为学生可读文案：已知错误码替换为可读说明，
 * 未知内部码（SCREAMING_SNAKE / *-ERR-*）替换为中性描述，令牌/secret 脱敏。
 * 不吞掉原因：非码部分的原始语义原样保留。
 * @param {string} reason
 * @returns {string}
 */
export function sanitizeReason(reason) {
  let text = String(reason);
  for (const re of SECRET_PATTERNS) {
    text = text.replace(re, (m) => {
      const head = m.split(/[=:\s]/)[0];
      return `${head}=[已隐藏]`;
    });
  }
  text = text.replace(INTERNAL_ERR_CODE_RE, "内部处理错误");
  text = text.replace(SCREAMING_CODE_RE, (m) => ERROR_CODE_MESSAGES[m] ?? "内部处理错误");
  // 无下划线的网络 errno（SCREAMING_CODE_RE 覆盖不到）逐个映射。
  for (const code of ["ECONNREFUSED", "ECONNRESET", "ECONNABORTED", "ETIMEDOUT", "ENOTFOUND", "EAI_AGAIN"]) {
    if (text.includes(code)) text = text.split(code).join(ERROR_CODE_MESSAGES[code]);
  }
  return text.trim();
}

/** 缺失类别逐项映射为中文名；未知类别原样展示（INV-SP-003 不合并、不隐藏）。 */
export function labelCategory(item) {
  return CATEGORY_LABELS[item] ?? String(item);
}

/** 配置字段名映射为中文名；未知字段原样展示。 */
export function labelConfigField(field) {
  return CONFIG_FIELD_LABELS[field] ?? String(field);
}

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function requireStringArray(value, field, { optional = false } = {}) {
  if (value === undefined || value === null) {
    if (optional) return [];
    viewNotAvailable(`${field} must be an array of strings`);
  }
  if (!Array.isArray(value) || value.some((x) => typeof x !== "string")) {
    viewNotAvailable(`${field} must be an array of strings`);
  }
  return [...value];
}

function optionalString(value, field) {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string") viewNotAvailable(`${field} must be a string when present`);
  return value;
}

/* ---------------------------------------------------------------------------
 * CMP-SP-TASK-VIEW-PROJECTOR：IC-M01-05 task_view 输入 → 任务视图模型
 * ------------------------------------------------------------------------- */

/**
 * 投影任务视图（IC-L2-SP-01）。字段原样保留；缺省数组按空处理。
 * @param {Object} input StatusView（plugin/src/ports/index.js）
 * @returns {{status: string, submission_id: string|null, received_at: string|null,
 *   missing_items: string[], failure_reason: string|null, progress: *}}
 */
export function projectTaskView(input) {
  if (!isPlainObject(input)) viewNotAvailable("task view input must be an object");
  if (typeof input.status !== "string" || input.status.trim() === "") {
    viewNotAvailable("task view input.status must be a non-empty string");
  }
  return {
    status: input.status,
    submission_id: optionalString(input.submission_id, "submission_id"),
    received_at: optionalString(input.received_at, "received_at"),
    missing_items: requireStringArray(input.missing_items, "missing_items", { optional: true }),
    failure_reason: optionalString(input.failure_reason, "failure_reason"),
    progress: input.progress ?? null,
  };
}

/* ---------------------------------------------------------------------------
 * CMP-SP-CONFIG-VIEW-PROJECTOR：IC-M01-05 config_view 输入 → 配置视图模型
 * ------------------------------------------------------------------------- */

/**
 * 投影配置视图（IC-L2-SP-02）。completeness / dir_errors 逐项透传。
 * @param {Object} input ConfigView{completeness[], dir_errors[]}
 * @returns {{completeness: string[], dir_errors: string[]}}
 */
export function projectConfigView(input) {
  if (!isPlainObject(input)) viewNotAvailable("config view input must be an object");
  return {
    completeness: requireStringArray(input.completeness, "completeness", { optional: true }),
    dir_errors: requireStringArray(input.dir_errors, "dir_errors", { optional: true }),
  };
}

/* ---------------------------------------------------------------------------
 * CMP-SP-STATUS-MESSAGE-MAPPER：事实 → 可读展示语义（IC-L2-SP-03）
 * 状态值不改写；失败原因原值透传 + 派生可读文案（LCD-SP-003）。
 * ------------------------------------------------------------------------- */

/**
 * 状态语义表：title/action_hint 为派生文案；status 本身原样保留。
 * severity 仅 success/info/warning/error 四档；received 与 completed 为 success。
 */
const TASK_STATUS_MESSAGES = Object.freeze({
  received: {
    severity: "success",
    title: "提交已被服务器接收",
    action_hint: null,
  },
  queued: {
    severity: "info",
    title: "提交待上传",
    action_hint: "任务已保留在本地待上传队列；网络恢复后将自动继续上传，无需重新采集材料。",
  },
  created: {
    severity: "info",
    title: "提交任务已创建",
    action_hint: "正在准备采集材料。",
  },
  collecting: {
    severity: "info",
    title: "正在采集材料",
    action_hint: null,
  },
  completed: {
    severity: "success",
    title: "上传已完成",
    action_hint: null,
  },
  failed_retryable: {
    severity: "error",
    title: "任务未完成（可恢复，已保留在本地）",
    action_hint: "本地任务已保留；网络恢复或问题解决后将自动继续，无需重新采集材料。",
  },
  failed_terminal: {
    severity: "error",
    title: "任务失败（不可恢复）",
    action_hint: "本次任务无法继续；请修正问题后重新发起提交。",
  },
  uploading: {
    severity: "info",
    title: "正在上传",
    action_hint: null,
  },
  paused: {
    severity: "warning",
    title: "上传已暂停（断网待上传）",
    action_hint: "任务已保留在本地，材料不会丢失；网络恢复后将自动继续上传。",
  },
  failed: {
    severity: "error",
    title: "上传未完成（任务已保留在本地）",
    action_hint: "本地待上传任务已保留；网络恢复或问题解决后可继续上传，无需重新采集材料。",
  },
  upload_failed: {
    severity: "error",
    title: "上传失败",
    action_hint: "可从断点继续上传；请检查网络后重试。",
  },
  confirm_required: {
    severity: "warning",
    title: "提交结果尚未确认",
    action_hint: "服务器应答超时，结果未知；请稍后查看状态，系统不会重复提交。",
  },
  rejected: {
    severity: "error",
    title: "提交被服务器拒绝",
    action_hint: "请按上述原因修正后重新提交。",
  },
  processing: {
    severity: "info",
    title: "提交已接收，正在处理",
    action_hint: null,
  },
  scored: {
    severity: "info",
    title: "评分已完成",
    action_hint: null,
  },
  scoring_failed: {
    severity: "error",
    title: "评分失败",
    action_hint: "评分未产生结果；系统重试后请再次查看，或联系课程管理员。",
  },
  deleted: {
    severity: "info",
    title: "提交已被删除",
    action_hint: null,
  },
  info_incomplete: {
    severity: "warning",
    title: "提交信息不完整",
    action_hint: "请补齐上述缺失项后重新提交。",
  },
});

/**
 * 任务视图 → 展示视图（IC-L2-SP-03）。
 * @param {Object} taskView StatusView 输入快照
 * @returns {Object} PresentationView（view_type="task"）
 */
export function presentTaskView(taskView) {
  const tv = projectTaskView(taskView);
  const known = TASK_STATUS_MESSAGES[tv.status];
  const severity = known?.severity ?? "warning";
  const title = known?.title ?? `提交状态：${tv.status}`; // 未知状态原样展示，不改写
  const lines = [title];

  if (tv.submission_id) lines.push(`提交编号：${tv.submission_id}`);
  if (tv.status === "received" && tv.received_at) lines.push(`接收时间：${tv.received_at}`);

  if (tv.status === "received" || tv.status === "info_incomplete") {
    if (tv.missing_items.length > 0) {
      lines.push(`缺失材料：${tv.missing_items.map(labelCategory).join("、")}`);
      if (tv.status === "received") lines.push("提示：材料不完整，补齐后可重新提交。");
    } else if (tv.status === "received") {
      lines.push("材料齐全。");
    }
  } else if (tv.missing_items.length > 0) {
    lines.push(`缺失材料：${tv.missing_items.map(labelCategory).join("、")}`);
  }

  // 失败/未知状态：展示真实原因（脱敏后），绝不替换为成功或等级。
  const showsReason =
    tv.failure_reason &&
    ["failed", "upload_failed", "rejected", "scoring_failed", "confirm_required", "failed_retryable", "failed_terminal"].includes(tv.status);
  const message_params = {};
  if (showsReason) {
    message_params.reason = sanitizeReason(tv.failure_reason);
    lines.push(`原因：${message_params.reason}`);
  }
  if (tv.progress !== null && tv.progress !== undefined) {
    lines.push(`进度：${typeof tv.progress === "object" ? JSON.stringify(tv.progress) : String(tv.progress)}`);
  }
  if (known?.action_hint) lines.push(known.action_hint);

  return Object.freeze({
    view_type: "task",
    status: tv.status,
    severity,
    message_key: `task.${tv.status}`,
    message_params,
    submission_id: tv.submission_id,
    received_at: tv.received_at,
    missing_items: tv.missing_items,
    failure_reason: tv.failure_reason, // 原值透传给宿主 renderer（INV-SP-002）
    progress: tv.progress,
    action_hint: known?.action_hint ?? null,
    title,
    lines: Object.freeze(lines),
  });
}

/** 目录错误原文 → 学生可读文案（保留具体字段与路径信息）。 */
function describeDirError(raw) {
  const m = /^directory not readable:\s*([a-z_]+)=(.+)$/.exec(raw);
  if (m) return `${labelConfigField(m[1])}不可读：${m[2]}`;
  return sanitizeReason(raw);
}

/**
 * 配置视图 → 展示视图（AC-REQ-002-01 展示面：不完整配置列出缺失字段清单）。
 * @param {Object} configView ConfigView 输入快照
 * @returns {Object} PresentationView（view_type="config"）
 */
export function presentConfigView(configView) {
  const cv = projectConfigView(configView);
  const incomplete = cv.completeness.length > 0 || cv.dir_errors.length > 0;
  const lines = [];
  if (!incomplete) {
    lines.push("配置完整，已保存。");
  } else {
    lines.push("配置不完整，无法用于提交：");
    if (cv.completeness.length > 0) {
      lines.push(`缺失字段：${cv.completeness.map(labelConfigField).join("、")}`);
    }
    for (const err of cv.dir_errors) {
      lines.push(`目录错误：${describeDirError(err)}`);
    }
    lines.push("请在设置页补齐上述配置项后重新保存。");
  }

  return Object.freeze({
    view_type: "config",
    status: incomplete ? "incomplete" : "complete",
    severity: incomplete ? "warning" : "success",
    message_key: incomplete ? "config.incomplete" : "config.complete",
    message_params: {},
    completeness: cv.completeness, // 原值逐项透传
    dir_errors: cv.dir_errors,
    action_hint: incomplete ? "请在设置页补齐上述配置项后重新保存。" : null,
    title: lines[0],
    lines: Object.freeze(lines),
  });
}

/* ---------------------------------------------------------------------------
 * CMP-SP-RENDER-ADAPTER：PresentationView → 学生侧纯文本（LCD-SP-006）
 * ------------------------------------------------------------------------- */

/**
 * 把展示视图渲染为多行纯文本（默认宿主形态）。
 * @param {Object} view presentTaskView / presentConfigView 的输出
 * @returns {string}
 */
export function renderPresentationView(view) {
  if (!isPlainObject(view) || !Array.isArray(view.lines)) {
    viewNotAvailable("presentation view must contain lines[]");
  }
  return view.lines.join("\n");
}

/** 便捷入口：StatusView → 学生可读文本。 */
export function renderTaskView(taskView) {
  return renderPresentationView(presentTaskView(taskView));
}

/** 便捷入口：ConfigView → 学生可读文本。 */
export function renderConfigView(configView) {
  return renderPresentationView(presentConfigView(configView));
}
