---
name: architecture-ddd-to-system-design
description: Compatibility entry for top-level canonical Architecture generation from an approved PRD v3.
---

# Top-Level Architecture Compatibility Entry

此目录保留旧 Skill 名称，避免已有调用路径失效；它不再维护独立输出规范。执行时必须完整遵循仓库根 `prd-to-artecture-skill/SKILL.md` 的 `top_level` 模式，以及 `contracts/architecture-contract-v1.md`、Schema 和 compiler。

本模式只拥有系统边界和第一层 `MOD-*` 模块。DDD 战略建模可作为形成设计草稿的分析方法，但旧的 DDD 工作文件、workbench 和七份 Markdown 不再是公开交付合同，也不得与 canonical bundle 并列成为第二权威。

```powershell
python scripts/run_architecture_flow.py top-level `
  --prd <root-prd.json> `
  --design templates/top-level-design-input.json `
  --output-dir <architecture-dir>
```

输出固定为 `architecture.json`、`architecture.md`、`architecture-manifest.yaml`、`validation_report.json`、`execution_log.json`。`architecture.json` 是唯一机器权威。

