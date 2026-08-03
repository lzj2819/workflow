# Task Plan: VeriLayer 四人十天完整 Vibecoding 实施计划

## Goal

接手 VeriLayer 的 A/B/C/D 工作，以 GitHub 远端和可复现命令为唯一事实基线，先消除 Day 1 Gate 的循环阻塞并完成其最小验收，再按十天计划逐日实现、验证和记录。任何阶段仅在对应命令与证据完整时标记完成；不得把文档、fixture、xfail、`--help` 或历史 Tutor 工件表述为真实端到端结果。

## Current Phase

Phase 18 — Day 3 dual-track calibration: complete. CMP remains a strict-complete semantic FAIL blocked from downstream; fresh S1 is a strict-PASS/Leaf-STOP/Coding/public-pytest positive control with zero repairs.

Phase 19 — Day 4 fresh recursive production run: in progress. Preserve failed run evidence, use Mocktest reports to make bounded Architecture-only fixes, then re-run validation until a root `CONTINUE_LAYERING → fresh child STOP_LAYERING` trace is proven or a final evidence-bounded stop condition is reached.

## Phases

### Phase 1: 要求与事实边界

- [x] 完整读取第三步要求
- [x] 固定论文定位、RQ、C0-C5、任务集和不可降级边界
- [x] 复用前两阶段仓库事实
- **Status:** complete

### Phase 2: 仓库路径与任务依赖映射

- [x] 将 20 项 P0 映射到真实文件/拟新增文件
- [x] 确定验收命令和依赖图
- [x] 估算四人人时并消除并发冲突
- **Status:** complete

### Phase 3: 十天排程与实验矩阵

- [x] 制定 Day 1-Day 10 每日唯一目标和 A-D 任务
- [x] 固定每日 Go/No-Go、晚间冻结项和降级路径
- [x] 完成 24/36/48 次实验矩阵设计
- **Status:** complete

### Phase 4: 证据、论文协作与风险降级

- [x] 定义叶子与根级证据目录
- [x] 制定论文章节、图表、审稿和版本管理
- [x] 制定半天/一天/两天及技术故障降级
- **Status:** complete

### Phase 5: 计划验证与交付

- [x] 核对全部用户要求
- [x] 生成 VeriLayer 十天主计划文档
- [x] 验证路径、表格和 Mermaid 完整性
- **Status:** complete

### Phase 6: 四人开工执行包

- [x] 将 A-D 职责拆成逐小时开工步骤
- [x] 固定每人的首批文件、验收命令和交接包
- [x] 定义 Day 1 共同工作协议和进入 Day 2 的 Gate
- [x] 生成四人可直接使用的实施启动文档
- **Status:** complete

### Phase 7: 四份独立成员实施文档

- [x] 生成成员 A 自包含实施文档
- [x] 生成成员 B 自包含实施文档
- [x] 生成成员 C 自包含实施文档
- [x] 生成成员 D 自包含实施文档
- [x] 检查四份文件边界、依赖、命令和交接关系
- **Status:** complete

### Phase 8: 路径可移植性与并行顺序修订

- [x] 移除四份成员文档中的机器专属绝对路径
- [x] 为每份文档加入本地根目录和 Python 变量初始化
- [x] 冻结仓库相对路径与本地路径映射规则
- [x] 为每人加入可并行、必须等待和汇合 Gate
- [x] 审计四份文档不存在机器专属路径并且顺序一致
- **Status:** complete

### Phase 9: 既有完整项目复用与十天计划压缩复核

- [x] 审计 tutor/tutor-app 的上游工件、Leaf、代码、测试和集成证据
- [x] 判断既有项目是否覆盖当前 VeriLayer production root 闭环
- [x] 决定 Day 3 删除、压缩或改为迁移复现
- [x] 提出十天计划和四人个人计划的修订方案
- [x] 给出新的并行顺序、Gate 和实验起点
- **Status:** complete

### Phase 10: 同步修订全部实施文档

- [x] 修订十天总计划的 Day 1-Day 6 和工作量口径
- [x] 修订四人启动方案的既有项目定位与新日程
- [x] 修订 A-D 四份个人计划的复用任务和影子复现
- [x] 修订工作流总文档的并行图和历史证据边界
- [x] 同步 `prd-to-architecture-skill` canonical 名称到治理文档
- [x] 扫描所有主文档，消除“Day 3 从零再造项目”的旧表述
- **Status:** complete

### Phase 11: tutor 文件夹全量复核与十天计划再校准

- [x] 枚举 `tutor/` 的代码、文档、工件、测试、运行报告和配置
- [x] 核验实际生成方式、递归方式、Mocktest strict 证据、Leaf 决策与 Coding/Integration 证据
- [x] 对照 Day 1-Day 10，判断保留、压缩、提前、替换或删除的任务
- [x] 识别此前审查遗漏的新阻断、可复用资产和实验污染风险
- [x] 给出逐日修订建议、优先级、工作量与是否需要修改计划文档
- **Status:** complete

### Phase 13: 开工前清洁团队输入包（Owner A）

- [x] 记录 `tutor/` 只读源的排除 `.env` 元数据指纹
- [x] 建立不覆盖原始包的清洁副本
- [x] 生成内容、排除、secret、绝对路径、hash、收件人和资产清点报告
- [x] 对副本和源目录执行验收并提交 B/C/D 复核交接报告
- **Status:** complete — 可供 B/C/D 复核，尚不可分发

## Phase 13 Boundary

- 范围仅限 `team-delivery/` 的 package-sanitation，不开始 Day 1 合同开发。
- `tutor/` 为只读归档；绝不读取、显示、复制或输出 `tutor/tutor-app/.env`。
- 不修改业务代码、历史报告、原始测试结果、原始 Git、Adapter、Executor 或根编排器。
- 最终验证：1,257 个清洁文件；禁项为 0；高风险 secret shape 为 0；可执行绝对路径为 0；内容和 SHA-256 manifest 可重算；源 `tutor/` 元数据指纹保持 `0d25bf1eea777132f653bfb8959c93999176e3a19b5987e41f2419c4932dcf2a`。
- 已知限制：20 个中风险候选须由 B/C/D 仅按路径审查；12 个 backfill 基线由 11 个已物化 task/completion pair 和 1 个 plan asset 构成。

### Phase 14: B/C/D sanitation rejection remediation（Owner A）

- [x] 仅从清洁副本移除 `mocktest/.env.example` 与 `tutor/tutor-app/data/`
- [x] 新增 A 所有权的 `vibe coding/docs/ARTIFACT_CONTRACT.md`
- [x] 以完整绝对路径规则重新扫描并重建四项 sanitation 报告、contents 与 manifest
- [x] 验证禁项为零、清单/manifest 可重算，完成源/副本逐文件对账，并生成 B 复核交接
- **Status:** complete — B review approved; package is approved for onward distribution, but no transfer was performed

## Phase 14 Boundary

- 原始 `tutor/` 始终只读；删除仅作用于 `team-delivery/verilayer-team-input-clean/`。
- 允许新增仅限 A 所有权的治理文档 `vibe coding/docs/ARTIFACT_CONTRACT.md`；不修改业务代码、Adapter、Executor 或根编排器。
- 最终状态：1,078 个清洁文件；`.env`/`.env.example`/`data`/Git/worktree/cache 均为 0；high-risk secret shape=0；executable absolute path=0；29 个 provenance-only 命中全部列入报告；contents/manifest 可重算。
- Tutor 对账：844 个可比较文件路径一一对应，829 个 hash 相同，15 个差异均为完整声明的绝对路径净化项；metadata-only 基线指纹已退役，不作未改源目录的唯一证据。

### Phase 15: Public GitHub publication preparation（Owner A）

- [x] 验证 `lzj2819/workflow` 的可访问性、管理员权限和现有 `main` 占位提交
- [x] 从已批准的清洁副本创建独立发布工作区和 `chore/publish-verilayer-workspace` 分支
- [x] 完成公开发布安全检查：`.env`/`.env.example`、`data/`、缓存为 0；强凭据形态为 0；可执行配置绝对路径为 0
- [x] 添加公开仓库 README、`.gitignore`、贡献约定和 PR 模板；发布副本使用 canonical `prd-to-architecture-skill` 目录名
- [x] 推送提交 `f63fb71` 到远程发布分支
- [ ] 创建并合并 PR 到 `main`（GitHub App 的 PR 接口返回 403，浏览器会话未登录；须由仓库管理员在网页完成）
- **Status:** in_progress — 发布分支已远程可用，`main` 尚未变更

## Phase 15 Boundary

- 只发布批准的清洁副本；原始 `tutor/` 和本地工作区保持不变。
- 第三方参考 PDF 不进入公开 Git 历史，引用说明保留；待再分发授权核验后另行处理。
- 首次发布不能强制推送或覆盖 `main`；仅接受从当前 `main` 快进的 PR 合并。

### Phase 16: Live takeover and Gate-driven implementation

- [x] Inspect the current remote refs, PRs, issues, and the available A worktree; record immutable baseline SHAs.
- [x] Safely reconcile and publish the A integration branch if its local-only work is valid; do not force-push, merge PRs, or change `main` without an earned Gate.
- [x] Replace the circular Day 1 evidence checklist with its minimal, repository-backed acceptance command and run it in the frozen environment.
- [ ] Land only the small changes required for a real Day 1 GO, then build Day 2 and later deliverables in dependency order.
- [ ] Keep `findings.md` and `progress.md` updated with executed commands, exit codes, evidence paths, and unambiguous PASS/FAIL/ERROR classification.

### Phase 17: Day 2 production skeleton

- [x] Inspect current Adapter/Executor/config/test surfaces and identify only the missing P0 skeletons.
- [x] Add shared production configuration and bounded Adapter/Executor entrypoints that return canonical structured `ERROR` for unavailable module wiring.
- [x] Add focused tests for configuration, controlled error semantics, path safety, and dry-run behavior.
- [x] Run Day 2 targeted tests and a non-fixture production dry-run; record GO/NO-GO without claiming Day 3 strict/Coding work.

### Phase 18: Day 3 dual-track calibration

- [x] Inspect real Architecture/Gherkin generation, Mocktest strict, Leaf Gate, and Coding execution entrypoints plus their credential/tool prerequisites.
- [x] Prepare isolated fresh-S1-positive inputs with no Tutor output reuse, and repair its machine-readable component contract bindings.
- [x] Run fresh S1 strict validation: unique run J completed four component hops and three validators; strict audit and final Mocktest report are PASS, with formal publication evidence `ALLOW`.
- [x] Run the CMP strict negative track: 5 component calls and 5 validators completed with strict audit PASS; formal Mocktest is semantic FAIL (17 findings, 5 failed scenarios, no tool ERROR) and downstream Leaf/Coding is blocked.
- [x] Run the fresh S1 Coding positive control only after strict PASS: isolated real Codex invocation, public ASGI pytest, repair budget, and hash-addressable evidence all completed; the first attempt passed, so actual repair count is 0.
- [x] Run the independent Leaf STOP decision for fresh S1 through the Leaf Gate formal adapter; retain the shared v0.2 Contract unchanged.
- [x] Record the Day 3 dual-track GO: S1 PASS→STOP→real Coding→pytest; CMP complete strict execution→semantic FAIL→downstream block.

### Phase 19: Day 4 fresh recursive production run

- [x] Verify the root workflow already supports recursive node creation, checkpoint/resume, parallel architecture/Gherkin branches, and parent-node trace under fixture coverage.
- [x] Identify the real Day 4 blocker: production configuration still routes all modules to the Day 2 controlled-error skeleton; fixture coverage is not production evidence.
- [~] Implement tested real module adapters and a fresh root/child task without reusing S1 output or Tutor code/tests. PRD/Architecture/Gherkin model-backed boundaries, strict Mocktest executor/adapter, formal Leaf conversion/adapter, and root-to-Coding request boundary are implemented and unit-tested; root configuration and the real trace remain.
- [x] Publish and dry-run a separate Day 4 pre-backfill configuration with fresh public input; it names its unimplemented human-gated backfill/integration stages rather than treating them as production success.
- [x] Diagnose and repair the first real-run orchestration crash without altering its failed evidence: structured adapter provenance could overwrite the root stage generator and break metric aggregation.
- [x] Diagnose the second real run as a strict semantic block, then strengthen the fresh generation boundary with the minimum machine-readable entry/contract conventions required by the canonical strict driver.
- [x] Repair strict finalization classification: a completed formal Mocktest report with a valid semantic `PASS`/`FAIL` now overrides a nonzero `finalize_exit`, while missing/incomplete/invalid formal evidence remains `ERROR`.
- [ ] Apply the report-driven Architecture-only repair, preserving the frozen Feature/Gherkin and each pre/post hash; then start a new unique Day 4 run.
- [ ] Verify the repair loop independently with a deterministic initial-failure fixture. Do not mutate the successful S1 output merely to create repair evidence.
- [ ] Run a real root `CONTINUE_LAYERING` → fresh child `STOP_LAYERING` trace; retain Mocktest/Leaf/Coding/repair evidence and preserve the two-repair limit.
- [ ] Run the Day 4 acceptance suite only after its dedicated integration tests exist; a missing test path is an acceptance ERROR, not a PASS.
- **Status:** in_progress

### Phase 20: Implementation-plan and paper-evidence synchronization

- [x] Correct the documented Mocktest control flow to require `FAIL → Architecture repair → revalidation` and to distinguish it from `ERROR → evidence/execution repair`.
- [x] Record the Day 3 S1 zero-repair fact and require an independent deterministic repair fixture.
- [x] Mark Day 4 as in progress / NO-GO and identify `.coord-worktree` as the active implementation evidence boundary.
- [x] Require a Day 6 `RQ × configuration × metric × evidence × figure` registry and a sanitized evidence manifest before the formal pilot.
- **Status:** complete

### Phase 21: All-role Mocktest feedback-loop synchronization

- [x] Audit the main plan, four-person start guide and all A–D independent implementation plans for an explicit Mocktest report-feedback loop.
- [x] Add the shared routing rule: `PASS + ALLOW → Leaf`; `FAIL / FIX_ARCH → B Architecture-only repair → C revalidation`; `ERROR → evidence/execution remediation → revalidation`.
- [x] Assign owner-specific stop rules so A blocks recursion/backfill, B does not alter frozen Feature/Gherkin, C does not convert incomplete validation to Leaf-ready, and D rejects non-PASS bundles.
- [x] Verify all six task-plan documents contain the required loop and prohibition against sending FAIL/ERROR into Leaf/Coding.
- **Status:** complete

### Phase 12: 将 tutor 复核结论落实到全部实施文档

- [x] 在主计划中加入开工前安全清理、四层资产清单、状态对账和路径重写
- [x] 将 Day 3 改为 CMP 负向 strict 校准与独立 S1 正向 Coding 校准
- [x] 在 Day 7–8 加入 benchmark contamination gate 和 hidden-test 物理隔离
- [x] 同步四人启动方案、A–D 个人计划和工作流总文档
- [x] 校验十天结构、成员边界、Markdown 表格和关键语义一致性
- **Status:** complete

## Key Questions

1. 哪些 P0 可通过 Adapter 完成，哪些必须新增真实执行器？
2. 如何在 Day 6 前完成至少一个真实多叶子 Modular Monolith 集成闭环？
3. 如何确保 C0-C5 使用相同 Coding Executor、模型、预算和修复上限？
4. 延期时如何减少规模而不删除真实编码、C0/C5 或多模块闭环？
5. Day 4 recursive run can now pass strict at root and its first child; can the repaired architecture-contract evidence admit real child Coding and complete the pending trace child without crossing the human-gated backfill boundary?

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| 计划限定 Python/FastAPI/pytest/SQLite Modular Monolith | 十天内保留真实多模块集成的最低风险技术边界 |
| Coding Executor 对 C0-C5 完全复用 | 防止 C5 获得额外模型、Prompt 或预算优势 |
| Day 6 后冻结代码、Prompt、Schema 和任务规格 | 避免实验期间实现漂移 |
| 24 次真实运行是不可低于的论文数据底线 | 已冻结实验协议要求 |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| 附件首次按 PowerShell 默认编码读取出现乱码 | 1 | 使用 `Get-Content -Encoding UTF8` 重新完整读取 |
| `rg.exe` 在当前 Windows 环境被拒绝执行 | 1 | 改用 PowerShell `Get-ChildItem` 和 `Select-String` |
| 默认 `C:\Python314\python.exe` 无 `pytest` | 1 | 使用已验证的 `E:\anaconda\ANACONDA\python.exe`，27 个基线测试通过 |
| `doctor` 因没有 STOP_LAYERING 节点返回非零 | 1 | 记录为当前 INIT 事实，不生成矩阵、不推进 legacy state |
| 四文件结构审计的 PowerShell `foreach` 后直接管道导致 ParserError | 1 | 改为先收集 `$rows` 再执行 `Format-Table` |
| 递归统计 tutor-app 时 `.pytest_cache` 访问被拒绝 | 1 | 保留已获得的工件/测试报告证据，后续只读取明确路径并排除缓存目录 |
| Memory 行号查询中的 Windows 路径被正则解释为转义 | 1 | 改用 `Select-String -SimpleMatch` |
| 同步修订时部分 `apply_patch` 大块上下文不匹配 | 1 | 重新读取现有文档，按精确小块更新 |
| Markdown 表格检查脚本中 `"$doc:..."` 触发 PowerShell 变量解析错误 | 1 | 改用 `"${doc}:..."` 后重新运行，检查通过 |
| `git -C tutor/tutor-app` 因 checkout ownership 不同而拒绝读取 | 1 | 后续使用命令级 `git -c safe.directory=<exact path>` 只读检查，不修改全局配置 |
| 当前 PowerShell 的 `ConvertFrom-Json` 不支持 `-Depth` 参数 | 1 | 去掉该参数后重新解析，80 份核心 JSON 全部可读 |
| Python unittest discovery 在中文路径下把绝对路径解码为乱码（默认 Python 与 Anaconda 均复现） | 2 | 停止重复 discovery，改为枚举测试文件并按 Python 模块名直接运行 |
| PowerShell 阻止执行 `npm.ps1` | 1 | 改用 `npm.cmd test`，不修改执行策略 |
| Anaconda Python 3.13.5 导入当前 SQLAlchemy 时触发 `__firstlineno__` canonical symbol TypeError | 1 | 不修改依赖；改用默认 Python 3.14 按模块名运行，避开 discovery 中文路径问题 |
| 项目根目录不是 Git 仓库，无法使用根级 `git status/diff` 验收文档修改 | 1 | 改用文件清单、关键语义扫描、标题计数、Markdown 表格列数和 SHA-256 进行验收 |
| Phase 12 验证脚本再次在 `foreach` 代码块后直接接管道，引发 PowerShell ParserError | 2 | 停止使用该写法，统一先收集 `$rows`/`$promptRows`，再单独执行 `Format-Table`；后续完整验证通过 |
| Phase 22 derive-all 集成测试把 Traceability 表误解析为需求表，子 priority 变成 Acceptance Contract ID | 1 | 收紧 legacy Markdown parser，只允许在固定功能需求章节解析 REQ 表；保留 validator，不放宽 canonical 枚举 |
| Phase 22 `ruff` 检查无法启动：当前 Python 环境未安装 `ruff` | 1 | 不进行网络安装；保留限制说明，以 `compileall`、8 项测试、Schema/表格/静态引用检查完成本轮验证 |
| Phase 23 多文件证据读取脚本对动态全长 range 使用 `[Math]::Min` 时发生 PowerShell 参数类型不匹配 | 1 | 不重复该循环；改为按文件直接读取或使用固定 `Select-Object -Skip/-First`，随后成功取得 Schema、consumer profile 和 Mocktest parser 证据 |
| Phase 23 首次规划记录补丁的 hunk 分隔格式错误 | 1 | 拆成有明确上下文的标准 hunk 后重新应用，不改动产品文件 |
| Phase 23 首次复查 canonical.py 时工作目录仍在仓库根却使用了 `scripts/...` 相对路径 | 1 | 改用 `prd-to-artecture-skill/scripts/...` 明确路径后成功读取；未执行写操作 |
| Phase 23 系统 Python 运行真实 Mocktest parser 时缺少 `yaml`，且首次临时 pip 安装因网络沙箱 `WinError 10013` 失败 | 1 | 按权限流程在 `C:\\tmp` 安装测试依赖；随后发现现成 Anaconda Python 已完整提供 PyYAML/Pydantic/jsonschema/Rich，改用该解释器执行真实链路 |
| Phase 23 首次真实 Mocktest 解析断言期待稳定 ID，但通用 `Module` 表解析得到显示名 `Order Module` | 1 | 将统一节点表同时保留 `child_id`、稳定 ID `Module` 与独立 `Name` 列，兼顾递归解析、Mocktest 稳定身份和人类可读名 |
| Phase 23 重写 Skill 的首个组合补丁因旧顶层 `openai.yaml` 含非法 UTF-8 字节而整体拒绝 | 1 | 先严格解析并删除该单一损坏配置，再用 apply_patch 以有效 UTF-8 重建；其余文件未被该失败补丁部分修改 |
| Phase 24 planning-with-files 文档所列 Claude 兼容路径不存在 `session-catchup.py` | 1 | 已直接完整读取现有 `task_plan.md`、`findings.md`、`progress.md` 恢复上下文；不伪造 catchup 结果 |
| Phase 24 首次读取 Council persona 假设文件名为 `ada.md` 等，实际文件有 `council-` 前缀 | 1 | 已由目录清单确认真实文件名，后续改读 `council-ada.md` 等，不重复错误路径 |
| Phase 24 尝试新建 Aristotle 席位时发现 `/root/council_aristotle` 已存在 | 1 | 不创建重复席位，改用 `followup_task` 复用现有 persona agent；不影响三席独立性 |

## Notes

- 本阶段只创建计划文档，不修改业务代码。
- 所有尚未存在的新文件位置必须明确标为“拟新增”。

### Phase 22: PRD Generation 全流程审计、重构与统一输出契约

- [x] 完整盘点并读取 `prd-generation`、`prd-to-artecture-skill`、`prd-to-gherkin`、`mocktest`、`leaf-gate`、`vibe coding` 与 `工作流总文档.md`
- [x] 建立六流程输入/输出/消费者映射，区分现状、重复、冲突与跨阶段契约缺口
- [x] 按 Council 完成复述门、三轮独立审议、匿名交叉审查、结构化表决与主席综合
- [x] 重构 `prd-generation`，删除或合并不合理及重复规则，同时保留必要的人类确认门
- [x] 定义并落地唯一 canonical PRD 格式、schema、模板、生成约束和兼容/校验入口
- [x] 用多组不同需求验证每次输出结构一致、内容可变，并验证下游 Architecture/Gherkin 可消费
- [x] 更新说明、发现和执行记录，明确改动范围、未改动流程与后续迁移建议
- **Status:** complete

## Phase 22 Boundary

- 本轮允许修改 `prd-generation` 及根级规划记录；其余五个流程仅作为消费者和接口约束进行只读审计，除非兼容性验证必需且变更可严格限定为 `prd-generation` 输出适配资产。
- 不删除历史产物、不改写既有运行证据、不把未执行的下游流程称为已重构。
- “统一格式”要求字段、章节、顺序、ID、枚举、缺省值和机器可读契约稳定；业务内容按需求变化。

### Phase 23: Architecture Generation 双模式重构与统一输出契约

- [x] 完整读取 `prd-to-artecture-skill` 的项目自有文档、源码、模板、schema、配置和测试，并核对实际入口
- [x] 建立 Top-level 与 Decompose 两种模式的输入、所有权、输出、停止条件和下游消费者映射
- [x] 按 Council 完成复述门、三轮独立审议、匿名交叉审查、结构化表决与独立主席综合
- [x] 识别并删除或合并相互冲突、重复、不可执行或依赖启发式猜测的设计
- [x] 落地唯一 canonical Architecture 模型、JSON Schema、确定性 Markdown renderer 和完整 bundle
- [x] 为 Top-level 与 Module/Component 两种 profile 建立 fail-closed 校验和兼容迁移入口
- [x] 用不同内容、输入重排、Root→Decompose、PRD v3、Gherkin/Mocktest/Leaf 消费边界进行契约验证
- [x] 更新 Skill、README、模板、工作流总文档、审计报告和文件化进度记录
- **Status:** complete

## Phase 23 Boundary

- 本轮允许修改 `prd-to-artecture-skill` 及根级说明/规划文件；PRD、Gherkin、Mocktest、Leaf Gate、Vibe Coding 仅作为真实消费者或输入契约读取，除非测试夹具可完全放在 Architecture 流程内。
- 顶层模式负责从 canonical PRD 建立系统边界和第一层可部署模块；细分模式只细化一个已选父模块或父组件，不得重新解释顶层产品范围。
- “统一格式”表示两种模式共享同一 envelope、payload 字段集合、章节集合与 sidecar 结构；通过显式 `architecture_mode` 和 profile 约束表达层级差异，而不是维护两套互相漂移的模板。
- 不把 producer-side profile 测试描述成完整 Gherkin/Mocktest strict 或全链 E2E；不移动当前拼写错误的实际目录名。

### Phase 24: PRD-to-Gherkin 全流程重构与统一 Feature 合同

- [x] 完整盘点并读取 `prd-to-gherkin` 的项目自有 Skill、源码、Schema、模板、配置、测试和示例，核对真实入口与生成/验证链
- [x] 建立 canonical PRD v3 → canonical testcase → Feature → Mocktest 的实际字段与证据映射，并删除重复 requirement-model 层
- [x] 按 Council 完成复述门、三轮独立审议、匿名交叉审查、结构化表决与独立主席综合
- [x] 识别并删除或合并重复、冲突、不可执行、依赖自由文本猜测或制造多重事实源的设计
- [x] 落地唯一 canonical testcase/Gherkin 模型、Feature formatter、JSON Schema、确定性 bundle 和 fail-closed validator
- [x] 固定 Feature 关键字、tag、标题、Background/Scenario、Given/When/Then 顺序、DocString/DataTable、空值与转义规则
- [x] 用不同 canonical PRD v3、输入重排、异常/边界案例和真实 Mocktest parser 验证“结构相同、内容不同”
- [x] 更新 Skill、README、合同、工作流总文档、Council/重构报告及根级文件化状态
- **Status:** complete

## Phase 24 Boundary

- 本轮允许修改 `prd-to-gherkin` 及根级说明/规划文件；`prd-generation`、Architecture、Mocktest、Leaf Gate、Vibe Coding 只作真实输入/消费者验证，测试夹具必须留在 Gherkin 流程内。
- canonical PRD v3 的 requirement、acceptance contract、evidence 和 release scope 是输入事实；Gherkin 不得补造未知 actor/precondition/trigger/response/oracle。
- “统一 Feature 格式”要求 tag 集合与顺序、Feature/Background/Scenario 结构、步骤关键字与顺序、ID、枚举、转义、空表和 bundle 文件名稳定；业务文本按 PRD 变化。
- 不把语法/结构 validator PASS 表述成 Mocktest strict 或业务语义 PASS；不修改被冻结的既有 `.feature` 运行证据。

### Phase 25: Mocktest 全流程重构、宽容提取与统一证据/报告合同

- [x] 完整盘点并阅读 `mocktest` 项目自有 Skill、CLI、loader/parser、normalizer、planner、simulator、validator、strict driver、schema、配置、测试和文档，复原真实执行图
- [x] 建立 Architecture v2 + Feature v2 → canonical input model → plan/hops/validators/audit → final report 的字段、身份、hash、状态与失败分类映射
- [x] 按 Council 完成复述门、三轮独立审议、匿名交叉审查、结构化表决与独立主席综合
- [x] 识别并删除或合并重复状态机、重复 schema/report renderer、历史兼容分支、硬编码标题/表头/别名和会制造假阴性的提取约束
- [x] 落地版本化 Architecture/Feature importer：优先 canonical JSON/Feature v2；Feature 仅作 sibling JSON 的确定性视图；歧义保持 fail-closed 并输出 provenance 诊断
- [x] 统一每次运行的输入快照、解析结果、执行计划、hop、validator、audit、manifest、final report 的文件名、JSON Schema、字段顺序、状态枚举、空集合和 hash 规则
- [x] 固定最终 Markdown/JSON 报告格式，并严格拆分 execution completeness、structural audit、business validation、tool/environment status
- [x] 用 Top-Level/Decompose Architecture v2、Feature v2、多 When、唯一/无/多绑定、零 hop 阻断、部分执行、FAIL/WARNING/PASS、跨目录输入和 producer run ID 独立性验证结构稳定与提取适配
- [x] 更新 Skill、README、配置、迁移说明、Council/重构报告、工作流总文档和根级文件化状态
- **Status:** complete

## Phase 25 Boundary

- 本轮允许修改 `mocktest` 与根级说明/规划文件；PRD、Architecture、Gherkin、Leaf、Vibe Coding 只作为输入/消费者读取。不得改写其 canonical Schema、既有 Architecture/Feature 或历史 strict run 证据。
- “更适配”不等于放宽业务门禁：解析器必须先消费 canonical `architecture/v2` 与 `feature/v2`；兼容 Markdown 通过多候选归一化、显式 confidence/diagnostic 和 fail-closed 歧义处理，禁止猜测业务合同或把组件 ID 变成事件。
- “统一格式”覆盖 run 目录、文件 allowlist、JSON envelope/schema、键/数组顺序、空产物、hash、最终 Markdown/JSON 章节和状态语义；同样输入与相同模拟响应应产生相同结构和内容 hash。
- execution complete、strict audit、business result 与 tool/environment error 必须独立；任何一个 PASS 不得替代其他维度。
- 历史 report/user/.work 产物只读；删除仅限经审计确认的重复代码/模板/schema，不清理用户证据目录。

### Phase 26: Leaf Gate 全流程重构、Mocktest 修复闭环准入与统一决策合同

- [x] 完整盘点并阅读 `leaf-gate` 项目自有 Skill、脚本、schema、references、配置、测试和文档，复原 legacy/formal/LLM/refinement/decomposition 的真实执行图
- [x] 建立 PRD v3 + Architecture v2 + Testcases v2 + Mocktest v2 → admission → deterministic rules → decision → fixed bundle 的字段、身份、hash 和状态映射
- [x] 按 Council 完成复述门、三轮独立审议、匿名交叉审查、结构化表决与独立主席综合
- [x] 识别并删除或合并重复判定器、重复报告/模板/schema、旧共享 run ID/status 假设和相互冲突的 refinement/decomposition 分支
- [x] 将 Mocktest 修复闭环固化为 Leaf Gate admission：只有最新 Architecture 对应的 revalidation `overall=PASS`、audit PASS、ALLOW 且无 superseding FAIL/BLOCKED/ERROR 才能进入具体 Leaf 判断
- [x] 落地唯一 canonical Leaf Gate v2 输入适配器、确定性规则引擎、固定决策模型、JSON Schema、Markdown renderer 和 bundle manifest
- [x] 固定 CONTINUE_LAYERING / STOP_LAYERING / ERROR 的证据、proposed_children、人工门禁、空集合、排序、hash 和退出码语义
- [x] 用首轮 PASS、修复后 PASS、stale PASS、WARNING/FAIL/BLOCKED/ERROR、阈值、深度、固定结构和输入重复验证结构稳定
- [x] 更新 Skill、使用说明、迁移/重构/Council 报告、工作流总文档及根级文件化状态
- **Status:** complete

## Phase 26 Boundary

- 本轮允许修改 `leaf-gate` 与根级说明/规划文件；PRD、Architecture、Gherkin、Mocktest 和 Vibe Coding 只作真实 producer/consumer 读取，不改写其 canonical Schema 或历史运行证据。
- Leaf Gate 不是 Mocktest 报告的修复执行器：FAIL/WARNING/BLOCKED/ERROR 必须返回 Architecture/验证层闭环；只有最新修复版本完成 revalidation 后才准入 Leaf 判断。
- “统一最终格式”覆盖 JSON envelope/schema、Markdown 章节、decision evidence、proposed children、manifest、键/数组顺序、空集合和 hash；不同业务内容不得改变结构。
- 不以共享 run ID 代替 artifact lineage；不以 strict audit PASS 代替 Mocktest business PASS；不以 Leaf STOP 代替 Coding/Integration PASS。

### Phase 27: Canonical 主链最小接通与遗留入口删除

- [x] 冻结根编排器与五个 canonical producer 的最小 adapter contract，禁止新增第二套业务 schema
- [x] 新增 canonical stage adapter，将各阶段固定 bundle 转成既有根编排回执
- [x] 修改 RootWorkflow：Mocktest 非 PASS 按 next action 路由修复/重验，不再立即错误终止
- [x] 对齐 Leaf v2 的 `child_node_id`、`next_action`、bundle hash 与 Coding admission
- [x] 让递归 child 使用父 PRD + 当前 Architecture 的 Derive 输入，不再退化成无所有权的 root requirement
- [x] 删除旧 `scan_leaves` 对 `leaf-gate.report.json`、自动 traceability/risks 和旧 Markdown 契约的依赖
- [x] 保留 Coding/backfill/integration 人工门禁；没有真实 executor 时 fail-closed，不伪造 PASS
- [x] 增加 deterministic adapter/repair-loop/Leaf-to-Coding/recursive-derive 回归并执行相关测试
- [x] 更新工作流总文档、findings、progress，明确真实可运行边界
- **Status:** complete

## Phase 27 Boundary

- 只修改主链接线、Vibe Coding consumer 和必要测试；不重构已稳定的 PRD/Architecture/Gherkin/Mocktest/Leaf 内部模型。
- 只保留一个 canonical adapter 层；删除已被 v2 替代的旧文件发现与字段别名，不新增兼容旁路。
- 不自动修改 Architecture 或 Feature；修复步骤必须由显式 Architecture repair command 完成，并保留前后 hash 与 revalidation receipt。
- 不自动批准 matrix、leaf completion、contract change、backfill 或 final gate；缺少生产 Coding/Integration executor 时必须 fail-closed。

### Phase 28: Mocktest 全目录无损清理

- [x] 建立包含隐藏项、大小、类型、更新时间和目录归属的完整 inventory
- [x] 读取运行入口、Skill、配置、Schema、源码、测试和文档，建立运行必需依赖边界
- [x] 识别缓存、临时目录、重复副本、废弃入口、历史运行证据和用户数据，逐项记录删除依据
- [x] 先执行清理前 baseline；只删除可重建且无运行/引用依赖的内容
- [x] 删除后执行 CLI、单元测试、compileall、schema/config/preflight 与 stale-reference 检查
- [x] 输出保留/删除/未删除清单，并更新 findings、progress 和总计划
- **Status:** complete

## Phase 28 Boundary

- 历史 strict run、`.work` 证据、用户报告、业务 Feature、真实审批和凭据默认视为受保护内容；除非能证明只是缓存或空壳，不删除。
- 不通过删测试、放宽 gate、修改 Feature 或伪造依赖来获得 PASS。
- 删除目标必须满足：可重建、无源码/配置/文档引用、不是发布必需文件，并有清理后回归证据。
