# VeriLayer 成员 D 实施与构建计划

## 1. 你的身份和最终责任

你是 **Coding、Testing、Evidence 与 Experiment Owner**。你负责：

- 唯一真实 Coding Executor；
- 叶子隔离 workspace；
- pytest runner；
- 最多两轮自动修复；
- code/test/evidence 保存；
- hidden tests 隔离；
- root acceptance tests；
- C0–C5 experiment runner；
- metrics、统计和论文图表；
- Introduction、Methodology、Results、Discussion 的最终整合。

你不能直接修 B/C 模块来制造实验成功。

## 2. 冻结事实

- 每个人的项目绝对路径可以不同；共享代码和 evidence manifest 使用仓库相对路径。
- 本地通过 `$veriRoot`、`$workflowRoot`、`$veriPython` 定位环境。
- Python 可位于不同盘符，但版本、依赖和模型设置必须一致。
- 已验证根编排器基线：27 passed。
- 技术栈固定：Python、FastAPI、pytest、SQLite、Modular Monolith。
- 同一个 Coding Executor 用于 C0–C5。
- 同一模型、参数、Prompt、Token 上限和 repair 上限用于 C0–C5。
- 自动修复最多 2 轮，每轮必须保留输入、patch、hash 和测试结果。
- hidden tests 必须与模型输入和叶子 workspace 物理隔离。
- Token 不可得时写 `null`，不得估造。
- 最低正式实验：C0–C5 × S1/M1/M2/L1 × 1 seed = 24 runs。
- Coding Admission 只接受同一版本的 `Mocktest PASS + ALLOW` 与 Leaf `STOP_LAYERING` 证据；任何 `FAIL/FIX_ARCH`、`ERROR` 或缺失报告的 bundle 一律拒收并返回上游。
- Day 6 冻结代码、Prompt、Schema、任务和模型参数。
- `tutor/tutor-app` 已有真实代码、测试、叶任务/完成包和集成报告，可作为代码行为 oracle 与迁移案例；其编码过程是人工/多 worktree 协作，不能当作统一 Coding Executor 或 C0–C5 的既有实验结果。
- Tutor 总范围是 22 个设计节点、16 套 L2 prepared 五件套、17 个实现叶和 12 个 backfill；D 只消费 17 个叶完成包中的工程模式，不把它们计为自动 Coding run。
- Day 3 只编码独立 fresh S1 positive bundle；CMP-CONFIG-STORE 是 validation-negative，architecture FAIL 时绝不进入 Coding。
- Tutor 代码、公开测试、预期行为和 STOP 标签均已暴露，Tutor 或其轻微改写任务不能进入正式 C0–C5 benchmark。

## 3. 开工前必须阅读

1. 本文档
2. `VERILAYER_10_DAY_IMPLEMENTATION_PLAN.md`
3. A 的 `vibe coding/docs/ARTIFACT_CONTRACT.md`
4. `vibe coding/AGENTS.md`
5. `vibe coding/.agents/skills/layered-vibecode/SKILL.md`
6. `vibe coding/vibecode/execution.py`
7. `vibe coding/vibecode/module_runner.py`
8. `vibe coding/vibecode/schemas/coding-task.schema.json`
9. `vibe coding/vibecode/schemas/experiment-metrics.schema.json`
10. `vibe coding/tests/test_execution.py`

## 4. 第一个终端操作

```powershell
$veriRoot = (Resolve-Path '<YOUR_LOCAL_VERILAYER_PROJECT_ROOT>').Path
$veriPython = '<YOUR_LOCAL_PYTHON_EXE>'
$workflowRoot = Join-Path $veriRoot 'vibe coding'
if (-not (Test-Path -LiteralPath $workflowRoot)) { throw "Missing workflow root: $workflowRoot" }
if (-not (Test-Path -LiteralPath $veriPython)) { throw "Missing Python: $veriPython" }
Set-Location $workflowRoot
& $veriPython -m pytest --version
& $veriPython -m pytest -q tests\test_contracts.py tests\test_module_runner.py tests\test_root_workflow.py
& $veriPython -c "import sys,platform; print(sys.executable); print(sys.version); print(platform.platform())"
```

记录 Python、pytest、OS、工作目录和依赖版本。不得让不同配置使用不同环境。

## 4.1 本地保存与团队合并

- 你的项目副本、模型缓存和 evidence 盘符可以不同，通过 `$veriRoot`、`$workflowRoot` 和本地 run output 设置解决。
- 共享 manifest 保存仓库相对路径；机器绝对路径只允许出现在 environment manifest 的 machine-local 字段。
- 推荐 Git 模式：使用独立 `verilayer/d-coding-experiments` 分支，只提交 D 所有权代码和测试。
- 没有 Git 时，交付 `changed-paths.txt`、diff/patch、run manifest 和 SHA-256 manifest 给 A。
- generated workspace、model cache 和 hidden tests 不通过代码 patch 交付；只交付受控 evidence 和 completion package。
- 多机器并行实验必须使用唯一 run ID，不得写同一个 output 目录或共享可变 ledger 文件。

## 5. Day 1：Executor 和实验协议冻结

开工前复核 A 的清洁包：不得包含 `.env`、data、Git/worktree、缓存、模型缓存或本机草稿；不要读取 `.env`，只核对排除清单、secret scan 和 SHA-256。

### 09:00–10:00

创建：

```text
vibe coding/docs/proposals/D_ENVIRONMENT_MANIFEST.md
```

冻结：

- Python 路径/版本；
- FastAPI/pytest/SQLite 版本；
- timeout；
- 工作目录；
- 允许的环境变量名称；
- 模型 provider/model/parameters；
- S1/M1/M2/L1 总 Token 和 coding Token 上限。

同时把 `CMP-CONFIG-STORE` 的既有代码、公开测试、接口和完成包登记为只读 oracle，记录相对路径与 hash；不把旧代码放入模型输入。另为独立 S1 positive control 建立不引用 Tutor 路径、代码、测试或行为文本的 task contract。

不要保存真实 API secret。

### 10:00–12:00

创建：

```text
vibe coding/docs/CODING_EXECUTOR_PROTOCOL.md
```

输入：

```text
canonical envelope
leaf PRD
architecture.json
testcases.json/public Feature
allowed paths
technology profile
model settings
token budget
repair budget
```

输出：

```text
raw model response
generated file manifest
patch/diff
code hashes
module-result
pytest command/exit/stdout/stderr
repair attempts
token/time/call metrics
```

### 13:00–14:00

定义 workspace：

- 每个 leaf 独立目录；
- safe resolved path；
- 禁止 `..` 越界；
- 不可写 sibling/parent；
- hidden tests 不复制到 workspace；
- integration 只接收 completion package。

### 14:00–16:00

定义 pytest 和 repair：

- pytest timeout 120 秒；
- 保存 command、exit code、stdout、stderr、duration；
- JUnit/JSON 摘要；
- attempt 0 为初次生成；
- attempt 1–2 为自动修复；
- 达到上限后明确 FAIL；
- 人工修复不得记为自动成功。

### 16:00–17:00

起草 S1：

```text
vibe coding/benchmark/tasks/S1/requirement.json
vibe coding/benchmark/tasks/S1/public_tests/
vibe coding/benchmark/private_tests/S1/acceptance-contract.json
```

要求：

- requirement 有权重；
- public/hidden mapping 明确；
- hidden acceptance 内容不进入模型上下文；
- 静态 S1 示例只验证协议，不计实验。

### 17:00–18:00

创建：

```text
vibe coding/docs/EXPERIMENT_PROTOCOL.md
```

定义 C0–C5 公平性机器检查：

- Executor identity 相同；
- model/settings 相同；
- repair=2；
- task/seed/budget 相同；
- 差异仅为工作流阶段开关；
- C2 明确 `ABLATION_NOT_RUN`。
- 正式 benchmark task 与 Tutor 的路径、标识符、代码片段、测试文本和公开 STOP 标签无重合。

### 20:00–21:00

参加共同 Gate，向 A 提交 Code/TestResult/Evidence 字段。

## 6. Day 2：Executor 骨架

Gate 通过后创建：

```text
vibe coding/vibecode/executors/model_runner.py
vibe coding/vibecode/executors/coding_executor.py
vibe coding/vibecode/executors/workspace.py
vibe coding/vibecode/executors/pytest_runner.py
vibe coding/vibecode/executors/repair_loop.py
vibe coding/vibecode/adapters/coding_adapter.py
vibe coding/vibecode/evidence.py
```

对应测试：

```text
vibe coding/tests/test_leaf_workspace.py
vibe coding/tests/test_pytest_runner.py
vibe coding/tests/integration/test_coding_executor.py
vibe coding/tests/integration/test_repair_loop.py
```

实施顺序：

1. 先写 path safety 和 timeout 测试。
2. 再实现 workspace/pytest runner。
3. 再实现 model runner 和 coding executor。
4. 最后实现 repair loop 和 evidence。

不要先做 experiment runner；没有真实 Coding/Test 证据时，实验 runner 只能制造空壳数据。

## 7. Day 3：独立 S1 正向编码校准

只消费 B/C 对独立 fresh S1 生成并验证为 strict PASS + `STOP_LAYERING` 的 leaf bundle，调用统一 Executor，在全新 positive workspace 中执行。CMP validation-negative 的 architecture FAIL 必须有 block evidence，不得作为 Coding 输入：

```text
leaf bundle
→ isolated workspace
→ real model call
→ generated FastAPI files
→ import/startup check
→ pytest
→ evidence
```

验收：

```powershell
Set-Location $workflowRoot
& $veriPython -m pytest -q tests\test_leaf_workspace.py tests\test_pytest_runner.py tests\integration\test_coding_executor.py
```

生成 workspace 内还要运行：

```powershell
& $veriPython -m pytest -q
```

必须保留：

- 所有生成文件；
- raw response；
- file manifest；
- code hash；
- pytest raw logs；
- module-result；
- token/time/call count。

完成后只在模型运行结束且测试证据冻结后，才与 Tutor 既有工程模式作高层 oracle 比较；不得把 CMP 旧代码当作 S1 目标答案。S1 结果用于校准 Executor，不计入正式 C0–C5 实验。

## 8. Day 4：自动修复

实现最大两轮：

```text
attempt 0: initial generation + public tests
attempt 1: public failure evidence → repair → tests
attempt 2: public failure evidence → repair → tests
then: PASS or FAIL
```

每轮必须保存：

```text
prompt/input refs
raw response
patch
before/after hash
test command
test result
duration
token/call metrics
```

hidden acceptance failure不能进入 repair Prompt。

## 9. Day 5–Day 10 路线

| Day | 你的构建任务 | 验收 |
|---|---|---|
| 5 | 消费至少两个全新 STOP leaf，完成 code→pytest→repair | 真实新代码、非 tutor 复制或 fixture |
| 6 | 对全新多叶结果执行 root startup、hidden acceptance、集成验收；冻结实现 | 至少两个 fresh leaf，根测试通过/诚实失败 |
| 7 | C0–C5 configs、独立 S1/M1/M2/L1 pilot、contamination scan | 六配置公平；无 Tutor/hidden-test 泄漏 |
| 8 | 在独立 benchmark 上跑最低 24 runs | 每 run 有完整 evidence 和 metrics，Tutor 只进入 case study |
| 9 | 聚合 24/36 runs，生成统计、表格和图 | 一键从 raw data 生成 |
| 10 | C0/C5 复现、最终归档和论文二稿 | run manifest 可重建 |

## 9.1 你的同步顺序

可以同步：

- A/B/C 做 Day 1 合同和预检时，你可同步冻结 Executor/Test/Evidence 协议。
- Day 2 可与 A/B/C 并行实现 workspace、pytest 和 Executor 骨架。
- B/C 尚未产出真实 STOP leaf 时，你可用明确标记的合同 fixture 做单元测试，但不得计为 E2E/实验结果。
- Day 7–8 可以按配置或任务把实验分到多台机器并行运行，但所有机器必须使用相同 freeze manifest，并使用唯一 run ID/output 目录。
- 正式 runner 只能接收独立 benchmark 的 public task bundle；private tests 使用不同根目录、不同权限/进程阶段，文件内容不进入 Prompt、workspace 或 repair evidence。
- 你做结果聚合时，C 可并行做失败分类复核。

必须等待：

1. A 的 Artifact Contract Gate 通过后，才能提交生产 Coding Adapter。
2. 当前节点必须先经过 B 真实生成、C Mocktest PASS 和 C `STOP_LAYERING`，才能进入真实 coding。
3. 所有 sibling completion packages 到齐后交给 A；不得由你直接改父层 wiring。
4. A 完成多叶 integration 后，你才能运行 root hidden acceptance。
5. Day 6 freeze manifest 完成后才能开始正式 C0–C5 实验。
6. hidden tests 只能在最终 acceptance 阶段运行，结果不得回流 repair Prompt。

## 10. Evidence 目录

每个正式 run：

```text
evidence/runs/<run_id>/
├─ run_manifest.json
├─ inputs/
├─ artifacts/
├─ workspace/leaves/<node_id>/
├─ model_calls/
├─ tests/
├─ repairs/
├─ integration/
├─ root_acceptance/
├─ experiment_metrics.json
└─ execution_log.json
```

任何失败记录都不能删除。重复运行必须使用新 run ID，不能覆盖旧证据。

## 11. 你的文件边界

你拥有：

```text
vibe coding/vibecode/executors/
vibe coding/vibecode/adapters/coding_adapter.py
vibe coding/vibecode/evidence.py
vibe coding/benchmark/tasks/
vibe coding/benchmark/private_tests/
vibe coding/experiments/
vibe coding/evidence/
对应测试和 D 协议文档
```

你不能修改：

```text
vibe coding/vibecode/root_workflow.py
B 的 Architecture/Gherkin 生成核心
C 的 Mocktest/Leaf 核心
A 的共享合同（只能提变更请求）
hidden tests 以迎合生成结果
```

## 12. 交给 A 和 C 的完成包

交给 A：

```text
child completion package
generated file manifest
public test results
interface manifest
code/test hashes
integration prerequisites
```

交给 C：

```text
raw failure classification input
repair evidence
tool/system failure details
run manifest
hidden-test leak audit result
```

统一交接：

```markdown
Owner: D
Run/task/config/seed:
Executor/model/version:
Input refs and hashes:
Generated paths:
Test command/exit:
Repair attempts:
Output hashes:
Token/time/calls:
Hidden-test leak check:
Known limitations:
```

## 13. 停止条件

立即停止并上报：

- A 的合同未冻结；
- C 未给出真实 `STOP_LAYERING`；
- leaf workspace 可越界；
- hidden tests 可被模型读取；
- repair 超过 2 轮；
- C0–C5 的模型/Prompt/预算不同；
- pytest 日志或 raw model output 缺失；
- 准备手工改代码后记录为自动成功；
- 准备删除失败 run；
- 需要直接修改 B/C/A 核心。
- CMP architecture FAIL 却被要求继续 Coding。
- 正式任务来自 Tutor 或其轻微改写，或 contamination scan 发现旧代码/测试/标签重合。

## 14. 可直接交给 Codex 的启动指令

```text
你是 VeriLayer 成员 D，Coding、Testing、Evidence 与 Experiment Owner。
完整阅读本文件、总计划、A 的 Artifact Contract、vibe coding/AGENTS.md
和本地 layered-vibecode SKILL.md。
先设置本地 $veriRoot、$workflowRoot 和 $veriPython，
再用 $veriPython 跑 27 个基线测试并记录环境。
开工前复核 A 的清洁包、secret scan 和 SHA-256。Day 1 冻结唯一 Coding
Executor、workspace、pytest、repair=2、evidence、hidden-test 隔离、
独立 S1 positive task 和 C0-C5 公平/污染检查协议，并登记 Tutor
CMP-CONFIG-STORE 既有代码为只读 oracle；A 的 Gate 通过后才写生产 Executor。
先实现 workspace/pytest，再实现 model/coding，再实现 repair/evidence，
最后才实现 experiment runner。Day 3 只对 C 验证为 PASS/STOP 的独立 S1
在空白 workspace 编码；CMP FAIL 不进入 Coding。旧 Tutor 代码只能在结果冻结后
作高层对照，不能复制或进入模型上下文。
只修改 D 所有权文件，不修改 root_workflow、Architecture、Mocktest、Leaf 或共享合同。
保留每次调用、生成文件、patch、hash、测试、token、时间和失败记录。
```

## 15. 今日完成定义

- 统一环境 manifest 完成；
- Coding Executor I/O 冻结；
- workspace 和 hidden-test 隔离冻结；
- pytest/repair=2 证据格式冻结；
- S1 task/public/hidden contract 完成；
- C0–C5 公平性可机器检查；
- A 能合并 Code/TestResult 字段；
- tutor 既有代码已登记为只读 oracle，且与 fresh generation 输入隔离；
- 独立 S1 positive 合同与 Tutor 内容无重合；
- 正式 benchmark contamination check 和 private-test 物理隔离规则已冻结；
- 没有把静态样例算作真实实验。
