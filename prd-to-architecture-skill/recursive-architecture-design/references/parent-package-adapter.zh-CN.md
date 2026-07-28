# 父包适配器

不要把它当成程序或工具。“父包适配器”只是先看懂父架构包长什么样、再找到这次要设计的那个节点的一套阅读方法。在读取父架构细节前使用，它只提取细化该节点所需的约束。

## 识别与匹配

1. 包根存在 `architecture-manifest.yaml` 时，识别为递归子层包。
2. 否则存在 `output/01-system-overview.md` 时，识别为顶层 DDD 到系统架构包。
3. 否则仅在 `migrate` 模式下检查声明的旧包索引，并允许一个有证据的精确显示名称匹配。
4. 其余情况停止：父包不支持或不可读。

优先精确匹配 `target_node_id`。旧包回退必须记录来源文件、标题或表格行、匹配文本和缺少稳定 ID 的原因；零个或多个匹配均停止。

## 选择性提取与快照

只提取目标节点的身份、职责、排除项、需求追溯、状态/数据、作为 Provider 或 Consumer 的契约、相关父运行流、直接边界、继承决策/技术/部署约束及委托项。不要因流程提到兄弟节点就读取或重设计其内部。

在 `architecture-manifest.yaml` 记录并在 `01-design-context.md` 摘要：

```text
parent_package_type
parent_node_id
target_node_id
node_match_evidence
responsibility_and_exclusions
state_and_data_ownership
provided_and_consumed_contracts
direct_boundaries
relevant_flows
inherited_decisions_and_constraints
delegated_and_unresolved_items
boundary_fingerprint
```

`parent_prd` 可选；仅当父包中无法找到目标节点需求、FR、契约、运行流或决策追溯，且缺失会导致实质不同架构时才要求补充。
