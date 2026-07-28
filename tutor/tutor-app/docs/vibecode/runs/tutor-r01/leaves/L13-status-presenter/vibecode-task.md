# VibeCode Task — L13 CMP-STATUS-PRESENTER（W2）

- run：tutor-r01；leaf：L13；波次：W2；分支：`tutor-r01/L13-status-presenter`
- 模块：MOD-01 codex-plugin / CMP-STATUS-PRESENTER 学生侧状态与错误展示（DU-1，Node ESM 零依赖）。

## 目标

实现学生侧状态展示：提交编号与接收确认、失败原因、缺失项、配置不完整提示（REQ-004、AC-REQ-001-01/002-01 展示面；IC-M01-05 消费）。

## 交付物

1. 展示渲染端口（IC-M01-05 consumer）：输入 StatusView（L11）/ 配置不完整状态（L04）→ 学生可读文本/结构；展示数据源唯一，**不伪造结论**（scoring_failed 展示真实失败原因与重试结果，不显示伪造等级）。
2. 展示形态：提交编号、received_at、missing_items 中文类别名映射（对话/代码/截图/结果）、失败原因、断网待上传提示、配置缺失项清单。
3. 测试：`plugin/test/status-presenter.test.js`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-status-presenter/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（04-contracts-and-runtime.md 的 IC-M01-05）
- 验收：根 PRD AC-REQ-001-01（exceptions 展示）、AC-REQ-002-01（不完整配置提示）、REQ-004
- 仓库：`plugin/src/ports/index.js`（StatusView）、`contracts/ct-001.json`（类别枚举）、`contracts/ct-002.json`（status 值域）

## 关键语义

- 展示数据只来自 IC-M01-05 端口；不新增数据源；不把内部错误码原文暴露给学生（映射为学生可读文案，保留真实原因）。
- 不实现：L04/L05/L06/L10/L11 的内部逻辑。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
