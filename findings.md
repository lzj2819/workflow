# Findings & Decisions

## 2026-08-02 — Phase 25 Mocktest initial scope

- 本轮目标是把 Mocktest 从“多入口、多中间格式、解析器硬编码驱动的 strict 工具”收敛为可解释的 canonical validation pipeline；不能靠放宽语义校验来减少提取失败。
- 前序已冻结 producer contracts：Architecture 使用 `architecture/v2` 且 Top-Level/Decompose 共用 envelope；Gherkin 使用 `testcases/v2` + deterministic `feature/v2`。Mocktest 应优先直接消费机器权威，Markdown/旧 Feature 只作为版本化兼容输入。
- 记忆提示三个高风险事实需从当前 checkout 复核：入口/合同普遍 unresolved 常来自 parser/header/alias 假阴性；零 hop blocked 也必须形成完整诊断证据；execution/audit/business result 必须分栏。
- 修改范围只在 `mocktest` 和根文档；历史 `.work`、user 报告、冻结 Architecture/Feature 与其他流程代码保持只读。
- 排除 cache/.work 后，当前 `mocktest` 是 73 个项目自有文件、850,276 字节：`.agents` 13 文件/396,697 B，`src` 49 文件/403,793 B，schemas 6、config/examples 各 1、README/pyproject/env 各 1；57 个 Python 文件构成绝大多数逻辑。
- Council 复述门中 Feynman 将目标压缩为“适配器—语义门禁—规范化发布器”，Ada 将核心抽象为版本化 importer + canonical IR + 稳定序列化 + 状态代数；二者均明确只能消除形状噪声，不能猜合同。
- 当前 Mocktest 自带的 Architecture schema 仍锁定 `architecture/v1`，而上游机器权威已经是 `architecture/v2`；上游 v2 同时暴露 projection（`components/interfaces/dependencies/modules`）和完整 `payload.nodes/contracts/runtime_flows`，因此新 importer 应优先读完整 payload，并用 projection 做一致性校验，而不是回退解析 Markdown 表头。
- 当前 Gherkin 上游的机器权威是 `testcases/v2`，其 Feature 明确是 deterministic `feature/v2` 视图，且固定 tag/场景顺序、禁用 Background/Outline/DocString/DataTable。Mocktest 若只接收旧 `testcases/v1` 或从自然语言猜入口，就会在 producer 已提供 `tc_id`、`acceptance_contract_id`、`requirement_ids`、有序 steps 时丢失身份和顺序信息。
- 初次 schema 读取暴露了文档/实现命名漂移：Skill 中描述的 formal input/output 概念没有同名 schema 文件；实际六份 schema 是 `architecture`、`testcases`、`mocktest_input`、`mocktest_report`、`leaf_gate_evidence`、`execution_log`。本轮必须以一个 registry/allowlist 消除“文档名、文件名、写盘名”三套叫法。
- 六份现行 schema 本身也混合了两代 envelope：`mocktest_report`、`execution_log`、`leaf_gate_evidence` 同时重复保留 `identity/coverage` 与顶层 project/node/scenario 字段，`execution_log` 甚至并列 `started_at/finished_at` 和 `start_time/end_time`。这些不是兼容层，而是同一产物内部的重复事实源，必须在 v2 中删除。
- `mocktest_protocol.py` 是这些混合 schema 的生成源：其 Pydantic 模型继续只接受 `architecture/v1`、`testcases/v1`，并把兼容性、身份、报告、Leaf evidence、execution log、Markdown 发布和退出码挤在一个约 42 KB 模块中；`validator/report_assembler.py` 与 `improvement/report_renderer.py` 又维护另一套 `ValidationReport`/Markdown 语义。报告统一必须先确立唯一模型/派生器，再把旧 renderer 降为明确的 legacy adapter 或删除。
- 旧报告路径用自然语言关键词把 LLM 建议反推为 top-level/module scope，并把未知维度兜底成业务缺陷；这种文本启发式不能作为 canonical finding 的事实来源。v2 finding 必须携带显式 `category/origin/scope/evidence_refs`，解析/工具问题不得映射成 architecture defect。
- Council 三轮最终加权票为 3.5/3.5（通过阈值 2.333），三位成员共同 dealbreaker 是 `AMBIGUOUS|UNBOUND` 不得被猜测成 strict PASS。独立主席采纳 schema-first 渐进迁移：本轮可删除已经被公共 `$defs` 取代的重复 schema 和无人依赖的项目补丁，但 driver/StepMapper/GapDetector/renderer 必须先成为显式 legacy adapter，待兼容语料 shadow 等价后物理退役。
- 已落地的 v2 输入适配不再从 Feature 文本猜组件：它以 testcase requirement IDs 连接 Architecture v2 runtime flow 的 requirement IDs，并要求唯一首步 contract/component；0 个候选为 `UNBOUND`，多个候选为 `AMBIGUOUS`，仅唯一候选为 `BOUND`，每个候选保留 JSON 字段路径 provenance。
- 新公共 schema `mocktest-run.schema.json` 集中定义 normalized input、extraction、plan、events、contract check、validator results、audit、正交状态、report、Leaf evidence 和 bundle manifest；原先重复维护的 Mocktest 内部 Architecture/Testcases v1 normalized schema 已删除，上游 Architecture/Testcases schema 仍由各 producer 所有。
- Canonical delivery 固定为五个文件：`mocktest_report.json`、纯视图 `mocktest_report.md`、`leaf_gate_evidence.json`、`execution_log.json`、`bundle_manifest.json`。所有状态由同一 result 派生；中间态即使 BLOCKED/ERROR 也先物化固定空集合，避免 zero-hop 没证据。
- `mocktest-input/v2` 已解除错误的跨流程 run ID 等值约束：Architecture/Testcases 的 producer run ID 与 Mocktest execution run ID 独立，project/node/parent/source PRD lineage 和 artifact hash 才是跨阶段身份约束。
- `input_fingerprint` 已排除绝对文件路径和 Feature 视图路径；同一输入复制到不同目录时保持相同。最终报告用无路径 `source_artifacts` 保存 producer artifact ID/schema/hash。
- 当前 Leaf Gate 正式读取器仍要求旧 common envelope、共享 run ID 和顶层 `status/defects`；本轮按边界未修改它。工作流总文档已明确 `mocktest-report/v2` 的 Leaf consumer adapter 属于下一阶段，不能宣称全链兼容。


## 2026-08-02 — Phase 24 PRD-to-Gherkin initial scope

- 本轮目标不是只统一缩进或关键字，而是让当前 canonical PRD v3 成为 Feature 的唯一产品事实来源，并用可执行模型固定场景、步骤、tag、证据与 testcase trace。
- 记忆只提示核对真实 adapter、严格区分生成/结构验证与 Mocktest strict；所有 Gherkin 当前实现、格式与下游兼容事实必须在本轮从实际文件重新验证。
- 用户授权删除具体重复/不合理内容，但范围只在 `prd-to-gherkin`；现有业务运行生成的 `.feature`、Mocktest 报告和其他流程文件保持只读。
- 排除 `.git`、`node_modules` 和缓存/构建目录后，`prd-to-gherkin` 当前只有 10 个项目自有文件、93,293 字节：1 个主 Skill 文档、3 个 YAML ontology/schema、1 个 composition 文档、3 个 Node 脚本及 package/lock；当前没有 tests、canonical testcase Schema、generator CLI 或固定输出模板目录。
- Council 自动选择 Aristotle/Ada/Feynman 三席，Ada 作为最贴合“形式化变换/确定性 formatter”的领域权重席预先锁定为 1.5×；Meadows 继续作为不参与三轮的独立主席。
- `prd-to-gherkin` 自身是 Git 仓库且工作树已有大量用户删除、`scripts/validate_feature.mjs` 修改、`scripts/feature_semantic_markers.mjs` 未跟踪；本轮必须把这些当作既有用户状态，不能 reset/checkout 或复活历史产物，涉及 validator 时只做精确增量修改。
- `skill3.md` 用 535 行规定 8 个阶段，反复维护 FACT/Ontology/IR/Derivation/Test Obligation/Coverage Graph/Test Condition/Feature 多层模型；它仍把“原始 PRD 稳定行号 + 自建 Requirement Model”作为主输入，没有把 canonical PRD v3 已提供的 requirement、acceptance contract、oracle ledger 和 evidence 作为直接合同，存在重复解析、重复冻结和第二事实源。
- 当前文档已经提出若干正确不变量：EXPLICIT/VALID_DERIVATION 才能权威化、英文关键字、TC↔Scenario 一一对应、Outline 数据行不可隐藏、Gherkin 只机械渲染、结构验证不等于语义正确。这些应保留，但迁移到短小的 canonical contract 和 executable validator，而不是继续埋在八阶段 prose 中。
- 当前交付仍是 `[module].feature + requirement-model.yaml + quality-report.md`，没有固定 testcase JSON、manifest、execution log 或原子 writer；不同运行可改变 YAML 键、Feature header/tag 顺序和报告章节，无法保证“格式相同、内容不同”。
- `validate_requirement_graph.mjs` 进一步把输入强制建模成 `SOURCE → REQUIREMENT_GROUP → CLAUSE → FACT → REQUIREMENT_IR → TEST_OBLIGATION → TEST_CONDITION → SCENARIO` 八层覆盖图，并额外要求 ontology、pattern candidate 与 composition；这与 PRD v3 的 requirement/acceptance contract/evidence/oracle 重复。
- 旧 graph validator 的五个 coverage 比率只验证“图上可达”，并不证明 actor/precondition/trigger/response/oracle 被 Feature 忠实表达；内置 self-test 也未覆盖 PRD v3、确定性排序/渲染或 Mocktest 消费。
- `scenario_compositions` 把跨 TC bridge 纳入默认主链，虽要求 evidence，仍扩大了发明桥接语义的表面积；确定性主链应以 PRD 中已有 Acceptance Contract 为边界，不默认组合。
- Council Round 1 的 Aristotle 席确认旧两个 validator 甚至依赖不同的 requirement-model 形状，且状态枚举、REQ 身份包装、Feature metadata/tag/排序/转义均未统一；其建议是 canonical testcase JSON 唯一派生权威、Feature 仅机械视图、Mocktest strict 独立判定。
- `validate_feature.mjs` 的前半段再次证明旧模型分叉：它不消费 graph validator 要求的 semantic/coverage graph，而改为 `requirement_groups + requirement_ir + derivations + acceptance_criteria + test_conditions + scenario_compositions + open_decisions + baseline`。
- 该脚本自己用正则解析 Scenario/tag/Examples/step，同时只借官方 parser 做语法检查；手写解析器还接受中文关键字、Scenario Template/Example 等多种变体，与 Skill 声称“英文关键字、统一输出”冲突。
- Test Condition 同时支持 SCENARIO/SCENARIO_OUTLINE、placeholder/columns/rows/evidence，多处重复检查数据形状，但没有一个 JSON Schema 固定整个模型，也没有 renderer 确保模型与 Feature 同源。
- Feature validator 后半段只把同 phase 的多步用中文分号拼接后与一个 template 字符串比对，无法严格保留每个 Given/When/Then 的顺序与身份；tag 只查存在性，不查唯一固定顺序，Scenario 标题和排序也未锁定。
- 组合规则发生直接冲突：composition 文档/Skill 要保留组件 TC trace，而 validator 要求 `@COMP-*` 场景不得有任何 `@TC-*`；这不是风格问题，而是两份规范无法同时满足。
- 结构输出虽在 `validator_scope.does_not_prove` 正确声明不证明 PRD 语义，但顶层仍使用泛化 `deterministic_gate: PASS`，容易被下游误读为严格业务 PASS；新合同必须把结构结论与 Mocktest strict 状态分栏。
- Ada/Feynman Round 1 分别从形式化确定性与真实消费者角度独立确认：Mocktest 会按 Feature 场景顺序重编号且只消费首个 Examples，因此 Scenario 排序与“恰一 Examples”属于真实接口合同；两席均要求以 canonical testcase JSON + 字节级重渲染一致性替代旧多图/YAML主链。
- 现有 `validate_feature.mjs` 的工作树差异仅是把 UNKNOWN 检查抽到未跟踪 helper，并放行引号内 UNKNOWN；这是本轮开始前的用户改动，后续若收敛 validator 必须保留其“协议字面值不误报”的意图，同时把 helper 纳入受测/可交付文件或迁移到新 canonical validator，不能让未跟踪依赖悬空。
- canonical PRD v3 Schema 已明确给出直接编译所需输入：固定 `prd/v3` envelope；`document.ready_for_test_generation`/`oracle_blocked_count`；current requirement 的稳定 ID/source_kind/evidence；Acceptance Contract 的 actor/preconditions/trigger/response/oracles/boundaries/exceptions 与 NFR 测量字段；oracle ledger 的 ready/blocked/excluded。旧 FACT/IR/AC 重建不是缺失数据的必要补偿。
- PRD Schema 也暴露一个必须 fail-closed 的边界：functional 与 NFR 共用 Acceptance Contract 形状，但 NFR 可能主要依赖 population/window/unit/threshold/pass_rule，不能强行伪装成单一交互式 Given/When/Then；新 testcase model 必须保留 scenario kind/结构化步骤或阻断不可无损映射。
- Council Round 2 已出现有价值分歧：Ada/Feynman 均反对把 strict execution 作为生成 bundle 的必需件，认为它应是下游证据；Feynman 还质疑新增 AC/SOURCE Feature tags 的真实 Mocktest 兼容必要性，并要求多前置、多响应/NFR 的映射算法显式、不可映射即 `GENERATION_BLOCKED`。
- PRD canonical builder 已按 ID 稳定排序 requirements/contracts/metrics，且 `canonical_json_text` 固定 UTF-8 JSON + 2-space indent + LF；Gherkin 应继承此顺序，不再从 Markdown 行号重建身份。
- PRD ready 语义门已经覆盖 PASS、approved/complete、ready flag、无 blocked ledger、无 blocking questions；Gherkin importer 应直接调用/等价复核这些条件，并对 source JSON 做 canonical-byte hash，避免再造 `baseline.status=FROZEN`。
- PRD 的 gherkin consumer profile 目前只验证 current requirement 是 atomic、有 evidence 且 PRD 不提前含 Feature/Given 等字段；它没有证明每条 current requirement 都有 ready ledger/Acceptance Contract，也没有证明 contract 可无损转成步骤。因此真正生成器仍需补 Acceptance Contract 级 fail-closed mapping。
- 真实 Mocktest `GherkinParser` 忽略 `# SC-*` 作为内部 ID，按 Feature 中出现顺序生成 `SCENARIO-001...`；因此 canonical scenario 排序是身份稳定性的硬接口，不只是美观。
- Mocktest 支持 Background、多步骤和 Scenario Outline，但 Outline 只读取第一个 Examples block；`ExamplesExpander` 再按 scenario 位置和 row 位置生成 TC ID。故生成器应默认无 Background、每个 Outline 恰一 Examples、固定行顺序，并用 loader 回归锁定位置语义。
- Mocktest 仓库已经声明 `testcases/v1` JSON Schema；新 Gherkin 流程不能复用同名却定义异构 schema，下一步必须完整核对并选择兼容、版本升级或显式不同 artifact schema 名称。
- 完整核对后，Mocktest 的 `testcases/v1` 只是一个 normalization envelope：`testcases` 项内容完全开放，且 envelope 采用 `schema_version=testcases/v1`、`status=COMPLETED`，与本工作流统一的 `schema_version=1.0 + artifact_schema_version=... + PASS/FAIL/ERROR` 不同。新 producer 应使用不冲突的 `testcases/v2`；当前 Mocktest 兼容路径走确定性 `.feature`（`testcases-source/v1`），未来再显式升级 JSON adapter。
- PRD-generation 没有仓库内现成 canonical PRD JSON 样例，唯一 fixture 在 Python 测试内构造；Gherkin repo 需要自带完整 `prd/v3` 示例，不能依赖上游测试实现细节。
- Council 主席有条件采纳 canonical-testcase-core，并裁决 generation bundle 排除 strict execution、Feature 只保留 `@REQ/@TC`、TO 收敛为每 TC 内的最小证据引用、composition/Outline 默认禁用。主席建议的 `testcases/v1` 已被本轮随后完成的真实 Mocktest Schema 核对修正为 `testcases/v2`，这是事实驱动的版本避冲突，不改变其核心裁决。
- 固定输出合同已落为五件：`testcases.json`、`testcases.feature`、`testcases_manifest.json`、`validation_report.json`、`quality_report.md`；成功包不含 execution，结构状态仅 `STRUCTURE_PASS|FAIL`。
- 已删除旧 authority-path 的 graph validator、三份 ontology/pattern/coverage YAML 和 composition 规范；旧 `validate_feature.mjs` 从 972 行双模型手写校验器收敛为读取 `testcases/v2 + feature/v2` 的兼容 CLI，并继续复用预存 UNKNOWN marker 处理意图。
- 当前机器只有系统 Python 3.14，未安装 `gherkin`，三个已知项目虚拟环境路径均不存在；因此“真实 Mocktest Python loader”仍需通过可用项目环境或安装锁定依赖完成，不能把 Node 官方 Gherkin parser 测试冒充该项证据。
- 进一步检查发现 uv 本地缓存已包含 `gherkin-official 24.1.0` 和 Pydantic 包内容；可以使用 `uv --offline` 构建临时验证环境，不需要联网或修改 Mocktest 仓库。
- 直接 `uv run --offline` 仍因沙箱不能在全局 uv cache 内创建内部状态文件而失败；已定位缓存中解包后的 gherkin、pydantic、pydantic_core、typing_extensions、typing_inspection、annotated_types，可通过只读 `PYTHONPATH` 组合运行真实 loader，避免复制/安装依赖。
- Mocktest 包的 `__init__` 会在加载 Gherkin parser 前级联导入 YAML 和 Rich；第一次只读 PYTHONPATH probe 暴露缺 PyYAML，补入缓存后又暴露 Rich。对应 Rich/markdown-it/mdurl/Pygments 缓存路径均已定位；这些是消费者环境依赖发现，不是 Feature 语义失败。
- 真实 sibling Mocktest `mock_framework.loader.GherkinParser` 已对新 formatter 生成的 Feature 执行成功：4 个场景，按位置产生 `SCENARIO-001..004`，无 Background/Examples，每场景恰一 `@TC`、至少一 `@REQ/@NFR`，且多 Given/Then + 固定 And + 恰一 When 均被保留。
- uv cache 还包含 jsonschema 4.26.0 及 Python 3.14 对应依赖，可对生成 `testcases.json` 做独立 Draft 2020-12 Schema 验证，不需要把 Ajv 加入生产依赖。
- Phase 24 最终链为 `prd/v3 → testcases/v2 → feature/v2 → Mocktest`；`testcases/v2` 避开 Mocktest 既有 `testcases/v1` 同名异构，Feature 是当前直接兼容投影。
- Feature v2 固定三行 metadata、一个 Feature header、逐 TC 的 SC/AC 注释、`@REQ/@NFR → @TC` tag 行、Scenario title 与有序 Given/And/When/Then/And；Background/Rule/Outline/Examples/DocString/DataTable 全部禁用。
- 生成器固定展开 functional main/boundary/exception 和 NFR measurement；所有 business text 只来自 PRD contract 字段并 NFC/单空格规范化。缺字段、blocked oracle、阻塞问题、非 current ref、未决 UNKNOWN/HYP 都 fail closed。
- 最终验证：7 个 Node 合同测试 PASS；17 个项目自有文本/JSON 文件无 CRLF；0 个 stale old-validator 引用；独立 JSON Schema PASS；真实 Mocktest loader PASS（4 scenarios）；临时 probe 已精确删除。


## 2026-08-02 — Phase 23 Architecture Generation final outcome

- Council 最终加权表决为 `dual-profile-contract-core=3.5/3.5`：一份 canonical Architecture 核心，两种显式 authority profile；独立主席结论已落盘到 `prd-to-artecture-skill/COUNCIL_REFACTOR_REPORT.md`。
- `architecture.json` 已成为唯一机器权威，`artifact_schema_version=architecture/v2`；Top-Level 与 Decompose 共享完全相同的 envelope、payload 键、12 节 renderer 和固定五件 bundle。
- 旧顶层七份 Markdown、递归七份 Markdown、workbench 和重复英/中文 reference 不再是输出规范；兼容 Skill 只负责路由到根 `SKILL.md`，避免继续形成多事实源。
- Top-Level 直接子节点强制 `MOD-*`；Decompose 只允许 `CMP-*`/`SUB-*`/`ADP-*`，并要求 current PRD node、exact target、parent depth+1、ready parent、immutable snapshot 和 boundary fingerprint 全部一致。
- 父变更不是第三种成功模式：仅 Decompose 可生成 `FAIL/draft/not-ready` 阻塞包，并在固定五件之外添加 `parent-change-request.md`；报告不会再虚称全部 consumer profile 已通过。
- 下游兼容投影已固定：PRD Derive `modules`；Mocktest canonical/Markdown table；Leaf `components/interfaces/dependencies/depth/complexity/risks`；Vibe receipt 保持 adapter-owned；Gherkin 明确为并行分支。
- 实际验证为 Anaconda Python 下 compile/Schema PASS、10/10 unittest PASS，覆盖双 CLI 同形、Schema/语义/profile、输入重排、Top→Module→Component 递归与祖先契约继承、parent mutation fail、PRD Derive、真实 Mocktest parser、真实 Leaf Gate 和 parent-change stop。
- 这些证据证明 producer contract 与相邻消费者兼容，不证明一次具体业务的 Mocktest strict PASS、Leaf 决策、Coding 或全流程 E2E。

## 2026-08-02 — Phase 23 Architecture Generation initial scope

- 用户明确要求同时保留两种生成模式：Top-level 系统架构，以及针对单个父模块/组件继续向下细分的 Decompose 架构；本轮不能把两者合并为含糊的单模式生成器。
- 统一目标初步冻结为“同一 canonical Architecture 模型 + 两个显式 profile”，而不是两套独立 Markdown 模板；是否可行必须以现有实现和下游契约审计为准。
- 上一阶段已落地 canonical PRD v3，因此 Architecture 新入口应直接校验其 `architecture` consumer profile，禁止继续依靠自由文本猜测 PRD 字段。
- 记忆中的完整运行资产、单一事实源和受控集成经验仅用于审计路线提示；所有 Architecture 事实都必须在当前目录重新验证。
- Architecture 目录只有 21 个项目自有文件、约 82 KB，没有 vendor/cache 排除项；内容全部是 Skill、Markdown 参考和两个 `agents/openai.yaml`，没有实际生成 CLI、canonical model、JSON Schema、validator 或 tests。
- 当前事实上是两套独立流程：Top-level DDD skill 交付 `output/README + 01..06`，同时保留 8 个 DDD 工作产物和 `architecture-workbench.md`；Decompose skill 交付 `architecture-manifest.yaml + 01..05 + child-handoff.md`，必要时另写 `parent-change-request.md`。两套最终文件名、章节、状态、版本和身份契约完全不同。
- Top-level Module 工作表只有 `Module` 显示名称，没有强制稳定 `node_id`，但 Decompose 又要求用 `target_node_id` 精确匹配父节点；因此现有 Top-level→Decompose 在身份层天然断链，只能依赖 migrate 名称回退。
- Top-level 规则把系统级 DDD、M1-M6 映射、Key Decision Queue 与最终输出重复写入多份 Markdown；没有机器事实源，因此 workbench 与 7 个最终文件可能漂移。
- Decompose 的方向性边界是合理的：父包是绑定合同；只允许在单个目标节点内部细化；父职责、跨节点契约、状态所有权、技术/部署边界改变必须创建 parent-change request 并停止。
- Decompose 的 `mode=new|revise|migrate` 是写入/迁移操作模式，不等于用户要求的架构生成模式；新契约必须避免继续用同一个 `mode` 字段表达两类不同概念。
- 英文与中文 `SKILL`/reference 成对复制同一规范，中文版本更短且有细节删减；这不是可靠的双语单源，会随修改产生行为漂移。规范应只保留一个权威版本，另一语言只作非规范说明或由同一模型生成。
- 顶层 `agents/openai.yaml` 在 UTF-8 读取下已是乱码，说明现有元数据本身不可可靠分发。
- 初步架构：共享 `architecture/v2` canonical envelope/payload/renderer/bundle；以 `architecture_mode=top_level|decompose` 表达权限域，以另一个 `operation=new|revise|migrate` 表达写入/迁移；两个 profile 共享字段全集与章节顺序，但拥有不同 required/forbidden invariants。
- Gherkin 当前没有读取 Architecture 的直接代码/契约命中，符合它与 Architecture 并行生成的关系；直接下游应表述为 Mocktest 和 Leaf，不能把 Gherkin 误列为 Architecture 消费者。
- Mocktest 同时接受 Markdown 目录、manifest 包或 `architecture/v1` JSON；但其 `architecture/v1` 只是 `source + requirement_ids + architecture: {}` 的 normalization wrapper，内部 architecture 没有语义 Schema，不能充当新生产者的 canonical Architecture 契约。
- Mocktest 的递归包读取器兼容多种 manifest key，并会在缺少 `target_node_id` 时回退到显示名；这证明历史输入兼容存在，但新 Architecture 输出必须提供精确稳定 ID，不能依赖该宽松回退。
- Leaf Gate 会优先发现 `architecture.json`/`architecture.md` 或 `architecture/`、`output/` 目录，并区分 primary/validation/supporting/remediation；新 bundle 可以在不修改 Leaf 的情况下被发现，但仍需真实 profile test 证明文件选择正确。
- canonical PRD 的 Architecture profile当前只保证 problem summary、scope 和至少一条 current requirement；Architecture 自身还必须校验 `source_prd_id`、node identity、requirement allocation 和所有跨引用闭合。
- Council Round 1 三席独立读完同一 21 文件，并分别从领域、形式化和运行证据得出同一硬边界：Top-level 拥有系统边界/模块/跨模块契约/部署；Decompose 只拥有一个父节点内部，越界必须 parent change + stop。
- 三席共同指出新格式不能直接复用 Mocktest 的 `architecture/v1` normalization wrapper；应使用共享 envelope `1.0` + Architecture payload 版本，并通过显式 adapter/profile 与 Mocktest 现合同衔接。
- Feynman 提出的最小可证伪链可作为首个端到端合同测试：一个 canonical PRD v3 → 一个稳定 Module ID 的 Top-level 包 → 选中该 Module → 一个子节点的 Decompose 包；两次输出必须共享 Schema/章节/bundle，且父契约不变。
- Council Round 2 修正了实现顺序：`authority_scope`、状态机和父字段级 mutation policy 必须先于原子 writer；`architecture/v2` 在真实 contract tests 通过前仅是候选版本。
- Round 3 加权表决 `dual-profile-contract-core=3.5/3.5`，超过 2/3 阈值；两项 dealbreaker 是 Decompose 仍可越权，或缺少可执行 validator/真实链路测试。
- 固定成功包确定为五件套：`architecture.json`、`architecture.md`、`architecture-manifest.yaml`、`validation_report.json`、`execution_log.json`；父层变更阻塞时仅额外增加 `parent-change-request.md`，但整个包保持 FAIL/draft/not-ready。
- 新 canonical payload 将 consumer projection 与业务模型分开：Leaf 所需 `components/interfaces/dependencies/depth/complexity/risks` 位于 envelope 顶层且必须与 payload 派生一致；Mocktest/Vibe 的专用包装由 manifest/profile/adapter承担，不反向污染核心。


## 2026-08-02 — Phase 22 initial scope

- 用户要求先完整理解六段工作流及总文档，再只对 `prd-generation` 做彻底重构。
- 本轮的关键验收不是“生成一份看起来一致的 PRD”，而是把稳定格式落实为模板、schema、生成规则与可执行验证，确保下游 Architecture/Gherkin 获得确定性输入。
- 其余流程当前仅作为接口消费者和约束证据，不默认授权修改。
- 目标目录当前规模：`prd-generation` 39 文件/约 293 KB；`prd-to-artecture-skill` 21 文件/约 82 KB；`prd-to-gherkin` 735 文件/约 27 MB（含 `.git`、Node 依赖与生成/供应商内容）；`mocktest` 197 文件/约 2.35 MB；`leaf-gate` 19 文件/约 292 KB；`vibe coding` 71 文件/约 589 KB。
- 根 `CLAUDE.md` 将流水线定义为 PRD → Architecture/Gherkin 并行 → Mocktest → Leaf Gate → Vibe Coding，并规定跨阶段 canonical envelope；但模块内部 schema 尚未统一，这正是 PRD 输出契约需要解决的上游不确定性。
- 根治理文档明确 `prd-to-architecture-skill` 是 canonical 名称，但当前实际目录仍是拼写错误的 `prd-to-artecture-skill`；本轮需以真实目录读取，以 canonical 名称描述接口，不能擅自移动该下游目录。
- “完整阅读”将覆盖所有项目自有文本、源码、schema、测试与模板；`.git` 对象、`node_modules`、`__pycache__`、`.pyc` 等供应商/缓存/二进制内容按文件清单与类型审计，不把其逐字节内容误称为流程设计。
- 《工作流总文档》把 PRD 的正式输出写成 `prd.md + prd.json + prd_manifest.json + validation_report.json + execution_log.json`，阻塞时另有 `blocking_questions.json`；正式交接要求 `status=approved`、`ready_for_test_generation=true`、Oracle ledger 零 blocked、独立审查通过。
- 下游契约的关键矛盾已显现：总文档一方面把 `prd.md` 及稳定行号作为 Gherkin 的精确证据源，另一方面又以 `prd.json` 作为 Leaf Gate 四件套之一；如果 Markdown 模板和 JSON 模型没有同源生成、版本化 schema 和 hash 绑定，就会产生“双重事实源”。
- Architecture 消费者需要原子功能/NFR、稳定 ID、证据引用和完整 acceptance/NFR contracts；Gherkin 消费者进一步要求不得把 UNKNOWN/HYPOTHESIS/CONFLICT 静默权威化。统一 PRD 不能只是固定 Markdown 标题，还必须固定机器语义与证据状态。
- `vibe coding` 的根编排器通过 `module-result.json` 接收可替换模块输出，并要求 run-scoped identity/hash；因此 `prd-generation` 的 canonical 输出还需明确 module result 如何引用整套 PRD bundle，而不是仅写单个文件路径。
- `vibe coding/AGENTS.md` 要求不得推进示例运行状态、不得跳过人工门、共享契约变化必须停手。本轮是上游技能维护，不会执行或推进现有 Vibe Coding state。
- 实际 PRD assembler 只输出 Problem Statement、Requirements、架构输入、Success Metrics、Acceptance Contracts/ledger，缺失规范声明的独立 Scope、Future Backlog、Risks/Dependencies/Blocking Questions、Agent Review 等稳定顶级章节；某些章节仅在有内容时出现，直接导致不同需求产生不同结构。
- `prd.json` 当前由 `_structured_prd_model` 同时展开 legacy `P1..P6` 和 canonical 字段，形成重复语义与潜在冲突；它也没有 JSON Schema。输入检查只做浅层类型检查，不验证必需字段、枚举、唯一 ID、证据类型或固定键集合。
- 当前 `prd-generation` 把 `schema_version=2.0` 同时用作 PRD 内容版本和跨流程 envelope 版本；正式 Leaf Gate 则硬性要求 envelope `schema_version=1.0`，并要求 `depth/max_depth/node_history/requirements`。现有 PRD sidecar 缺少这些 Leaf profile 字段，无法直接进入正式 Leaf Gate。
- 已有 common envelope 只要求 `schema_version` 为非空字符串，而 Leaf Gate 的 profile 收窄为 `1.0`。重构应保持既有共享合同：输出 envelope `schema_version=1.0`，另设 `prd_schema_version=prd/v1` 表达 PRD 内容 schema，避免两种版本语义继续混用。
- Derive 的父 PRD parser 依赖固定 Markdown 标题和 bullet/metadata 语法；新 renderer 必须保留这些可解析形式，或同时更新 parser 并用 Root→Derive contract test 证明兼容。本轮将优先保留兼容语法并消除可选顶级章节。
- 现有 Root 文档声称 R1–R8/Oracle Closure，但 CLI 实际只有 P1–P5 粗粒度收集；歧义检查发现问题后允许用户选择继续，且“完整性类别”写死安全/认证/授权/错误/性能/日志，会对不适用产品产生伪阻断/噪声。这些规则应降为非阻断诊断或由适用性证据驱动。
- Council Round 1 三席分别完整审计了 `prd-generation + Architecture`、`prd-generation + vibe coding`、`prd-generation + Gherkin/Mocktest/Leaf` 的项目自有内容；共同识别 derive-all 丢 sidecar、无 PRD Schema/测试、review hash 时序不稳、Architecture/Gherkin 缺机器入口、source/status/version 枚举混用与 heuristic ownership 风险。
- Council Round 2 明确边界：Leaf 的 `depth/max_depth/node_history` 属于 artifact consumer profile/递归上下文，不进入 PRD 业务 payload；`module-result` 由根编排 adapter 生成，不由独立 PRD CLI 冒充领域产物。
- Round 3 加权表决 `contract-core-strangler=3.5/3.5`，超过 2/3 阈值，无少数反对；dealbreaker 是继续保留多重事实源、静默启发式迁移或没有真实消费者契约测试。
- 实施采用 `schema_version=1.0` 作为现有共享 envelope/Leaf profile 的兼容字段，另用 `artifact_schema_version=prd/v3` 表达 PRD payload 版本；业务 payload 位于唯一 `payload` 对象，Leaf 所需 ID/depth profile 保留在顶层而不污染业务语义。
- 新 canonical renderer 无条件输出 12 个固定顶级章节；缺省内容使用稳定的 `None/TBD/null/[]/false/0` 语义，不再因内容为空而省略章节。
- `run_derive_all_mode` 现要求临时区内五件 bundle 全部存在才写目标，并复制 `prd.md/prd.json/prd_manifest.json/validation_report.json/execution_log.json`，修复此前只复制 Markdown 的违反承诺问题。
- 最终验证已通过 8 项：两组不同需求的 CLI bundle 同构、固定 12 节、输入数组重排字节稳定、Schema/三消费者 profile、非法 mutation fail-closed、Markdown→Derive parser round-trip、真实 Leaf Gate 接收 PRD profile，以及 derive-all 五件套完整交付。
- Architecture/Gherkin 的结论仅是生产者侧 consumer profile 合同通过；两个下游尚未新增直接 canonical importer，本轮也没有执行完整 Architecture/Gherkin/Mocktest/Vibe Coding 链。
- `ruff` 不在当前 Python 环境中，本轮未联网安装；此限制不影响 compile/test/schema 结果，但不能等价表述为 Ruff PASS。

## 2026-07-29 — plan and paper-evidence synchronization

- The active implementation authority is the isolated `.coord-worktree/`; the root-level `vibe coding/` tree remains a historical baseline. Plans and paper claims must name which boundary supplies their evidence.
- Day 3 calibration is complete but has two distinct meanings: CMP is strict-execution-complete with architecture FAIL and downstream block; fresh S1 is strict PASS → Leaf STOP → real Coding → public pytest PASS. S1 passed on its first Coding attempt, so it has `repair=0` and must not be described as a demonstrated repair cycle.
- A repair-capability claim now requires a separate deterministic initial-failure fixture that records pytest failure, repair prompt/input, patch, before/after hashes and final pytest. It is prohibited to alter a successful S1 model output merely to create repair evidence.
- Day 4 evidence is not a completed recursive run: the first root attempt is a PRD-stage system ERROR; the next complete attempt generated PRD/Architecture/Gherkin and then received a Mocktest semantic FAIL. The required response is a bounded Architecture-only correction followed by a fresh validation run; Feature/Gherkin remain frozen for that correction loop.
- Before Day 7 pilot, freeze an RQ/configuration/metric/evidence/figure registry and a sanitized evidence manifest. Raw run directories may stay private when they contain machine paths or private-test material, but their hashes, relative references, version IDs and result summaries must remain auditable.

## 2026-07-30 — all-role Mocktest feedback-loop synchronization

- The prior update covered the main plan and shared four-person guide, but the A–D independent plans lacked a complete owner-to-owner feedback chain. “FAIL must not enter Coding” alone was insufficient because it did not state who fixes what or how validation restarts.
- All task plans now use the same route: `PASS + ALLOW → Leaf`; `FAIL / FIX_ARCH → B modifies only Architecture → C reruns strict`; `ERROR → the responsible owner restores evidence/execution validity → C reruns strict`.
- A owns blocking recursion/backfill and preserving failed runs; B preserves frozen Feature/Gherkin while producing a new Architecture artifact/hash; C publishes the report/classification and blocks Leaf conversion; D rejects every non-PASS/non-current-hash bundle.

## 2026-07-29 — live takeover baseline discovery

- `E:\myprogramfiles\workflow` is not present as a Git worktree on this host, so the reported local-only A commit cannot be reconciled or pushed here.
- GitHub's unauthenticated REST API currently returns `API rate limit exceeded` for this host. This is an access limitation, not evidence that any branch, PR, issue, or commit is absent.
- The browser CDP prerequisite is healthy; a public GitHub page or Git smart-protocol read is the next read-only source without treating the REST failure as repository state.
- Git smart protocol at 2026-07-29 returned these live heads: `main=671d5d3`, `verilayer/a-contract-integration=6d6f266`, `verilayer/b-generation=3cca4a8`, `verilayer/c-validation=3117416`, `verilayer/d-coding-experiments=1407c5e`, `verilayer/d-environment-evidence=8cb3582`, and `verilayer/d-environment-evidence-rebased=2aed7c1`.
- The public GitHub PR list at the same checkpoint shows three open PRs: #3 (B → A), #9 (rebased D evidence), and draft #10 (D → A current-baseline evidence). This supersedes the earlier two-PR screenshot; neither PR existence nor title is treated as merge or verification evidence.
- The active Day 1 checklist in A's `6d6f266` requires only: frozen v0.2 contract; D current-A environment plus freeze/hash and a four-file pytest target; B's existing fixture passing contract validation in that environment; C's three import/`--help` smoke commands. It explicitly defers fresh B output, strict/semantic results, Leaf, Coding, and integration tests to Day 3 or later.
- The current Gate document nevertheless records no project-local `.venv` and labels the current A environment as `ERROR`; this is the immediate executable blocker, not an unresolvable Contract dispute.
- The checked-out ten-day and four-person plans retain the intended dependency: Day 2 production skeleton waits for Day 1 GO; Day 3 is the first allowed strict/Coding calibration. This will be followed rather than repeated through further documentation-only reviews.
- This host exposes only Python 3.14 through `py`, while the Day 1 environment specification requires CPython 3.12.10. `uv` is locally available, so a project-local managed 3.12.10 interpreter is the least invasive candidate for satisfying the frozen version requirement.
- A project-local CPython 3.12.10 virtual environment was created and the frozen five-package input installed. The first four-file pytest attempt was `27 passed, 1 error`, exit `1`: the error is a Windows permission failure while pytest scans the user-level temporary directory, not an asserted test failure. The environment also lacked `pip`, so the required `pip freeze --all` evidence is not yet available.
- The working-tree requirements hash on this host is `464c4c...e76e03` (CRLF checkout); this is the documented noncanonical Windows observation. A prior ad-hoc blob calculation was invalid because PowerShell text decoding altered bytes; all canonical blob checks must use a binary-safe process.
- After adding the environment tool `pip==26.1.2` without altering the frozen project dependency input and setting `TMP`/`TEMP` to a project-local temporary directory, the exact four-file Day 1 pytest target exited `0` with `28 passed in 28.12s`. Binary-safe verification confirms canonical Git blob SHA-256 `f55ab0...ad472`; checkout bytes are the retained CRLF observation `464c4c...e76e03`; `pip freeze --all` SHA-256 is `cc5ba7713301dfbe49be982fb62d6c588e3ea8dae025abc307b3e10291897c44`.
- B PR #3 contains seven proposal/fixture files and explicitly remains fixture-only. Its historical validator record is useful only as a proposal; the current-A frozen-environment Contract validation must be run before the Day 1 item is closed.
- Direct validation of B's two JSON envelopes against the live v0.2 schema failed (exit `1`) for both: `schema_version` is `0.1` instead of `verilayer-artifact/v0.2`, and the required `error` field is absent. This is a concrete, bounded fixture compatibility defect; it blocks only the Day 1 B item and is safe to repair on B's branch. The first content-hash validation also used the wrong repository root and is discarded as invalid evidence.
- B fixture repair is validated in the CPython 3.12.10 frozen environment: both envelopes pass the live JSON schema and canonical `content_sha256` checks (exit `0`), and `tests/test_artifact_contract.py` passes (1 passed, exit `0`). The patch changes only the two fixture files: v0.2 schema version, explicit `error: null`, and recomputed canonical self-hashes.
- C's three Day 1 smoke commands are currently `ENVIRONMENT_ERROR`, all exit `1`, because `mock_framework.config` and the strict driver import `yaml` while the frozen environment input omits PyYAML. This is a genuine dependency-spec defect, not a strict/semantic failure. It must be repaired in A's requirements input, then the input hash, freeze, pytest, B fixture validation, and C smoke evidence must be regenerated on the resulting A tip.
- PyYAML `6.0.2` was added as A commit `a70dd3f` and a clean environment was rebuilt. The new canonical requirements blob hash is `855174e1cd32681fbb9c0f45cd5ff41e2c306f73d0d1db9254ecca03db83966a`; the CRLF checkout observation is `ade5b2a2c7acecab2591f200be3f7dbe614f2a4ab443d6ab810103d5d6c183da`. Four-file pytest again passes (28 passed, exit `0`), but all C smoke commands still exit `1` because `mock_framework.__init__` eagerly imports its logger and the frozen input also omits its declared runtime dependency `rich`.
- After adding `rich==13.9.4` in A commit `2ab9722` and rebuilding, both required C imports pass (exit `0`) and pytest remains 28 passed (exit `0`). The strict driver `--help` still exits `1`, now solely because its eager loader import needs the declared `gherkin-official` runtime dependency. This remains an environment dependency error, not strict execution or semantic evidence.
- The final minimal Day 1 input adds `gherkin-official==24.1.0` in A commit `8766793`. Its binary-safe Git blob SHA-256 is `370d4e7bd1ae9df0ede903ac4741c5f1fd4c02a53b13eb0e732c380a10ba0bc6`; its CRLF checkout observation is `de4f9477b138a00a3c959d33766ef92bff6c03048d06710c59caf4ebb3ca49fb`; freeze SHA-256 is `f7477b69477c9b29ee43f8434d26ad6fa533ab46f3e652cd131b620749d8a288`.
- On that exact A commit, the four-file Day 1 pytest target exits `0` with 28 passed; C's two imports and strict-driver `--help` all exit `0`; and B branch `6272d30`'s two fixtures pass the live A v0.2 schema and canonical content-hash validators (both exit `0`) plus its artifact-contract unit test (1 passed, exit `0`). These are sufficient technical closures for the narrowed Day 1 checklist only. They do not establish strict execution, semantic PASS/FAIL, Leaf, Coding, E2E, or experimental results.

## Day 2 workflow-state finding

- `vibe coding/AGENTS.md` requires the repository-local `layered-vibecode` workflow for implementation work. Its legacy `vibecode/state.json` is at `INIT` with no leaves and no execution log; `next-step` requests `doctor` then `generate-matrix`.
- This legacy state is not a real Day 2 production run and must not be auto-approved or advanced. The Day 2 skeleton can be inspected and tested independently, while any actual root/leaf run still requires its own matrix and human approval.
- `doctor` and `generate-matrix` returned exit `20` because no STOP_LAYERING nodes exist. Generation temporarily mutated the legacy state to `BLOCKED`; that agent-induced state projection is being restored to the original `INIT` form and its generated, untracked files are excluded from Day 2 changes.

## Day 2 code inventory

- The existing `RootWorkflow` already has fail-closed command-adapter validation, dry-run semantics, run-scoped reports, and fixture-only tests. Its only checked-in command configuration is `tests/fixtures/root_workflow/project-config.single.json`; no production `config/`, Adapter package, Executor package, experiment runner, or Day 2 integration tests exist.
- Day 2 therefore needs a minimal production surface, not a root-workflow rewrite: relative command config, module adapter entrypoints that emit structured `ERROR` when real wiring is unavailable, an isolated workspace/pytest/evidence skeleton, and tests proving controlled error and path safety.
- The generated legacy event/matrix files are untracked and will not be staged. Their deletion is blocked by the execution policy, but they do not modify tracked code or the restored state projection.
- Day 2 implementation validation: 11 targeted tests pass; the production configuration validator exits 0 and confirms complete, relative, fixture-free commands; root `run-workflow --dry-run` exits 0; and `guard-paths` exits 0 with no active leaf guard. Dry-run and controlled module `ERROR` outputs are explicitly not execution/E2E success evidence.
- First full suite attempt: 58 passed and one schema-registry test failed because its static filename set omitted the Day 1 v0.2 schema. Review also found two Day 2 adapter-envelope defects before release: uppercase `SYSTEM` violates the lowercase error-category enum, and absolute input paths violate the repository-relative input-artifact rule. Both are corrected with a schema-validation regression assertion.

## Day 3 preflight

- Mocktest bundled preflight exits 0 on the frozen A environment and returns the strict driver path plus a clean secret scan. Leaf Gate `--help` also exits 0.
- The Leaf Gate documentation still describes legacy `child_node_id` in its own output. Any Day 3 adapter must dual-read this legacy field but emit canonical cross-module `node_id`; it must not change the shared v0.2 Contract.
- The architecture package and PRD-to-Gherkin package expose skills/templates and structural validators, not a checked-in production model CLI. Day 3 must therefore establish a real generator binding or stop honestly before claiming fresh generation.
- Local capability check: `codex-cli 0.144.1` is installed, reports a ChatGPT login, and `api.openai.com:443` is reachable. The optional local bridge at `127.0.0.1:15721` is unavailable, so any Day 3 backend must use the CLI's documented direct mode rather than assume a local service.
- Fresh S1 generation attempt 1 exited 0 but failed independent envelope checks; attempt 2 repaired both JSON envelopes and their canonical content hashes (all exit 0). This confirms transport/generation provenance only, not semantic validation.
- After locked `npm ci` succeeded (exit 0) in `prd-to-gherkin`, the S1 requirement-graph validator failed because the generated model lacks `semantic_graph` and `coverage_graph`; the Feature validator failed because the model lacks a frozen baseline/TC graph and the Feature lacks required `SC-*` / `TC-*` trace tags. These are deterministic generation failures, not strict results.
- A second generator repair, constrained by the shipped validator scripts, now passes independent deterministic validation: requirement graph exit 0 (23 nodes, 22 edges, 3 frozen TCs); Feature validation exit 0 (3 scenarios/3 rendered TCs); both v0.2 envelopes also pass schema validation. This is B-stage generation/validator evidence only; strict execution remains unrun.
- First real S1 strict run (`strict-run-20260729-a`) initialized successfully, but `prepare-validators` exits 1 with `semantic_errors.json`: every scenario has unresolved/low-confidence entry component and entry contract. Per strict workflow this run is blocked before validators/finalize; it has no strict-audit PASS and no semantic PASS. The fresh Architecture expression, not the strict tool, needs a bounded entry-binding repair before a new run can start.
- The entry-binding generator invocation timed out after 304 seconds (tool ERROR exit 124), but inspection shows it wrote a bounded architecture repair before timeout: named Note Creation Service entry component, `POST /notes`, `note.create` contract, request/201/422 mapping, and repository interaction. This output is unaccepted until its self-hash/schema and a new strict run independently verify it.

## 2026-07-28 — Phase 13 package-sanitation

- 共享配置与证据仅使用仓库相对路径；本机的 `$veriRoot` 不写入共享文件。
- `tutor/` 是只读归档，尤其不得读取或输出 `tutor/tutor-app/.env`；构建和扫描均按文件名排除所有 `.env`。
- 资产清点必须分别保留 22 个设计节点包、16 套 L2 结构化五件套、17 个实现叶子、12 个 backfill 任务/完成包；这些不表示 16 个完整自动运行。
- 清洁包最终含 1,257 个文件；8 个历史 YAML 配置中的成员本机绝对路径已仅在副本中替换为 provenance 占位符，复扫后 executable configuration 命中为 0。
- secret scan 无高风险真实密钥形态；20 个中风险 credential-assignment 候选只以相对路径记录，待 B/C/D 复核，当前包不标记为可分发。
- backfill 以 12 的基线保留：主历史目录有 11 个已物化 task/completion pair，另有 `backfill-plan.md`；交接文件显式说明此对账差异。

## 2026-07-28 — Phase 14 B/C/D rejection remediation

- B/C/D 确认历史 Tutor 证据在副本中可追溯，差异仅为 8 个已声明的绝对路径净化项；拒绝原因是清洁副本误含 `tutor/tutor-app/data/` 与 `mocktest/.env.example`，以及缺失 A 的 Artifact Contract。
- 本轮删除只能作用于清洁副本；原始 Tutor 归档禁止删除或移动。
- 绝对路径扫描必须扩展到所有可读文本文件和任意 Windows drive/user-home 路径，并且报告只能记录相对文件路径、分类和处置，不回显路径原文。
- Phase 14 最终包为 1,078 文件：删除的两项在副本内为 `mocktest/.env.example` 和 `tutor/tutor-app/data/`；原始 source 仍保留且未删除。
- 新 `vibe coding/docs/ARTIFACT_CONTRACT.md` 是 Day 1 draft，只定义既有 schema 的 canonical envelope/profile/gate，不将未实现的生产执行器表述为已实现。
- 扩展扫描完整报告 29 个 provenance-only 文本路径、0 个 executable configuration 路径；844 个可比较 Tutor 路径无增删，15 个哈希差异均为绝对路径净化。
- B 已确认 Phase 14 清洁包复核通过；审批已记录，但本轮未创建压缩包、未执行任何对外传输、未启动 Day 1。

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

## 2026-07-28 Public GitHub publication finding

- `lzj2819/workflow` 的 Git 推送可用，公开发布应从经批准的清洁副本而非原始工作区进行。
- 已推送的审查分支为 `chore/publish-verilayer-workspace`，提交 `f63fb71`；它相对于 `main` 可快进，但在管理员创建并合并 PR 前不应声称默认分支已发布。
- GitHub App 的读取/仓库权限与 PR 创建权限不一致（创建 PR 返回 HTTP 403）；浏览器会话也未登录，因此该合并动作需要用户在 GitHub 网页完成。
- 公共版本排除 `.env`、`.env.example`、`data/`、缓存、worktree 与第三方参考 PDF；保留源码、计划、测试、结构化工件和协作治理文档。

## 2026-07-29 Day 3 fresh-S1 strict calibration

- Fresh S1 is an independent in-memory `POST /notes` control, not Tutor reuse and not a C0-C5 experiment.
- A clean frozen-environment strict run completed all four real component hops and all three independent validator judgments. Its strict audit was PASS, but the report remained FAIL because `compat.json` correctly exposed missing machine-readable inbound contracts.
- Root causes fixed in the S1 architecture: explicit `note.create.store` provider/consumer binding; explicit Client-to-Service `note.create.request`; parsed `输入/输出` contract fields. The generated JSON envelope content hash was recomputed after each architecture update.
- Root cause fixed in the local strict helper: explicit quoted Given values are now injected into a synthetic setup hop only when they exactly match the resolved entry contract's required-field arity. This is a generic compatibility repair, not a gate bypass.
- Windows path encoding caused formal-artifact publication errors under the Chinese workspace path. `E:\vl` is a junction to the same isolated worktree and is used only as an ASCII execution alias.
- Fresh rerun `strict-run-20260729-j` completed all four component hops and all three independent validator judgments: strict audit PASS, final Mocktest PASS, zero architecture defects, and formal publication evidence `ALLOW`. This is strict/Mocktest evidence, not an independent Leaf STOP decision.
- The real isolated Coding Executor then invoked the locally authenticated Codex CLI once using only the S1 public specification and copied public tests. Its output workspace contains a FastAPI `POST /notes` implementation; the public ASGI pytest check passed 2/2, the v0.2 result envelope validates, and its self-hash matches. This remains a Day 3 S1 positive control, not production end-to-end evidence or a C0-C5 result.
- The first model invocation emitted Windows console decode noise after successful completion because Python used the GBK default while reading UTF-8 child output. `model_runner` now captures child output as UTF-8 with replacement; no assertion/test outcome was affected.
- The independent Leaf Gate initially rejected the v0.2 shared envelope because its own structured-input contract requires schema version `1.0`. A documented, derived S1 Leaf input adapter preserves source references and the `REQ-S1` calibration mapping; the Leaf decision is `STOP_LAYERING`. This is an adapter boundary, not a shared Contract change.
- CMP strict run `strict-run-20260729-b` completed 5 component calls and 5 validator judgments with strict audit PASS, then correctly emitted formal Mocktest FAIL: 5 failed scenarios and 17 findings, including missing machine-readable flow/interface fields and unsupported preconditions. `TOOL_EXECUTION_ERROR=0`; CMP is blocked from Leaf/Coding. This is the planned negative-control result, not a tool failure.

## 2026-07-29 Day 4 preflight

- `root_workflow.py` already has recursive child creation, checkpoint/resume, parallel Architecture/Gherkin branches, parent-node trace and fixture regression coverage. It is not production evidence because `config/verilayer.production.json` still routes every module to the Day 2 controlled-error adapter.
- Legacy `vibecode/state.json` audit fails only because it has no first checkpoint; `next-step` requests legacy `doctor`/matrix work. Day 4 is a new run-scoped root workflow, so this state must remain untouched and cannot block or be used as evidence for the new run.
- Added model-backed PRD/Architecture/Gherkin generation boundaries that constrain Codex to one fresh attempt directory and a declared output filename, return canonical v0.2 result envelopes, and preserve input/model evidence. Focused injected-runner tests pass; no real Day 4 model generation has run yet.
- `run-workflow` requires commands for all active modules and accepts only a JSON project config. The checked production config still invokes `production_adapter` for every module, so it cannot be reused for a Day 4 claim. A separate, explicitly versioned Day 4 config must not embed local absolute tool paths.
- Added `strict_executor` and the `strict_adapter` boundary for the future root `mocktest` stage. It obtains the actual Architecture/Gherkin primary artifacts from the root bundle, drives every strict component and validator response through the configured strict driver, and writes an evidence-backed v0.2 module result. The strict driver path is an explicit `VERILAYER_STRICT_DRIVER`/CLI input rather than a machine path in configuration.
- The adapter treats `execution_status=COMPLETED`, semantic `validation_status`, and strict-audit status as independent facts. In particular, a formal semantic FAIL is returned with process exit 0 and structured `status=FAIL`, so `RootWorkflow` records a validation failure instead of misclassifying it as a tool/environment ERROR. Focused executor and adapter tests: 3 passed.
- Added `leaf_adapter` as a derived formal-input boundary for the in-repository `leaf-gate/scripts/run_leaf_gate.py`. It converts actual root PRD/Architecture/Gherkin/Mocktest primary artifacts into the Leaf Gate's required v1.0 input package, records source paths, invokes the formal script, and normalizes its compatibility-only `child_node_id` into the root workflow's canonical `node_id`. The shared v0.2 Artifact Contract is unchanged.
- The formal Leaf script itself was exercised through this adapter with a fresh two-requirement root bundle and returned `CONTINUE_LAYERING`; this is adapter-level execution evidence, not a Day 4 root run, child run, Coding result, or production end-to-end result. Full repository regression after the addition: 67 passed.
- Added `root_coding_adapter` for the STOP path. It accepts only a root bundle whose formal Leaf decision is `STOP_LAYERING`, writes a run-local public FastAPI health-contract test plus request, calls the existing isolated Coding Executor with the fixed two-repair limit, and returns `module-result.json` as the bounded stage artifact. A semantic Coding/pytest FAIL remains a structured `FAIL` with CLI exit 0 for `RootWorkflow`; a process failure is not re-labeled as semantic success. Unit test uses an injected executor and does not claim a fresh model run.
- `config/verilayer.day4-prebackfill.json` plus `experiments/day4-root-trace/requirement.json` is the first fresh root-run input/config pair. It has no fixture references or local absolute paths. Root dry-run `day4-root-preflight-20260729-a` exited 0 and validated all eight named commands without invoking modules; the manifest records config hash `f36e532886bc22e40f5d5a9f1a4966ea11b69d4941f872aacc4a48c8b2ee23e0`. Backfill and integration are deliberately marked unimplemented/human-gated, so this is not a full production claim.
- First real run `day4-root-actual-20260729-a` is retained as an `ERROR` at PRD recording, not discarded. Its real PRD model call wrote `nodes/root/prd/attempt-1/prd.json`, but `RootWorkflow._stage` merged the adapter's structured `generator` object over the stable stage string; `_accumulate` then attempted to use that dict as a metric key and raised `TypeError: unhashable type: 'dict'`. No Architecture/Gherkin, strict, Leaf, Coding, child, backfill, or integration result exists in this run.
- Fixed the root record boundary: `generator` remains the stable stage name and adapter provenance is stored separately as `adapter_generator`. New regression coverage verifies structured adapter provenance no longer changes aggregation; targeted root/adapter suite: 21 passed. The failed `-a` run is not modified or resumed because it lacks an authoritative completed-stage checkpoint; the next real attempt must use a new run id.
- Second real run `day4-root-actual-20260729-b` retained a different, valid negative result: PRD, Architecture and Gherkin all returned PASS from actual model calls (with Architecture/Gherkin parallel), then Mocktest returned semantic `FAIL`/`STRICT_SEMANTIC_BLOCKED` before validators. `semantic_errors.json` shows both scenarios have unresolved/low-confidence entry component and entry contract; no Leaf, Coding, child, backfill, or integration step ran. This is neither a strict PASS nor a tool/environment ERROR.
- The generated Architecture was detailed but lacked the strict driver's canonical component registry, entry binding, and contract/sequence conventions; the independently generated Gherkin also named no canonical entry component. The generation boundary now instructs a `validate-arch-package` comment, `Component registry` with required columns, canonical `Public API Service`, explicit Client→entry flow and Contract mapping, with Gherkin When steps bound to that entry. Targeted regression: 19 passed; the failed `-b` run remains unchanged and the next retry must have a new run id.
- Third real run `day4-root-actual-20260729-c` completed strict execution: one real component call and one validator judgment, strict audit `PASS`, formal report `execution_status=COMPLETED` but `validation_status=FAIL` (two FAIL findings, four WARNING findings, `TOOL_EXECUTION_ERROR=0`). The architecture parser retained components but no sequence/contracts, so the strict dispatcher began at `Leaf Identity Provider` and could not reach `Public API Service`; its public response assertions were therefore unsatisfied. This is a valid semantic negative result, not a strict PASS or environment ERROR.
- Generation instructions now require the exact additional strict parser structures observed in the successful S1 control: `组件职责`, Mermaid `sequenceDiagram`, `Entry endpoint and request`, and `Internal contract mapping` with `输入`/`输出`, while Gherkin Given steps avoid internal component names. Targeted generator/strict tests: 5 passed. The new run must use a distinct id and retain `-c` unchanged.
- Fourth real run `day4-root-actual-20260729-d` is preserved unchanged. Its formal report records `execution_status=COMPLETED` and `validation_status=FAIL`; `strict_audit.json` is `PASS`; its warnings concern orphan components and machine-readable inbound contract coverage. The root `ERROR` was a classification defect: a nonzero strict `finalize_exit` overrode the valid formal semantic result.
- Phase 19 classification repair changes only `strict_executor.py` and its unit test. Once a report is present, execution is complete, and semantic/audit statuses are recognized, the formal semantic `PASS`/`FAIL` is authoritative and `finalize_exit` remains diagnostic evidence. Missing report, incomplete execution, or invalid semantic/audit status remains `ERROR`. Focused strict tests: 4 passed; full suite in a fresh worktree-local pytest base temp: 71 passed. This repairs reporting only; it does not revalidate `-d`, repair Architecture, or establish a Day 4 GO.
- The strict parser recognizes the generated public inbound contract only when the architecture has a parser-visible `### GET /health` section with ordered `**输入**`/`**输出**` JSON blocks. The prompt now requires that exact shape; root run `-h` then achieved formal strict PASS with zero findings and empty global compatibility findings.
- Coding Admission consumes `architecture.interfaces`, not the strict report. The model-generated Markdown can therefore be strict-valid yet fail admission if the architecture adapter does not publish normalized interface evidence. `generation_executor` now derives that evidence from parser-visible HTTP sections and publishes blocking issues when the shape is absent; it does not manufacture an interface from prose or a JSON-only contract.
- Background root launches must explicitly carry `VERILAYER_STRICT_DRIVER=E:\pythonproject\mocktest\.agents\skills\validate-arch\main_session_strict_driver.py`; otherwise `strict_adapter` exits before init and no formal report exists. This is an environment/process ERROR, not semantic FAIL.
## 2026-08-03 — Phase 26 Leaf Gate initial scope

- 本轮目标是把 Leaf Gate 收敛为单一、确定性、只判定的 v2 consumer；首先修复 Mocktest v2 接口和阶段准入，再判断是否继续分层，不能把修复建议或 FAIL 报告直接送入叶子判定。
- 上一阶段已确认当前 Leaf Gate reader 仍要求旧 common envelope、共享 run ID 和顶层 `status/defects`，与 Mocktest v2 的正交 states、独立 producer run ID 和 `gate_recommendation` 不兼容；这是本轮必须从实际代码复核的首要接口债务。
- 记忆仅用于提醒边界：strict audit PASS 与 Mocktest business PASS 必须同时满足，Leaf/Coding fail-closed；历史 Leaf cleanup 的核心保留面是 Skill、`scripts/run_leaf_gate.py`、references、schemas、agents、tests 和设计文档。具体设计以当前 checkout 为准。
- 排除缓存/输出后 Leaf Gate 当前只有 18 个项目自有文件；核心逻辑高度集中在 2,391 行、约 108 KB 的 `scripts/run_leaf_gate.py`，另有 5 份互相分叉的 Schema、7 份 reference/配置、2 个测试模块和 1 份 Skill。
- 文档本身已经出现两代不可兼容合同：rubric/LLM prompt 坚持语义判断只有二元决策、输入不完整走独立 `INPUT_ERROR`；formal Skill/decision schema 又把 `ERROR` 与 `CONTINUE_LAYERING/STOP_LAYERING` 放进同一个 decision/status 枚举。
- `structured_input_contract.json` 和 Skill 强制四个输入共享 `run_id/schema_version/status`，并要求 Mocktest 顶层 `status/defects`；这与已经冻结的 PRD v3、Architecture v2、Testcases v2、Mocktest v2 的独立 producer run ID、嵌套 identity、正交 states/source_artifacts 不兼容。
- `report_template.json`、static/final/input-error 三份 schema、formal decision schema 同时定义不同最终形状，已形成多事实源；统一输出必须先选择一个 canonical envelope，再将人类 Markdown、metrics、annotation、execution log 和 manifest 从同一 decision 派生。
- 当前 fixture 仍以共享 `fixture-run`、扁平 `status=PASS`、mock `defects=[]` 和字符串化 components/interfaces 为基准，不能证明 v2 producer 适配或 Mocktest FAIL→修复→revalidation 的最新证据准入。
- 两套测试验证的是两套平行产品：`test_run_leaf_gate_discovery.py` 覆盖 legacy Markdown/Feature 的启发式发现、fallback Gherkin parser、trace term/synonym 和额外 decomposition Markdown；`test_structured_contract.py` 覆盖 formal JSON 阈值计数。二者没有共享 canonical decision fixture。
- 脚本前 1,200 行已经定义大量 producer-side 重复模型与解析器（Requirement/Scenario/Step/Contract/Risk、PRD Markdown parser、official/fallback Gherkin parser、Architecture package semantic scoring、trace term/synonym/keyword evidence）。PRD v3、Testcases v2、Architecture v2 已提供这些结构，Leaf v2 不应再次从文本重建第二事实源。
- legacy Architecture 选择依赖目录名、manifest link、文件名/内容正则和 semantic score；traceability 依赖通用英文 token、中文 marker、synonym 和“两个 term + marker”强度分级。这类证据可留在显式 legacy adapter，但不能参与 canonical v2 admission 或最终 decision。
- 现有 formal proposed children 仅按组件标签轮转分配 requirements/interfaces；测试只检查数量和字段存在，尚未证明 child responsibility、合同边界、requirement allocation 可由上游证据无损推出，存在生成 scheduler-ready 假精确性的风险。
- 完整脚本确认 legacy 路径会主动覆写节点内 `traceability.md`/`risks.md`，随后再从这些自生成文件进行 precondition/risk 判定；同一个工具既造证据又判证据，职责冲突且可能覆盖上游权威产物。v2 必须只读 producer artifacts。
- formal 路径把 Testcases 中没有定义的每场景 `status` 当作验证状态；当前 `testcases/v2` 是生成合同，其 `status=PASS` 仅说明 bundle 可用，场景不携带 Mocktest business verdict。真正的场景验证结果应来自 Mocktest v2 `validator_results`/report coverage，而不是 Testcases。
- formal rule 仅用数量阈值决定 CONTINUE/STOP，并把 Mocktest defects 数纳入“是否继续分层”；架构缺陷数不是 decomposition gain。Mocktest 必须先 PASS/ALLOW，因此 Leaf 判定阶段不应再按 defect threshold 改变分层决定。
- legacy 语义流需要外部 LLM judgement，而 formal 流完全忽略 C1-C5 rubric；脚本内并存“数量阈值即 scheduler children”和“证据化 decomposition gain”的两套决策模型。需要一个 canonical rule evidence 模型，并对无法确定的 child proposal fail-closed/人工门禁。
- `write_formal_artifacts` 每次写入 wall-clock `created_at/start_time/end_time`、不排序 JSON，并重复写 `--output`；相同输入不能字节确定。输出缺 bundle manifest/content hashes，metrics/log/annotation 各自复制 envelope，且只有 decision schema 被手工 required-set 校验。
- CLI 只要 formal decision 为 CONTINUE/STOP 就返回 0，无法让编排器区分“继续分层”和“可进入 Coding”；ERROR 细分退出码存在，但 decision/status 强制相等又把工具错误混成业务决策。

## 2026-08-03 — Phase 26 Leaf Gate final findings

- Council 三席以 3.5/3.5 加权票通过 `canonical-v2-with-conditional-semantic`；首次完整 PASS 不伪造 repair receipt，发生过非 PASS 才强制修复链，全量重跑可替代定向重验但必须覆盖 affected set。
- canonical producer mapping 已落地：PRD/Architecture/Testcases 的稳定 identity 与 PRD lineage 对齐，producer run ID 独立；Mocktest report/evidence 自身 run/states 对齐；所有跨阶段引用同时校验 artifact ID/version/file SHA-256。
- Mocktest admission 分离了业务与证据故障：WARNING/FAIL/BLOCKED 返回 Architecture；execution/audit/publication ERROR 返回 Validation；任一路由都令 Leaf decision 为 null，不能进入 Coding。
- `REPAIRED` history 证明 failed report、修复前后不同 Architecture、finding、affected/revalidated testcase 包含关系和当前最终报告；最后一轮 hash 不指向当前文件即 fail-closed。
- 全量 coverage 不再从 Testcases 场景 status 猜测，而要求 Mocktest v2 的 total/evaluated/passed 等于 canonical testcase 数、warning/failed/blocked 为 0、covered requirements 与 PRD 精确一致。
- 分层 child 不再通过 requirements/interfaces 轮询生成；`proposed_children` 是 Architecture `payload.nodes` 的稳定排序投影，并保留责任、排除项、需求、状态、依赖、契约、依据。
- 输出统一为 report JSON/固定七节 Markdown/next action/execution log/bundle manifest 五件，错误态也保持同一 report 结构；无时间戳、稳定键序、LF、terminal newline 和 content/bundle hashes。
- 旧五套 schema、report template、structured input contract、自由文本 LLM prompt、legacy discovery/formal 双测试和 2,391 行混合脚本均已被单一 v2 合同/runner/test suite 取代。
- Skill 创建规范要求包内只留执行必需资源，因此使用说明、Council 记录与重构报告放在根级 `reports/leaf-gate/`，未作为 Skill context 冗余加载。
- Vibe Coding 的旧 `scan_leaves` 仍需在阶段⑥重构时新增 v2 Coding adapter；总文档已经明确在接通前 fail-closed，不能回退旧文件名绕过 Leaf v2。

## 2026-08-03 — Phase 27 integration audit

- `RootWorkflow` 的 command boundary 要求每个阶段在 attempt 目录写 `module-result.json`；当前仓库只有 `tests/fixtures/root_workflow/command_adapter.py` 实现这一协议，五个真实 producer 明确把该回执留给 adapter。
- `_process_node` 在 Mocktest `status != PASS` 时立即抛错，尚未消费 Mocktest v2 的 `RETURN_TO_ARCHITECTURE/RETURN_TO_VALIDATION` 语义，也没有 Architecture repair 与 revalidation cycle。
- 新 Leaf Gate 的 child key 是 `child_node_id`，根编排器要求 `node_id`；新 Leaf report 没有旧 `evidence_complete`，而 `_coding_evidence` 仍以该字段做 Coding admission。
- 递归 child 当前被写成 `{requirement_ids: ...}` 后重新走 Root PRD 输入，未提供父 PRD、父 Architecture、target node 的显式 Derive ownership context。
- legacy `scan_leaves` 仍只扫描 `leaf-gate.report.json`，并强制 `traceability.md`、`risks.md`、Markdown contract 和 Feature；这些均与 canonical v2 产物合同冲突，应删除而不是继续加 alias。
- 当前 checkout 没有生产 `coding/backfill/integration` command adapters；`execution.py` 只实现 admission/delivery 状态，不是代码生成器。接通工作必须保留人工门禁，不能以 fixture 或空 PASS 代替执行。

## 2026-08-03 — Phase 27 final findings

- 根编排器现在可直接识别 PRD、Architecture、Gherkin、Mocktest、Leaf Gate 的固定 canonical bundle；Mocktest/Leaf 的 manifest/hash 按各自 v2 覆盖范围验证，缺文件、错文件名或 hash 篡改均 fail-closed。
- Mocktest 非 PASS 不再直接进入 Leaf：业务 FAIL/WARNING 返回 Architecture；工具/证据/audit ERROR 返回 Validation。Architecture repair 必须改变 canonical bytes，并记录 finding、affected testcase、前后 hash、最终报告 hash和复验集合。
- Leaf v2 的 `child_node_id` 已成为单一公共字段；递归 child 输入包含 parent PRD、parent Architecture 与精确 target node，Root/Derive 语义不再混用。
- Vibe Coding scanner 已删除旧文件猜测、旧状态别名及自造 traceability/risks 依赖，只接受 `ADMITTED + STOP_LAYERING + VIBECODE` 和已验证的当前 artifact hashes。
- 真实 PRD/Architecture/Gherkin producer 仍需要各自规定的产品证据、独立 review 或结构化 design draft；Coding/backfill/integration 仍需配置真实 executor 与人工批准。根编排器会拒绝缺失配置，不以 fixture 代替生产执行。

## 2026-08-03 — Phase 28 Mocktest cleanup inventory

- `mocktest` 当前共 204 files / 43 directories / 2,541,365 bytes；其中 127 个 `.pyc` 占 1,660,124 bytes，是可重建且无发布价值的明确清理候选。
- 排除 `.pyc` 后只有约 77 个项目文件；顶层由 `.agents`、`config`、`examples`、`schemas`、`scripts`、`src`、`tests`、README/报告/pyproject/.env.example 构成，没有当前 checkout 内的 `user/`、`.work/` 或历史运行目录。
- `.agents/skills/validate-arch` 约 835 KB，但它是当前正式 skill/strict driver，不可按体积删除；内含 SKILL、preflight、strict driver、subagent runner、report enhancements、batch helpers 和 prompts，需要做引用级审计。
- 非 `.pyc` 文件没有 SHA-256 完全重复项；因此不能通过“相同内容副本”直接清理源码或文档。
- 项目不是独立 Git checkout，无法用 tracked/untracked 状态推断用户文件；删除决策必须依赖运行入口、imports、字符串路径引用、发布边界与回归。
- 正式入口为 `mock-test = mock_framework.canonical_cli:main` 和 `python -m mock_framework`；Skill 正式入口为 `.agents/skills/validate-arch/SKILL.md`，并直接调用 `run_subagent_skill.py`、`main_session_strict_driver.py`、`scripts/preflight.py`。
- `README.md` 和 Skill 明确规定 legacy Pipeline/StepMapper/GapDetector/renderer 在 shadow 等价语料完成前不得物理删除；当前测试只有 canonical contract 测试，没有该完整 shadow corpus，因此这些 legacy 源码虽非公共入口，仍不满足安全删除条件。
- 引用扫描确认 `run_subagent_skill.py` 仍直接 import `ValidateArchSkill`、旧 `ReportRenderer` 和 `report_enhancements`；`ValidateArchSkill` 又依赖 Pipeline、loader、simulator、validator、gateway。因此不能把旧包按“canonical CLI 未 import”判为死代码。
- `aggregate_batch_results.py`、`prepare_batches.py` 和 batch instructions 由 `multi-session-orchestrator-prompt.md` 手工工作流引用；它们不是默认 small-serial path，但仍是有文档入口的可选多会话工具。
- `sim_driver.py` 仅被重构报告列为 legacy；`subagent-prompts.md`、`multi-session-orchestrator-prompt.md` 没有程序化引用，需要继续检查是否属于明确的人工入口或已被 Skill v2 取代。
- 清理前 baseline（显式 `PYTHONPATH=src`，Anaconda 解释器）为 23/23 pytest PASS；compileall 与 validate-arch preflight PASS。未显式设置仓库路径时，CLI 子进程会加载 Anaconda 中的旧安装包，这是环境遮蔽而非当前源码失败。
- 全包 mypy 在 pytest 已完成后仍超过 120 秒，未获得本轮 baseline；不能把它列为 PASS，后续清理验收以相同 pytest/preflight/compileall 加静态引用检查为主。
- 旧 multi-session prompt、batch instructions、`prepare_batches.py`、`aggregate_batch_results.py` 形成一个内部闭环，但未被当前 README/SKILL/pyproject/源码入口引用，且要求 `plan.json/hops.json/compat.json/...` 旧私有产物作为最终工作流，和 v2 mandatory workspace/delivery contract 冲突，属于高可信退役候选。
- `subagent-prompts.md` 没有任何文件引用，内容复制旧手工 subagent schema；当前 v2 prompt 由 runner/driver根据 canonical plan 生成，属于高可信退役候选。
- `mock_framework.cli.layer_check` 只被自己的 package `__init__` 导出，当前 canonical CLI 没有 `layer-check` 命令，README/SKILL/pyproject 均未暴露它；它连同 `layer_validation` 与 `models.layer` 构成隔离的退役旧 CLI 簇，可整体删除。
- `arch_modifier.py`、`decision_engine.py`、`json_report_renderer.py` 只被 `improvement/__init__.py` 重新导出，当前 runner 只使用 `improvement.report_renderer.ReportRenderer`；Mocktest v2 明确禁止自动修改 Architecture，因此该三文件加 `models.modification` 是无调用退役簇，可删除并收窄 package exports。
- `hypothesis` 和 `config.pbt` 没有任何源文件消费；现有 PBT 源码已经不存在，只剩历史 `.pyc`，因此依赖和配置属于孤儿声明，可删除。
- baseline 工具执行新增了 `.coverage`、`.mypy_cache`，连同所有 `__pycache__/*.pyc` 都是可重建缓存；它们必须在最终清理中删除，不能把验证副作用留在项目内。
- 进一步检查发现 Pipeline 在运行时从 `mock_framework.improvement` 动态导入 `ImprovementEngine` 和 `ArchDocModifier`；它们属于被明确保留的 legacy shadow path，不能删除。此前“无调用退役簇”的判断已收窄为仅 `JsonReportRenderer` 与 `models.modification`。
- `mock_framework.cli.layer_check`、`layer_validation`、`models.layer` 仍是完全隔离簇：canonical CLI、Skill、Pipeline、tests 和文档均无入口；`config.skill.enable_cross_layer_check=false` 也从未被读取。删除该簇不会改变当前公开或 shadow Mocktest 路径。
- 多个 `SkillConfig` 历史字段与整个 `ValidatorDimensionConfig` 没有消费者，但为避免把目录清理扩大成配置 API 重设计，本轮只删除明确孤立的 PBT block和直接关联依赖，不批量重写 SkillConfig。
- 最终删除边界收敛为：全部可重建缓存；孤立的 `layer-check/layer_validation/models.layer` 旧 CLI 簇；孤立的 `JsonReportRenderer` 与 `models.modification`；未被引用的 `subagent-prompts.md`；无源码消费者的 Hypothesis/PBT 配置声明。清理后对 13 个退役标识的全目录扫描为零命中。
- 保留 legacy Pipeline、ArchDocModifier、ImprovementEngine、batch scripts/prompts、两个重构报告、示例、schemas 与正式 validate-arch Skill：这些内容仍被运行时动态导入、文档化 shadow-equivalence 路径或可运行交付包直接需要，不能仅因不是 canonical CLI 主入口就删除。
- 最终目录为 69 个文件、858,903 bytes，且没有 `__pycache__`、`.pytest_cache`、`.mypy_cache` 或 `.coverage`；相对清理前 204 个文件、2,541,365 bytes，净减少 135 个文件、1,682,462 bytes。baseline 期间额外生成并随后删除的约 93 MB mypy/coverage 缓存不计入净差值。
