# Leaf Gate v2 Council 决策记录

日期：2026-08-03  
议题：Leaf Gate 全面重构、统一输出、Mocktest 修复闭环准入

## 1. Panel 与权重

| 角色 | 视角 | 权重 |
|---|---|---:|
| Aristotle | 工作流语义、职责边界与可解释性 | 1.0 |
| Ada | 契约、状态机、确定性与可验证实现 | 1.5 |
| Feynman | 最小充分模型、反例与可证伪性 | 1.0 |
| Meadows | 独立主席，只做最终综合 | 不投票 |

三位成员均先通过任务复述门，再完成盲审；第二轮只收到匿名 A/B/C 意见并明确执行 anti-conformity；第三轮分别给出 confidence 与 dealbreaker。

## 2. 表决结果

三个有效席位、加权总票 3.5；通过阈值 2.333。三席均支持 `canonical-v2-with-conditional-semantic`，加权赞成 3.5/3.5，结论通过。综合置信度：High。

## 3. 主席综合

采用“Canonical v2 + conditional semantic”方案：

1. Leaf Gate 首先是 Mocktest admission gate，其次才是 layering decision gate。
2. 首次完整 PASS 不强制伪造 repair receipt；发生过非 PASS 时必须证明 failed finding → changed Architecture → affected testcase revalidation → current PASS。
3. 全量重跑可替代定向重验，但必须覆盖全部 affected testcase。
4. `next_action` 从 canonical report 确定性派生，不形成第二事实源。
5. 生产 annotation template 删除；人工语义判断仅在 policy 要求时以 schema-constrained artifact 输入。
6. 遗留解析器不得参与 canonical v2 判定；如未来保留，只能是只读、有版本、有退场日期的外部迁移工具。
7. `proposed_children` 只能来自 Architecture 显式 child nodes，禁止轮询分配 requirements/interfaces。

## 4. Kill criteria

| 截止 | Kill criterion |
|---|---|
| 2026-08-03 | 任一 admission failure 仍能产生 PASS/STOP/CONTINUE，则停止发布 |
| 2026-08-10 | 相同输入产生不同输出 hash，则回滚非确定性输出 |
| 2026-08-10 | 任一 child 缺少 Architecture 原生投影证据，则禁止 DECOMPOSE |
| 2026-08-10 | 历史失败无需新 Architecture hash 和失败测试覆盖即可关闭，则阻断准入 |
| 2026-08-17 | legacy 路径仍影响 canonical decision，则移除该路径 |
| 2026-08-17 | 旧 schema 仍被当作生产合同且未有迁移映射，则阻止下游接入 |

## 5. 尚存边界

Council 的分歧只在“何时需要语义判断”：最终采用 policy 驱动的 `DISABLED|OPTIONAL|REQUIRED`。无论何种模式，语义判断均不能覆盖 Mocktest、hash、lineage、coverage、depth 和显式 child plan 硬门禁。

