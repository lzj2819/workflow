# Council 审议报告：Canonical Architecture 双模式重构

## 1. 议题复述

审议目标是彻底检查原 Architecture 流程，消除不合理和重复设计，并在不混淆权限的前提下，让 Top-Level 与 Module/Component Decompose 每次都输出结构相同、仅内容不同的 Architecture。

## 2. 不可违反的约束

父级批准语义不可由子级静默修改；稳定 ID 必须贯穿 Top→Decompose；机器权威只能有一个；阻塞状态不得伪装为 PASS；Gherkin 并非 Architecture 的直接消费者。

## 3. Council 配置

采用 Full 模式，三名成员进行三轮审议：Aristotle（1.5 权重）、Ada（1.0）、Feynman（1.0）；Meadows 作为独立主席，不参加成员投票。

## 4. 复述门

三席最终均正确复述“双模式、同一格式、父边界不可变和真实下游兼容”问题。Aristotle 在两次有界重试后通过；没有离线席位或模拟意见。

## 5. 第一轮独立分析

三席分别完整读取重构前 21 个项目文件。共同发现：设计原则本身大体合理，但输出分裂、规则重复、无机器权威、无执行器/Schema/测试，以及 Top-Level 缺失稳定 ID 使递归入口断链。

## 6. 第二轮匿名交叉审查

成员以 A/B/C 匿名审查，且每席至少回应两名同伴。分歧集中在“是否维护两套 profile schema”；交叉审查后都否决双 schema，转向单一 core model + 模式约束。

## 7. 第三轮立场

三席最终立场均为 `dual-profile-contract-core`，置信度 high：一个 canonical contract，Top-Level 与 Decompose 作为两个权限 profile。

## 8. 表决

加权赞成 3.5/3.5，超过 2.333 的通过阈值。Aristotle 与 Feynman 标记了必须在落地前解决的 dealbreaker；Ada 无 dealbreaker。

## 9. 主席裁决

通过“共享 canonical core + 两个显式 mode”的方案。JSON 是机器权威，Markdown/manifest 是投影；writer 必须原子发布并绑定 hash。

## 10. 保留内容

保留父包绑定合同、单节点细分、父变更返父停止、局部/系统决策分层、完整接口合同字段和人类批准门。

## 11. 删除或合并内容

删除两套多 Markdown artifact spec、重复中英文 reference、重复 workbench/final/handoff 权威，以及依赖显示名和 prose 的隐式绑定。

## 12. 优先 dealbreakers

先定义 `authority_scope`、状态转换和字段级 parent mutation policy；再实现 stable ID、immutable snapshot/fingerprint、Schema、semantic validator 和 atomic writer。缺少其中任一项不能称为完成双模式统一。

## 13. 最小真实链路

至少验证 Top-Level→Decompose→Mocktest/Leaf。PRD Derive 作为反向递归入口要能读 nodes；Gherkin 明确为并行分支；Vibe 只通过 adapter receipt 间接消费。

## 14. 少数意见与风险

没有反对最终方向的少数意见。保留风险是：producer profile PASS 可能被误报为完整下游 E2E，因此所有报告必须区分结构兼容、真实 parser/Gate 运行和业务 strict PASS。

## 15. 执行元数据

- 模式：Full
- Panel：3；Rounds：3；Chairman：independent
- Live seats：3；Fallbacks：none；Provider count：1
- 使用工具：`followup_task`、`wait_agent`、`list_agents`
- 重试：Aristotle restatement 2；其余 0
- Token/duration：Council 工具未提供可审计总量，记为 unknown

