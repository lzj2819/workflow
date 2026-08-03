# Canonical Architecture Flow

这个目录把旧的“顶层七份 Markdown”与“递归七份 Markdown”收敛为一个 `architecture/v2` 合同。业务内容可以变化，公开文件名、JSON 字段、Markdown 章节、ID 规则和状态语义保持不变。

## 两种模式

| 项目 | Top-Level | Decompose |
|---|---|---|
| CLI | `top-level` | `decompose` |
| 输入 PRD | 根级 canonical PRD v3 | 当前所选节点的 canonical PRD v3 |
| 父架构 | 无 | 必需 |
| 当前节点 | PRD `node_id` | 精确 `target_node_id` |
| 直接子节点 | 仅 `MOD-*` module | `CMP-*` / `SUB-*` / `ADP-*`，不能重建 `MOD-*` |
| 权限 | 系统和第一层边界 | 一个父节点内部 |
| 父变更 | 不适用 | 输出显式 change request 并停止 |

两种模式不是两套 Architecture Schema。统一格式见 [contracts/architecture-contract-v1.md](contracts/architecture-contract-v1.md)，机器约束见 [schemas/canonical-architecture.schema.json](schemas/canonical-architecture.schema.json)。

## 快速验证

运行时只依赖 Python 3.10+ 与 `jsonschema>=4`：

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

真实下游兼容测试还会读取同级 `prd-generation`、`mocktest` 和 `leaf-gate`；Mocktest 测试解释器需安装其 `pyproject.toml` 中的依赖。

## 兼容边界

- PRD Derive 可直接读取 `architecture.json` 顶层 `modules` 投影。
- Mocktest 可读取 `architecture.md` 或 canonical JSON；Markdown 节点表同时保留 `child_id`、稳定 ID `Module` 和显示 `Name`。
- Leaf Gate 直接读取顶层 `components/interfaces/dependencies/depth/complexity/risks` 投影。
- Vibe Coding 的 `module-result.json` 是编排适配回执，不属于 Architecture 核心包。
- Gherkin 与 Architecture 是从 PRD 并行生成的分支，不应伪装为 Architecture 的直接消费者。

旧文件名暂留作兼容入口，但只允许指向本合同；旧的多 Markdown 输出清单不再具有规范权威。

