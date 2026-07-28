# validate-arch

`validate-arch` 是一个面向 Codex 的架构验证 Skill。它读取 Gherkin `.feature`
场景和当前层架构文档，通过逐组件模拟、独立验证、契约检查和严格产物审计，生成可执行的架构改进报告。

它回答的核心问题是：

> 当前架构是否能够完整、明确且可审计地支撑这些业务场景？

## 核心能力

- 解析 Gherkin Feature、Scenario、Scenario Outline、Examples 和需求标签。
- 读取单个 Markdown、架构目录或带 `architecture-manifest.yaml` 的架构包。
- 从架构中提取组件、数据流、接口契约、状态所有权、约束和 NFR。
- 为每个场景确定入口组件和入口契约；证据不足时由语义门禁阻止模拟。
- 严格执行“一跳一个组件 subagent”，保留完整组件调用链。
- 为每个场景派发一个独立 validator，验证：
  - 结构
  - 流程
  - 状态
  - 契约
  - 性能
  - 接口兼容性
- 对输入哈希、组件调用、契约绑定、trace 和 validator 结果执行 strict audit。
- 将重复问题聚合为面向架构设计者的 Architecture Change Card。
- 支持不同场景间并行、跨运行精确缓存和可选的严格等价复用。

## 验证原则

### 当前层验证

只验证 `--arch` 指定的架构层，不要求下一层设计已经完成。架构目录中的
handoff、README 等材料不会自动被当作当前层组件定义。

### 组件级隔离

一个组件 subagent 只扮演一个组件并完成一次 hop，不允许单个 subagent
自行模拟整条链路。同一场景内的 hop 严格串行，不同场景可以并行。

### Simulator 与 Validator 分离

组件 subagent 负责按照架构执行场景；validator subagent 只根据已经产生的证据
进行判断，不能补写或猜测缺失的执行过程。

### 语义门禁

如果无法唯一确定入口组件、入口契约或合法组件集合，流程会停止并输出
`semantic_errors.json`。这属于有效的架构验证结果，而不是需要绕过的程序错误。

### 不自动修改架构

默认把架构文档和 Feature 当作只读输入。最终报告提供修改建议和验收条件，
但不会自动改写架构文档。

### 严格审计

只有 `strict_audit.json` 的 `status` 为 `PASS`，才可以声称完成了 strict
组件级验证。validator 返回 `FAIL` 不等于 strict audit 失败：前者代表架构问题，
后者代表验证证据或流程本身不完整。

## 目录结构

完整可运行包至少包含：

```text
validate-arch-package/
├─ .agents/
│  └─ skills/
│     └─ validate-arch/
│        ├─ SKILL.md
│        ├─ agents/
│        │  └─ openai.yaml
│        ├─ scripts/
│        │  └─ preflight.py
│        ├─ run_subagent_skill.py
│        ├─ main_session_strict_driver.py
│        ├─ report_enhancements.py
│        ├─ aggregate_batch_results.py
│        ├─ prepare_batches.py
│        ├─ sim_driver.py
│        ├─ patch_plan.py
│        ├─ batch-subagent-instructions.md
│        ├─ multi-session-orchestrator-prompt.md
│        └─ subagent-prompts.md
├─ src/
│  └─ mock_framework/
├─ pyproject.toml
└─ README.md
```

`.agents/skills/validate-arch` 提供 Codex Skill 和严格编排脚本，
`src/mock_framework` 提供 Gherkin、架构解析、模型、契约检查和报告能力。

## 环境要求

- Python 3.10 或更高版本。
- Codex CLI，并已完成登录。
- 从包含 `.agents`、`src` 和 `pyproject.toml` 的仓库根目录启动 Codex。

## 安装

### pip

```powershell
python -m pip install -e .
```

### Poetry

```powershell
poetry install
```

主要 Python 依赖包括：

- `pydantic`
- `pyyaml`
- `gherkin-official`
- `jsonschema`
- `rich`

项目还保留 OpenAI、Anthropic 等 API 客户端依赖，但 Codex strict subagent
流程不要求配置独立的 LLM API Key。

## 安装验证

在仓库根目录运行：

```powershell
python .agents\skills\validate-arch\scripts\preflight.py --root .
```

正常结果类似：

```json
{
  "status": "ok",
  "root": "D:\\path\\to\\project",
  "driver": "D:\\path\\to\\project\\.agents\\skills\\validate-arch\\main_session_strict_driver.py",
  "python": "D:\\path\\to\\python.exe",
  "errors": []
}
```

如果 Python 不在常规位置，可以指定：

```powershell
$env:VALIDATE_ARCH_PYTHON = "D:\Python\python.exe"
```

## 准备输入

### Gherkin Feature

```gherkin
Feature: 用户认证架构验证

  @REQ-AUTH-001
  Scenario: 用户使用有效凭据登录
    Given 用户账户处于可登录状态
    When 客户端提交正确的用户名和密码
    Then 系统应创建有效会话
    And 返回访问令牌
```

Feature 应尽量包含：

- 可识别的需求标签；
- 具体 Given 前置状态；
- 明确的 When 动作；
- 可验证的 Then 结果；
- 必要时包含契约字段、状态变化或 NFR 阈值。

### 架构输入

`--arch` 支持三种形式。

单文件：

```text
architecture/authentication.md
```

架构目录：

```text
architecture/authentication/
├─ 01-overview.md
├─ 02-components.md
├─ 03-contracts.md
└─ 04-runtime.md
```

Manifest 架构包：

```text
architecture/authentication/
├─ architecture-manifest.yaml
├─ 01-overview.md
├─ 02-architecture-decomposition.md
├─ 03-data-and-state.md
└─ 04-contracts-and-runtime.md
```

为了获得稳定结果，架构文档应明确描述：

- 当前层内部组件及职责；
- 组件间调用或事件流；
- 接口/事件的 provider、consumer 和 `contract_id`；
- 请求与响应的必要字段；
- 状态实体及唯一 owner；
- 需求或 NFR 到组件的分配；
- 外部系统与当前层内部组件的边界。

## 在 Codex 中使用

从项目根目录启动新的 Codex 会话，然后输入：

```text
使用 $validate-arch 严格验证 features/authentication.feature
与 architecture/authentication 目录，输出到 reports/authentication-run
```

也可以使用自然语言：

```text
验证这个 Gherkin Feature 是否被当前层架构完整支持。要求逐组件严格模拟，
不要修改架构文档，将报告写入 reports/validate-auth。
```

Codex 会从 `.agents/skills/validate-arch` 发现并加载 Skill。

## Strict 执行流程

```text
Feature + Architecture
        │
        ▼
解析、场景展开、组件卡和契约提取
        │
        ▼
语义门禁：入口组件和入口契约是否明确
        │
        ├─ 不明确 ──► semantic_errors.json + blocked report
        │
        ▼
逐场景、逐组件 hop 模拟
        │
        ▼
确定性契约与产物检查
        │
        ▼
每场景一个独立 validator
        │
        ▼
strict artifact audit
        │
        ▼
validation-report.md
```

推荐使用 canonical driver。它支持不同场景之间并行，同时保持同一场景内部
逐 hop 串行。Codex Skill 会负责生成 prompt、派发 subagent、消费响应并最终审计。

## 一键串行运行

少量场景也可以直接运行：

```powershell
python .agents\skills\validate-arch\run_subagent_skill.py run-strict `
  --feature features\authentication.feature `
  --arch architecture\authentication `
  --output-dir reports\authentication-run `
  --slim-prompts `
  --compact-trace
```

`run-strict` 内部使用 `codex exec`，适合小规模串行验证。大型 Feature
应由 Codex 使用 `main_session_strict_driver.py` 并行派发不同场景。

正式实验统一使用 `--input-manifest`。架构真实源仍可直接是 Markdown 文件夹，
测试真实源仍可直接是单个 `.feature` 或 Feature 目录；准备阶段会生成
`inputs/architecture.normalized.json` 与 `inputs/testcases.normalized.json`。已经生成的
`architecture/v1`、`testcases/v1` JSON 也可作为清单分支输入，但其内部 `source.path`
必须回指真实 Markdown/Gherkin 源，严格引擎不会维护第二套解析或模拟逻辑。

```powershell
python .agents\skills\validate-arch\run_subagent_skill.py run-strict `
  --input-manifest examples\mocktest-input.example.json `
  --ground-truth tests\fixtures\mocktest_defects\ground_truth.json `
  --output-dir .work\validate-arch\runs\formal-example
```

正式清单强制校验 `run_id`、`project_id`、`node_id`、`source_prd_id`、
`schema_version` 以及架构/测试分支身份一致性。退出码固定为：`0=PASS`、
`2=有效架构 FAIL`、`3=输入/依赖/配置错误`、`4=执行或证据错误`、
`5=Schema/身份/下游契约错误`。无法从调用记录取得的 Token、成本等指标写为
`null`，不会推测或伪造。

常用参数：

| 参数 | 作用 |
|---|---|
| `--feature`, `-f` | Gherkin `.feature` 文件 |
| `--arch`, `-a` | 架构文件、目录或 manifest 包 |
| `--input-manifest` | 正式实验统一输入清单；不可与 `--feature/--arch` 混用 |
| `--ground-truth` | 可选的真实缺陷注入 Ground Truth JSON |
| `--output-dir`, `-o` | 本次运行的独立产物目录 |
| `--scenario-ids` | 只验证指定 `test_case_id` |
| `--start-scenario` | 从第 N 个原始 Scenario 开始 |
| `--scenario-range` | 验证指定 Scenario 范围，例如 `34-40` |
| `--entry-overrides` | 显式入口覆盖文件 |
| `--slim-prompts` | 动态生成单 hop prompt，减少重复内容 |
| `--compact-trace` | 为 validator 生成紧凑 trace |
| `--strict-equivalence` | 可选的同运行严格等价复用 |
| `--max-hops` | 每个场景允许的最大组件 hop 数 |
| `--diagnostics` | 额外输出流程诊断报告 |

`--entry-overrides` 应只用于已有明确架构依据但自动映射无法识别的情况，
不能用它掩盖架构中实际缺失的入口定义。

## 输出产物

一次完整 strict run 通常包含：

| 文件 | 内容 |
|---|---|
| `plan.json` | 展开后的场景、组件卡、入口、契约和执行计划 |
| `run_manifest.json` | 输入文件、有效架构产物和哈希信息 |
| `driver_state.json` | canonical driver 的可恢复执行状态 |
| `hops.json` | 每个场景的完整组件执行链 |
| `subagent_calls.jsonl` | 组件和 validator 的调用审计记录 |
| `compat.json` | 确定性接口兼容检查结果 |
| `plan_with_val.json` | 带 validator prompt 的计划 |
| `val_results.json` | 每个场景的多维验证结果 |
| `strict_audit.json` | 严格产物审计结果 |
| `validation-report.md` | 面向架构设计者的最终报告 |
| `semantic_errors.json` | 语义门禁失败时的阻断原因 |

严格引擎之外还会生成一个 run-scoped 正式交付目录，固定包含：

| 文件 | 稳定用途 |
|---|---|
| `mocktest_report.json` | `mocktest/v1` 主结果、身份、覆盖率、稳定缺陷 ID 与实验指标 |
| `mocktest_report.md` | 从同一结构化结果渲染的人类摘要 |
| `leaf_gate_evidence.json` | Leaf Gate 的最小 ALLOW/BLOCK/ERROR 输入 |
| `execution_log.json` | 模型、随机种子、调用/重试/缓存计数与输入、输出哈希 |

下游应读取这些 JSON，不应解析 Markdown。对应 JSON Schema 位于 `schemas/`。
已有 strict run 可不重新模拟，直接重新发布正式产物：

```powershell
$py .agents\skills\validate-arch\run_subagent_skill.py publish-artifacts `
  --run-dir <strict-run-dir> --output-dir <delivery-dir> `
  --project-id <project> --branch-id <branch>
```

正式状态固定为：全部验证通过才是 `PASS`；流程完整但架构存在缺陷是 `FAIL`；
输入身份、依赖、模型、工具或证据链异常是 `ERROR`。`FAIL` 是有效实验结果，
`ERROR` 不得计入架构缺陷率。

## 如何理解结果

### strict audit PASS

表示验证流程和证据完整，所有必要组件/validator 调用、文件哈希和契约绑定
均通过审计。它不代表架构中的所有场景都通过。

### validator FAIL

表示已有完整证据证明架构存在缺口。最终报告会把相关场景聚合为
Architecture Change Card，并给出目标文件、目标章节、所需修改和重跑验收条件。

### semantic gate blocked

表示架构没有提供足够证据启动可靠模拟，例如：

- 入口组件不明确；
- 多个组件得分相同；
- 入口契约不存在或无法绑定；
- Feature 涉及当前架构层之外的责任。

此时不应伪造组件调用链。应先根据 `semantic_errors.json` 和报告补充架构定义，
再重新运行。

### strict audit FAIL

表示验证过程本身不完整或产物不一致，例如：

- 缺少组件/validator 调用日志；
- subagent 返回无效 JSON；
- hop 或 validator 结果被修改；
- 当前输入与计划记录的哈希不一致；
- 缓存来源不是 strict PASS。

修复流程证据后才能生成可信的 strict 报告。

## 并行、缓存和 Token

- 不同场景可以并行；同一场景的组件 hop 必须串行。
- 并行主要减少墙钟时间，不会直接减少总 prompt Token。
- `--slim-prompts` 和 `--compact-trace` 用于减少重复 prompt 内容。
- 跨运行缓存只复用显式指定且 strict audit 为 PASS 的旧运行。
- `--strict-equivalence` 默认关闭，只有严格证明等价的 Scenario Outline
  行才会复用。
- P95、P99、可用性等聚合 NFR 不能通过单条 synthetic trace 直接证明。

## 分发给其他人

建议发送以下内容：

```text
.agents/skills/validate-arch/
src/mock_framework/
pyproject.toml
README.md
```

不要发送：

```text
.work/
__pycache__/
*.pyc
.pytest_cache/
.env
API Key
Codex 登录信息
历史运行报告
业务架构和 Feature（除非作为示例明确授权）
```

接收者解压后应保持目录结构不变，安装依赖，运行 preflight，然后从包根目录
重新启动 Codex。

## 开发验证

验证 Skill 元数据：

```powershell
$env:PYTHONUTF8 = "1"
python <skill-creator-path>\scripts\quick_validate.py .agents\skills\validate-arch
```

运行核心回归：

```powershell
python -m pytest -q `
  tests\unit\skills\test_strict_driver.py `
  tests\unit\skills\test_subagent_helpers.py
```

## 安全与边界

- 不要把 API Key、Codex 凭据或私有架构材料写入 Skill。
- 每次验证使用独立输出目录，不要复用其他正在运行的目录。
- 不要手工把缺失调用补进 `subagent_calls.jsonl`。
- 不要在 strict audit 失败时声明验证完成。
- 未经用户明确授权，不修改架构文档或 Feature。
