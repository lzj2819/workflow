# PRD Generation 重构审计报告

## 1. 结论

本轮将 `prd-generation` 从“多份文档约定 + 运行时拼接”重构为单一 canonical model 驱动的输出链：

`legacy/internal draft → canonical PRD → JSON Schema/semantic validation → deterministic Markdown + sidecars → consumer profile validation`

正式 PRD bundle 固定为五件套：

- `prd.md`
- `prd.json`
- `prd_manifest.json`
- `validation_report.json`
- `execution_log.json`

存在阻塞问题时另写 `blocking_questions.json`，但不得把阻塞产物标为可交接。

## 2. 审计范围

已审读以下流程的项目自有文档、源码、模板、schema、配置和测试，并以《工作流总文档》核对跨阶段关系：

- `prd-generation`
- `prd-to-artecture-skill`（目录沿用现状；文档中的规范名称为 `prd-to-architecture-skill`）
- `prd-to-gherkin`
- `mocktest`
- `leaf-gate`
- `vibe coding`

`.git` 对象、`node_modules`、`__pycache__`、`.pyc`、生成缓存及其他供应商/二进制内容只做清单和边界审计，不视为流程设计文本逐字阅读。

本轮只重构 `prd-generation`。其余五个流程作为消费者进行只读契约审计，没有被改写，也没有被宣称为已重构。

## 3. 原设计问题

| 问题 | 影响 | 处理 |
|---|---|---|
| Skill 声称固定 12 节，旧 assembler 实际只按内容输出约 6 类章节 | 不同需求生成不同结构 | canonical renderer 无条件输出固定 12 节 |
| `prd_template.md` 与 `prd_fillable_template.md` 都像正式模板 | 两套输出权威 | 前者成为固定 outline；后者降级为输入证据 worksheet |
| `prd.json` 同时保留 `P1..P6` 和展开字段 | 双重事实源、字段漂移 | 正式 JSON 只保留一个 `payload` |
| 缺少 PRD JSON Schema 和跨字段语义校验 | 下游只能猜测格式 | 新增 Draft 2020-12 schema 与 fail-closed semantic validator |
| `schema_version=2.0` 同时表达 envelope 与 PRD 内容版本 | 与 Leaf Gate `1.0` profile 冲突 | 分离为 `schema_version=1.0` 与 `artifact_schema_version=prd/v3` |
| Markdown 与 JSON 分别形成、缺少共同 hash 约束 | 证据源可能分叉 | 两者从同一 canonical model 生成，并写入 manifest hash |
| review hash 受时间戳或最终 review 内容影响 | 同内容复审身份不稳定 | 改为 canonical semantic subject hash |
| derive-all 只复制 `prd.md` | 子节点 bundle 不完整 | 五件套齐全后才允许提交目标目录 |
| 未文档化的 `parent_requirement` source enum | 枚举不一致 | 正式输出统一为 `valid_derivation`；仅在输入迁移层兼容旧值 |
| 固定安全/认证/日志等通用类别的歧义启发式 | 对不适用产品产生伪阻断 | 仅保留证据驱动的诊断，不允许启发式代替人类确认 |
| 未使用的 auto-fixer 和 orphan 推断逻辑 | 静默猜测 ownership 的风险 | 删除无调用、非确定性路径 |
| Architecture/Gherkin 没有直接 PRD 入口校验 | 跨阶段只能靠文字约定 | 在生产者侧增加 architecture/gherkin consumer profile 与测试 |

## 4. Canonical PRD v3

### 4.1 固定章节

1. Problem Statement
2. Scope and Non-goals
3. Current Release — Functional Requirements
4. Current Release — Non-functional Requirements
5. Architecture Input Contract
6. Success Metrics
7. Acceptance Contracts
8. Oracle Coverage Ledger
9. Future Backlog / Documented Exclusions
10. Risks, Dependencies, and Blocking Questions
11. Traceability Index
12. Review Report

章节名称、数量和顺序固定；空内容写稳定占位语义，不删除章节。

### 4.2 固定机器契约

- 顶层字段、payload 字段、枚举、ID pattern、缺省值及 `additionalProperties=false` 由 `schemas/canonical-prd.schema.json` 固定。
- 数组按稳定 ID/键排序，输入顺序变化不改变 canonical JSON 字节。
- 功能需求、NFR、acceptance contract、metric、ledger、traceability 的引用关系做跨字段校验。
- retired ID 不得复用；current requirement 必须 atomic 且有 evidence；ready 状态必须满足零阻塞及覆盖闭合。
- `depth/max_depth/node_history/requirements` 是 Leaf/递归 consumer profile，不进入 PRD 业务 payload。
- `module-result.json` 仍由根编排 adapter 负责，不伪装为独立 PRD 领域产物。

## 5. Council 裁决

三席完成复述门、三轮独立审议、匿名交叉审查和结构化表决。领域专家 Aristotle 权重 1.5，Ada 与 Feynman 各 1.0；`contract-core-strangler` 获得 `3.5/3.5`，超过 2/3 阈值，无少数反对。

共同 dealbreaker：继续保留多重事实源、静默启发式迁移，或没有真实消费者契约测试。Meadows 主席据此裁决采用“canonical model + schema + deterministic renderer + consumer profiles/tests”，并保留人工批准门。

## 6. 关键实现资产

- `scripts/prd_flow/canonical.py`：canonical model、语义校验与 Markdown renderer。
- `schemas/canonical-prd.schema.json`：唯一机器可读格式规范。
- `scripts/prd_flow/consumer_profiles.py`：canonical、Architecture、Gherkin、Leaf 四类收窄校验。
- `scripts/validate_prd.py`：便携校验入口。
- `tests/test_canonical_prd.py`：结构确定性、非法 mutation、round-trip、真实 Leaf 与 derive-all 合同测试。
- `SKILL.md`、`README.md`、templates、handoff contract：与实际实现同步后的操作说明。

## 7. 验证边界

已执行的证据：编译、CLI 帮助、8 项单元/契约测试、两个 JSON 文件解析、Markdown 表格结构、删除模块引用检查、真实 Leaf Gate 输入验证。

没有执行或声称：完整 Architecture 生成、完整 Gherkin 生成、Mocktest strict 运行、Leaf 递归执行、Vibe Coding 执行。本轮的 Architecture/Gherkin 结论是 producer-side profile compatibility，不等于两个消费者已完成自己的解析器迁移。

`ruff` 未安装，因此未执行 Ruff；本轮以 `compileall`、测试和结构扫描补足，但这不等价于 Ruff lint 结果。

## 8. 后续迁移顺序

1. 为 `prd-to-architecture-skill` 增加直接调用 `validate_prd.py --consumer architecture` 的入口，再重构其输出契约。
2. 为 `prd-to-gherkin` 增加 canonical PRD importer，并以 UNKNOWN/HYPOTHESIS/CONFLICT 状态做 fail-closed 映射。
3. 用同一 envelope/profile 策略依次统一 Mocktest、Leaf Gate 和 Vibe Coding adapter，不把 consumer profile 混入领域 payload。
4. 最后运行一条新的端到端样例链并冻结 artifact hashes；在此之前不宣称全链已经串通。
