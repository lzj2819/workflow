# Council 决策记录：Mocktest v2

日期：2026-08-02  
Schema version：1

## Selected Panel

| 成员 | 权重 | 独立审计重点 |
|---|---:|---|
| Richard Feynman | 1.5 | 多 driver、phase/blocked 分歧、最小可解释机制 |
| Socrates | 1.0 | 精确表头/隐藏注释/词法猜测与可证伪门禁 |
| Ada Lovelace | 1.0 | 双模型、renderer、状态代数、serialization/hash |
| Donella Meadows | 主席 | 未参加三轮，独立系统综合 |

## Decision

以 3.5/3.5 加权票通过 schema-first 渐进迁移：

```text
v2 adapters → provenance/ambiguity IR → one runner → orthogonal states → fixed bundle
```

通过阈值 2.333。三名成员最终 confidence 均为 high，dealbreaker 均为 yes。

共同 dealbreaker：任何路径仍可把 `AMBIGUOUS|UNBOUND` 猜测成 strict PASS，或对同一证据
产生不同门禁结论。

## Chairman synthesis

最高杠杆点不是继续扩充 alias，也不是放宽 strict validator，而是拆开四个反馈环：输入适配、
语义绑定、执行/审计、发布。公共系统只允许一个 Canonical IR 和一个 Canonical Result。

## Acceptable compromises

- legacy parser/driver/renderer 可暂存，但只能是显式 adapter/shadow implementation；
- alias 必须版本化和可审计，多候选仍是 AMBIGUOUS；
- 兼容文件可以存在，但下游只读固定 v2 bundle；
- renderer 可分期迁移，但只能读取同一 result，不能自行重判。

## Minority report

Socrates 与 Ada 的条件性异议被主席采纳：没有兼容语料的字段/状态/产物等价证据时，不得本轮
一次性物理删除 driver、StepMapper、GapDetector 和 renderer。先 shadow comparison，差异分类
完成后再退役。项目专用 `patch_plan.py` 不具兼容价值，已删除。

## Kill criteria

- If provenance/candidate/binding status cannot cover every binding by 2026-08-02, invalidated → stop runner integration and redesign the IR.
- If AMBIGUOUS or UNBOUND can receive strict PASS by 2026-08-02, invalidated → roll back that adapter and restore fail-closed behavior.
- If identical canonical inputs/evidence produce different semantic hashes by 2026-08-09, invalidated → prohibit v2 publication and redefine hash boundaries.
- If blocked/error/zero-hop/partial cannot publish fixed empty artifacts by 2026-08-09, invalidated → do not mark the bundle stable.
- If legacy and v2 cannot show agreed corpus equivalence by 2026-08-16, invalidated → retain legacy as shadow and do not physically delete it.

## Concrete next step outcome

主席要求的唯一立即动作是创建 `mocktest-run/v2` 公共 JSON Schema。该工件现已落地于
`schemas/mocktest-run.schema.json`，并通过 Draft 2020-12 schema/instance 验证。

## Execution reliability

Council 决策可靠性：高。实现可靠性：已完成结构化/确定性回归，但真实 strict 业务执行仍必须
在具体 Architecture/Testcases 与真实 subagent 证据上独立运行，不能由本次单元测试代替。
