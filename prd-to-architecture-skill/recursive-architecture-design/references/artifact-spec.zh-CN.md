# 架构产物规范

这份文件说明“最后交什么”。只生成架构文档，不生成代码、测试、脚手架、部署清单、独立验证报告或实施工单。

常规包严格包含：

```text
architecture/
|-- architecture-manifest.yaml
|-- 01-design-context.md
|-- 02-architecture-decomposition.md
|-- 03-state-and-data.md
|-- 04-contracts-and-runtime.md
|-- 05-local-decisions.md
`-- child-handoff.md
```

需要改变父决策或边界时才创建 `parent-change-request.md`；除非用户明确要求非权威草案，否则此时不得继续生成完整权威分解。

| 产物 | 必需内容 |
|---|---|
| `architecture-manifest.yaml` | 当前节点名称、层级、`target_node_id`、职责/排除项、输入路径、`mode`、`parent_package_type`、父节点、`node_match_evidence`、`boundary_fingerprint`、产物索引和状态。 |
| `01-design-context.md` | 父边界快照、`inherited`/`allocated`/`local`/`out-of-scope` 需求分配、局部驱动、假设、问题和冲突。 |
| `02-architecture-decomposition.md` | 局部语义细化、带稳定 `child_id` 的子节点清单、依赖图、兄弟节点未被重设计的确认和分解理由。 |
| `03-state-and-data.md` | 状态所有者 `child_id`、读写方、生命周期、一致性、保留/隐私、存储意图、数据流和父/兄弟所有权未转移的确认。 |
| `04-contracts-and-runtime.md` | 父契约清单、父契约到子节点的实现映射、当前节点内部契约、成功/失败/生命周期运行流，以及兼容性与可靠性规则。 |
| `05-local-decisions.md` | 局部决策及其替代方案、继承决策、下一层委托、父层专属禁止项和决策队列结果。 |
| `child-handoff.md` | 当前节点边界指纹、可作为下一层 `target_node_id` 的精确 `child_id`、契约、状态、决策、风险和祖先上下文要求。 |
| `parent-change-request.md` | 触发需求、受影响父产物/ID、当前规则、建议变更、兼容性/运行影响、受阻子决策和父层修订路径。 |
