# VeriLayer 论文分析与当前写作依据

> 同步日期：2026-07-30。本文区分论文设计、计划目标和已经由当前工作树运行证据确认的实施状态。

## 论文主题

VeriLayer 研究的是：复杂软件能否先被递归拆解为带有需求、架构和测试证据的节点，再用严格的架构模拟验证与 Leaf Gate 决定何时开始编码，从而减少 AI/多人协作中的“过早写代码、接口失配、无法回填”的问题。

核心不是单纯提高代码生成成功率，而是建立一个可审计的决策链：

`PRD → Architecture 与 Gherkin → Mocktest 报告 → Architecture 修复或 Leaf Gate → Coding/Test → 集成/回填`。

## 要解决的问题

1. 需求和架构不完整时直接编码，导致接口、依赖和验收标准在后期才暴露。
2. “该继续拆分还是停止拆分”依赖主观判断，缺少可复核证据。
3. 多层节点回填时缺乏身份、hash、父子关系和失败原因的可追踪记录。
4. 失败被混为一类，无法区分有效架构 FAIL、证据不足 ERROR 和代码/集成失败。

## 关键机制：Mocktest 反馈而非直通 Leaf

Mocktest 必须首先生成 `mocktest_report` 和处置建议。

- `PASS + ALLOW`：才将同版本工件送入 Leaf Gate。
- `FAIL/FIX_ARCH`：说明获得了有效但为负面的架构结论；B 只修改 Architecture，生成新 artifact/hash 后重新验证。
- `ERROR`：说明证据、身份绑定、入口解析、strict 完整性或工具环境不足，先恢复运行条件再重跑。

Feature/Gherkin 在此闭环中冻结。FAIL 和 ERROR 都不能进入 Leaf Gate 或 Coding；二者的差别是前者可作为架构负面结果统计，后者只记录为系统/证据问题，不可冒充业务失败。

## 实验设计

论文固定以 C0-C5 为对照配置、S1/M1/M2/L1 为任务层级；最低矩阵为 `6 × 4 × 1 seed = 24` 次，目标 36 次、理想 48 次。所有配置共用 Coding Executor、模型、Prompt、项目级 Token 上限与最多两轮修复，hidden tests 与模型上下文物理隔离。

应分别汇报：

- strict 执行是否完整；
- Architecture 的 PASS/FAIL/ERROR；
- Leaf 的 CONTINUE/STOP/ERROR；
- 编码公开/隐藏测试、修复轮数、成本与耗时；
- 集成、回填和端到端结果；
- 每个结果对应的 artifact/hash、环境与脱敏证据路径。

Day 6 前建立 `RQ × configuration × metric × evidence × figure` 登记表，避免论文图表无法追溯到运行证据。

## 当前已证实与尚未证实

- 已证实：Day 3 fresh S1 的公开编码测试 PASS，且 `repair=0`；这只能说明正向编码路径，不证明 repair 已被演示。
- 已证实：Day 4 出现过 root strict PASS/CONTINUE，及 health child strict PASS/STOP 的局部证据。
- 未证实：完整 `PASS → STOP → Coding → Integration` 闭环。Coding Admission 曾揭露 Architecture 缺少 parser 可见接口证据，后续运行仍出现 Mocktest FAIL/ERROR，最新 `20260730-k` 停在 Mocktest FAIL。因此 Day 4 当前为 NO-GO。

论文写作应如实把上述局部成功、有效负面结果和系统/证据问题分开呈现；不得把 Tutor 的人工协调案例或 prepared evidence 当作本研究 production workflow 的正式实验结果。
