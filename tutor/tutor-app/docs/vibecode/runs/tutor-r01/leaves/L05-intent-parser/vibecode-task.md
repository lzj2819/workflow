# VibeCode Task — L05 CMP-INTENT-PARSER（W1）

- run：tutor-r01；leaf：L05；波次：W1；分支：`tutor-r01/L05-intent-parser`
- 模块：MOD-01 codex-plugin / CMP-INTENT-PARSER 指令解析与确定性缺项闸门（DU-1，Node ESM 零依赖）。

## 目标

实现自然语言提交指令的解析与缺项校验（REQ-001 / F1-1 / AC-REQ-001-01）：提取作业、姓名、小组；三者缺一即不创建提交。

## 交付物

1. `parseSubmissionIntent(text)` → `IntentResult {complete, assignment?, student_name?, group_name?, missing[]}`（形状对齐 plugin/src/ports/index.js 的 IC-M01-01）。
2. 确定性闸门（MOD-01 LCD-001）：三项必填任一缺失 → complete=false + 具体缺失字段；不产生任何网络/提交副作用（INV-1）。
3. 提取实现为可配置规则（关键词/模式表），不依赖外部服务（implementation_detail）；指令与插件配置不一致时以当次指令为准（R-05）。
4. 测试：`plugin/test/intent-parser.test.js`（覆盖 tutor/L2/mod-01/L2-mod-01-cmp-intent-parser/testcases.json 中的场景）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-01/L2-mod-01-cmp-intent-parser/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-01/architecture/`（04-contracts-and-runtime.md 的 IC-M01-01、05-local-decisions.md 的 LCD-001）
- 验收：根 PRD AC-REQ-001-01（boundaries：缺任一项不创建可评分提交，返回具体缺失字段）
- 仓库：`plugin/src/ports/index.js`、`contracts/internal-contracts.json`

## 关键语义

- 缺项判定必须确定性（同一输入同一输出）；不得调用模型/网络。
- 不实现：配置（L04）、采集（L06/L07）、上传（L10）、队列（L11）、展示（L13）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
