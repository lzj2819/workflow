# Task Plan: VeriLayer 四人十天完整 Vibecoding 实施计划

## Goal

基于仓库真实状态，交付一份不修改代码、可由四人直接执行的十天实施、实验和论文协作计划，覆盖冻结的 P0、C0-C5、真实 Coding/Test/Integration 闭环、Go/No-Go 与降级策略。

## Current Phase

Phase 13

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

- [ ] 记录 `tutor/` 只读源的排除 `.env` 元数据指纹
- [ ] 建立不覆盖原始包的清洁副本
- [ ] 生成内容、排除、secret、绝对路径、hash、收件人和资产清点报告
- [ ] 对副本和源目录执行验收并提交 B/C/D 复核交接报告
- **Status:** in_progress

## Phase 13 Boundary

- 范围仅限 `team-delivery/` 的 package-sanitation，不开始 Day 1 合同开发。
- `tutor/` 为只读归档；绝不读取、显示、复制或输出 `tutor/tutor-app/.env`。
- 不修改业务代码、历史报告、原始测试结果、原始 Git、Adapter、Executor 或根编排器。

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

## Notes

- 本阶段只创建计划文档，不修改业务代码。
- 所有尚未存在的新文件位置必须明确标为“拟新增”。
