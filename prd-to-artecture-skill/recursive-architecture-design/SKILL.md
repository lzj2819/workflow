---
name: recursive-architecture-design
description: Compatibility entry for canonical decompose mode on one exact parent module or component.
---

# Decompose Architecture Compatibility Entry

此目录保留旧 Skill 名称，避免已有调用路径失效；它不再维护第二套输出规范。执行时必须完整遵循仓库根 `prd-to-artecture-skill/SKILL.md` 的 `decompose` 模式，以及统一合同、Schema 和 compiler。

硬边界：

- `target_node_id` 必须与父 `payload.nodes[].id` 唯一精确匹配；
- 当前 PRD `node_id` 必须等于 target，`depth` 必须等于父 depth + 1；
- 只设计该节点内部的 `CMP-*`、`SUB-*`、`ADP-*`；
- 父责任、排除项、公共契约、数据所有权、技术/部署和兄弟边界只读；
- 需要改变父级时输出 `FAIL/draft` + `parent-change-request.md` 并立即停止。

```powershell
python scripts/run_architecture_flow.py decompose `
  --prd <current-node-prd.json> `
  --parent-architecture <parent/architecture.json> `
  --target-node-id <exact-stable-id> `
  --design templates/decompose-design-input.json `
  --output-dir <child-architecture-dir>
```

正常 PASS 的文件名、JSON 字段和 12 个 Markdown 章节与 Top-Level 完全相同；模式差异只由 `architecture_mode=decompose`、authority scope 和 parent binding 表达。

