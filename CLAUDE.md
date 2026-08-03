# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库性质

这是 **VeriLayer** 研究项目的"完整工作流"仓库：一套分层开发（layered development）流水线的技能与运行时代码集合，用于论文实验（C0-C5 配置对比、RQ1-RQ5）。根目录**不是 git 仓库**（仅 `prd-to-gherkin/` 自带 `.git`）。

**当前状态与工作区规则**：`task_plan.md`、`findings.md`、`progress.md` 是跨会话状态文件。计划阶段的“仅规划、不改业务代码”边界已被后续实施授权取代；当前实施以 `.coord-worktree/` 的 Git 提交、run report 和 hash 为准。根目录的旧 `vibe coding/` 仅作历史基线，不能与隔离工作区的实现或证据混用。恢复工作时只推进 `task_plan.md` 中标记 `in_progress` 的 phase。

## 流水线架构（big picture）

各子目录是流水线的独立阶段，通过 **canonical envelope**（共享身份字段 `schema_version/run_id/project_id/node_id/artifact_id` 等）在 Adapter 层衔接，模块内部 Schema 暂不统一：

```text
                     ┌→ prd-to-architecture-skill ─┐
prd-generation ──────┤                              ├→ mocktest → leaf-gate → vibe coding
                     └→ prd-to-gherkin ────────────┘
```

- **leaf-gate/**：判定节点 `CONTINUE_LAYERING` / `STOP_LAYERING` / `ERROR`。入口 `leaf-gate/scripts/run_leaf_gate.py`，要求 `prd.json + architecture.json + testcases.json + mocktest_report.json` 四件产物身份字段一致；证据不足必须返回 `ERROR`，绝不允许默认 `STOP_LAYERING`。
- **vibe coding/vibecode/**：根编排器（`root_workflow.py`），通过外部 command adapter 和 `module-result.json` 调用模块。Coding / Integration / Backfill 是外部模块插槽。CLI 入口 `python vibecode/scripts/vibecode.py`（`next-step` / `verify-stage` / `advance-state` / `audit-state` / `run-workflow`）。
- **mocktest/**：架构模拟验证框架（`src/mock_framework/`，另有 `.agents/skills/validate-arch/`）。strict 正式运行必须先做本机 preflight，并区分 execution completeness 与 architecture PASS/FAIL；不可仅凭 strict audit PASS 宣称架构通过。
- **prd-to-gherkin/**：canonical `prd/v3` → `testcases/v2` → deterministic `feature/v2`。`testcases.json` 是唯一派生权威，固定五件 bundle；不可映射即 `GENERATION_BLOCKED`，结构 `PASS` 不等于 Mocktest strict `PASS`。
- **prd-generation/**：PRD 上游契约编译器（Root/Derive 两模式）。唯一机器权威为 `prd.json`（共享 envelope `schema_version=1.0`，内容 `artifact_schema_version=prd/v3`），`prd.md` 是固定 12 节确定性视图；使用 `scripts/validate_prd.py --consumer canonical|architecture|gherkin|leaf` 验证。
- **prd-to-artecture-skill/**（团队 canonical 名称 `prd-to-architecture-skill`）：Architecture v2 compiler；唯一机器权威为 `architecture.json`，Top-Level 与 Decompose 共享同一 Schema、固定五件 bundle 和 12 节视图，通过 `architecture_mode` 与父边界指纹区分权限。入口 `scripts/run_architecture_flow.py top-level|decompose`。
- **参考文献/**：论文参考资料。

## 冻结约束（不可违反）

- 最大自动修复轮数 = 2；C0-C5 必须共享同一 Coding Executor、模型、预算和修复上限。
- 最低实验矩阵 24 次：C0-C5 × S1/M1/M2/L1 × seed 20260701。
- hidden tests 与生成上下文物理隔离；系统失败、工具错误、负面结果分别统计。
- 集成目标为单进程 Python/FastAPI/pytest/SQLite Modular Monolith。
- Tutor 只作 migration fixture、工程 oracle 和 case study：分别登记 22 个设计节点、16 套 L2 五件套、17 个实现叶和 12 个 backfill；不得把 Tutor 或其轻微改写任务放入正式 C0-C5 benchmark。
- Tutor 的 L2 STOP 受 terminal/product-owner policy 强制，不得作为 Leaf accuracy/κ ground truth。
- Day 3 使用双轨校准：CMP-CONFIG-STORE 是负向验证轨，复现 strict execution complete + architecture FAIL 并阻断下游；独立 fresh S1 是正向编码轨，验证 PASS→STOP→Coding→pytest→repair。
- Mocktest 的 FAIL 必须形成“报告 → 只修 Architecture → 重新验证”的闭环；ERROR 必须补齐证据、入口绑定或执行条件。两者均不得进入 Leaf/Coding，且不得通过改写冻结 Feature/Gherkin 规避。
- S1 正向校准首次 pytest 通过时 repair=0；repair 能力须用独立、可复现的初始失败 fixture 验证，不得人为破坏成功模型输出。
- Day 4 仍未完成；任何 root `CONTINUE → child STOP`、多叶集成、C0–C5 或论文实证结果主张必须有对应 run-scoped evidence。
- 分发 Tutor 前必须生成清洁副本，排除 `.env`、`data/`、`.git/`、`.worktrees/`、缓存和 `.superdesign/`，并保留 secret scan 与 SHA-256 manifest。

## 常用命令

```powershell
# Leaf Gate（判定单个节点）
python leaf-gate/scripts/run_leaf_gate.py <node-dir> --output <node-dir>/leaf_gate_decision.json

# Vibe Coding 编排（在 "vibe coding" 目录下）
python vibecode/scripts/vibecode.py next-step        # 读 state.json 后先跑这个
python vibecode/scripts/vibecode.py verify-stage     # 推进前必须跑
python vibecode/scripts/vibecode.py advance-state    # 只能用这个推进（run-workflow 除外）
python vibecode/scripts/vibecode.py run-workflow --help   # 新根级运行入口

# 测试
python -m pytest "vibe coding/tests"                 # 根编排器测试
python -m pytest "vibe coding/tests/test_root_workflow.py" -k <name>   # 单测
python -m pytest leaf-gate/tests
cd mocktest && python -m pytest                      # 有 pyproject pytest 配置（带 coverage）

# PRD→Gherkin 生成与产物校验（Node）
node prd-to-gherkin/scripts/run_gherkin_flow.mjs --prd <prd.json> --out <new-bundle-dir>
node prd-to-gherkin/scripts/validate_bundle.mjs --bundle <bundle-dir>
```

## 环境注意事项（Windows）

- `rg.exe` 在此环境被拒绝执行——搜索用 PowerShell `Get-ChildItem` + `Select-String`。
- 读取中文文件必须显式 UTF-8：`Get-Content -Encoding UTF8`，否则乱码。
- 工作流状态规则：先读 `vibecode/state.json`（存在 `execution-log.jsonl` 则先 `audit-state`）；人工门禁（matrix 批准、契约变更、高风险失败、最终发布）不可跳过；Leaf Owner 只能改 `allowed-context.md` 允许的文件；共享契约变更须停手并产出 `contract-change-request.md`。
