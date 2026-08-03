/**
 * L11 CMP-PENDING-QUEUE 测试（plugin/test/pending-queue.test.js）。
 *
 * 覆盖 verification-checklist 语义断言：
 * - 意图完整 → 建任务（uuid 生成一次后不变）→ 创建即快照 → 编排采集 → 交上传端口；
 *   意图缺项 → 不建任务、零网络/端口调用（spy 断言，INV-1）
 * - 断网/上传失败 → failed_retryable 保留 + 失败原因；重启扫描恢复（LCD-005，注入时钟）
 * - 重传不重采（INV-4）：恢复复用原采集快照（采集端口 spy 只被调一次）
 * - HostUnsupportedError → 显式失败且原因含 unsupported（不静默、不伪造）
 * - 状态机非法迁移拒绝；failed_terminal 不可恢复
 * - IC-M01-05 StatusView 形状与 ports/index.js 一致
 *
 * 全部兄弟端口（L04 配置 / L06 材料 / L07 对话 / L10 上传）均为注入 stub/spy。
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { createPendingQueue } from "../src/pending_queue/index.js";
import {
  assertTransition,
  InvalidTransitionError,
  TASK_STATES,
} from "../src/pending_queue/task-machine.js";
import { HostUnsupportedError } from "../src/host/dialogue-export-port.js";

function createSpy(impl) {
  const spy = async (...args) => {
    spy.calls.push(args);
    return impl(...args);
  };
  spy.calls = [];
  return spy;
}

function makeClock(startMs = 1_000_000) {
  let now = startMs;
  return {
    now: () => now,
    advance(ms) {
      now += ms;
    },
  };
}

const COMPLETE_INTENT = Object.freeze({
  complete: true,
  assignment: "homework-1",
  student_name: "张三",
  group_name: "G1",
  missing: [],
});

function makePorts(overrides = {}) {
  return {
    readConfig: createSpy(async () => ({
      invite_code: "INV-001",
      code_dir: "C:/materials/code",
      screenshot_dir: "C:/materials/shots",
      result_dir: "C:/materials/results",
    })),
    collectDialogue: createSpy(async () => ({
      format_version: "1",
      source_host: "test-host",
      exported_at: new Date(1_000_000).toISOString(),
      turns: [{ role: "user", content: "请提交作业" }],
    })),
    collectMaterials: createSpy(async (taskRef) => ({
      submission_uuid: taskRef.submission_uuid,
      identity: taskRef.intent,
      items: [
        {
          category: "code",
          path: "C:/materials/code/main.py",
          size_bytes: 128,
          sha256: "a".repeat(64),
          modified_at: new Date(1_000_000).toISOString(),
        },
      ],
      missing_items: [],
      total_bytes: 128,
      over_budget: false,
      warnings: [],
      snapshot_at: new Date(1_000_000).toISOString(),
    })),
    upload: createSpy(async () => ({
      status: "confirmed",
      submission_id: "sub-0001",
      received_at: new Date(1_000_100).toISOString(),
      missing_items: [],
    })),
    ...overrides,
  };
}

async function makeQueue(t, ports, { clock = makeClock(), ...rest } = {}) {
  const dir = await mkdtemp(path.join(tmpdir(), "pq-test-"));
  t.after(async () => {
    await rm(dir, { recursive: true, force: true });
  });
  const storagePath = path.join(dir, "queue", "pending-queue.json");
  const queue = createPendingQueue({ storagePath, ports, clock, ...rest });
  return { queue, storagePath, clock };
}

test("意图完整 → 建任务（uuid 一次生成）→ 创建即快照 → 编排采集 → 交上传端口", async (t) => {
  const ports = makePorts();
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  assert.equal(res.intake_result, "created");
  const uuid = res.task_ref.submission_uuid;
  assert.equal(typeof uuid, "string");
  assert.notEqual(uuid.length, 0);

  // 采集端口各调一次，task_ref 携带同一 uuid（IC-M01-03 点路径消费）
  assert.equal(ports.collectDialogue.calls.length, 1);
  assert.equal(ports.collectMaterials.calls.length, 1);
  assert.equal(ports.collectDialogue.calls[0][0].submission_uuid, uuid);
  assert.equal(ports.collectMaterials.calls[0][0].submission_uuid, uuid);

  // 上传端口收到同一 uuid + 快照 bundle + 完整 identity（INV-2 / IC-M01-04）
  assert.equal(ports.upload.calls.length, 1);
  const job = ports.upload.calls[0][0];
  assert.equal(job.submission_uuid, uuid);
  assert.equal(job.bundle_ref.dialogue_artifact.format_version, "1");
  assert.equal(job.bundle_ref.material_manifest.items.length, 1);
  assert.deepEqual(job.identity, {
    invite_code: "INV-001",
    student_name: "张三",
    group_name: "G1",
    assignment: "homework-1",
  });

  const task = queue.getTask(uuid);
  assert.equal(task.state, "completed");
  assert.equal(task.submission_id, "sub-0001");
  // 创建即快照（LCD-002）：意图与配置快照在创建时刻冻结
  assert.deepEqual(task.intent_snapshot, {
    assignment: "homework-1",
    student_name: "张三",
    group_name: "G1",
  });
  assert.equal(task.config_snapshot.invite_code, "INV-001");
  assert.equal(task.bundle_ref.warnings.length, 0);
  await queue.dispose();
});

test("意图缺项 → 不建任务、零端口/网络调用（INV-1，spy 断言）", async (t) => {
  const ports = makePorts();
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent({
    complete: false,
    assignment: "homework-1",
    missing: ["group_name"],
  });
  assert.equal(res.intake_result, "info_incomplete");
  assert.equal(res.task_ref, null);
  assert.ok(res.missing_fields.includes("group_name"));

  assert.equal(ports.collectDialogue.calls.length, 0);
  assert.equal(ports.collectMaterials.calls.length, 0);
  assert.equal(ports.upload.calls.length, 0);
  assert.equal(queue.listTaskViews().length, 0);
  await queue.dispose();
});

test("配置前置失败 → 不建任务（CONFIG_UNAVAILABLE，PQ-INV-001）", async (t) => {
  const ports = makePorts({ readConfig: createSpy(async () => ({ invite_code: "" })) });
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  assert.equal(res.intake_result, "config_unavailable");
  assert.equal(res.error, "CONFIG_UNAVAILABLE");
  assert.ok(res.missing_fields.includes("invite_code"));
  assert.equal(ports.collectDialogue.calls.length, 0);
  assert.equal(ports.upload.calls.length, 0);
  assert.equal(queue.listTaskViews().length, 0);
  await queue.dispose();
});

test("上传中断 → failed_retryable 保留 + 失败原因；重启扫描恢复（LCD-005），重传不重采（INV-4）、uuid 不变（INV-2）", async (t) => {
  const clock = makeClock();
  // 第一次运行：上传中断（断网）
  const ports1 = makePorts({
    upload: createSpy(async () => ({ status: "interrupted", cause: "network offline" })),
  });
  const { queue: q1, storagePath } = await makeQueue(t, ports1, { clock });
  await q1.init();
  const res = await q1.submitIntent(COMPLETE_INTENT);
  const uuid = res.task_ref.submission_uuid;

  const failed = q1.getTask(uuid);
  assert.equal(failed.state, "failed_retryable");
  assert.ok(failed.failure_reason.includes("network offline"));
  assert.notEqual(failed.next_attempt_at, null);
  assert.equal(ports1.upload.calls.length, 1);
  await q1.dispose();

  // 重启：时钟推进越过退避点，启动扫描（process_start）应恢复同一 uuid
  clock.advance(60_000);
  const ports2 = makePorts(); // 新端口实例：采集 spy 必须保持 0 次
  const q2 = createPendingQueue({ storagePath, ports: ports2, clock });
  await q2.init(); // LCD-005 启动扫描触发恢复

  assert.equal(ports2.collectDialogue.calls.length, 0, "INV-4: 恢复不得重采对话");
  assert.equal(ports2.collectMaterials.calls.length, 0, "INV-4: 恢复不得重采材料");
  assert.equal(ports2.upload.calls.length, 1);
  assert.equal(ports2.upload.calls[0][0].submission_uuid, uuid, "INV-2: uuid 全程不变");

  const recovered = q2.getTask(uuid);
  assert.equal(recovered.state, "completed");
  assert.equal(recovered.submission_id, "sub-0001");
  assert.equal(recovered.submission_uuid, uuid);
  await q2.dispose();
});

test("对话端口抛 HostUnsupportedError → 显式失败且原因含 unsupported（不静默、不伪造、不上传）", async (t) => {
  const ports = makePorts({
    collectDialogue: createSpy(async () => {
      throw new HostUnsupportedError("TD-01: host export mechanism not confirmed");
    }),
  });
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  const uuid = res.task_ref.submission_uuid;
  const task = queue.getTask(uuid);

  assert.equal(task.state, "failed_retryable");
  assert.equal(task.failure_code, "HOST_EXPORT_UNSUPPORTED");
  assert.ok(task.failure_reason.includes("unsupported"), "失败原因必须显式含 unsupported");
  assert.equal(task.bundle_ref, null, "不得伪造对话导出物/快照");
  assert.ok(!task.missing_items.includes("dialogue"), "不得静默转为「对话缺失」");
  assert.equal(ports.upload.calls.length, 0, "采集失败不得发起上传");

  const view = queue.getTaskView(uuid);
  assert.ok(view.failure_reason.includes("unsupported"));
  assert.equal(view.submission_id, undefined);
  await queue.dispose();
});

test("状态机非法迁移拒绝；failed_terminal 不可恢复", async (t) => {
  // 纯状态机层
  assert.throws(() => assertTransition("created", "completed"), InvalidTransitionError);
  assert.throws(() => assertTransition("failed_terminal", "uploading"), InvalidTransitionError);
  assert.throws(() => assertTransition("completed", "uploading"), InvalidTransitionError);
  assert.throws(() => assertTransition("queued", "completed"), InvalidTransitionError);
  assert.doesNotThrow(() => assertTransition("created", "collecting"));
  assert.doesNotThrow(() => assertTransition("failed_retryable", "uploading"));
  assert.ok(TASK_STATES.includes("confirm_required"));

  // 队列层：rejected → failed_terminal；手动恢复不得再调上传端口
  const ports = makePorts({
    upload: createSpy(async () => ({
      status: "rejected",
      rejection_reason: "REJECTED_MEMBERSHIP",
    })),
  });
  const { queue } = await makeQueue(t, ports);
  await queue.init();
  const res = await queue.submitIntent(COMPLETE_INTENT);
  const uuid = res.task_ref.submission_uuid;
  assert.equal(queue.getTask(uuid).state, "failed_terminal");
  assert.ok(queue.getTask(uuid).failure_reason.includes("REJECTED_MEMBERSHIP"));

  const rec = await queue.triggerRecovery({ trigger_id: "manual-1", trigger_type: "manual_retry" });
  assert.deepEqual(rec.candidate_task_uuids, []);
  assert.equal(ports.upload.calls.length, 1, "failed_terminal 不可恢复");
  await queue.dispose();
});

test("上传 unknown → confirm_required 保留（不伪造结论）；恢复后收敛", async (t) => {
  const clock = makeClock();
  let outcome = { status: "unknown" };
  const ports = makePorts({ upload: createSpy(async () => outcome) });
  const { queue } = await makeQueue(t, ports, { clock });
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  const uuid = res.task_ref.submission_uuid;
  const task = queue.getTask(uuid);
  assert.equal(task.state, "confirm_required");
  assert.equal(task.submission_id, null, "结果未知不得伪造提交编号");

  const view = queue.getTaskView(uuid);
  assert.equal(view.status, "confirm_required");
  assert.equal(view.submission_id, undefined);
  assert.ok(view.failure_reason.includes("unknown"));

  // 退避到期后恢复（同一 uuid、同一快照），服务端应答 confirmed 后收敛
  clock.advance(60_000);
  outcome = {
    status: "confirmed",
    submission_id: "sub-0009",
    received_at: new Date(clock.now()).toISOString(),
    missing_items: [],
  };
  const rec = await queue.triggerRecovery({ trigger_id: "hint-1", trigger_type: "reachability_hint" });
  assert.deepEqual(rec.candidate_task_uuids, [uuid]);
  assert.equal(ports.upload.calls.length, 2);
  assert.equal(ports.upload.calls[1][0].submission_uuid, uuid);
  assert.equal(ports.collectDialogue.calls.length, 1, "confirm_required 恢复同样不重采");
  assert.equal(queue.getTask(uuid).state, "completed");

  // trigger_id 去重：重复触发为空操作
  const dup = await queue.triggerRecovery({ trigger_id: "hint-1", trigger_type: "reachability_hint" });
  assert.equal(dup.deduplicated, true);
  assert.equal(ports.upload.calls.length, 2);
  await queue.dispose();
});

test("command_id 幂等：重复提交返回既有任务，不创建第二个任务（PQ-IDEM-001）", async (t) => {
  const ports = makePorts();
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const first = await queue.submitIntent(COMPLETE_INTENT, { command_id: "cmd-1" });
  const second = await queue.submitIntent(COMPLETE_INTENT, { command_id: "cmd-1" });
  assert.equal(second.intake_result, "duplicate");
  assert.equal(second.task_ref.submission_uuid, first.task_ref.submission_uuid);
  assert.equal(ports.upload.calls.length, 1);
  assert.equal(queue.listTaskViews().length, 1);
  await queue.dispose();
});

test("材料采集失败 → failed_retryable + 具体原因，不上传（目录不可读语义）", async (t) => {
  const ports = makePorts({
    collectMaterials: createSpy(async () => {
      const err = new Error("directory unreadable: C:/materials/code (EACCES)");
      err.code = "MC-ERR-DIR-UNREADABLE";
      throw err;
    }),
  });
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  const task = queue.getTask(res.task_ref.submission_uuid);
  assert.equal(task.state, "failed_retryable");
  assert.equal(task.failure_code, "MC-ERR-DIR-UNREADABLE");
  assert.ok(task.failure_reason.includes("EACCES"));
  assert.equal(ports.upload.calls.length, 0);
  await queue.dispose();
});

test("IC-M01-05 StatusView 形状与 ports/index.js 一致（真实状态/原因，不伪造结论）", async (t) => {
  const ports = makePorts();
  const { queue } = await makeQueue(t, ports);
  await queue.init();

  const res = await queue.submitIntent(COMPLETE_INTENT);
  const view = queue.getTaskView(res.task_ref.submission_uuid);

  // StatusView typedef：{submission_id?, status, missing_items[], failure_reason?}（追加字段允许）
  assert.equal(typeof view.status, "string");
  assert.ok(TASK_STATES.includes(view.status));
  assert.ok(Array.isArray(view.missing_items));
  assert.equal(view.submission_id, "sub-0001");
  assert.equal(view.failure_reason, undefined);
  const allowed = new Set([
    "submission_uuid",
    "status",
    "missing_items",
    "submission_id",
    "failure_reason",
    "retry_at",
    "progress",
  ]);
  for (const key of Object.keys(view)) {
    assert.ok(allowed.has(key), `unexpected StatusView field: ${key}`);
  }

  assert.throws(() => queue.getTaskView("no-such-uuid"), /VIEW_NOT_AVAILABLE/);
  await queue.dispose();
});
