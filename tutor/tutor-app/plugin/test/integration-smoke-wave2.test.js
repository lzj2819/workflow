import { test } from "node:test";
import assert from "node:assert/strict";

import { presentTaskView } from "../src/status_presenter/index.js";

// Wave 2 集成接线项 2：L11 任务状态枚举 → L13 展示映射对齐。
// 断言 L11 全部状态值均有语义化展示（不回退原始字符串），失败态展示真实原因。

const L11_STATES = [
  "created",
  "collecting",
  "queued",
  "uploading",
  "confirm_required",
  "completed",
  "failed_retryable",
  "failed_terminal",
];

function viewFor(status, extra = {}) {
  return {
    status,
    submission_id: null,
    received_at: null,
    missing_items: [],
    failure_reason: null,
    ...extra,
  };
}

test("L11 全部状态均有语义化展示（title 不含原始 status 字符串回退）", () => {
  for (const status of L11_STATES) {
    const view = presentTaskView(viewFor(status));
    const text = JSON.stringify(view);
    assert.ok(!text.includes(`提交状态：${status}`), `status ${status} fell back to raw display`);
  }
});

test("failed_retryable / failed_terminal 展示真实原因且不含等级", () => {
  const retryable = presentTaskView(viewFor("failed_retryable", { failure_reason: "network down" }));
  assert.ok(JSON.stringify(retryable).includes("network down"));
  const terminal = presentTaskView(viewFor("failed_terminal", { failure_reason: "host export unsupported" }));
  const text = JSON.stringify(terminal);
  assert.ok(text.includes("host export unsupported"));
  for (const grade of ["A", "B", "C", "D", "E"]) {
    assert.ok(!text.includes(`等级：${grade}`));
  }
});

test("completed 为 success；created/collecting 为 info", () => {
  assert.equal(presentTaskView(viewFor("completed")).severity, "success");
  assert.equal(presentTaskView(viewFor("created")).severity, "info");
  assert.equal(presentTaskView(viewFor("collecting")).severity, "info");
});

test("confirm_required 不伪造结论（提示结果未知、不重复提交）", () => {
  const view = presentTaskView(viewFor("confirm_required"));
  const text = JSON.stringify(view);
  assert.ok(text.includes("结果") || text.includes("尚未确认"));
  assert.ok(!text.includes("等级"));
});
