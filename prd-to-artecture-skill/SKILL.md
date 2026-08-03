---
name: prd-to-architecture-skill
description: Compile an approved canonical PRD into one deterministic canonical Architecture bundle in either top_level or decompose mode.
---

# PRD to Canonical Architecture

本 Skill 只有一个公开输出合同，但有两个显式执行模式。`architecture.json` 是机器权威；`architecture.md`、manifest、校验报告和执行日志都是从同一模型确定性生成的投影。不得手写其中任一投影来替代 canonical model。

规范源按优先级排序：

1. `schemas/canonical-architecture.schema.json`：字段、类型和枚举；
2. `scripts/architecture_flow/canonical.py`：跨字段语义、不变量和确定性 renderer；
3. `contracts/architecture-contract-v1.md`：所有权、状态迁移、兼容边界；
4. 本文件：执行顺序和人工门禁。

## 模式选择

| 模式 | 何时使用 | 本层拥有 | 本层禁止 |
|---|---|---|---|
| `top_level` | 从根级 approved PRD 生成系统架构 | 系统边界、第一层 `MOD-*` 模块、跨模块契约、系统级数据/技术/部署决策 | 组件内部设计、实现代码、测试用例 |
| `decompose` | 细化父架构中一个精确选中的模块或组件 | 所选节点内部的 `CMP-*`/`SUB-*`/`ADP-*` 子节点、内部契约、局部状态实现和局部决策 | 修改父责任/排除项/公共契约/数据所有权/技术部署，设计兄弟节点 |

不要用两个模板体系表达两种模式。两者必须共享同一 envelope、payload 字段集合、12 个 Markdown 章节和五个固定 sidecar 文件，只用 `architecture_mode`、`authority_scope` 和 `parent_binding` 区分权限。

## 必需输入

两种模式都要求：

- approved/complete 且 `status=PASS` 的 canonical PRD v3 `prd.json`；
- 与相应模板同字段集合的结构化设计草稿；
- 新目录，或显式 `--operation revise` 的已有目录。

`decompose` 还要求：

- 父级 canonical `architecture.json`；
- 与父级 `payload.nodes[].id` 唯一精确匹配的 `target_node_id`；
- 当前 PRD 的 `node_id` 等于该 target，且 `depth = parent.depth + 1`。

## 执行顺序

1. 校验 PRD consumer profile；不接受旧格式、草稿或无 current requirement 的 PRD。
2. 选择模式并固定 authority scope。
3. `top_level` 只分配第一层模块；`decompose` 先复制父边界快照并计算 `boundary_fingerprint`，再设计所选节点内部。
4. 为每个 current requirement 写且只写一条 allocation；为每个节点、契约、状态和决策使用稳定 ID。
5. 将必须当前决定的项目标为 `decide_now` 并完成决定。存在 open question、未批准 review 或未完成决定时不得标为 ready。
6. `decompose` 若必须改变父边界，只能写 `change_requests`；流程输出 `FAIL/draft` 和 `parent-change-request.md` 后停止，不得把建议当成已批准事实。
7. 人工评审基于 semantic hash 批准草稿；随后运行 compiler。Schema、语义、父边界或 consumer profile 任一失败均不得发布 bundle。

## 命令

```powershell
python scripts/run_architecture_flow.py top-level `
  --prd <root-prd.json> `
  --design templates/top-level-design-input.json `
  --output-dir <architecture-dir>

python scripts/run_architecture_flow.py decompose `
  --prd <current-node-prd.json> `
  --parent-architecture <parent/architecture.json> `
  --target-node-id MOD-ORDER `
  --design templates/decompose-design-input.json `
  --output-dir <child-architecture-dir>

python scripts/validate_architecture.py <architecture.json> --consumer canonical
```

覆盖已有目录必须显式加入 `--operation revise`。迁移缺失稳定 ID 的旧包才允许 `--operation migrate`；迁移完成后仍必须使用精确 ID，不得长期依赖显示名猜测。

## 固定输出

正常 PASS 时目录严格包含：`architecture.json`、`architecture.md`、`architecture-manifest.yaml`、`validation_report.json`、`execution_log.json`。

`decompose` 的父变更阻塞包在以上五件之外仅允许增加 `parent-change-request.md`。两种模式的 `architecture.md` 始终按同一 12 节顺序渲染；空内容写显式空值，不删除章节或改名。

## 完成条件

- JSON Schema 与跨字段语义校验均为零错误；
- `content_sha256` 与 review semantic hash 一致；
- PASS 包已通过 `canonical`、`decompose`、`mocktest`、`leaf`、`vibe_adapter` producer-side profiles；
- Decompose 已用原父文件重验 immutable snapshot 与 fingerprint；
- manifest hash 与实际五件文件一致；
- 未把 producer-side profile PASS 宣称为完整 Mocktest strict、Leaf 决策或全链 E2E。

