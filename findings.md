# Findings & Decisions

## 2026-07-28 — Phase 13 package-sanitation

- 共享配置与证据仅使用仓库相对路径；本机的 `$veriRoot` 不写入共享文件。
- `tutor/` 是只读归档，尤其不得读取或输出 `tutor/tutor-app/.env`；构建和扫描均按文件名排除所有 `.env`。
- 资产清点必须分别保留 22 个设计节点包、16 套 L2 结构化五件套、17 个实现叶子、12 个 backfill 任务/完成包；这些不表示 16 个完整自动运行。

## Requirements

- 系统名 VeriLayer，论文定位、RQ1-RQ5、C0-C5 和四个核心任务均已冻结。
- 真实 Coding Executor、pytest、有限修复、多叶集成、根级验收和端到端追踪均为 P0。
- 输出必须包括任务表、十天计划、三张 Mermaid、实验矩阵、证据设计、论文协作、Go/No-Go 和降级策略。
- 不修改代码，不重新设计论文方向。

## Research Findings

- 当前根编排器在 `vibe coding/vibecode/root_workflow.py`，通过外部 command adapter 和 `module-result.json` 调用模块。
- 当前唯一完整 command config 位于测试 fixture，生产配置不存在。
- Architecture 当前为 Skill/Markdown 规程，缺少真实 CLI 和 `architecture.json`。
- Gherkin 当前只有 Skill 和验证脚本，缺少真实生成器及 `testcases.json`。
- Mocktest strict 驱动存在，但本机 `codex.exe` 当前不可直接启动；需要在计划中设置可执行后端 Go/No-Go。
- Leaf 正式入口、Mocktest 和 PRD 之间存在 identity、Schema 和字段形状差异，应在 Adapter 层转换。
- 当前 Coding、integration、backfill 都是外部模块插槽，真实 Executor 尚不存在。

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| 新增 `verilayer/` 作为薄适配、执行、实验与证据层的建议位置 | 避免大规模重构现有模块，并保持论文实现边界清晰 |
| 现有模块内部 Schema 暂不统一，使用 canonical envelope + Adapter | 十天内成本最低且不改变模块内部设计 |
| 集成目标固定为单进程 Modular Monolith | 保留真实多模块代码集成，同时避免微服务部署复杂度 |
| hidden tests 与生成上下文物理隔离 | 防止评测泄漏 |
| 系统失败、工具错误和架构/代码负面结果分别统计 | 保证论文结果不删除失败，也不混淆环境故障 |
| 生产适配与实验代码集中拟新增到 `vibe coding/vibecode/adapters/`、`executors/`、`benchmark/`、`experiments/` | 贴近现有根编排器，降低跨目录重构成本 |
| 最大自动修复轮数冻结为 2 | 满足有限修复要求，并使 C0-C5 公平可比 |
| 项目级总 Token 上限按任务规模固定，所有配置共享同一上限 | 避免 C5 获得更多编码预算；未使用预算不强制消耗 |
| 最低实验矩阵为 24 次：C0-C5 × S1/M1/M2/L1 × seed 20260701 | 与冻结协议一致 |
| 目标 36 次：M2/L1 增加 seed 20260702 | 优先重复复杂任务和缺陷注入任务 |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| Architecture 目录曾使用错误拼写 | canonical 名称已修正为 `prd-to-architecture-skill`；各成员开工时检查本地 checkout，不建立双路径兼容 |
| 真实 strict 后端当前不可启动 | Day 2 设专门预检与替代 canonical current-session 路径，但实验前必须自动化稳定 |
| 默认 `C:\Python314\python.exe` 无 `pytest` | 团队统一使用已验证的 `E:\anaconda\ANACONDA\python.exe` |
| 部分旧 checkout 可能仍保留错误目录名 | 先同步到 `prd-to-architecture-skill`，共享配置和证据只接受 canonical 名称 |

## 2026-07-27 启动基线

- `vibecode/state.json` 为 legacy `INIT`，当前没有 `execution-log.jsonl`。
- `next-step` 返回先执行 `doctor`，但 doctor 报告当前没有 `STOP_LAYERING` 节点。
- 新根流程应使用 `run-workflow`，不应推进 legacy 示例状态。
- 使用 `E:\anaconda\ANACONDA\python.exe` 运行
  `tests/test_contracts.py tests/test_module_runner.py tests/test_root_workflow.py`：
  `27 passed in 6.94s`。
- 本地 `vibe coding/.agents/skills/layered-vibecode/SKILL.md` 要求保留人工 Gate、
  文件修改边界、contract diff 和逐阶段验证。

## 2026-07-27 分布式协作修订

- 四位成员可以使用不同本地绝对根目录和 Python 安装位置。
- 共享代码、Schema、配置和交接包必须使用仓库相对路径；机器绝对路径只允许进入本地 environment manifest。
- 本地统一使用 `$veriRoot`、`$workflowRoot`、`$veriPython`，模块在根目录外时再设置模块专属 root。
- 推荐每人独立分支/工作副本，由 A 合并；无 Git 时使用 patch、changed-paths、测试结果和 SHA-256 manifest。
- 关键真实工件顺序：
  `A PRD → B Architecture/Gherkin 并行 → C Mocktest → C Leaf → D Coding/Test → A Integration → D Root Acceptance`。
- 不同节点可以进行流水线重叠；同一节点不能越过上游 artifact Gate。
- 正式实验可以多机器并行，但必须共享 freeze manifest，并使用唯一 run ID 和 output 目录。

## 2026-07-27 既有 tutor/tutor-app 项目复核

### 已确认可复用

- `tutor` 中存在 16 套结构化 `prd.json`、`architecture.json`、`testcases.json`、
  `mocktest_report.json`、`leaf_gate_decision.json`、Leaf metrics/execution log。
- `tutor-app/docs/vibecode/runs/tutor-r01/` 存在 17 个叶子任务/完成包、多波集成、
  backfill、E2E 和 release-readiness 报告。
- 既有实现包含真实代码、叶子测试、集成测试、E2E、Docker/数据库演练和诚实的 blocked 项。
- 这些产物适合作为 canonical contract 的 migration fixture、回归基线和论文工程案例。

### 不能替代当前 VeriLayer P0 的证据

- `run-manifest.md` 明确写明运行是“手动协调”，未调用 `run-workflow` 自动执行。
- 16 套 PRD/Architecture/Testcases/Mocktest 的 `generator` 全部为
  `structured-input-preparer`，不是当前计划中的真实 PRD、Architecture、Gherkin 或 strict Mocktest 执行器。
- 示例 Mocktest 报告只声明 prepared non-blocking contract PASS，没有 strict component hop、
  validator judgments 和 strict audit 完整证据。
- 既有代码由多 worktree/人工协调叶子完成，不是 C0-C5 共用的统一 Coding Executor。
- 既有运行没有 C0-C5 公平配置、24-run matrix 和统一实验 metrics。
- `run-manifest.md` 的阶段状态落后于后续 release/task registry，说明历史证据可作参考，
  但必须先生成一致的 migration manifest 才能成为当前实验真相源。

### 计划结论

- 不再需要 Day 3 “从零再造一个完整项目”。
- Day 3 仍必须保留为半天至一天的兼容迁移与影子复现：
  导入既有 golden artifacts，选择一个叶子进行真实生成/strict/Leaf/Coding smoke，
  输出新的 run-scoped evidence，但不覆盖 tutor-app。
- Day 4/5 仍需由新 root workflow 完成一次 fresh recursive two-leaf run，
  才能证明生产 Adapter、Derive、统一 Coding Executor 和 integration 真正贯通。
- tutor-r01 可作为工程案例或 pilot，不得计入 C0-C5 正式对照实验。

## Resources

- `vibe coding/vibecode/root_workflow.py`
- `vibe coding/vibecode/scripts/vibecode.py`
- `prd-generation/scripts/prd_flow/main.py`
- `prd-to-architecture-skill/`
- `prd-to-gherkin/`
- `mocktest/.agents/skills/validate-arch/`
- `leaf-gate/scripts/run_leaf_gate.py`
- `vibe coding/vibecode/schemas/module-result.schema.json`
- `vibe coding/tests/test_root_workflow.py`
- `mocktest/schemas/mocktest_input.schema.json`

## 2026-07-28 tutor 文件夹重新复核（进行中）

### 当前归档结构

- 当前 `tutor/` 下包含两个并列部分：
  - `tutor/tutor/`：L0、L1、L2 分层设计工件，共约 424 个文件；
  - `tutor/tutor-app/`：真实应用、测试、部署、运行文档、历史 worktree 和缓存，共约 2681 个文件。
- `tutor/tutor-app/docs/vibecode/runs/tutor-r01/` 当前包含：
  - run manifest、contract freeze、execution matrix、task registry；
  - 17 份叶任务/完成包；
  - 12 份 backfill 任务/完成包；
  - wave 1–3 readiness/integration 报告；
  - E2E、staging、vendor、release readiness 和 final gate 文档；
  - append-only `execution-log.jsonl`。
- `.worktrees/` 内存在历史工作副本，不能与主工作区重复计数；`.pytest_cache`、`__pycache__` 和 `.ruff_cache` 也不属于实现资产。

### 本轮新增环境事实

- `tutor/tutor-app` 保留 `.git` 元数据，但 sandbox 用户读取 Git 状态时触发 dubious ownership。
- 后续只用命令级 `git -c safe.directory=<exact path>` 做只读检查，不修改全局 Git 配置。

### 控制面重新读取后的关键事实

- `AGENTS.md` 明确本项目实现范围是 17 个叶子：16 个 L2 STOP 节点，加上 L1 即终止的 MOD-03；只统计 16 个 L2 会漏掉一个真实叶子。
- 代码开发采用人工协调、隔离 worktree、任务包、完成包、波次集成和 human gate；`run-manifest.md` 明确没有调用 legacy `advance-state` 或 `run-workflow`。
- `task_plan.md`、`findings.md`、`progress.md` 显示后续工作已经超过旧 run manifest 的状态：
  - 17/17 叶子实际完成；
  - CCR-001 已批准并实施；
  - SCENARIO-016 已完成；
  - GAP-02 已关闭；
  - DeepSeek 受限接入已完成 staging/stub 验证；
  - 正式发布和真实密钥首轮调用仍未批准/验证。
- 四份所谓“运行真相文件”内部存在明显时间漂移：
  - `run-manifest.md` 仍写 16/17、L07 blocked、等待 Phase 5；
  - `task-registry.md` 叶子表已写 17/17 done，但页首和末尾仍保留 SCENARIO-016 未批准、CCR-001 in_progress；
  - `contract-freeze.md` 和后续 progress/findings 已写 CCR-001 完成。
- 因此 Day 1 不能只做 Schema migration；必须先增加“控制面一致性对账”，生成 current-state manifest，明确哪些文档是历史快照、哪些是最终证据。

### 对十天计划的初步影响

- 既有 tutor 实现比旧复核结论更完整，代码/测试/集成/发布准备资产的复用价值应上调。
- 但它仍不能替代 production `run-workflow`、统一 Coding Executor 和 C0–C5 正式实验。
- 当前计划选择 `CMP-CONFIG-STORE` 作为“预期 PASS 的黄金 strict 样本”存在风险：历史真实 strict 结果是 architecture `FAIL`（strict audit 可 PASS），应改为“诊断/负例 shadow”或先选择另一个已知 strict PASS 节点。

### 设计工件机器检查结果

- `tutor/tutor/` 只有 16 个 L2 节点具备五件结构化 JSON：
  `prd.json`、`architecture.json`、`testcases.json`、`mocktest_report.json`、`leaf_gate_decision.json`；另各有一份 `execution_log.json`。
- 80 份核心 JSON 均可解析，统一写 `schema_version=1.0`。
- 16 个节点的 PRD、Architecture、Testcases、Mocktest 全部由 `structured-input-preparer` 生成并预填 `status=PASS`。
- 示例 `CMP-CONFIG-STORE` 的 PRD 只有一条泛化的 `REQ-DD002`，文本为 inherited/bounded 占位描述；testcases 的断言统一是 `scenario outcome is verified`，不是完整 PRD→Gherkin 证据链。
- 示例 Mocktest 只写 “prepared L2 scenarios pass the non-blocking Mocktest contract”，没有 strict hop、validator judgment 或 strict audit。
- `tutor/` 主归档内未发现 strict audit、component-hop、semantic-errors 或 validator evidence 文件。
- Leaf 决策虽然由真实 `leaf-gate` 生成，但它消费的是 prepared PASS；同时 `leaf-gate.L2-terminal.md` 明确由产品所有者强制规定全部 16 个 L2 节点 STOP，且“不论内部组件数、架构细节或未决问题都禁止继续分层”。
- MOD-03 的 L1 STOP 同样包含显式 product-owner decision。

### 对 Leaf 实验的新增风险

- tutor 的 17 个 STOP 标签不是独立 Leaf-gate ground truth：16 个 L2 标签受统一最大层级/产品决策强制，MOD-03 也有人为叶子决策。
- 因此这些标签可用于协议、路径、任务切分和 case study，但不能直接用于：
  - 评估 Leaf-gate 判断准确率；
  - 计算专家一致率；
  - 证明证据驱动停止优于固定深度；
  - 作为 C5 的无偏 expected STOP 标签。
- 正式 Leaf 实验必须使用未被固定深度/owner terminal policy 预先决定的新任务或重新盲标的数据。

### 当前主工作区代码与现场验证

- `tutor/tutor-app` 是真实 Git 仓库，当前 `main` 最新提交为
  `f13d578 feat(vendor): deepseek 供应商受限接入（内部试用/灰度）`。
- Git 跟踪文件约 422 个：server 149、worker 41、plugin 46、contracts 19、docs 136、scripts 13。
- 主工作区存在未提交的 `.gitignore` 修改和未跟踪 `.superdesign/`；本轮未触碰。
- 源码/测试规模：
  - server 约 113 个非测试 Python 文件、22 个测试文件；
  - worker 约 30 个非测试 Python 文件、10 个测试文件；
  - plugin 约 28 个 JS 源文件、15 个测试文件。
- 当前现场测试：
  - plugin 使用 `npm.cmd test`：117/117 PASS；
  - Python 全量测试未能在当前 sandbox 环境复现：
    - 默认 Python 3.14 缺少 SQLAlchemy/FastAPI/jsonschema/httpx；
    - Anaconda Python 3.13.5 的现有 SQLAlchemy 与解释器组合导入时报 `__firstlineno__` TypeError；
    - 不依赖这些库的部分 server/worker 测试可以运行，但整套结果不能宣称 PASS。
- 因此历史报告中的 473/463/440 等 PASS 属“已保存历史证据”，不是本轮当前环境重新验证结果。

### 对计划的环境影响

- Day 1 必须增加 reproducible environment lock/preflight，不能只记录 Python 路径和版本。
- 应冻结并校验 server/worker/plugin 三套依赖、Python/Node 版本、requirements lock/hash 与实际导入。
- Day 2 的 Go Gate 应包含“在正式实验机器上完整复跑 tutor 回归或最少 contract+selected E2E”，否则 Day 3 shadow 的失败可能只是环境问题。

### 发布与 E2E 报告的时间版本关系

- `release-readiness-report.md`（2026-07-22）和 `e2e-report.md`（2026-07-21）是历史阶段报告，仍列出 L07、SCENARIO-016、received→processing、正式压测等未完成项。
- 后续提交与报告已经逐项关闭这些历史阻塞：
  - `d4-staging-acceptance-report.md` 完成 NFR-001/002 接收侧压测，并发现/修复 DU-2 relay 调度器缺口；
  - CCR-001 后续关闭 SCENARIO-016；
  - `gap-02-verification-report.md` 完成 DU-3 常驻 worker 和 ICT-003 材料读取，重跑 NFR-002 得到 1624/1624；
  - `vendor-integration-report.md` 完成 DeepSeek provider 的 stub staging、最小化、超时、kill switch 和熔断验证。
- 最新仍未完成的是：
  - 使用真实 DeepSeek key 的首轮人工 staging 调用；
  - 正式发布 human gate；
  - 真实课程期 SM-001/002/003 统计。
- 历史文档不能简单按文件名视为当前状态；迁移 manifest 必须记录 `evidence_time`、`superseded_by` 和 `claim_scope`。

### 既有代码可复用程度上调

- tutor 已具备可复用的：
  - FastAPI/SQLAlchemy/Alembic/PostgreSQL 组合根；
  - plugin/server/worker 三端实现；
  - 17 叶任务/完成包与 allowed-path 约束；
  - 15 个跨模块契约和内部契约索引；
  - Outbox、租约、幂等、repair-like 业务重试、读模型、保留删除；
  - Docker staging、压测脚本、E2E、hardening、runbooks；
  - DeepSeek provider、安全降级和证据样例。
- 这些资产可以显著减少 Day 1–2 的 fixture、workspace、pytest/evidence、integration scaffold 设计工作。
- 但不能直接减少 production Architecture/Gherkin/Mocktest/Leaf/recursive Derive/统一 Coding Executor 的核心 P0。

### 可移植性与打包风险

- `server/requirements.txt` 和 `worker/requirements.txt` 只有下限约束（如 `SQLAlchemy>=2.0`），没有 lock 文件或完整精确版本冻结。
- `plugin/package.json` 仍保留 `0.1.0-phase1` 和“Phase 1 骨架”描述，README 也仍写“当前阶段 Phase 1”，与实际 Phase 6+/473 测试状态不一致。
- `tutor/tutor-app/` 当前物理包含：
  - `.env`；
  - `data/`；
  - `.git/`；
  - `.worktrees/`；
  - `.pytest_cache/`、`.ruff_cache/`、`__pycache__/`；
  - `.superdesign/`。
- `.env`、data、worktrees 和 pytest cache 被 Git ignore，但“直接打包整个 tutor 文件夹”仍会把它们带给成员。
- 尤其 `.env` 可能含真实或本地密钥；本轮没有读取其内容。交付包必须在 Day 0/Day 1 前做 secret scan 和排除清单，至少排除 `.env`、data、`.git`、`.worktrees`、缓存和机器本地设计草稿。

### 事件日志与输入完整性

- `execution-log.jsonl` 有 41 条可解析 append-only 事件，末尾明确记录：
  - 17 叶/三波集成；
  - CCR-001、SCENARIO-016；
  - GAP-02；
  - DeepSeek stub integration。
- run manifest 中列出的 9 个关键设计输入 SHA-256 在当前迁移后的 `tutor/tutor/` 位置全部 MATCH，说明核心设计输入没有因移动目录而改变。
- 事件日志比 run-manifest/task-registry 的顶部状态更新，是当前状态对账的重要来源，但仍需用 Git commit 和测试报告交叉验证。

### 叶任务包与自动编码证据

- 17 个叶目录和 17 份 completion report 均存在；16 个叶目录有任务/allowed/forbidden/verification/completion 四件套。
- L07 是后续解除阻塞后补做的叶子，目录缺少 `forbidden-changes.md` 和 `verification-checklist.md`，只有 task、allowed、completion 三件，说明历史任务包格式并非完全一致。
- completion reports 保存 commit 和测试摘要，但未形成统一的：
  - raw model response；
  - coding prompt；
  - token/call/time metrics；
  - repair attempt 0/1/2；
  - generated file manifest/module-result。
- 主工作区没有标准化的 `model_calls/`、`repairs/`、`evidence/runs/...` 目录。
- 因此历史实现可证明“受约束的多代理/多 worktree 工程开发与集成”，不能证明“统一 Coding Executor 自动生成并有限修复”。

### 对 P0 的复用分类

- 仍必须全新实现：P0-01~09、P0-12、P0-18~20 的核心生产路径。
- 可从 tutor 提炼模板但仍需实现为通用执行器：
  - P0-10 workspace：复用 allowed/forbidden path、隔离 worktree 的安全规则；
  - P0-11 test runner：复用三类测试命令与结果口径；
  - P0-13 evidence：复用 task/completion/report/hash 结构；
  - P0-14 dependency graph：复用 17 叶三波执行矩阵；
  - P0-15 backfill：复用 B-01~B-05 计划和 contract-change gate；
  - P0-16/17 integration/root acceptance：复用 composition root、E2E、staging、hidden-test 设计思路。
- 不能把上述“模板可复用”写成“通用 Executor 已实现”。

### 代码实读补充

- `server/course_app/main.py` 已有真实 FastAPI app factory、router 挂载、health/readiness、metrics 和 lifespan relay scheduler。
- `server/course_app/composition.py` 是真实组合根，包含 Outbox、入站去重、CT-005/006/012/014/015 消费注册、teacher API、retention 与读模型装配。
- `worker/assessment_worker/runner.py` 与 `model_provider_deepseek.py` 提供真实 worker 循环、租约/重试/恢复、DeepSeek HTTP provider、安全最小化和可观测。
- `plugin/src/app/index.js` 是真实插件组合根，装配配置、意图、材料/对话采集、队列、上传与状态呈现。
- `scripts/` 已有 13 个 smoke/E2E/hardening/loadtest/staging 脚本。
- 这证明代码原型、多模块集成、根级测试和发布准备本身是真实工程成果；缺的是把这些能力抽象成 VeriLayer 通用生产执行器。

### 正式实验污染风险

- tutor 的设计包、代码、测试、completion reports 和 expected behavior 现在全部放在同一共享包中并计划发给四位成员。
- 因此任何基于 tutor 叶子或其轻微改写的任务，都不能再作为“隐藏、未见”的 C0–C5 正式 benchmark：
  - Coding Agent 可能直接读取旧实现；
  - 测试与 expected behavior 已公开；
  - Leaf STOP 标签已公开且受固定深度策略影响。
- Day 3 可以继续把 tutor 用作 engineering calibration/shadow case。
- Day 7–8 正式任务必须来自独立 benchmark 目录，hidden tests 与 tutor 包、Codex 上下文、成员工作区物理隔离。

### 技术栈差异

- tutor 生产实现采用 FastAPI + SQLAlchemy + Alembic + PostgreSQL，测试中部分使用 SQLite。
- 当前十天计划将实验集成限定为 FastAPI + SQLite Modular Monolith。
- 两者不能直接复制合并；建议只复用 app-factory/router/contract/outbox/evidence 模式，正式实验仍使用轻量 SQLite scaffold，避免把 PostgreSQL/Docker 运维复杂度带入十天 P0。

### 设计包完整范围（修正“16 套”的口径）

- `tutor/tutor/` 实际包含：
  - 1 个 L0 root；
  - 5 个 L1 模块；
  - 16 个 L2 模块；
  - 共 22 份 `.feature`；
  - 208 Markdown、169 JSON、25 YAML。
- 只有 16 个 L2 节点有五件 canonical-like JSON；实现叶子是 17 个，因为 MOD-03 在 L1 STOP。
- Day 1 migration manifest 若只写“16 套工件”，会漏掉 L0、5 个 L1、MOD-03 的 Leaf 证据和 6 份 L0/L1 Feature。
- 正确清单应同时记录：
  - 22 个设计节点包；
  - 16 个 L2 结构化五件套；
  - 17 个实现叶子；
  - 12 个父级 backfill 任务/完成包。

### L1 Leaf 证据的真实形态

- L1-mod-01 等非叶模块已有 `leaf-gate.static.json` + decomposition 文档，能作为 CONTINUE 样例。
- MOD-03 有 static + semantic judgement + architecture leaf decision，能作为 STOP 样例。
- 但这些不是当前统一 Artifact Contract 下由 root workflow 执行的 formal Leaf output：
  - static JSON 内保存旧机器绝对路径；
  - 部分解析使用 `parser: fallback`；
  - architecture validation 为空；
  - MOD-03 含显式 product-owner leaf decision。
- 因此可用于 Adapter 回归和 case study，不可直接作为无偏 Leaf ground truth。

### 路径可移植性的新阻断

- 5 个 L1 `leaf-gate.static.json` 保存了原机器 `C:\Users\Lenovo1\Desktop\Proj_PRD\...` 的绝对路径。
- `tutor-app/AGENTS.md` 和 `run-manifest.md` 仍保存迁移前的 `E:\pythonproject\完整流程\代码设计\完整代码开发工作流\...`。
- 这些历史路径不会因为把目录复制到新位置而自动失效为“仅显示信息”：若 Adapter 直接读取并尝试访问，会造成真实运行失败。
- Day 1 migration loader 必须：
  - 把历史绝对路径当作 provenance string；
  - 按 artifact 所在目录重新解析当前相对路径；
  - 输出 path-rewrite manifest；
  - 禁止将成员本机路径写回共享证据；
  - 对不能重定位的引用 fail-closed。

### 通用 VeriLayer 执行能力的缺失再次确认

- 在排除 worktree/cache 后的 tutor-app 主工作区中：
  - `run-workflow` 只出现在 manifest 的“未调用”说明中；
  - 不存在 `coding_executor`、`module-result.json`、`experiment_metrics`、C0–C5 config、repair loop 或 run matrix；
  - 不存在对应文件名。
- 所以 tutor 不能直接把十天计划中的 P0-02/P0-09/P0-12/P0-18/P0-19/P0-20 标为完成。

### 当前可复现的静态验证

- 本轮现场验证通过：
  - Python `compileall`：server/worker/shared/scripts 全部通过；
  - 28 个 plugin JS 文件 `node --check` 全部通过；
  - contracts 目录 18 个 JSON 全部可解析；
  - `ruff check server worker shared scripts` 通过；
  - plugin 117/117 测试通过。
- Python 完整行为测试仍因当前依赖环境不可复现，必须和上述静态 PASS 分开报告。

## 2026-07-28 十天计划再校准结论

### 总判断

- 十天结构 `合同/骨架 → 校准 → fresh 递归 → 双叶编码 → 集成冻结 → pilot → 24 run → 论文` 仍然合理，不需要推倒重来。
- 必须修改 Day 1、Day 2、Day 3 和 Day 7–8 的验收口径。
- Day 4–6 的 fresh recursive/two-leaf/integration 不能删除；它们仍是 production VeriLayer 与历史人工 tutor run 的分界证据。

### 必须修改（P0）

1. 开工前增加半天以内的 package sanitation：
   - 排除 `.env`、data、`.git`、`.worktrees`、缓存、`.superdesign` 本地内容；
   - secret scan；
   - 生成 `PACKAGE_MANIFEST.sha256` 和 recipient requirements。
2. Day 1 migration manifest 的范围从“16 套”改为四层计数：
   - 22 个设计节点包；
   - 16 个 L2 五件结构化 JSON；
   - 17 个实现叶子；
   - 12 个 backfill 任务/完成包。
3. Day 1 增加 current-state reconciliation：
   - 以 Git commit + execution-log + 后续验证报告对账；
   - 给历史报告加 `superseded_by/claim_scope/evidence_time`；
   - 不直接相信 run-manifest/task-registry 顶部旧状态。
4. Day 1 增加 path rewrite：
   - 历史绝对路径只保留为 provenance；
   - 运行路径统一重定位为仓库相对路径。
5. Day 1/2 增加双环境冻结：
   - VeriLayer 实验环境；
   - tutor reference regression 环境；
   - 不强制二者共用一个 Python。
6. Day 2 不再从零设计 workspace/evidence/integration 模式：
   - 从 tutor 的 allowed-context、completion package、execution matrix、backfill、composition root 提取模板；
   - 但仍实现通用 Executor。
7. Day 3 改为双轨校准：
   - Validation track：CMP-CONFIG-STORE 作为已知负例，预期 strict audit 完整但 architecture FAIL；
   - Coding track：用独立小型 S1 positive control 检查 Coding Executor/pytest/evidence；
   - 只有 Architecture 修复并 strict PASS 后才能把同一节点送入 Leaf/Coding。
8. Day 7–8 增加 benchmark contamination gate：
   - tutor 及其改写任务不进入正式 C0–C5；
   - tutor Leaf 标签不进入 κ/accuracy；
   - hidden tests 不随四人工作包分发，也不进入 Coding Agent 上下文。

### 保留不改

- Architecture 与 Gherkin 并行。
- Mocktest execution completeness 与 architecture conclusion 分开。
- 真实 PRD Derive、CONTINUE→child STOP。
- 至少两个 fresh leaf 的统一 Coding Executor、pytest 和有限 repair。
- Day 6 多叶集成和 freeze。
- C0–C5 公平性、失败保留、最低 24 run、Day 9/10 统计与 claim-evidence audit。

### 工作量判断

- tutor 的代码/测试/集成资产可以节省 workspace、evidence、DAG、backfill、app-factory 设计时间。
- 新增的包清理、控制面对账、环境锁定、路径重写和实验污染防护会消耗相近时间。
- 因此不建议把十天缩成 7–8 天；建议保持十天不变，重新分配 Day 1–3。
- 36 run 保持目标，24 run 保持最低；48 run 不应进入主承诺。

## 2026-07-28 复核建议实施结果

- 已把开工前清洁包变成正式前置 Gate：原始 Tutor 归档不修改，只生成排除 `.env`、data、Git/worktree、缓存和本机草稿的清洁副本，并要求 secret/path scan、内容清单、SHA-256 和 recipient requirements。
- Day 1 已从“16 套工件迁移”改为四类资产对账：22 个设计节点、16 套 L2 五件套、17 个实现叶、12 个 backfill；新增 current-state 和 path-rewrite manifest。
- Day 1/2 已改为 VeriLayer 与 Tutor reference 双环境分别冻结；生产配置禁止 fixture 和旧绝对路径。
- Day 3 已正式拆成两个隔离 Gate：
  - CMP validation-negative：strict execution evidence 完整但 architecture FAIL，必须阻断 Leaf/Coding；
  - fresh S1 coding-positive：strict PASS、Leaf STOP、统一 Coding Executor、pytest 和受控 repair。
- Day 7–8 已加入 contamination gate：Tutor 或其轻微改写任务、公开测试和强制 STOP 标签不能进入正式 C0–C5；hidden tests 必须物理隔离。
- 上述规则已同步到十天主计划、四人启动指南、A–D 个人计划、工作流总文档和根治理说明。
- P0 数量仍为 20；因安全清理、状态对账、路径重写和双环境 preflight，毛估算由 220 调整为 226 人时，净估算调整为 180–195 人时。
- 本阶段没有修改 Tutor 业务代码、历史报告、原始归档或实验运行结果。
