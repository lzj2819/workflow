---
name: prd-to-gherkin
description: 将 PRD 通过本体约束解析、模式辅助抽取、语义分析、证据验证、需求冻结、受控推导、覆盖图、测试义务、场景组合、标准英文关键字 Gherkin 生成和独立验证，转换为可追踪的 Requirement Model、Feature 和 Quality Report。用于生成可信 BDD 测试并检查冲突、歧义、未知项、假设、oracle、边界、状态、接口、NFR 和跨需求旅程，禁止无证据补全业务行为。
---
# PRD 转证据约束 Gherkin
## 目标
建立一条可审计转换链：
```text
PRD Source
→ Pattern Candidates
→ Requirement Group
→ Clause
→ FACT
→ Ontology-typed Requirement Semantic Graph
→ Verified Requirement Graph
→ Validated Requirement Baseline
→ Frozen Requirement Model
→ Derived Test Obligation
→ Authoritative Test Condition
→ Gherkin Scenario
→ Independent Verification
```
同时满足：
1. **证据忠实**：每个业务术语、条件、动作和预期结果均可回溯到精确来源或有效推导。
2. **系统覆盖**：探索所有证据支持的等价类、边界、决策、状态、工作流、接口和 NFR。
3. **显式不确定性**：未知、冲突、假设和缺失 oracle 不得静默进入权威场景。
4. **验证独立性**：生成链、确定性验证和独立语义评审职责分离。
5. **可计算性**：语义节点、关系、覆盖路径和组合路径使用固定 schema。
场景数量不等于覆盖完整，语法通过不等于语义正确。
## 核心分类
所有内容必须属于以下一种：
- `EXPLICIT`：精确、连续的 PRD 原文直接支持。
- `VALID_DERIVATION`：由已批准策略和显式 FACT 必然推出。
- `HYPOTHESIS`：有探索价值，但不能由证据必然推出。
- `UNKNOWN`：形成确定业务解释或 oracle 所需的信息缺失。
- `CONFLICT`：来源支持互不兼容的解释。
- `DOCUMENTED_EXCLUSION`：来源明确说明为非规范性或不在当前范围。
只有 `EXPLICIT` 和 `VALID_DERIVATION` 可以进入权威 Test Condition 和 Scenario。
测试技术可以选择输入、边界和行为路径，不能创造业务响应。
## 按需资源
- Stage 1 必须读取 `references/requirement-ontology.yaml` 和 `references/requirement-patterns.yaml`。
- Stage 5–8 必须读取 `references/coverage-graph-schema.yaml`。
- 生成跨需求组合场景时必须读取 `references/scenario-composition.md`。
- 资源定义与主文件冲突时，以主文件的证据、安全和冻结门禁为准。
## 必须交付
- `requirement-model.yaml`：唯一机器语义来源，保存 Ontology Graph、Coverage Graph 和全链追踪。
- `[module].feature`：必须使用英文 Gherkin 关键字；只渲染冻结 eligible TC；有阻塞时标记部分产物。
- `quality-report.md`：保存门禁、图计算覆盖率、阻塞、组合、验证和最终状态。
可选生成 `requirements-analysis.md` 作为 `requirement-model.yaml` 的只读渲染视图，不得成为第二语义来源。
## 全局禁止
禁止：
- 发明阈值、角色、权限、状态、错误码、重试、超时、回退、保留期、安全策略、成功标准或业务响应；
- 用常识、行业惯例、测试经验或示例填充 `UNKNOWN`；
- 把示例列表当作封闭全集，除非 PRD 明确封闭该领域；
- 从输入类别推断系统必然拒绝、接受、截断或警告；
- 静默选择多个合理解释中的一个；
- 将 `HYPOTHESIS`、`UNKNOWN`、`CONFLICT` 或未入基线决定放入权威场景；
- 在 Gherkin 阶段重新读取 PRD 并补充 TC 中不存在的含义；
- 用语法检查、标签检查或覆盖率证明自然语言业务语义正确；
- 为追求场景数量合并不兼容 oracle 或重复测试义务；
- 用“或”“分别”“以及以下情况”等自然语言把两个以上可独立执行的数据行压入一个 TC 或 Scenario；
- 将接口、触发、状态转换、步骤结构或 oracle 不同的行为伪装成参数行。
自动修复只能处理格式、ID、引用、标签和重复渲染等不改变语义的问题。
`/fast` 只能跳过等待交互，不能绕过证据、冻结、oracle 或验证门禁。
# Stage 1：Evidence-preserving Requirement Parsing
**目的：** 把 PRD 转换为保留原始证据位置的 Requirement Semantic Graph，不做测试设计。
## 输入
仅使用原始 PRD 和稳定来源位置。
先用 Pattern Library 识别 clause、modality、决策、边界、状态、接口和指标候选。Pattern 命中只产生 Candidate；保留命中范围、`pattern_id` 和原文，再由证据验证决定是否成为 FACT。未命中内容必须进入 LLM residual pass。
### 1. Requirement Group Detection
- 按连续、语义连贯的原文块创建 Requirement Group。
- 保存文件、章节、起止行、精确连续引文和可选内容哈希。
- 标记原文是规范性、说明性、治理信息还是范围排除。
### 2. Clause Segmentation
- 拆分为可独立追踪的 clause。
- 保留 `AND`、`OR`、`SEQUENCE`、`DEPENDS_ON`、`EXCEPTION_TO` 和 `INVARIANT_FOR`。
- 不把同一句中的独立条件或结果压成不可分析的摘要。
### 3. Evidence-preserving FACT Extraction
每个 FACT 至少包含：
```yaml
fact_id: FACT-001
requirement_group_id: RG-001
clause_type: behavior|rule|constraint|exception|transition|interface|nfr
normalized_fact: "只使用引文中已有术语的原子陈述"
source_ref: "prd.md:10-12"
introduced_terms: []
status: EXPLICIT|INVALID
```
标准化 FACT 中的名词、数值、状态、角色、条件和结果必须存在于对应引文。
### 4. Requirement Semantic Structuring
使用 Requirement Ontology 创建类型化节点和边，不允许自由 Node。核心节点包括 Actor、Action、Object、Data、Condition、Event、State、Constraint、Temporal、Boundary、Policy、Interface、Exception、Metric 和 Oracle。
每个节点与边必须满足 Ontology 端点约束并引用 FACT；Ontology 只约束结构，不能作为业务证据。领域扩展必须使用批准的命名空间。
缺少内容时写 `UNKNOWN`，不得补全。
**输出：** `Requirement Semantic Graph`
## Stage 1 门禁
- 每个规范性原文陈述映射到 FACT 或合法排除；
- 每个 `source_quote` 与来源范围一致；
- 每个 `EXPLICIT` FACT 的 `introduced_terms` 为空；
- clause 关系保留原始逻辑；
- Pattern Candidate 均有 VALIDATED、REJECTED 或 AMBIGUOUS 处置；
- Ontology 节点、边、端点类型和证据引用有效；
- 本阶段没有 AC、TC 或 Scenario。
# Stage 2：Requirement Semantic Analysis
**目的：** 分析需求语义质量，生成 Verified Requirement Graph。`Verified` 表示分析完成，不表示没有缺口。
### 1. Requirement Classification
分类：
- functional、nfr、interface、data、security、privacy、compliance、governance；
- atomic 或 aggregate；
- 规范性、说明性或合法排除；
- 优先级、范围和层级只使用来源元数据。
聚合需求只能引用已存在的原子子需求，不得产生重复测试义务。
### 2. Requirement Dependency Analysis
识别：
- 前置依赖；
- 跨需求 AND/OR；
- 状态和工作流顺序；
- 接口消费者与提供者；
- NFR 对功能路径的约束；
- 数据生命周期依赖。
每条依赖必须引用 FACT。
### 3. Requirement Conflict Detection
比较支持同一语义字段的来源。存在不兼容解释时：
- 记录 `CONFLICT`；
- 保存双方证据；
- 禁止选择其中一方；
- 标记受影响 Requirement IR。
### 4. Requirement Ambiguity Detection
检查：
- 多种合理解释；
- 模糊量词或时间含义；
- 不明确的 actor、对象、状态或触发；
- “支持”“适当”“明确”“及时”等缺少可观察判定的措辞；
- 示例集合是否开放。
歧义发现不能自动改写为确定规则。
### 5. Requirement Completeness Checking
按适用性检查：
- actor、input、precondition、trigger、response；
- 正向与显式异常 oracle；
- 数量、时间、大小和包含/排除边界；
- 状态、转换和终止条件；
- 接口契约与 schema；
- 权限或角色矩阵；
- NFR 的 population、start、end、unit、threshold、exclusion 和 pass rule。
只报告真实缺口，不生成“最佳实践需求”。
## Requirement IR
```yaml
requirement_id: REQ-001-R1
parent_requirement: REQ-001
requirement_group: RG-001
requirement_kind: atomic|aggregate
layer: architecture|module|component|UNKNOWN
actor: {value: "student", evidence: [FACT-001]}
precondition: {value: UNKNOWN, evidence: []}
trigger: {value: "submit image", evidence: [FACT-002]}
response: {value: "validation result", evidence: [FACT-003]}
unsupported_terms: []
analysis_findings: []
status: VERIFIED|BLOCKED
```
**输出：** `Verified Requirement Graph`
## Stage 2 门禁
- 每个 FACT 已映射到 IR、治理节点或合法排除；
- 每个业务语义字段都有证据或显式 `UNKNOWN`；
- 所有冲突、歧义和缺失均关联受影响 IR；
- 没有静默遗漏或静默消歧。
# Stage 3：Evidence Validation
**目的：** 验证 Requirement Graph 中每项业务语义的证据充分性，形成 Validated Requirement Baseline。
## 检查
### Evidence Coverage
- 从每个 IR 字段反查 FACT；
- 从 FACT 反查精确 PRD 引文；
- 计算规范性来源核对率；
- 不把阻塞项计入权威测试覆盖率。
### Unsupported Terms
识别 IR 中未出现在支持 FACT 或批准元数据中的角色、对象、动作、结果、状态、数值和政策。
### Unknown Detection
记录形成确定测试所缺少的信息，并指定影响元素：
`given|when|then|oracle|boundary|permission|state|time|interface|nfr`
### Hypothesis Detection
将合理但非必然的解释标为 `HYPOTHESIS`。假设只可进入报告或探索性建议。
### Oracle Completeness
检查预期结果是否：
- 可观察；
- 可判定通过或失败；
- 参数确定；
- 没有依赖未定义的“正确”“清晰”“合理”等概念；
- 对每个显式异常和边界都有来源支持的结果。
## 证据判定
每个 IR 只能得到一个状态：
- `EVIDENCE_VALID`
- `BLOCKED_UNKNOWN`
- `BLOCKED_CONFLICT`
- `BLOCKED_UNSUPPORTED_TERM`
- `BLOCKED_NO_ORACLE`
- `DOCUMENTED_EXCLUSION`
**输出：** `Validated Requirement Baseline`
## Stage 3 门禁
- 证据有效 IR 可进入冻结候选；
- 阻塞 IR 保留在模型中；
- 没有 UNKNOWN、HYPOTHESIS 或 CONFLICT 混入可冻结子集；
- oracle 不完整的 IR 不得进入测试推导。
# Stage 4：Requirement Freezing
**目的：** 通过审批、决策登记和版本化冻结可测试需求，输出 Frozen Requirement Model。
## Decision Register
```yaml
open_decisions:
  - id: DEC-001
    affected_requirements: [REQ-001-R1]
    question: "需要决定的问题"
    affected_element: oracle
    classification: BLOCKING|NON_BLOCKING
    resolution_type: INTERACTIVE_DECISION|FORMAL_APPROVAL_REQUIRED
    owner: PO
    status: PENDING|ACCEPTED|REJECTED|DEFERRED_NON_BLOCKING|BASELINED
    approval_evidence: null
```
状态规则：
- `PENDING`：受影响 IR 保持阻塞；
- `ACCEPTED`：已同意但尚未进入正式基线，仍不可生成 TC；
- `BASELINED`：决定已进入正式来源并形成新 FACT；
- `REJECTED`：候选方案被拒绝，原缺口仍存在；
- `DEFERRED_NON_BLOCKING`：确认不改变当前验收结果，仅保留在报告。
安全、隐私、合规、数据保留、架构边界和实质范围变化必须正式审批。
聊天偏好不能直接成为业务 FACT 或 Scenario。
## Baseline Freeze
```yaml
baseline:
  version: 1.0.0
  prd_hash: "sha256:..."
  model_hash: "sha256:..."
  approval_ref: "批准记录"
  freeze_scope: FULL|PARTIAL
  eligible_requirement_ids: [REQ-001-R1]
  blocked_requirement_ids: []
  status: FROZEN
```
- `FULL`：当前范围没有阻塞 IR。
- `PARTIAL`：存在阻塞 IR，但有安全的可测试子集。
eligible 与 blocked 必须互斥，并解释全部非排除 IR。
## Requirement Versioning
- 新 FACT 使用新 ID；
- 已发布 ID 不可改变含义；
- 根本变化时废弃旧 ID 并创建新 ID；
- 证据变化使依赖它的 IR、推导、义务、TC 和 Scenario 失效。
**输出：** `Frozen Requirement Model`
## Stage 4 门禁
- 基线状态为 `FROZEN`；
- 每个 eligible IR 证据和 oracle 完整；
- 每个 blocked IR 有 gap/decision 引用；
- 每个已接受业务决定达到 `BASELINED`；
- 有正式版本、哈希和审批引用。
# Stage 5：Evidence-constrained Requirement Derivation
**目的：** 只从冻结基线的 eligible IR 推导逻辑上必然成立的测试义务。
## 允许策略
- `CONJUNCTION_DECOMPOSITION`
- `EXPLICIT_DISJUNCTION_EXPANSION`
- `BOUNDARY_POINT`
- `BOUNDARY_INSIDE`
- `BOUNDARY_OUTSIDE`，仅当边界外响应有显式证据；
- `DECISION_EXPANSION`
- `WORKFLOW_EXPANSION`
- `STATE_EXPANSION`
- `INTERFACE_EXPANSION`
- `NFR_EXPANSION`，仅限来源定义的测量口径。
每项推导必须保存：
```yaml
derived_id: DR-001
strategy: BOUNDARY_POINT
premises:
  - {fact_id: FACT-001}
conclusion: "必然成立的测试义务"
proof_obligations:
  input_class_supported: true
  expected_behavior_supported: true
scope_limits: []
competing_interpretations: []
decision: VALID_DERIVATION|INVALID_DERIVATION|INSUFFICIENT_EVIDENCE|MULTIPLE_INTERPRETATIONS
```
只允许 `VALID_DERIVATION` 进入 Test Obligation Graph。
不得因识别出“边界外输入”而假设系统拒绝、接受、截断或警告。
## Test Obligation 与 Coverage Graph
建立来源支持的行为、边界、决策、状态、工作流、接口和 NFR 义务。
同时构建 Requirement Coverage Graph：
`SOURCE → GROUP → CLAUSE → FACT → IR → TO → TC → SC`。
用 `BLOCKED_BY` 和 `EXCLUDED_BY` 表达阻塞与排除；用 `DERIVATION`、`AC` 作为可选中间节点。所有覆盖率必须由图的可达路径计算，不得手工声明。
**输出：** `Test Obligation Graph`
## Stage 5 门禁
- 每个推导引用 eligible FACT；
- 输入分类和预期行为分别得到证明；
- 无效或证据不足的推导不会进入权威义务；
- Coverage Graph 没有悬空节点、错误端点或断裂权威路径；
- blocked IR 没有推导。
# Stage 6：Evidence-driven Test Obligation Analysis
**目的：** 把 Test Obligation Graph 系统化转换为 Authoritative Test Conditions。
## 测试空间
对每个义务检查：
- Equivalence Classes
- Boundary Values
- Decision Tables
- State Transitions
- Workflow Paths
- Interface Contracts
- Explicit Exceptions and Recovery
- Compatible Parameter Combinations
- Measurable NFR Coverage
- Cross-requirement Interactions
每个候选条件分类为：
- `AUTHORITATIVE`：输入、路径和 oracle 均有证据；
- `INPUT_ONLY`：输入可得，但响应缺失；
- `HYPOTHESIS`：有探索价值但证据不足；
- `NOT_APPLICABLE`：该维度不适用。
只有 `AUTHORITATIVE` 可以成为权威 TC。
## 完整测试案例生成
- 为每个证据充分的 Test Obligation 生成 Test Condition。
- 不得省略任何具有独立业务含义的测试条件。
- 不同 oracle、边界、异常、状态、接口和可测量 NFR 必须分别生成测试案例。
- 每个冻结 eligible Test Condition 必须生成一个原子 Scenario 或 Scenario Outline。
- 每个 `VALID_COMPOSITION` 必须生成一个独立的组合 Scenario。
- 不得通过合并场景减少或弱化独立的业务断言。
## Test Condition
```yaml
tc_id: TC-001
requirement_id: REQ-001-R1
covered_requirement_ids: [REQ-001-R1]
test_obligation_ids: [TO-001]
classification: EXPLICIT|VALID_DERIVATION
technique: boundary-value-analysis
render_mode: SCENARIO_OUTLINE
step_template:
  precondition: "冻结条件"
  action: "使用 <input> 执行冻结动作"
  expected: "系统返回 <expected>"
example_columns: [input, expected]
approved_data_rows:
  - row_id: ROW-001
    values: {input: "获批输入", expected: "获批结果"}
    evidence: [FACT-001]
evidence: [FACT-001, DR-001]
```
`render_mode: SCENARIO` 时，`example_columns` 和 `approved_data_rows` 必须为空，`step_template` 不得含占位符。`render_mode: SCENARIO_OUTLINE` 时，两者必须非空。

### 参数化 Test Condition 合同
当同一测试义务存在两个以上数据组合时，强制执行：
1. 若各行的业务前置逻辑、动作结构、步骤顺序和预期结果结构完全相同，仅参数值变化，设置 `render_mode: SCENARIO_OUTLINE`。
2. 将变化项提取为命名参数，在 `step_template` 中使用 `<parameter>`；禁止用“JPG 或 PNG”“不超过和超过”“分别执行”等聚合文本代替数据行。
3. `example_columns` 按占位符首次出现顺序列出全部参数；每个占位符精确对应一列。
4. 每个 `approved_data_rows` 包含唯一 `row_id`、与 `example_columns` 完全一致的 `values` 和逐行 `evidence`。禁止空值、额外列、缺失列或自行补充数据。
5. 参数值和逐行 oracle 必须由冻结 FACT 或有效 Derivation 支持；测试技术不能创造边界精度或业务响应。
6. 若接口、触发、状态转换、步骤结构、错误结果或 oracle 类型任一不同，禁止使用 Outline，必须拆成独立 TO/TC。
7. 只有一个获批数据行时使用普通 `SCENARIO`，不得创建单行 Outline。

边界值分析必须将来源支持的边界点展开为具体数据行。来源定义精度时，至少检查边界点及来源支持的边界内、边界外相邻点；来源未定义精度或边界外响应时记录缺口，不得自行假设“1 秒”“0.01MB”或拒绝行为。

每个 eligible 原子 IR 必须有 AC/测试义务/TC，或有合法聚合覆盖。
## Scenario Composition Candidates
原子 TC 冻结后，使用 Requirement Dependency Graph 和状态边寻找跨需求组合候选。只有顺序、bridge、角色、数据作用域、时间语义和 oracle 全部兼容且有证据时，才能标为 `VALID_COMPOSITION`。组合不替代原子 TC，也不增加来源覆盖分子。
**输出：** `Authoritative Test Conditions`
## Stage 6 门禁
- 每个 TC 的 Given、When、Then 和 oracle 均有证据；
- 每个有证据支持的测试空间维度均已生成权威 TC；
- INPUT_ONLY 和 HYPOTHESIS 仅进入报告；
- 每个 TC 只有兼容的前置条件、动作和 oracle；
- 每个多行同构 TC 均使用结构化参数和 `SCENARIO_OUTLINE`，每个非同构行为均拆分 TC；
- 每个 Outline 数据行的值、oracle 和 evidence 完整，没有用聚合自然语言隐藏数据行；
- blocked IR 没有 TC。
# Stage 7：Gherkin Scenario Generation
**目的：** 将权威 TC 机械渲染为可追踪 Gherkin，不增加业务含义。
## `.feature` Gherkin 输出合同
- 文件扩展名必须为 `.feature`，关键字必须使用 `Feature`、`Scenario`、`Scenario Outline`、`Given`、`When`、`Then`、`And`、`But`、`Examples`。
- 禁止 `# language: zh-CN` 以及 `功能`、`场景`、`假如`、`当`、`那么`、`而且` 等本地化关键字；标题和步骤正文可以使用中文。
```gherkin
Feature: <功能名称>
  # SC-001
  @REQ-001 @TC-001
  Scenario: <场景名称>
    Given <TC.step_template.precondition>
    When <TC.step_template.action>
    Then <TC.step_template.expected>
```
机械映射：`TC.step_template.precondition → Given`、`TC.step_template.action → When`、`TC.step_template.expected → Then`。

`SCENARIO_OUTLINE` 的规范渲染：
```gherkin
# SC-001
@REQ-001 @TC-001
Scenario Outline: 支持规定格式的题目图片
  Given 答疑输入为题目图片
  When 学生上传 <format> 格式的题目图片
  Then 系统接受该图片作为答疑输入

  Examples:
    | format |
    | JPG    |
    | PNG    |
```

每个 TC 精确生成一个原子 `Scenario` 或 `Scenario Outline`；一个 Outline 仍映射一个 TC，每个 Examples 行是独立执行实例。
`render_mode` 必须机械决定 Gherkin 类型，Stage 7 不得重新选择。
`SCENARIO_OUTLINE` 必须输出且只输出一个 `Examples` 表；表头与 `example_columns` 顺序完全一致，每个 `approved_data_rows` 按模型顺序精确渲染一行。
步骤占位符、Examples 列和值必须逐字符来自模型；禁止遗漏、合并、增加、改名或改写数据行。
普通 `Scenario` 不得包含占位符、Examples，或用“或”“分别”等表达隐藏多个独立测试输入。
原子 Scenario 必须包含唯一 `# SC-*`、一个 `@TC-*` 和全部被覆盖的 `@REQ-*`、`@NFR-*` 或正式指标标签。
对 `VALID_COMPOSITION` 额外生成含唯一 `@COMP-*` 的组合 Scenario，并保存 component TC、bridge evidence 和 coverage paths。
禁止添加 TC/bridge 外步骤、改写 oracle、合并不兼容 TC、渲染待决事项或自行增加 Examples 数据。
**输出：** `Feature + Trace Links`
## Stage 7 门禁
- 文件仅使用规定的英文 Gherkin 关键字，并通过正式 Cucumber Gherkin 解析器；
- 原子 TC 与原子 Scenario/Scenario Outline 一一对应，组合 Scenario 单独核算；
- 标签和 ID 唯一且引用有效；
- 普通 Scenario 的 Step 与 `step_template` 字符级或规范化后相等；
- Outline 的模板、占位符、Examples 表头、行数、顺序和值与 TC 参数合同完全一致；
- 每个 Outline 占位符恰有一个同名 Examples 列，不得存在未使用列、缺失列、空值或重复 `row_id`；
- Feature 不含 UNKNOWN、CONFLICT、HYPOTHESIS 或待决决策；
- 部分冻结 Feature 明确标记为部分产物。
# Stage 8：Independent Semantic Verification
**目的：** 独立验证结构、语义、覆盖和幻觉风险。
## A. Deterministic Validation
运行：
```bash
node scripts/validate_requirement_graph.mjs <requirement-model.yaml>
node scripts/validate_feature.mjs <feature> <requirement-model.yaml>
```
至少检查：
- 正式 Gherkin 语法；
- YAML 可解析与 ID 唯一；
- FACT/IR/DR/义务/TC/Scenario 引用有效；
- Ontology 节点、边、端点类型和 Pattern Candidate 处置有效；
- Coverage Graph 路径、节点类型和边类型有效；
- eligible 与 blocked 互斥并解释全部 IR；
- 基线为 `FROZEN`；
- 每个 eligible FACT 和 IR 被覆盖；
- 每个 TC 精确渲染一次；
- `render_mode` 与 `Scenario`/`Scenario Outline` 类型一致；
- 每个 Outline 的占位符集合与 `example_columns` 相等，Examples 数据与 `approved_data_rows` 逐行相等；
- 每个 `approved_data_rows` 精确产生一个可执行实例，普通 Scenario 不承载多个隐藏数据行；
- 每个组合场景引用有效 composition、component TC 和 bridge evidence；
- blocked 内容没有泄漏到 Feature；
- 声明计数与实际对象一致。
验证器若不能解析 Outline 占位符和 Examples 表，记录 `VALIDATION_TOOLING_GAP`，不得声称确定性验证通过。工具不可用或失败时同样不得声称通过。
## B. Forward Trace
逐项验证：
```text
PRD → Pattern Candidate → FACT → Ontology Node/IR → Derivation/TO → TC → Coverage Path → Scenario
```
确认每次转换没有丢失来源支持义务。
## C. Reverse Trace
逐场景验证：
```text
Scenario → Coverage Path/Composition → TC → TO → Ontology Node/IR → FACT → PRD
```
检查 Scenario 是否新增角色、状态、权限、条件、数值、动作、结果或政策。
标记：
- `OVER_SPECIFICATION`
- `UNDER_SPECIFICATION`
- `ORACLE_DRIFT`
- `AMBIGUITY`
- `TRACEABILITY_BREAK`
语义问题不得自动修复。
## D. Independent Review
存在隔离评审能力时，只向独立评审者提供：
- 原始 PRD；
- 生成的 Feature；
- 验证合同。
不得提供生成推理、Requirement Model、分析文档、假设或先前结论。
要求识别：
- 竞争解释；
- 无证据业务行为；
- 遗漏义务；
- 被错误封闭的开放领域；
- 不确定或不可执行 oracle。
每个发现必须引用 PRD 和 Scenario 证据，并允许判定为误报。
无法执行隔离评审时记录 `INDEPENDENT_REVIEW_NOT_RUN`，不得伪称通过。
## E. Coverage and Consistency
分别报告：
- `source_accounting_rate`
- `eligible_fact_test_coverage`
- `eligible_ir_test_coverage`
- `test_obligation_tc_coverage`
- `tc_scenario_coverage`
- `approved_example_row_coverage`
- `blocked_fact_count`
- `blocked_ir_count`
- `documented_exclusion_count`
- `unsupported_scenario_semantics_count`
- `composable_path_count`
- `valid_composition_count`
- `blocked_composition_count`
- `critical_journey_coverage`
阻塞和排除只计入“已核对”，不计入权威测试覆盖。
## F. Hallucination Detection
搜索并反查 Feature 中所有：
- 来源不存在的名词和数值；
- 未批准错误响应、权限或状态；
- 无证据边界外行为；
- 从示例推断的封闭全集；
- 未入基线决定；
- 假设性恢复、重试或降级。
发现一个未解决的无证据业务语义，Feature 即不能 READY。
## Stage 8 门禁
- 确定性验证、正向追踪和反向追踪全部通过；
- 语义发现均已处置，覆盖计数与模型一致；
- 独立评审已完成，或明确输出 `NEEDS_INDEPENDENT_REVIEW`。
## 最终状态
按顺序判定：
1. `VALIDATION_FAILED`
   - 确定性验证失败；
   - 存在 `VALIDATION_TOOLING_GAP`，验证器不能验证 Outline/Examples 合同；
   - 存在未修复语义错误。
2. `PENDING_FORMAL_APPROVAL`
   - eligible 候选仍等待必须的正式审批。
3. `BLOCKED_BY_MISSING_REQUIREMENTS`
   - 存在其他 blocked IR。
4. `NEEDS_INDEPENDENT_REVIEW`
   - 其余门禁通过，但规定的隔离评审未执行。
5. `READY_FOR_DELIVERY`
   - 所有门禁通过；
   - `freeze_scope = FULL`；
   - blocked IR 为零；
   - 权威覆盖率均为 100%；
   - unsupported Scenario semantics 为零；
   - 独立评审完成。
**输出：** `[module].feature`、`requirement-model.yaml`、`quality-report.md`
# 变更管理
按影响分类：
- `INDEPENDENT_ADDITION`
- `PARTIAL_IMPACT`
- `BASELINE_REBUILD`
变更时：
1. 识别受影响 FACT、IR、推导、义务、TC 和 Scenario；
2. 保留未变化 ID；
3. 废弃含义已改变的 ID 并创建新 ID；
4. 重新冻结受影响基线；
5. 重新生成依赖子图；
6. 执行完整 Stage 8 验证。
不得通过局部修改 Feature 绕过上游证据链。
