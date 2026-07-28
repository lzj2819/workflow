# VeriLayer 成员 C 实施与构建计划

## 1. 你的身份和最终责任

你是 **Mocktest strict 与 Leaf-gate Owner**。你负责：

- Mocktest strict 可重复执行路径；
- Architecture/Testcases→Mocktest Adapter；
- Mocktest report→Leaf formal input 转换；
- Leaf Adapter、状态和 `node_id` 兼容；
- 缺陷注入 Ground Truth 和缺陷分类；
- Leaf 专家盲评协议；
- 系统失败、工具错误和业务结论的独立复核；
- Mocktest、Leaf、Defect Case Study 论文内容。

你不负责 Coding Prompt、实验指标聚合和根编排器核心。

## 2. 冻结事实

- 每个人的项目绝对路径可以不同；本文路径均以本地 `$veriRoot` 为基准。
- Python 可位于不同盘符；VeriLayer 与 strict backend 各自使用冻结环境，通过已登记的 `$veriPython`/driver 调用。
- Mocktest strict driver 已存在，但必须验证本机真实后端。
- strict execution completeness 与 PASS/FAIL 业务结论必须分别记录。
- 工具错误不得记为 Architecture FAIL。
- Leaf formal input 要求 PRD、Architecture、Testcases、Mocktest 四类结构化工件。
- 新正式输出使用 `CONTINUE_LAYERING`、`STOP_LAYERING`、`ERROR`。
- legacy `LEAF_READY`/`DONE_LAYERING` 只允许兼容读取并映射为 `STOP_LAYERING`。
- Leaf 当前 proposed child 使用 `child_node_id`；跨模块正式 Adapter 输出统一为 `node_id`。
- C2 不运行 Mocktest 时必须记录 `ABLATION_NOT_RUN`，不能伪造 PASS。
- `tutor/tutor-app` 已有 16 份 Mocktest/Leaf 产物可作为迁移样本，但其中 Mocktest 报告由 `structured-input-preparer` 生成，属于 prepared evidence，不能当作 strict component-hop/validator/audit 已执行的证明。
- Tutor 总范围是 22 个设计节点、16 套 L2 prepared 五件套、17 个实现叶和 12 个 backfill；C 不得把这些不同口径混成“16 个完整自动运行”。
- 既有 Leaf 决策可用于字段映射和回归基线；正式实验仍必须由 fresh Architecture/Testcases 重新经过 strict Mocktest 和 Leaf-gate。
- Tutor 的 16 个 L2 STOP 来自显式 terminal/owner policy，MOD-03 也有人为叶子决定；这些标签不能作为正式 Leaf accuracy/κ ground truth。
- CMP-CONFIG-STORE 的历史真实 strict 结果是 execution complete、strict audit PASS，但 architecture FAIL；Day 3 应复现并阻断，而不是预设为正向叶子。

## 3. 开工前必须阅读

1. 本文档
2. `VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md`
3. A 的 `vibe coding/docs/ARTIFACT_CONTRACT.md`
4. `mocktest/.agents/skills/validate-arch/SKILL.md`
5. `mocktest/.agents/skills/validate-arch/main_session_strict_driver.py`
6. `mocktest/.agents/skills/validate-arch/scripts/preflight.py`
7. `leaf-gate/SKILL.md`
8. `leaf-gate/schemas/leaf_gate_decision.schema.json`
9. `leaf-gate/references/structured_input_contract.json`
10. `leaf-gate/scripts/run_leaf_gate.py`

## 4. 第一个终端操作

```powershell
$veriRoot = (Resolve-Path '<YOUR_LOCAL_VERILAYER_PROJECT_ROOT>').Path
$veriPython = '<YOUR_LOCAL_PYTHON_EXE>'
$workflowRoot = Join-Path $veriRoot 'vibe coding'
$mocktestRoot = '<YOUR_LOCAL_MOCKTEST_MODULE_ROOT>'
$leafGateRoot = '<YOUR_LOCAL_LEAF_GATE_MODULE_ROOT>'
if (-not (Test-Path -LiteralPath $workflowRoot)) { throw "Missing workflow root: $workflowRoot" }
if (-not (Test-Path -LiteralPath $mocktestRoot)) { throw "Missing Mocktest root: $mocktestRoot" }
if (-not (Test-Path -LiteralPath $leafGateRoot)) { throw "Missing Leaf-gate root: $leafGateRoot" }
if (-not (Test-Path -LiteralPath $veriPython)) { throw "Missing Python: $veriPython" }
Set-Location $veriRoot
& $veriPython -m pytest --version
& $veriPython -m pytest -q 'vibe coding\tests\test_contracts.py' 'vibe coding\tests\test_module_runner.py' 'vibe coding\tests\test_root_workflow.py'
& $veriPython (Join-Path $mocktestRoot '.agents\skills\validate-arch\scripts\preflight.py') --root $mocktestRoot --scan-path $mocktestRoot
& $veriPython (Join-Path $mocktestRoot '.agents\skills\validate-arch\main_session_strict_driver.py') --help
& $veriPython (Join-Path $leafGateRoot 'scripts\run_leaf_gate.py') --help
```

保存全部输出。把结果分成：

1. strict backend 可直接运行；
2. 需要 canonical current-session driver 封装；
3. 环境/工具错误。

第 3 类不得进入 Architecture 缺陷计数。

## 4.1 本地保存与团队合并

- Mocktest 和 Leaf-gate 可以位于你机器上的不同绝对目录，由 `$mocktestRoot` 和 `$leafGateRoot` 映射。
- 对外 artifact 中只保存逻辑模块名、run ID、仓库相对路径和 hash，不保存你的盘符。
- 推荐 Git 模式：使用独立 `verilayer/c-validation` 分支，只提交 C 所有权文件。
- 没有 Git 时，交付 `changed-paths.txt`、diff/patch、strict 报告 manifest 和 SHA-256 manifest 给 A。
- `.work` 等 mutable strict 工作区不得直接给 A 覆盖；只交付正式 report/evidence 目录。
- 每个并行 strict run 使用独立 `run_id/output-dir/report-dir`，禁止共享同一 mutable 目录。

## 5. Day 1：映射和后端决策

开工前复核 A 的清洁包和 secret/path scan；清洁包不得包含 `.env`、data、Git/worktree、strict mutable `.work`、缓存或本机草稿。

### 09:00–10:00

- 完成 strict preflight。
- 确定 Day 2 使用现有 strict 命令还是 canonical driver 封装。
- 审计 `tutor/tutor-app` 的 16 份 Mocktest/Leaf 产物，逐份标记 `prepared`、`strict-complete` 或 `tool-error`，不得根据 `PASS` 字段反推 strict 已完成。
- 单独标注 `owner_forced_terminal=true`，禁止把 Tutor STOP 标签写入正式盲评 ground truth。
- 创建：

```text
vibe coding/docs/proposals/C_STRICT_BACKEND_DECISION.md
```

记录 resolved Python、driver、依赖、网络/模型要求、命令、退出码和已知 blocker。

### 10:00–12:00

比较：

- Mocktest 输入/输出 Schema；
- Leaf formal input；
- tutor 既有 prepared Mocktest/Leaf 样本；
- A 的 canonical envelope；
- 根编排器期望的 module-result。

创建：

```text
vibe coding/docs/proposals/C_MOCKTEST_LEAF_MAPPING.md
```

映射必须覆盖：

| 来源 | 目标 |
|---|---|
| run/project/node/parent | A 的统一 identity |
| scenario/validator/hop | Leaf 验证证据 |
| strict audit | execution completeness |
| business PASS/FAIL | Mocktest semantic result |
| tool error | error artifact |
| `child_node_id` | Adapter 输出 `node_id` |

### 13:00–15:30

创建：

```text
vibe coding/docs/proposals/C_DEFECT_TAXONOMY.md
```

冻结分类：

```text
entry
contract
data_schema
state
flow
auth
nfr
tool
```

定义每类的判定依据、严重度、受影响 requirement/scenario 和是否属于工具错误。

### 15:30–18:00

- 定义 C2：`is_ablation=true`、`full_run=false`、`status=ABLATION_NOT_RUN`。
- 制作 M2 单缺陷示例：

```text
vibe coding/benchmark/defect_injection/M2/example-001/
├─ before/
├─ after/
├─ ground-truth.json
└─ expected-finding.json
```

- 创建合同示例：

```text
vibe coding/tests/fixtures/contracts/mocktest.example.json
vibe coding/tests/fixtures/contracts/leaf-decision.example.json
```

### 20:00–21:00

参加共同 Gate，重点审查：

- 工具错误是否与业务结果分离；
- `node_id` 是否统一；
- C2 是否正确标记消融；
- D 是否只能看到公开失败证据。

## 6. Day 2：Adapter 骨架

创建：

```text
vibe coding/vibecode/adapters/mocktest_adapter.py
vibe coding/vibecode/adapters/leaf_adapter.py
vibe coding/tests/integration/test_mocktest_adapter.py
vibe coding/tests/integration/test_leaf_adapter.py
```

Mocktest Adapter 必须：

- 接受 B 的真实 Architecture/Testcases；
- 创建 strict input manifest；
- 调用稳定 strict driver；
- 保存 component hops、validator judgments、audit；
- 区分 execution completeness 和 semantic conclusion；
- 输出 canonical Mocktest artifact/module-result。

Leaf Adapter 必须：

- 生成 formal PRD/Architecture/Testcases/Mocktest 四件套；
- 校验 identity；
- 调用 `run_leaf_gate.py`；
- 双读旧 `child_node_id`；
- 对根编排器正式输出 `node_id`；
- 对不完整证据 fail-closed 为 `ERROR`。

## 7. Day 3：CMP 负向 strict 与 S1 正向 Leaf 双轨校准

使用两个隔离 run：

1. `CMP-validation-negative`：使用 B 从 CMP 原始 PRD 重新生成/迁移的 Architecture + Feature 执行完整 strict；预期执行证据完整，但 architecture 结论保持 FAIL/WARNING。必须生成 downstream-block evidence，禁止进入 Leaf/Coding。
2. `S1-coding-positive`：对独立 fresh S1 Architecture + Feature 执行 strict，只有 semantic PASS 才运行 Leaf-gate，并预期得到可供 D 编码的 STOP bundle。

旧 prepared Mocktest 只用于字段对照，不能作为本次 strict 输入证据，也不能覆盖旧 Tutor 工件：

```powershell
& $veriPython (Join-Path $mocktestRoot '.agents\skills\validate-arch\main_session_strict_driver.py') run-strict `
  --feature '<feature-path>' `
  --arch '<architecture-path>' `
  --output-dir '<work-output>' `
  --report-dir '<delivery-report>' `
  --artifact-retention full `
  --run-id '<run-id>' `
  --project-id '<project-id>' `
  --node-id '<node-id>'
```

具体 command 名以 driver 的实际支持为准，不猜测；先通过 help/preflight 冻结。

验收必须同时报告：

- 场景数；
- component hop 数；
- validator 数；
- strict audit；
- PASS/FAIL/WARNING 结论；
- 工具错误数；
- 四个正式报告文件；
- 输入/输出 hash。

两个校准 run 只用于发现 Adapter、Schema、strict backend、阻断逻辑和 Leaf 映射问题，不计入正式 C0–C5 实验。若新结果与旧 prepared 报告不一致，保留两者并记录差异原因，禁止修改结果以追求一致。strict audit PASS 只能证明流程证据完整，不能覆盖 architecture FAIL。

## 8. Day 4–Day 10 路线

| Day | 你的构建任务 | 验收 |
|---|---|---|
| 4 | 对全新 root run 执行 Mock report→Leaf formal input→decision | identity/status/node 无冲突，CONTINUE/STOP 可解释 |
| 5 | 对至少两个全新 child 执行 strict Mocktest 与 Leaf-gate | A 可回填，D 只接收证据完整的 STOP |
| 6 | 复核多叶集成前验证证据；冻结协议 | 未验证 leaf 不进入 coding |
| 7 | 独立缺陷注入、C2/C3 语义、fresh Leaf 双盲包、contamination review | ground truth 与 Tutor 强制标签及系统输出隔离 |
| 8 | 独立复核 24 runs 失败分类 | 不删除负面结果 |
| 9 | Mocktest/Leaf/defect 统计与案例 | 数据可回溯 |
| 10 | claim-evidence 独立审计 | 论文不夸大完成度 |

## 8.1 你的同步顺序

可以同步：

- A 起草合同、B 提取生成合同、D 定义 Coding 协议时，你可同步运行 strict preflight 和比较 Schema。
- Day 2 你可与 A/B/D 并行写自己的测试和 Adapter 骨架。
- 不同 node 的 strict/Leaf 工作可以并行，但必须使用独立 run/output/report 目录。
- Day 7–8 可与 D 并行做缺陷复核和失败分类，但不能修改 D 的 raw 结果。

必须等待：

1. 收到 A 的 canonical contract 后，才能冻结正式 Mock/Leaf 映射。
2. 收到 B 对当前节点验证通过的 Architecture、Feature、`testcases.json` 后，才能运行 Mocktest。
3. Mocktest 完整执行且业务 PASS 后，才能运行该节点 Leaf-gate。
4. Leaf 输出 `STOP_LAYERING` 后，D 才能对该节点编码；`CONTINUE_LAYERING` 必须回到 A 做 Derive。
5. D 的实验结果产生后，你才能独立复核失败分类和论文缺陷统计。

## 9. 你的文件边界

你拥有：

```text
vibe coding/vibecode/adapters/mocktest_adapter.py
vibe coding/vibecode/adapters/leaf_adapter.py
对应集成测试
vibe coding/docs/proposals/C_*
vibe coding/benchmark/defect_injection/
vibe coding/benchmark/leaf_review_protocol.md
mocktest/ 内与稳定 strict 封装直接相关的文件
leaf-gate/ 内 Adapter 必需的低风险兼容修改
```

你不能修改：

```text
vibe coding/vibecode/root_workflow.py
Coding Executor/Prompt
repair budget
experiment aggregate 规则
B 的生成 Prompt 来掩盖缺陷
hidden tests
```

Leaf 核心决策或递归协议的大改必须先提交给 A，不能自行扩展范围。

## 10. 交给 A 和 D 的完成包

交给 A：

```text
mocktest_report.json
leaf_gate_decision.json
proposed children with canonical node_id
decision evidence
strict completeness summary
semantic conclusion
input/output hashes
module-result
```

交给 D：

```text
verified STOP leaf reference
public failure evidence
defect category
repair-eligible evidence
明确排除的 hidden ground truth
```

## 11. 停止条件

立即停止并上报：

- strict backend 不能执行；
- validator judgments 不完整；
- audit PASS 被错误当成业务 PASS；
- identity 不一致；
- Mocktest 非 PASS 却准备进入 Leaf/coding；
- Leaf `ERROR` 被降级为 STOP；
- C2 被伪装成真实 Mocktest PASS；
- 需要把 hidden ground truth 交给 D；
- 需要修改根编排器或 Coding Prompt。
- 有人要求把 Tutor 强制 STOP 标签用于正式 Leaf accuracy/κ。
- 有人要求 CMP architecture FAIL 继续进入 Leaf/Coding。

## 12. 可直接交给 Codex 的启动指令

```text
你是 VeriLayer 成员 C，Mocktest strict 与 Leaf-gate Owner。
完整阅读本文件、总计划、A 的 Artifact Contract、
mocktest validate-arch SKILL.md 和 leaf-gate/SKILL.md。
先设置本地 $veriRoot、$veriPython、$mocktestRoot 和 $leafGateRoot，
再用 $veriPython 跑基线、strict preflight 和两个 CLI help。
开工前复核清洁包、排除清单和 SHA-256。Day 1 只完成 strict 后端决策、
Mock→Leaf 映射、defect taxonomy、C2 ABLATION_NOT_RUN、M2 单缺陷示例，
并审计 Tutor prepared 报告和 owner-forced STOP 标签；
A 的合同 Gate 通过后才写 Adapter。Day 3 用 CMP 做 validation-negative，
预期 execution complete 但 architecture FAIL 并阻断下游；用独立 S1 做
strict PASS + Leaf STOP 正向校准。旧 prepared PASS 只能作回归对照。
严格区分 execution completeness、业务 PASS/FAIL 和工具错误。
只修改 C 所有权文件，不修改 root_workflow、Coding Prompt、实验聚合或 hidden tests。
每次交付包含命令、退出码、场景/hop/validator/audit 数、hash 和已知限制。
```

## 13. 今日完成定义

- strict 后端有明确可执行方案；
- Mock→Leaf 字段映射无歧义；
- `node_id` 转换规则冻结；
- defect taxonomy 完整；
- C2 消融语义正确；
- M2 Ground Truth 示例可审计；
- tutor prepared、strict-complete 与 tool-error 三类证据已明确区分；
- Tutor owner-forced STOP 已从正式 ground truth 排除；
- CMP 负例和独立 S1 正例的预期 Gate 已冻结；
- 工具错误绝不污染论文的架构缺陷结论。
