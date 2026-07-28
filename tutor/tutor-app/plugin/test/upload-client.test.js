import { test } from "node:test";
import assert from "node:assert/strict";

import {
  CATEGORY_ID_TO_CT001,
  createUploadClient,
  toCt001Category,
  UploadClientError,
} from "../src/upload_client/index.js";

const UUID = "11111111-2222-3333-4444-555555555555";

const IDENTITY = {
  invite_code: "INV-2026",
  student_name: "张三",
  group_name: "第 7 组",
  assignment: "作业一",
};

function makeBundle() {
  return {
    chunks: [
      { category: "dialogue", filename: "dialogue.md", media_type: "text/markdown", size_bytes: 12, content: "DIALOGUE" },
      { category: "code", filename: "a.js", media_type: "text/javascript", size_bytes: 4, content: "CODE" },
      { category: "screenshot", filename: "s.png", media_type: "image/png", size_bytes: 3, content: "PNG" },
      { category: "result", filename: "out.csv", media_type: "text/csv", size_bytes: 3, content: "CSV" },
    ],
  };
}

function makeJob(overrides = {}) {
  return { submission_uuid: UUID, bundle_ref: makeBundle(), identity: { ...IDENTITY }, ...overrides };
}

/**
 * MOD-02 stub：按 uuid 幂等（重复 create_session 返回同一会话与 submission_id）。
 * hooks.override(req, {submissions}) 返回非 undefined 时作为响应（可返回
 * 永不 resolve 的 Promise 模拟响应丢失；可 throw 模拟网络中断）。
 */
function createStubServer(hooks = {}) {
  const requests = [];
  const submissions = new Map(); // uuid -> {session_id, submission_id, acked:Set, merged}
  let tokenSeq = 0;

  const issueToken = () => {
    tokenSeq += 1;
    return {
      status: 200,
      body: { access_token: `tok-${tokenSeq}`, token_type: "Bearer", expires_in: 3600 },
    };
  };

  const defaultHandle = (req) => {
    if (req.path === "/api/v1/auth/token") return issueToken();

    if (req.path.startsWith("/api/v1/submissions/") && req.method === "GET") {
      const uuid = decodeURIComponent(req.path.slice("/api/v1/submissions/".length));
      const sub = submissions.get(uuid);
      if (!sub) return { status: 404, body: { error_code: "NOT_FOUND" } };
      return {
        status: 200,
        body: {
          submission_id: sub.submission_id,
          status: sub.merged ? "received" : "upload_failed",
          missing_items: [],
          ...(sub.merged ? {} : { failure_reason: "upload interrupted" }),
        },
      };
    }

    const phase = req.body?.phase;
    if (phase === "create_session") {
      const uuid = req.body.submission_uuid;
      let sub = submissions.get(uuid);
      if (!sub) {
        sub = {
          session_id: `sess-${uuid}`,
          submission_id: `sub-${uuid}`,
          acked: new Set(),
          merged: false,
        };
        submissions.set(uuid, sub);
      }
      return { status: 200, body: { upload_session_id: sub.session_id } };
    }
    if (phase === "chunk") {
      const sub = submissions.get(req.body.submission_uuid);
      sub.acked.add(req.body.chunk_index);
      return { status: 200, body: { acked: true, chunk_index: req.body.chunk_index } };
    }
    if (phase === "merge") {
      const sub = submissions.get(req.body.submission_uuid);
      sub.merged = true;
      return {
        status: 200,
        body: {
          submission_id: sub.submission_id,
          received_at: "2026-07-20T09:00:00.000Z",
          status: "received",
          missing_items: [],
        },
      };
    }
    throw new Error(`unexpected request: ${req.method} ${req.path}`);
  };

  const transport = (req) => {
    requests.push(req);
    if (hooks.override) {
      const r = hooks.override(req, { submissions });
      if (r !== undefined) return r; // 可能是 pending Promise（响应丢失），不 await
    }
    return defaultHandle(req);
  };

  const byPhase = (phase) => requests.filter((r) => r.body?.phase === phase);
  return {
    transport,
    requests,
    submissions,
    byPhase,
    authCount: () => requests.filter((r) => r.path === "/api/v1/auth/token").length,
    queryCount: () => requests.filter((r) => r.method === "GET").length,
  };
}

function silentClient(server, deps = {}) {
  const events = [];
  const client = createUploadClient({
    transport: server.transport,
    sleep: async () => {},
    onEvent: (e) => events.push(e),
    ...deps,
  });
  return { client, events };
}

test("全流程：建会话 → 逐分片 → 合并，请求形状含 submission_uuid 与中文类别枚举", async () => {
  const server = createStubServer();
  const { client } = silentClient(server);

  const outcome = await client.startOrResumeUpload(makeJob());

  assert.equal(outcome.outcome_type, "confirmed");
  assert.equal(outcome.submission_id, `sub-${UUID}`);
  assert.equal(outcome.received_at, "2026-07-20T09:00:00.000Z");
  assert.deepEqual(outcome.missing_items, []);

  // 协议顺序：auth/token → create_session → chunk × 4 → merge
  assert.equal(server.authCount(), 1);
  assert.deepEqual(
    server.requests.map((r) => r.body?.phase ?? (r.method === "GET" ? "query" : "auth")),
    ["auth", "create_session", "chunk", "chunk", "chunk", "chunk", "merge"],
  );

  // create_session 形状：submission_uuid + CT-001 必填字段 + 中文类别
  const create = server.byPhase("create_session")[0];
  assert.equal(create.body.submission_uuid, UUID);
  assert.equal(create.body.invite_code, IDENTITY.invite_code);
  assert.equal(create.body.student_name, IDENTITY.student_name);
  assert.equal(create.body.group_name, IDENTITY.group_name);
  assert.equal(create.body.assignment, IDENTITY.assignment);
  assert.equal(create.body.total_chunks, 4);
  assert.deepEqual(
    create.body.material_chunks.map((c) => c.category),
    ["对话", "代码", "截图", "结果"],
  );

  // 每个 CT-001 请求都带 uuid + Bearer 授权
  for (const req of server.byPhase("chunk").concat(server.byPhase("merge"))) {
    assert.equal(req.body.submission_uuid, UUID);
    assert.match(req.headers.authorization, /^Bearer tok-/);
  }
  assert.deepEqual(server.byPhase("chunk").map((r) => r.body.chunk_index), [0, 1, 2, 3]);
  assert.equal(server.byPhase("chunk")[0].body.chunk.category, "对话");

  // checkpoint：全部分片已确认（INV-5）
  const cp = await client.loadCheckpoint(UUID);
  assert.deepEqual(cp.confirmed_chunks, [0, 1, 2, 3]);
  assert.equal(cp.total_chunks, 4);
  assert.equal(cp.upload_session_id, `sess-${UUID}`);
  assert.ok(cp.last_ack_at !== null);
});

test("断点续传：已确认分片不重传，未确认分片重发；不重建会话", async () => {
  let failChunk1 = true;
  const server = createStubServer({
    override: (req) => {
      if (failChunk1 && req.body?.phase === "chunk" && req.body.chunk_index === 1) {
        throw new Error("ECONNRESET");
      }
      return undefined;
    },
  });
  const { client } = silentClient(server);

  const first = await client.startOrResumeUpload(makeJob());
  assert.equal(first.outcome_type, "interrupted");
  assert.equal(first.interruption_cause, "NETWORK_INTERRUPTED");

  // checkpoint 只记已确认分片 [0]（INV-5），中断不丢 checkpoint
  const cp = await client.loadCheckpoint(UUID);
  assert.deepEqual(cp.confirmed_chunks, [0]);

  failChunk1 = false;
  const second = await client.startOrResumeUpload(makeJob());
  assert.equal(second.outcome_type, "confirmed");
  assert.equal(second.submission_id, `sub-${UUID}`);

  // 恢复后：无第二次 create_session；chunk 0 未重传；1/2/3 重发
  assert.equal(server.byPhase("create_session").length, 1);
  const resumedChunks = server.byPhase("chunk").slice(2); // 首轮发了 chunk0 + 失败的 chunk1
  assert.deepEqual(resumedChunks.map((r) => r.body.chunk_index), [1, 2, 3]);

  const cpAfter = await client.loadCheckpoint(UUID);
  assert.deepEqual(cpAfter.confirmed_chunks, [0, 1, 2, 3]);
});

test("幂等：同一 submission_uuid 重试返回同一 submission_id，不产生第二次创建", async () => {
  const server = createStubServer();
  const { client } = silentClient(server);

  const first = await client.startOrResumeUpload(makeJob());
  const second = await client.startOrResumeUpload(makeJob());

  assert.equal(first.outcome_type, "confirmed");
  assert.equal(second.outcome_type, "confirmed");
  assert.equal(second.submission_id, first.submission_id);
  assert.equal(server.submissions.size, 1); // 服务端无重复提交
  assert.equal(server.byPhase("create_session").length, 1); // checkpoint 复用会话
});

test("30 秒未确认 → CT-002 查询真实状态（received → confirmed），不重复上传", async () => {
  const server = createStubServer({
    override: (req, { submissions }) => {
      if (req.body?.phase === "merge") {
        submissions.get(req.body.submission_uuid).merged = true; // 服务端实际已接收
        return new Promise(() => {}); // 响应丢失：永不 resolve
      }
      return undefined;
    },
  });
  const { client, events } = silentClient(server, { confirmTimeoutMs: 25 });

  const outcome = await client.startOrResumeUpload(makeJob());

  assert.equal(outcome.outcome_type, "confirmed");
  assert.equal(outcome.submission_id, `sub-${UUID}`);
  assert.ok(events.some((e) => e.event === "UploadConfirmationTimedOut"));
  assert.ok(server.queryCount() >= 1);

  // 关键：超时后未重发整包（无第二次 create_session / chunk / merge）
  assert.equal(server.byPhase("create_session").length, 1);
  assert.equal(server.byPhase("chunk").length, 4);
  assert.equal(server.byPhase("merge").length, 1);
});

test("30 秒未确认 → CT-002 为 upload_failed → interrupted（保留待上传，可恢复）", async () => {
  const server = createStubServer({
    override: (req) => {
      if (req.body?.phase === "merge") return new Promise(() => {});
      return undefined;
    },
  });
  const { client } = silentClient(server, { confirmTimeoutMs: 25 });

  const outcome = await client.startOrResumeUpload(makeJob());
  assert.equal(outcome.outcome_type, "interrupted");
  assert.equal(outcome.interruption_cause, "upload_failed");

  // checkpoint 保留，恢复后仅补 merge 即成功
  const cp = await client.loadCheckpoint(UUID);
  assert.deepEqual(cp.confirmed_chunks, [0, 1, 2, 3]);
  const server2 = createStubServer();
  server2.submissions.set(UUID, {
    session_id: `sess-${UUID}`,
    submission_id: `sub-${UUID}`,
    acked: new Set([0, 1, 2, 3]),
    merged: false,
  });
  const { client: client2 } = silentClient(server2);
  const resumed = await client2.startOrResumeUpload(makeJob({ checkpoint: cp }));
  assert.equal(resumed.outcome_type, "confirmed");
  assert.equal(server2.byPhase("chunk").length, 0); // 已确认分片全部跳过
  assert.equal(server2.byPhase("merge").length, 1);
});

test("CT-002 持续不可达 → unknown（不伪造服务端终态）", async () => {
  const server = createStubServer({
    override: (req) => {
      if (req.body?.phase === "merge") return new Promise(() => {});
      if (req.method === "GET") throw new Error("ETIMEDOUT");
      return undefined;
    },
  });
  const { client } = silentClient(server, { confirmTimeoutMs: 25, backoffMs: [1, 1, 1] });

  const outcome = await client.startOrResumeUpload(makeJob());
  assert.equal(outcome.outcome_type, "unknown");
  assert.equal(outcome.unknown_reason, "UNREACHABLE");
  assert.equal(server.queryCount(), 3); // 指数退避序列耗尽
});

test("类别映射表：dialogue/code/screenshot/result → 对话/代码/截图/结果 一一对应", async () => {
  assert.deepEqual(CATEGORY_ID_TO_CT001, {
    dialogue: "对话",
    code: "代码",
    screenshot: "截图",
    result: "结果",
  });
  assert.equal(toCt001Category("dialogue"), "对话");
  assert.equal(toCt001Category("code"), "代码");
  assert.equal(toCt001Category("screenshot"), "截图");
  assert.equal(toCt001Category("result"), "结果");
  assert.throws(() => toCt001Category("video"), (err) => {
    assert.ok(err instanceof UploadClientError);
    assert.equal(err.code, "UP-ERR-CATEGORY-UNKNOWN");
    return true;
  });

  // 未知类别：本地显式失败，零网络请求
  const server = createStubServer();
  const { client } = silentClient(server);
  await assert.rejects(
    () => client.startOrResumeUpload(makeJob({ bundle_ref: { chunks: [{ category: "video" }] } })),
    (err) => err.code === "UP-ERR-CATEGORY-UNKNOWN",
  );
  assert.equal(server.requests.length, 0);
});

test("令牌：缓存命中不重复换领；过期后重领一次", async () => {
  let now = 1_000_000;
  const server = createStubServer();
  const { client } = silentClient(server, { clock: () => now });

  await client.startOrResumeUpload(makeJob({ submission_uuid: `${UUID}-a` }));
  await client.startOrResumeUpload(makeJob({ submission_uuid: `${UUID}-b` }));
  assert.equal(server.authCount(), 1); // 缓存命中，第二次上传未换领

  now += 3600 * 1000 + 1; // 越过 expires_in
  await client.startOrResumeUpload(makeJob({ submission_uuid: `${UUID}-c` }));
  assert.equal(server.authCount(), 2); // 过期重领一次
});

test("令牌：401 后失效重领一次并重放当前请求；令牌不出现在日志/错误消息", async () => {
  const server = createStubServer();
  const rawTransport = server.transport;
  let injected401 = true;
  const transport = (req) => {
    if (injected401 && req.body?.phase === "chunk" && req.body.chunk_index === 1) {
      injected401 = false;
      server.requests.push(req);
      return { status: 401, body: { error_code: "AUTH_INVALID" } };
    }
    return rawTransport(req);
  };
  const events = [];
  const client = createUploadClient({
    transport,
    sleep: async () => {},
    onEvent: (e) => events.push(e),
  });

  const outcome = await client.startOrResumeUpload(makeJob());
  assert.equal(outcome.outcome_type, "confirmed");
  assert.equal(server.authCount(), 2); // 失效后重领一次
  // chunk 1 重放过一次（401 的那次 + 重放成功的一次）
  assert.equal(
    server.requests.filter((r) => r.body?.phase === "chunk" && r.body.chunk_index === 1).length,
    2,
  );

  // 令牌绝不进入结构化日志
  assert.ok(!JSON.stringify(events).includes("tok-"));

  // AUTH_INVALID 终态：错误呈现不含令牌
  const badServer = createStubServer();
  const badTransport = async (req) => {
    badServer.requests.push(req);
    if (req.path === "/api/v1/auth/token") {
      return { status: 401, body: { error_code: "AUTH_INVALID" } };
    }
    throw new Error("should not reach CT-001 without token");
  };
  const badClient = createUploadClient({ transport: badTransport, sleep: async () => {} });
  const authFailed = await badClient.startOrResumeUpload(makeJob());
  assert.equal(authFailed.outcome_type, "interrupted");
  assert.equal(authFailed.interruption_cause, "AUTH_INVALID");
  assert.ok(!JSON.stringify(authFailed).includes("tok-"));
});

test("网络中断 → 可恢复失败：保留待上传语义，不丢 checkpoint", async () => {
  const server = createStubServer({
    override: (req) => {
      if (req.body?.phase === "chunk" && req.body.chunk_index === 2) {
        throw new Error("ECONNRESET");
      }
      return undefined;
    },
  });
  const { client, events } = silentClient(server);

  const outcome = await client.startOrResumeUpload(makeJob());
  assert.equal(outcome.outcome_type, "interrupted");
  assert.equal(outcome.interruption_cause, "NETWORK_INTERRUPTED");
  assert.ok(events.some((e) => e.event === "UploadInterrupted" && e.chunk_index === 2));

  // checkpoint 只含已确认的 0/1；未确认的分片 2 不被跳过（INV-5）
  const cp = await client.loadCheckpoint(UUID);
  assert.deepEqual(cp.confirmed_chunks, [0, 1]);
});

test("单任务单活跃执行：同一 uuid 并发 Start 归并到既有执行", async () => {
  const server = createStubServer();
  const { client, events } = silentClient(server);

  const p1 = client.startOrResumeUpload(makeJob());
  const p2 = client.startOrResumeUpload(makeJob());
  assert.equal(p1, p2); // 归并：同一执行句柄
  const [o1, o2] = await Promise.all([p1, p2]);
  assert.equal(o1.outcome_type, "confirmed");
  assert.equal(o2.submission_id, o1.submission_id);
  assert.ok(events.some((e) => e.event === "UploadExecutionMerged"));
  assert.equal(server.byPhase("create_session").length, 1);
});

test("UploadJob 校验：缺必填字段本地失败，不发网络请求", async () => {
  const server = createStubServer();
  const { client } = silentClient(server);
  await assert.rejects(
    () => client.startOrResumeUpload({ submission_uuid: UUID, bundle_ref: { chunks: [] }, identity: { invite_code: "x" } }),
    (err) => err.code === "UP-ERR-JOB-INVALID",
  );
  assert.equal(server.requests.length, 0);
});
