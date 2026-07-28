# Scenario Composition Contract

## 目的

把多个已冻结原子 Test Condition 组合为跨需求业务旅程，同时保持证据、状态和 oracle 可追踪。

组合场景是补充覆盖，不替代原子 TC 或原子 Scenario。

## 组合资格

仅当全部满足时创建组合候选：

1. 每个组成 TC 均为 `AUTHORITATIVE` 且位于冻结 eligible 子集。
2. PRD FACT、有效推导或冻结依赖图支持 TC 之间的顺序或依赖。
3. 前一 TC 的后置状态满足后一 TC 的前置条件。
4. 各 TC 的角色、对象、数据作用域和时间语义兼容。
5. oracle 不冲突，失败分支不会假装继续成功路径。
6. 每个连接步骤都有 FACT 或 `VALID_DERIVATION`。

缺少任一连接证据时，将候选标为 `COMPOSITION_BLOCKED`，不得用常识补“胶水步骤”。

## 组合类型

- `SEQUENTIAL_WORKFLOW`：按来源顺序连接。
- `STATEFUL_JOURNEY`：以后置状态驱动下一 TC。
- `DECISION_PATH`：组合一个明确决策分支。
- `RECOVERY_PATH`：显式失败与恢复规则。
- `CROSS_INTERFACE_FLOW`：跨接口契约。
- `NFR_ATTACHED_FLOW`：在功能旅程上观察来源定义的 NFR。

## 组合对象

```yaml
composition_id: COMP-001
composition_type: SEQUENTIAL_WORKFLOW
component_tc_ids: [TC-001, TC-004, TC-007]
ordered_transitions:
  - from_tc: TC-001
    to_tc: TC-004
    bridge:
      statement: "来源支持的衔接状态"
      evidence: [FACT-010]
entry_state: "来源支持的起始状态"
exit_state: "来源支持的结束状态"
combined_oracles:
  - {tc_id: TC-001, observation: "原 TC oracle"}
coverage_paths: [PATH-001, PATH-004, PATH-007]
status: VALID_COMPOSITION
```

## 生成规则

1. 先生成并冻结原子 TC。
2. 从 Requirement Dependency Graph 和状态边寻找候选路径。
3. 验证每个 bridge 的证据和状态兼容性。
4. 对循环设置来源支持的最大展开；来源未定义时不展开循环次数。
5. 仅生成证据充分且语义不重复的有效组合路径。
6. 为组合场景分配独立 `@COMP-*`，并保留所有组成 `@TC-*` 或可机器读取的 composition trace。
7. 组合 Scenario 的每个断言仍指向原 TC oracle，不创建新的综合业务结果。

## 覆盖核算

- 原子 TC → Scenario 覆盖率只由原子 Scenario 计算。
- 组合 Scenario 不增加 FACT、IR、义务或 TC 覆盖分子。
- 单独报告：
  - `composable_path_count`
  - `valid_composition_count`
  - `blocked_composition_count`
  - `critical_journey_coverage`
- 同一路径的排列不重复计为独立语义覆盖。

## 禁止

- 通过 UI 常识或产品惯例连接两个需求；
- 把“用户可能会”当作工作流证据；
- 为顺畅叙事添加登录、导航、保存、重试或清理行为；
- 合并角色、数据作用域、时间窗口或 oracle 不兼容的 TC；
- 用组合场景掩盖缺失的原子测试；
- 让组合后的长场景成为唯一权威覆盖。

## 失败处置

- 缺少 bridge 证据：`INPUT_ONLY` 或 `COMPOSITION_BLOCKED`。
- 状态不兼容：记录 `STATE_MISMATCH`。
- 多种合理顺序：记录 `MULTIPLE_INTERPRETATIONS`。
- oracle 冲突：拆分路径，不得弱化断言。
