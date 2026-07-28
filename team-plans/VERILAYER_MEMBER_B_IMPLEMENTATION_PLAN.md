# VeriLayer 成员 B 实施与构建计划

## 1. 你的身份和最终责任

你是 **Architecture 与 Gherkin Generation Owner**。你负责：

- PRD→Architecture 真实执行器；
- Architecture 七文件包和结构化 `architecture.json`；
- PRD→Gherkin 真实执行器；
- requirement model、Feature 和 `testcases.json`；
- 两类生产 Adapter、Schema、validator 和集成测试；
- PRD、Architecture、Gherkin 的论文方法与工件统计。

你不负责 Mocktest、Leaf、Coding Executor 或根编排器核心。

## 2. 冻结事实

- 每个人的项目绝对路径可以不同；本文所有交付路径均为仓库相对路径。
- 本地通过 `$veriRoot`、`$workflowRoot`、`$veriPython` 和 `$architectureRoot` 定位文件。
- Python 可位于不同盘符，但版本和依赖必须与冻结环境一致。
- 已验证根编排器基线：27 tests passed。
- 技术输出限定为 Python/FastAPI/pytest/SQLite Modular Monolith。
- `architecture.json` 和 `testcases.json` 是机器 source of truth；Markdown/Feature 是人类可读产物。
- 共享 identity、status、hash、error 字段必须使用 A 发布的 Artifact Contract。
- Architecture 模块 canonical 名称已统一为 `prd-to-architecture-skill`；本地 checkout、配置与交接包不得继续使用旧拼写。
- Day 1 只冻结合同、示例和 validators；A 的合同通过后，Day 2 才编写生产 Adapter。
- Tutor 总范围是 22 个设计节点、16 套 L2 prepared 五件套、17 个实现叶和 12 个 backfill；B 重点审计其中 22 份 L0/L1/L2 Feature 与 16 套 Architecture/Testcases。它们是 migration regression，不是真实生成器证据。
- CMP-CONFIG-STORE 是已知 strict 负例；Day 3 不能预设它通过架构验证或继续 Coding。

## 3. 开工前必须阅读

1. 本文档
2. `VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md`
3. A 发布的 `vibe coding/docs/ARTIFACT_CONTRACT.md`
4. `prd-to-architecture-skill/architecture-skill/architecture-ddd-to-system-design/SKILL.md`
5. `prd-to-architecture-skill/recursive-architecture-design/SKILL.md`
6. `prd-to-architecture-skill/recursive-architecture-design/references/artifact-spec.md`
7. `prd-to-gherkin/skill3.md`
8. `prd-to-gherkin/scripts/validate_feature.mjs`
9. `prd-to-gherkin/scripts/validate_requirement_graph.mjs`
10. `vibe coding/AGENTS.md`

## 4. 第一个终端操作

```powershell
$veriRoot = (Resolve-Path '<YOUR_LOCAL_VERILAYER_PROJECT_ROOT>').Path
$veriPython = '<YOUR_LOCAL_PYTHON_EXE>'
$workflowRoot = Join-Path $veriRoot 'vibe coding'
$architectureRoot = '<YOUR_LOCAL_ARCHITECTURE_MODULE_ROOT>'
$gherkinRoot = Join-Path $veriRoot 'prd-to-gherkin'
if (-not (Test-Path -LiteralPath $workflowRoot)) { throw "Missing workflow root: $workflowRoot" }
if (-not (Test-Path -LiteralPath $architectureRoot)) { throw "Missing architecture root: $architectureRoot" }
if (-not (Test-Path -LiteralPath $gherkinRoot)) { throw "Missing Gherkin root: $gherkinRoot" }
if (-not (Test-Path -LiteralPath $veriPython)) { throw "Missing Python: $veriPython" }
Set-Location $workflowRoot
& $veriPython -m pytest --version
& $veriPython -m pytest -q tests\test_contracts.py tests\test_module_runner.py tests\test_root_workflow.py
```

然后：

```powershell
Set-Location $veriRoot
Get-ChildItem -LiteralPath (Join-Path $gherkinRoot 'scripts') -File
```

必须确认三个现有脚本：

- `validate_feature.mjs`
- `validate_requirement_graph.mjs`
- `feature_semantic_markers.mjs`

## 4.1 本地保存与团队合并

- 你的项目副本和 Architecture/Gherkin 模块可以位于任意本地目录，通过 `$veriRoot`、`$architectureRoot`、`$gherkinRoot` 映射。
- 交给 A/C/D 的路径必须转换为仓库相对路径或 artifact URI，不能写你的盘符。
- 推荐 Git 模式：使用独立 `verilayer/b-generation` 分支，只提交 B 所有权文件。
- 没有 Git 时，交付 `changed-paths.txt`、diff/patch、validator 结果和 SHA-256 manifest 给 A。
- 不要把完整 Architecture/Gherkin 目录复制覆盖 A 的 canonical copy。
- 模型原始输出和大体积 run evidence 使用 run ID 目录交付；代码变更与运行证据分开。

## 5. Day 1：输出合同与示例

开工前先复核 A 生成的清洁包：不得包含 `.env`、data、Git/worktree、缓存或本机设计草稿；核对文件清单和 SHA-256，不接触 `.env` 内容。

### 09:00–10:30

先对比 22 份 L0/L1/L2 Feature 和 16 套 L2 migration Architecture/Testcases，形成字段覆盖率和缺失字段清单；随后
从两个 Architecture Skill 中提取：

- 必需输入；
- 七文件最小输出；
- 递归 child 所需父上下文；
- requirement mapping；
- dependency/interface 表达；
- 风险和状态字段。

### 10:30–12:00

向 A 提交字段提案，不直接修改共享 Schema：

```text
vibe coding/docs/proposals/B_ARCHITECTURE_CONTRACT.md
vibe coding/docs/proposals/B_TESTCASES_CONTRACT.md
```

`architecture.json` 至少包含：

```text
components
interfaces
dependencies
data_and_state
risks
requirement_mappings
integration_points
```

`testcases.json` 至少包含：

```text
features
scenarios
testcase_id
requirement_ids
preconditions
expected_result
verification_status
source_feature_path
```

### 13:00–16:30

优先从 CMP-CONFIG-STORE 提取 migration 合同示例，不重新手写已有事实；同时为独立 S1 positive control 起草不依赖 Tutor 的输入合同：

```text
vibe coding/tests/fixtures/contracts/architecture.example.json
vibe coding/tests/fixtures/contracts/testcases.example.json
vibe coding/tests/fixtures/contracts/s1.feature
```

示例只用于合同验证，不能计为真实实验生成结果。

### 16:30–18:00

运行 validators：

```powershell
Set-Location $veriRoot
node (Join-Path $gherkinRoot 'scripts\validate_feature.mjs') '<S1 feature path>'
node (Join-Path $gherkinRoot 'scripts\validate_requirement_graph.mjs') '<S1 requirement model path>'
```

记录：

- command；
- exit code；
- stdout/stderr；
- 输入和输出 hash；
- validator 错误分类。

### 20:00–21:00

参加 A 主持的合同 Gate。确认 Architecture/Testcases 示例通过统一 envelope，且 C 和 D 可以消费。

## 6. Day 2：建立生产执行骨架

Gate 通过后创建：

```text
vibe coding/vibecode/adapters/architecture_adapter.py
vibe coding/vibecode/adapters/gherkin_adapter.py
vibe coding/vibecode/schemas/architecture-artifact.schema.json
vibe coding/vibecode/schemas/testcases-artifact.schema.json
vibe coding/tests/integration/test_architecture_adapter.py
vibe coding/tests/integration/test_gherkin_adapter.py
```

Adapter 必须：

- 接收 A 的 canonical envelope；
- 调用真实生成执行器；
- 保存 raw model output；
- 生成 JSON source of truth；
- 调用 validator；
- 写合法 module-result；
- 保留 input/output hash；
- 在失败时返回结构化 error，而不是创建空产物。

Day 2 先写失败测试，再实现最小骨架。不得复制 root fixture adapter 当生产实现。

## 7. Day 3：负向验证与正向编码双轨中的真实生成

建立两个完全隔离的生成 run：

1. `CMP-validation-negative`：使用 CMP-CONFIG-STORE PRD 重新生成/迁移 Architecture 与 Gherkin，目标是给 C 复现已知架构 FAIL/WARNING，不预设 PASS。
2. `S1-coding-positive`：使用独立 fresh S1 requirement 生成预期可 strict PASS 的 Architecture/Gherkin，为 D 的 Coding Executor 提供正向输入。

既有 Tutor 工件只作只读结构对照，不复制内容：

```text
PRD
├─ architecture/output/*.md
├─ architecture.json
├─ requirement-model.*
├─ *.feature
└─ testcases.json
```

验收：

```powershell
Set-Location $workflowRoot
& $veriPython -m pytest -q tests\integration\test_architecture_adapter.py tests\integration\test_gherkin_adapter.py
```

并运行两个 Node validator。

真实生成必须有：

- model/settings；
- raw response；
- 生成耗时和 token（不可得时为 null）；
- 输入/输出 hash；
- requirement trace；
- 非空结构化产物。
- 与 migration artifact 的结构差异报告；差异不是失败，需按 contract 和 strict 结论判定。
- 两个轨道的 run ID、workspace、raw response、hash 和最终工件完全分离。
- CMP 若 architecture FAIL，不得为了进入 Coding 而修改 Feature、隐藏缺陷或伪造 PASS。

## 8. Day 4–Day 10 路线

| Day | 你的构建任务 | 验收 |
|---|---|---|
| 4 | 为 fresh Root/Child PRD 双生成，支持父架构和 target module | child identity/trace 一致 |
| 5 | 为 fresh 双叶提供设计与测试包 | C 可 strict，D 可 coding |
| 6 | 输出可供 A 构建 DAG 的 dependencies/interfaces；冻结 Prompt/Schema | 多叶依赖无歧义 |
| 7 | S1/M1/M2/L1 pilot | 四种复杂度均有可验证工件 |
| 8 | 正式实验只修技术失败 | 不改变任务、Prompt、Schema |
| 9 | 生成方法描述和工件统计 | 数据来自 evidence |
| 10 | 抽查论文案例、artifact hash 和复现命令 | claim 与产物一致 |

## 8.1 你的同步顺序

可以同步：

- A 起草 envelope v0.1 时，你可阅读 Skill、裁剪七文件模板、研究 validator。
- Day 1 收到 envelope v0.1 后，你的 Architecture 与 Gherkin 合同提案可以同步进行。
- 对同一个 PRD，Architecture 生成和 Gherkin 生成必须并行启动并分别保存调用证据。
- Day 2 你写 Adapter 时，A/C/D 可以在各自所有权范围并行开发。
- 父合同冻结后，不同节点的 B 阶段可以并行，但每个节点使用独立 output/run ID。

必须等待：

1. 未收到 A 的 envelope v0.1，不提交绑定 identity/status 的最终 Schema。
2. 未通过 Day 1 Gate，不提交生产 Adapter。
3. 未收到 A 的 Root/Child PRD，不运行该节点真实 Architecture/Gherkin。
4. 你的两类结构化产物和 validators 未通过，C 不得启动 Mocktest。
5. Day 6 Prompt/Schema 冻结后，不得为正式实验临时修改生成逻辑。

## 9. 你的文件边界

你拥有：

```text
prd-to-architecture-skill/
prd-to-gherkin/
vibe coding/vibecode/adapters/architecture_adapter.py
vibe coding/vibecode/adapters/gherkin_adapter.py
vibe coding/vibecode/schemas/architecture-artifact.schema.json
vibe coding/vibecode/schemas/testcases-artifact.schema.json
对应测试与 B 提案文档
```

你不能直接修改：

```text
vibe coding/vibecode/root_workflow.py
vibe coding/vibecode/backfill.py
mocktest strict 核心
leaf-gate 决策核心
Coding Executor/Prompt
experiment aggregate 逻辑
hidden tests
```

需要共享合同变更时，提交给 A：

```markdown
Requested field/change:
Reason:
Affected artifacts:
Backward compatibility:
Required reruns:
Proposed adapter fallback:
```

## 10. 交给 C 和 D 的完成包

交给 C：

```text
architecture.json
architecture Markdown package
testcases.json
Feature files
requirement mapping
validator command/results
input/output hashes
module-result
```

交给 D：

```text
leaf PRD reference
architecture.json
public Feature/testcases
interfaces/dependencies
allowed implementation constraints
known risks
all hashes
```

## 11. 停止条件

立即停止并通知 A：

- A 的 Artifact Contract 尚未发布；
- Architecture 物理路径仍不确定；
- Gherkin validator 失败；
- requirement 无法映射到 testcase；
- 为通过 Mocktest 必须隐藏 Architecture 缺陷；
- 生成器需要读取 hidden tests；
- 需要修改根编排器或 Coding Prompt；
- 真实模型失败却准备使用手工 fixture 替代实验结果。
- 准备把 Tutor 或其轻微改写任务作为正式 C0–C5 benchmark。
- 准备让 CMP architecture FAIL 绕过 C 的 Gate 进入 Coding。

## 12. 可直接交给 Codex 的启动指令

```text
你是 VeriLayer 成员 B，Architecture 与 Gherkin Generation Owner。
完整阅读本文件、总计划、A 的 Artifact Contract、两个 Architecture Skill、
prd-to-gherkin/skill3.md 和 vibe coding/AGENTS.md。
先设置本地 $veriRoot、$workflowRoot、$veriPython 和 $architectureRoot，
再用 $veriPython 验证 27 个基线测试。
开工前复核 A 的清洁包、排除清单和 SHA-256。
只执行当前 Day 任务；Day 1 审计 22 份 Feature 和 16 套 L2 migration
Architecture/Testcases，提交迁移合同提案、CMP-CONFIG-STORE 负例示例、
独立 S1 positive 输入合同和 validator 结果，
等 A 的合同 Gate 通过后才创建生产 Adapter。
共享 identity/status/hash/error 只能使用 A 的合同。
不要修改 root_workflow、Mocktest、Leaf、Coding Executor 或 hidden tests。
每次交付附 command、exit code、stdout/stderr、hash、module-result 和已知限制。
```

## 13. 今日完成定义

- Architecture/Testcases 字段提案完成；
- Tutor migration 字段覆盖与缺失清单完成；
- 七文件最小输出明确；
- `architecture.json` 和 `testcases.json` 示例合法；
- Feature 与 requirement graph validators 通过；
- requirement trace 完整；
- A/C/D 能无歧义消费；
- 明确 migration fixture 只作回归，未伪装为真实生成；
- CMP 已标记为 strict 负例，独立 S1 positive 合同已准备。
