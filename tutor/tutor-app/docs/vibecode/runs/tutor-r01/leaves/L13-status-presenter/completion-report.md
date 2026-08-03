# Completion Report — L13 CMP-STATUS-PRESENTER（tutor-r01，W2）

- 状态：done
- 提交 SHA：`848cb863cfa286fec1fc2b6b1f9dc12c933854fd`（分支 tutor-r01/L13-status-presenter）
- 基线：main a4d373f

## 改动清单

- `plugin/src/status_presenter/index.js`（新增，约 380 行）：IC-M01-05 消费端。四个 L2 子节点分段实现于单文件（对齐 L06 单 index.js 先例）：
  - `projectTaskView` / `projectConfigView`（TASK/CONFIG-VIEW-PROJECTOR）：输入快照校验与字段原样投影，非法输入抛 `VIEW_NOT_AVAILABLE`；
  - `presentTaskView` / `presentConfigView`（STATUS-MESSAGE-MAPPER）：status/submission_id/failure_reason/missing_items/completeness/dir_errors 原值透传（INV-SP-002/003/004），派生 severity/message_key/message_params/action_hint（LCD-SP-003 中性未知语义）；
  - `renderPresentationView` / `renderTaskView` / `renderConfigView`（RENDER-ADAPTER）：纯文本宿主渲染（LCD-SP-006）；
  - `sanitizeReason`：CT-001/CT-002 错误码、`*-ERR-*` 内部码、网络 errno 映射为学生可读文案；Bearer/token=/secret 等脱敏为 `[已隐藏]`；非码部分原文保留（真实含义不吞掉）；
  - missing_items 中文类别名映射（对话/代码/截图/结果，兼容 code/screenshot(s)/result(s)/dialogue 内部名）；配置字段中文名映射（课程邀请码/姓名/小组/代码目录/截图目录/结果目录）。
- `plugin/test/status-presenter.test.js`（新增，16 测试）：覆盖 verification-checklist 全部语义断言。

## 验证命令与结果（worktree 的 plugin/ 目录）

- `node --test test/status-presenter.test.js` → tests 16 / pass 16 / fail 0（duration 96.8ms）
- `npm test` → tests 59 / pass 59 / fail 0（既有 43 测试无回归；duration 371.9ms）
- `node --check src/status_presenter/index.js`、`node --check test/status-presenter.test.js` → 通过

语义断言对照：
- received → 提交编号 + received_at + missing_items 中文类别名：已覆盖；
- upload_failed / rejected / scoring_failed → 真实原因、无等级（GRADE_LIKE 反断言）、状态不改写：已覆盖；
- 配置不完整 → 中文缺失字段清单 + 具体目录错误（AC-REQ-002-01 展示面）：已覆盖；
- 断网待上传（queued/paused/failed）→ 本地保留与网络恢复提示：已覆盖；
- 输出无内部错误码原文（REJECTED_MEMBERSHIP / ECONNREFUSED / MC-ERR-* 用例）、无令牌/secret：已覆盖；
- 输入形状与 ports/index.js StatusView 一致（仅 status 必填）：已覆盖；
- 附加：failure_reason 原值透传、同一输入确定性等价（INV-SP-005）、未知状态原样展示、非法输入 → VIEW_NOT_AVAILABLE。

## 契约影响

无。未修改 IC-M01-05 任何字段/owner/错误语义；未新增跨模块契约；未触碰 contracts/、ports/index.js、package.json 或任何 forbidden 路径；零 npm 依赖。

## 风险/阻塞

- 低：本地待上传类状态取值（queued/paused/failed）按 L1 retained_states 与 IC-M01-04 状态集推断；若 L11 PENDING-QUEUE 最终采用其他 status 字符串，集成时只需在 TASK_STATUS_MESSAGES 增补键（兼容追加，不改契约）。
- received_at 不在 ports/index.js StatusView typedef 中，按 ST-04「时间戳」与验收清单要求作为可选字段消费（缺省不展示），属兼容追加消费，不改契约。
- 无阻塞。

## 范围自检

`git diff --name-only main...HEAD` 输出（仅允许路径，2 文件）：

```
plugin/src/status_presenter/index.js
plugin/test/status-presenter.test.js
```
