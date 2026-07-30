# VeriLayer 成员 A 实施与构建计划

## 1. 你的身份和最终责任

你是 **Integration Owner + Contract Owner**。你负责：

- canonical Artifact Contract；
- 原始 Tutor 归档到清洁团队包的安全转换、manifest 和状态对账；
- 根编排器和 production config；
- PRD Root/Derive Adapter；
- `node_id`、父子关系、状态和错误语义；
- dependency graph、integration order、父子接口回填；
- 多叶代码集成和最终端到端验收总控；
- Workflow、Artifact Contract、Integration 论文内容。

你是共享合同和父层 wiring 的唯一 owner。B、C、D 通过提案和交接包与你协作，不直接修改你的核心文件。

## 2. 冻结事实

- 每个人的项目绝对路径可以不同；共享合同、配置和交接包只记录仓库相对路径。
- 每个人必须在本地设置 `$veriRoot`、`$workflowRoot` 和 `$veriPython`；需要复跑 Tutor 时另设 `$tutorPython`。
- 同一运行角色的 Python、pytest 和依赖版本必须一致；VeriLayer 与 Tutor reference 环境分别冻结，不要求强行共用解释器。
- 不得把任何成员的盘符或用户目录写入共享 Schema、production config 或论文 evidence。
- 已验证基线：27 个根编排器测试通过。
- 新根流程使用 `run-workflow`，不得推进 legacy 示例 `state.json`。
- Architecture 模块 canonical 名称已统一为 `prd-to-architecture-skill`；你必须在 Day 1 确认四位成员的本地 checkout 和 production config 均只使用该名称。
- 技术范围固定：Python、FastAPI、pytest、SQLite、Modular Monolith。
- 自动修复最多 2 轮。
- C0–C5 必须共享同一 Coding Executor、模型、参数、Prompt 和预算。
- 既有 Tutor 范围必须分开登记：22 个设计节点包、16 套 L2 prepared 五件套、17 个实现叶子和 12 个 backfill 完成包；只作为 migration fixture、oracle 和 case study。
- tutor-r01 是手动协调 run，不证明 production `run-workflow`；不得登记为当前 E2E 或正式实验结果。
- Mocktest `FAIL/FIX_ARCH` 或 `ERROR` 时，阻断递归、Leaf 与 Coding；保存失败运行和输入 hash，待 B 或 C 修复后以新版本重跑，绝不回填为已完成。

## 3. 开工前必须阅读

以下均相对于你自己的 `$veriRoot`：

1. `VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md`
2. `VERILAYER_FOUR_PERSON_START_GUIDE.md`
3. `vibe coding/AGENTS.md`
4. `vibe coding/.agents/skills/layered-vibecode/SKILL.md`
5. `vibe coding\vibecode\contracts.py`
6. `vibe coding\vibecode\root_workflow.py`
7. `vibe coding\vibecode\module_runner.py`
8. `vibe coding\vibecode\orchestrator.py`
9. `vibe coding\vibecode\backfill.py`

## 4. 第一个终端操作

先把两个占位符替换为你自己机器上的真实位置。该设置只保留在本地，不提交到共享仓库：

```powershell
$veriRoot = (Resolve-Path '<YOUR_LOCAL_VERILAYER_PROJECT_ROOT>').Path
$veriPython = '<YOUR_LOCAL_PYTHON_EXE>'
$tutorPython = '<YOUR_LOCAL_TUTOR_REFERENCE_PYTHON_EXE_OR_SAME_AS_VERI>'
$workflowRoot = Join-Path $veriRoot 'vibe coding'
if (-not (Test-Path -LiteralPath $workflowRoot)) { throw "Missing workflow root: $workflowRoot" }
if (-not (Test-Path -LiteralPath $veriPython)) { throw "Missing Python: $veriPython" }
if (-not (Test-Path -LiteralPath $tutorPython)) { throw "Missing tutor Python: $tutorPython" }
Set-Location $workflowRoot
& $veriPython -m pytest --version
& $veriPython -m pytest -q tests\test_contracts.py tests\test_module_runner.py tests\test_root_workflow.py
& $veriPython vibecode\scripts\vibecode.py next-step
& $veriPython vibecode\scripts\vibecode.py run-workflow --help
```

预期：`pytest 8.2.0`、`27 passed`。如果不同，停止编码并记录环境差异。

不要执行：

```text
advance-state
generate-matrix
approve
```

当前没有真实 `STOP_LAYERING` 节点，不能推进 legacy 状态制造进度。

## 4.1 本地保存与团队合并

- 四个人可以把完整项目副本保存在不同盘符和目录。
- 仓库内部相对布局必须保持一致；共享合同只引用 `vibe coding/...` 等相对路径。
- 你维护唯一 canonical integration copy。
- 推荐 Git 模式：你使用 `verilayer/a-contract-integration`，B/C/D 使用各自分支，你只合并通过验收的 owner 文件。
- 如果当前没有 Git：每人提交 `changed-paths.txt`、统一 diff/patch、测试结果和 SHA-256 manifest；你应用到 canonical copy。
- 禁止用整目录覆盖另一位成员的工作副本。
- 如果某人的模块存放在项目根之外，由其本地 `$...Root` 映射解决；共享 production config 只保存逻辑模块名、相对 `cwd` 或可注入占位符。
- 可以提供 `config/verilayer.local.paths.example.json`，但带个人绝对路径的 `config/verilayer.local.paths.json` 不得进入共享交付。

## 5. 开工前清洁包与 Day 1 合同冻结

### 开工前 2～3 小时

- 从原始 Tutor 归档生成新的清洁副本，不覆盖原始包。
- 排除 `.env`、`data/`、`.git/`、`.worktrees/`、`.pytest_cache/`、`.ruff_cache/`、`__pycache__/`、`.superdesign/`。
- 执行 secret scan、绝对路径扫描，生成 `PACKAGE_CONTENTS.txt`、`PACKAGE_MANIFEST.sha256` 和 `RECIPIENT_REQUIREMENTS.md`。
- B/C/D 复核后才能把清洁副本发给团队；不要读取或复制 `.env` 内容。

### 09:00–09:30

- 收集四人的 VeriLayer 环境；需要 Tutor 回归者另登记 reference 环境、依赖版本和 hash。
- 冻结 Architecture 真实目录名。
- 发布文件所有权。
- 创建 `docs/contract-change-log.md`。
- 创建 `docs/TUTOR_MIGRATION_MANIFEST.md`，分别记录 22 个设计节点、16 套 L2 五件套、17 个实现叶和 12 个 backfill。
- 创建 `docs/TUTOR_CURRENT_STATE.md`，按 Git commit、execution-log 和后续报告对账，登记 `evidence_time`、`superseded_by`、`claim_scope`。
- 创建 `docs/PATH_REWRITE_MANIFEST.md`，旧绝对路径只作 provenance；无法重定位的引用 fail-closed。

### 09:30–12:00

创建：

```text
vibe coding/docs/ARTIFACT_CONTRACT.md
vibe coding/docs/FILE_OWNERSHIP.md
vibe coding/vibecode/schemas/verilayer-artifact.schema.json
```

统一字段：

```text
schema_version
run_id
project_id
node_id
parent_node_id
artifact_id
artifact_type
status
created_at
generator
model
input_artifacts
requirement_ids
content_path
content_sha256
error.category
error.code
error.message
```

约束：

- 跨模块正式 child key 只用 `node_id`。
- `child_node_id` 只允许 Adapter 兼容读取。
- 工具错误、系统错误、业务 FAIL 分开。
- error artifact 也必须通过 Schema。

### 13:00–16:00

- 合并 B 的 Architecture/Testcases 字段。
- 合并 C 的 Mocktest/Leaf 状态与证据字段。
- 合并 D 的 Code/TestResult/Evidence 字段。
- 起草 `config/verilayer.production.json`，所有 command 必须指向真实模块，不得使用 fixture。

### 16:00–18:00

从 CMP-CONFIG-STORE 提取并规范化七类 migration 示例；不重新手写或改变历史事实，并明确标注它是已知 strict 负例：

```text
vibe coding/tests/fixtures/contracts/prd.example.json
vibe coding/tests/fixtures/contracts/architecture.example.json
vibe coding/tests/fixtures/contracts/testcases.example.json
vibe coding/tests/fixtures/contracts/mocktest.example.json
vibe coding/tests/fixtures/contracts/leaf-decision.example.json
vibe coding/tests/fixtures/contracts/code.example.json
vibe coding/tests/fixtures/contracts/test-result.example.json
```

创建 `tests/test_artifact_contract.py`，覆盖：

- 七类示例均合法；
- identity 一致；
- hash 可重算；
- error 结果合法；
- child key 统一；
- 未知状态 fail-closed。

### 20:00–21:00

主持 Day 1 Gate。B/C/D 必须在 Gate 记录中确认字段无歧义。

### Day 1 验收命令

```powershell
Set-Location $workflowRoot
& $veriPython -m pytest -q tests\test_contracts.py tests\test_artifact_contract.py
```

## 6. Day 2–Day 10 实施路线

| Day | 你的构建任务 | 必须交付 | 验收重点 |
|---|---|---|---|
| 2 | common Adapter、production config、migration/path-rewrite loader、双环境 preflight、PRD Root/Derive 骨架 | common/prd Adapter、migration regression | production 无 fixture/旧绝对路径，两个环境可复现 |
| 3 | 建 CMP validation-negative 与 S1 coding-positive 两个隔离 run | 两个 run ID、独立 workspace、双轨 evidence | CMP FAIL 阻断下游；S1 完成 PASS→STOP→code |
| 4 | 从 fresh requirement 启动真实 recursive Derive | Root→CONTINUE→child PRD/parent refs | production run-workflow trace 完整 |
| 5 | 主持 fresh 双叶代码闭环 | 两个 completion packages | 两个 child STOP→code→pytest→repair |
| 6 | DAG、接口回填、多叶集成 | integration order、backfill report、root app | 至少两个叶模块同一 FastAPI app |
| 7 | 审核实验配置 | C0–C5 config diff report | 差异只在冻结阶段开关 |
| 8 | 正式实验运行监控 | run ledger、技术失败单 | 不修改冻结实现 |
| 9 | Workflow/Contract/Integration 论文初稿 | 方法段、系统图、trace table | 所有主张有 evidence |
| 10 | C0/C5 复现与最终审计 | reproduce report、final manifest | hash、命令、版本可重建 |

## 6.1 你的同步顺序

可以同步：

- 你冻结 envelope v0.1 时，B 可提取 Architecture/Gherkin 字段，C 可运行 strict preflight，D 可定义 Coding/Test 协议。
- Day 2 合同 Gate 通过后，你做 PRD/common Adapter，B、C、D 可分别做自己的测试和骨架。
- 不同叶节点在父合同冻结后可以流水线重叠执行。

必须串行等待：

1. 你先发布 envelope v0.1，B/C/D 才能提交绑定共享字段的 Schema/示例。
2. 你合并 v0.2 并通过 Day 1 Gate，四人才能提交生产 Adapter/Executor。
3. 每个真实节点严格执行：`A PRD → B Architecture/Gherkin（两者并行）→ C Mocktest → C Leaf → D Coding/Test`；任何 architecture FAIL 都不得进入 Leaf/Coding。
4. D 提交所有 child completion package 后，你才能做多叶集成。
5. 你完成 integration 后，D 才能运行 root hidden acceptance。
6. Day 6 freeze manifest 发布后，才能启动正式实验。

你负责每天确认上游 artifact 已到位，并在交接账本中释放下一阶段。

## 7. 你的文件边界

你可以修改：

```text
vibe coding/vibecode/contracts.py
vibe coding/vibecode/root_workflow.py
vibe coding/vibecode/orchestrator.py
vibe coding/vibecode/backfill.py
vibe coding/vibecode/adapters/common.py
vibe coding/vibecode/adapters/prd_adapter.py
vibe coding/vibecode/adapters/integration_adapter.py
vibe coding/vibecode/executors/integration_executor.py
vibe coding/config/
vibe coding/docs/ARTIFACT_CONTRACT.md
共享 Schema
```

不要直接修改：

- Architecture/Gherkin 生成器核心；
- Mocktest strict/Leaf 决策核心；
- Coding Prompt、pytest/repair 核心；
- hidden tests 内容。

## 8. 你必须向团队发布的交接包

```markdown
Owner: A
Contract version:
Schema paths:
Production path map:
Status/error enums:
Valid example paths:
Validation command and exit code:
Input/output hashes:
Breaking changes:
Required actions for B/C/D:
```

任何 contract change 都必须进入 `contract-change-log.md`。Day 6 冻结后，变更必须升级版本并明确需要重跑哪些实验。

## 9. 你的停止条件

立即停止并发起人工 Gate：

- Architecture 路径仍有两种拼写；
- B/C/D 的 identity 或 status 不能无损映射；
- hidden tests 进入生成上下文；
- contract diff 返回 `CONTRACT_CHANGE_REQUIRED`；
- 多叶合并需要修改 sibling 内部；
- C0–C5 的 Coding Executor 或预算不同；
- 有人要求把 dry-run/fixture 当完成证据。
- 原始 Tutor 包尚未清除 `.env`、Git/worktree、data 或缓存就准备分发。
- 有人要求把 Tutor 或其轻微改写任务放入正式 C0–C5 benchmark。

## 10. 可直接交给 Codex 的启动指令

```text
你是 VeriLayer 成员 A，Integration Owner 和 Contract Owner。
完整阅读本文件、VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md、
vibe coding/AGENTS.md 和本地 layered-vibecode SKILL.md。
开工前先从原始 Tutor 归档生成清洁共享副本，排除 .env、data、Git/worktree、
缓存和本机草稿，输出 secret scan、PACKAGE_MANIFEST.sha256 和 recipient requirements。
Day 1 设置本地 $veriRoot、$workflowRoot、$veriPython 和可选 $tutorPython，
分别验证冻结环境；确认 Architecture 物理路径；建立 22/16/17/12 migration manifest、
current-state/path-rewrite manifest；以 CMP migration fixture 创建 Artifact Contract、统一 Schema、
文件所有权、七类合同示例和 production config 草案。
只修改本文件列出的 A 所有权路径。不要推进 legacy state，不实现 B/C/D 的核心。
完成后运行合同测试，并提交命令、退出码、hash、测试摘要和 contract change 记录。
```

## 11. 今日完成定义

你今天完成工作的标准不是“写了多少代码”，而是：

- 同一运行角色环境一致，VeriLayer/Tutor reference 双环境分别可复现；
- 路径唯一；
- 清洁包和 SHA-256 manifest 已经 B/C/D 复核；
- Artifact Contract 可机器验证；
- tutor 历史 prepared/manual 事实被明确标注；
- 22/16/17/12 清单、状态对账和路径重写完整；
- CMP-CONFIG-STORE 七类 migration 示例贯通并标为 strict 负例；
- 文件所有权清晰；
- production config 没有 fixture；
- B/C/D 可以在 Day 2 无歧义地实现自己的 Adapter/Executor。
