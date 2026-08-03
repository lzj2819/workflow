# VibeCode Task — L11 CMP-PENDING-QUEUE（W2）

- run：tutor-r01；leaf：L11；波次：W2；分支：`tutor-r01/L11-pending-queue`
- 模块：MOD-01 codex-plugin / CMP-PENDING-QUEUE 本地任务队列与状态机（DU-1，Node ESM 零依赖）。

## 目标

实现本地待上传任务队列（断网保留/恢复续传）与采集编排枢纽（IC-M01-01/03/04/05），含 LCD-005 恢复调度触发。

## 交付物

1. PendingTask 持久化（ST-04：submission_uuid（INV-2 全程不变）、状态机、失败原因；JSON 文件原子写，LCD-004 implementation_detail）。
2. 任务状态机：created → collecting → queued → uploading →（completed | failed_retryable | failed_terminal）；恢复调度触发（LCD-005：启动扫描 + 事件触发，可注入时钟/调度器）。
3. 采集编排（IC-M01-03）：意图完成（IC-M01-01）→ 创建任务快照（LCD-002 创建即快照）→ 编排对话采集端口（L07，**经端口注入；当前为 TD-01 unsupported 状态——必须显式传播 HostUnsupportedError，不得静默转为「对话缺失」或伪造导出物**）与材料采集（L06 端口形状）→ 组装 CT-001 载荷交上传端口（L10 IC-M01-04）。
4. 状态展示数据源（IC-M01-05）：向 L13 输出 StatusView 形状（真实状态/原因，不伪造结论）。
5. 测试：`plugin/test/pending-queue.test.js`（端口全部注入 stub/spy）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-pending-queue/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（03-state-and-data.md 的 ST-04/INV-1~5、04-contracts-and-runtime.md 的 IC-M01-01/03/04/05、05-local-decisions.md 的 LCD-002/004/005）
- 验收：根 PRD AC-REQ-001-01 及 exceptions；SM-001 contributing
- 仓库：`plugin/src/ports/index.js`、`plugin/src/host/dialogue-export-port.js`（HostUnsupportedError 语义）、L04/L05/L06/L10 端口形状（只读引用）

## 关键语义

- INV-1 缺项不产生网络调用；INV-2 uuid 全程不变；INV-4 采集快照重传不重采。
- 对话采集 unsupported（TD-01）→ 任务显式失败原因 observable（可观测失败），不得伪造对话导出物或静默降级为 missing。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
