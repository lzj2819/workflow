/**
 * L13 CMP-STATUS-PRESENTER 测试（REQ-004 / REQ-DD001/DD002；
 * AC-REQ-001-01 exceptions 展示面 / AC-REQ-002-01 展示面）。
 *
 * 覆盖 verification-checklist 语义断言：
 * - received → 提交编号 + received_at + missing_items（中文类别名）；
 * - upload_failed / rejected / scoring_failed → 真实失败原因，不显示任何等级；
 * - 配置不完整 → 缺失字段清单（中文名）与具体目录错误；
 * - 断网待上传 → 本地保留与恢复提示；
 * - 输出不含内部错误码原文、不含令牌/secret；
 * - 状态不改写（INV-SP-004）、失败原因原值透传（INV-SP-002）、
 *   同一输入确定性等价视图（INV-SP-005）、非法输入 → VIEW_NOT_AVAILABLE（INV-SP-006）。
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  SP_ERROR_CODES,
  StatusPresenterError,
  CATEGORY_LABELS,
  CONFIG_FIELD_LABELS,
  sanitizeReason,
  labelCategory,
  labelConfigField,
  presentTaskView,
  presentConfigView,
  renderPresentationView,
  renderTaskView,
  renderConfigView,
} from "../src/status_presenter/index.js";

const GRADE_LIKE = /等级|得分|分数|优秀|良好|及格|成绩[为是：:]/;

test("received → 展示提交编号、received_at 与中文类别名 missing_items", () => {
  const view = presentTaskView({
    status: "received",
    submission_id: "SUB-2026-0001",
    received_at: "2026-07-19T10:00:00Z",
    missing_items: ["截图", "结果"],
    failure_reason: null,
  });
  assert.equal(view.view_type, "task");
  assert.equal(view.status, "received");
  assert.equal(view.severity, "success");
  const text = renderPresentationView(view);
  assert.match(text, /SUB-2026-0001/);
  assert.match(text, /2026-07-19T10:00:00Z/);
  assert.match(text, /缺失材料：截图、结果/);
});

test("received 缺省/内部类别名 missing_items → 映射为中文；空 missing → 材料齐全", () => {
  const withInternal = renderTaskView({
    status: "received",
    submission_id: "S1",
    received_at: "2026-07-19T10:00:00Z",
    missing_items: ["code", "dialogue"],
  });
  assert.match(withInternal, /缺失材料：代码、对话/);

  const complete = renderTaskView({
    status: "received",
    submission_id: "S2",
    received_at: "2026-07-19T10:00:00Z",
    missing_items: [],
  });
  assert.match(complete, /材料齐全/);
});

test("upload_failed / rejected / scoring_failed → 展示真实失败原因，不显示任何等级，状态不改写", () => {
  for (const [status, reason] of [
    ["upload_failed", "网络中断，分片 3/8 未确认"],
    ["rejected", "提交信息与课程名单不匹配"],
    ["scoring_failed", "评分服务处理超时，重试后仍未完成"],
  ]) {
    const view = presentTaskView({
      status,
      submission_id: "SUB-X",
      missing_items: [],
      failure_reason: reason,
    });
    assert.equal(view.status, status, `${status} 不得改写`);
    assert.equal(view.failure_reason, reason, "failure_reason 原值透传");
    assert.notEqual(view.severity, "success");
    const text = renderPresentationView(view);
    assert.match(text, new RegExp(reason.slice(0, 6)), `${status} 展示真实原因`);
    assert.doesNotMatch(text, GRADE_LIKE, `${status} 不得显示等级/成绩`);
    assert.doesNotMatch(text, /已被服务器接收/, `${status} 不得伪造 received`);
  }
});

test("scoring_failed → 展示真实原因与重试提示，不伪造评分结论", () => {
  const text = renderTaskView({
    status: "scoring_failed",
    submission_id: "SUB-9",
    missing_items: [],
    failure_reason: "评分 worker 崩溃，已自动重试 2 次仍失败",
  });
  assert.match(text, /评分失败/);
  assert.match(text, /评分 worker 崩溃，已自动重试 2 次仍失败/);
  assert.match(text, /重试/);
  assert.doesNotMatch(text, GRADE_LIKE);
});

test("confirm_required → 中性未知提示，不推断成功或失败", () => {
  const view = presentTaskView({
    status: "confirm_required",
    submission_id: "SUB-C",
    missing_items: [],
    failure_reason: "30 秒未收到服务器确认",
  });
  assert.equal(view.severity, "warning");
  const text = renderPresentationView(view);
  assert.match(text, /尚未确认/);
  assert.match(text, /30 秒未收到服务器确认/);
  assert.doesNotMatch(text, /已被服务器接收|上传失败|评分/);
});

test("断网待上传（queued/paused/failed）→ 明确的本地保留与恢复提示", () => {
  for (const status of ["queued", "paused", "failed"]) {
    const text = renderTaskView({
      status,
      submission_id: "SUB-OFF",
      missing_items: [],
      failure_reason: status === "failed" ? "无法连接服务器" : null,
    });
    assert.match(text, /本地/, status);
    assert.match(text, /网络恢复/, status);
    if (status === "failed") assert.match(text, /无法连接服务器/);
  }
});

test("配置不完整 → 列出缺失字段清单（中文名）与具体目录错误（AC-REQ-002-01 展示面）", () => {
  const view = presentConfigView({
    completeness: ["invite_code", "code_dir"],
    dir_errors: ["directory not readable: screenshots_dir=D:/hw/shots"],
  });
  assert.equal(view.view_type, "config");
  assert.equal(view.status, "incomplete");
  assert.deepEqual(view.completeness, ["invite_code", "code_dir"], "原值逐项透传");
  const text = renderPresentationView(view);
  assert.match(text, /缺失字段：课程邀请码、代码目录/);
  assert.match(text, /截图目录不可读：D:\/hw\/shots/);
  assert.doesNotMatch(text, /invite_code|code_dir|screenshots_dir/);
});

test("配置完整 → 配置已保存提示", () => {
  const text = renderConfigView({ completeness: [], dir_errors: [] });
  assert.match(text, /配置完整/);
});

test("输出不含内部错误码原文：映射为学生可读文案且保留真实含义", () => {
  const text = renderTaskView({
    status: "rejected",
    submission_id: "SUB-A",
    missing_items: [],
    failure_reason: "REJECTED_MEMBERSHIP",
  });
  assert.doesNotMatch(text, /REJECTED_MEMBERSHIP/);
  assert.match(text, /不在本课程提交名单中/);

  const text2 = renderTaskView({
    status: "upload_failed",
    submission_id: "SUB-B",
    missing_items: [],
    failure_reason: "upload aborted: ECONNREFUSED",
  });
  assert.doesNotMatch(text2, /ECONNREFUSED/);
  assert.match(text2, /无法连接服务器/);

  const text3 = renderTaskView({
    status: "upload_failed",
    submission_id: "SUB-C",
    missing_items: [],
    failure_reason: "MC-ERR-DIR-UNREADABLE: directory unreadable",
  });
  assert.doesNotMatch(text3, /MC-ERR-DIR-UNREADABLE/);
  assert.match(text3, /内部处理错误/);
});

test("输出不含令牌/secret：Bearer 与 token= 被脱敏", () => {
  const text = renderTaskView({
    status: "upload_failed",
    submission_id: "SUB-T",
    missing_items: [],
    failure_reason: "request failed: Bearer abc123secrettoken, token=xyz789key",
  });
  assert.doesNotMatch(text, /abc123secrettoken|xyz789key/);
  assert.match(text, /\[已隐藏\]/);
});

test("failure_reason 原值在视图透传，派生文案不替代原值（INV-SP-002）", () => {
  const raw = "REJECTED_MEMBERSHIP";
  const view = presentTaskView({
    status: "rejected",
    submission_id: "SUB-R",
    missing_items: [],
    failure_reason: raw,
  });
  assert.equal(view.failure_reason, raw);
  assert.match(view.message_params.reason, /不在本课程提交名单中/);
  assert.equal(view.message_params.reason.includes("REJECTED_MEMBERSHIP"), false);
});

test("输入形状与 ports/index.js StatusView 一致：仅 status 必填，其余可缺省", () => {
  const view = presentTaskView({ status: "processing" });
  assert.equal(view.submission_id, null);
  assert.deepEqual(view.missing_items, []);
  assert.equal(view.failure_reason, null);
  assert.match(renderPresentationView(view), /正在处理/);
});

test("同一输入快照产生确定性等价视图（INV-SP-005）", () => {
  const input = {
    status: "received",
    submission_id: "SUB-D",
    received_at: "2026-07-19T10:00:00Z",
    missing_items: ["代码"],
    failure_reason: null,
  };
  assert.deepEqual(presentTaskView(input), presentTaskView(input));
  assert.equal(renderTaskView(input), renderTaskView(input));
  const cfg = { completeness: ["group_name"], dir_errors: [] };
  assert.deepEqual(presentConfigView(cfg), presentConfigView(cfg));
});

test("非法输入 → VIEW_NOT_AVAILABLE，不静默降级（INV-SP-006）", () => {
  assert.ok(SP_ERROR_CODES.includes("VIEW_NOT_AVAILABLE"));
  for (const bad of [null, undefined, "received", 42, [], { status: "" }, { missing_items: [] }]) {
    assert.throws(() => presentTaskView(bad), (err) => {
      assert.ok(err instanceof StatusPresenterError);
      assert.equal(err.code, "VIEW_NOT_AVAILABLE");
      return true;
    });
  }
  assert.throws(
    () => presentTaskView({ status: "received", missing_items: "代码" }),
    (err) => err.code === "VIEW_NOT_AVAILABLE",
  );
  assert.throws(() => presentConfigView({ completeness: "x" }), (err) => err.code === "VIEW_NOT_AVAILABLE");
});

test("未知状态原样展示，不改写为已知状态（INV-SP-004）", () => {
  const view = presentTaskView({ status: "some_future_status", missing_items: [] });
  assert.equal(view.status, "some_future_status");
  assert.equal(view.severity, "warning");
  assert.match(renderPresentationView(view), /some_future_status/);
});

test("类别与字段标签映射辅助函数", () => {
  assert.equal(labelCategory("screenshots"), "截图");
  assert.equal(labelCategory("未识别类别"), "未识别类别");
  assert.equal(labelConfigField("results_dir"), "结果目录");
  assert.equal(labelConfigField("unknown_field"), "unknown_field");
  assert.equal(CATEGORY_LABELS["对话"], "对话");
  assert.equal(CONFIG_FIELD_LABELS.invite_code, "课程邀请码");
  assert.equal(sanitizeReason("普通中文原因"), "普通中文原因");
});
