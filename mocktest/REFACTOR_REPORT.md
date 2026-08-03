# Mocktest v2 重构报告

日期：2026-08-02

## 1. 目标与边界

本轮将 Mocktest 从“多入口、Markdown 形状驱动、多报告事实源”收敛为：

```text
Architecture v2 + Testcases v2 / verified Feature v2 view
→ canonical adapter
→ provenance-aware IR
→ strict runner
→ orthogonal states
→ deterministic bundle
```

不修改 PRD、Architecture、Testcases/Feature、Leaf Gate 或 Vibe Coding。历史 `.work`、
用户报告和 strict evidence 保持只读。减少假阴性不等于放宽业务门禁。

## 2. 阅读与盘点

排除 cache、`.work` 和二进制后，重构前 Mocktest 有 73 个项目自有文件、约 850 KB：

- `.agents/skills/validate-arch`：13 个严格执行/编排/报告文件；
- `src/mock_framework`：49 个 Python 源文件；
- `schemas`：6 个 JSON Schema；
- 另有配置、示例、README 和 pyproject。

审计覆盖 Skill、README、配置、schema、formal protocol、CLI、Loader、Architecture parser、
Gherkin parser、StepMapper、GapDetector、Pipeline、Simulator、Validator、strict helpers、主会话
driver、batch/sim driver、报告组装与 renderer。并以只读方式核对上游 Architecture v2 和
Testcases/Feature v2 的真实 schema、compiler、hash 与固定渲染合同。

## 3. 已确认的不合理与重复设计

### 3.1 五条执行事实源

并存：

1. `run_subagent_skill.py run-strict`；
2. `main_session_strict_driver.py`；
3. `sim_driver.py`；
4. `src/mock_framework/pipeline.py`；
5. batch prepare/aggregate 路径。

这些路径分别解释 loop、resume、blocked、phase 和最终状态。例如 main-session 把真实 hop
统一标为 `when`，另一条路径可能把末 hop 改成 `then`；blocked 又可能被写成 done、skip
或 global failure。同一证据因此可能得到不同 trace 和结论。

处理：v2 只承认 canonical adapter + canonical result + canonical publisher。旧路径在 shadow
迁移完成前保留为显式 legacy implementation，不能再定义公共输出。

原 `python -m mock_framework` / `mock-test` 的旧 Pipeline 编排入口已经移除，现统一进入
`canonical_cli.py`，只提供 v2 input inspection、workspace 初始化、schema export 和 retained
run publication。旧 `Pipeline` 类留作 shadow comparison，但已不能从公共 CLI 触发。

### 3.2 输入 parser 把“形状没匹配”当成“语义不存在”

旧 Architecture 路径依赖精确 Markdown 表头、章节名、文件前缀、隐藏 comment 和项目别名；
递归包预处理还会改写运行副本。Feature 路径会重建场景 ID、只取第一组 Examples，并用步骤
词汇推技术映射。GapDetector 和 StepMapper 又重复推断相同缺口。

处理：v2 直接读取 Architecture `payload.nodes/contracts/runtime_flows/state_ownership` 和
Testcases `tc_id/scenario_id/requirement_ids/steps/evidence_refs`。Feature 只做 deterministic
byte view 校验，绝不反向解析成产品事实。

### 3.3 入口绑定是猜测而非合同连接

旧路径综合组件名、描述词、局部 alias、业务词和可选 LLM 推断入口，格式变化容易产生
unresolved，也可能把近似词误绑定。

处理：v2 只通过 testcase requirement IDs → runtime flow requirement IDs → 有序首步
contract/to component → canonical contract ID 连接。结果为 `BOUND | AMBIGUOUS | UNBOUND |
INVALID`，候选携带字段路径 provenance。只有唯一候选可执行；confidence 不参与放行。

### 3.4 两套模型、三套 renderer、重复状态字段

legacy `ValidationReport` 与 strict `MocktestReport` 并存；report assembler、improvement
renderer、`report_enhancements.py` 各自重新分类和渲染。旧 schema 同时出现：

- `identity` 与重复顶层 project/node 字段；
- `coverage` 与重复 scenario count 字段；
- `started_at/finished_at` 与 `start_time/end_time`；
- `status/execution_status/validation_status/error_status` 的重叠含义。

处理：公共 v2 只有一个 result，正交拆分 execution、validation、audit、publication。
Markdown、Leaf evidence 和 execution log 只从该 result 派生，不能各自重判。

### 3.5 空场景、缺维度和 WARNING 可误 PASS

旧路径存在“缺失维度默认 PASS”“0 场景可 PASS”“WARNING 被 Skill 返回 PASS”等非闭合状态。

处理：固定真值表。零场景/未评估是 `NOT_EVALUATED`，未启动/阻塞/部分执行的 overall 为
`BLOCKED`；只有 execution COMPLETED + validation PASS + audit PASS 才是 overall PASS。

### 3.6 hash 和时间字段不稳定

旧 `input_fingerprint/input_hash` 有路径实际填 run ID；output hash 漏掉 Markdown/execution
log；UUID、时间戳、未排序 JSON 和 dict 遍历导致同输入/响应不可重复。

处理：UTF-8/LF/terminal newline/sorted keys；语义 hash 排除自身、执行时间和本机绝对路径；每个内容文件
有 SHA-256，bundle hash 覆盖稳定文件清单。测试证明相同 run evidence 发布到两个目录时五个
交付文件字节完全相同；同一输入移至不同目录时 `input_fingerprint` 不变。

### 3.7 项目特定补丁污染通用 Skill

`patch_plan.py` 硬编码教学/隐私业务组件、合同、NFR、状态和 testcase IDs，并写回
`plan_locked.json`。它既没有通用调用方，也会绕过真实 Architecture。

处理：已物理删除 `patch_plan.py`。`report_enhancements.py` 中旧业务分类只允许服务 legacy
view；v2 publisher 不调用它。剩余 legacy renderer 在等价迁移完成后再删除。

默认配置同时移除了特定 `AuthController/LoginService` 延迟数据、第三方 base URL、默认 API
Key 环境变量和自动改架构开关；canonical 默认使用 strict driver 注入的 Codex subagent，
`auto_modify=false`、`max_modify_rounds=0`。

## 4. 新统一输入合同

### Architecture

- `artifact_schema_version=architecture/v2`
- `status=PASS`
- `ready_for_downstream=true`
- `content_sha256` 验证通过
- `architecture_mode=top_level|decompose`，两种模式共用同一 IR/输出格式

### Testcases / Feature

- 机器权威：`testcases.json`, `artifact_schema_version=testcases/v2`
- 人类/工具视图：`testcases.feature`, `feature/v2`
- 若 CLI 接收 `.feature`，必须存在 sibling `testcases.json`，且 Feature bytes 必须等于从
  Testcases v2 确定性渲染的 bytes；不反向解析 Feature。

### 身份

Architecture/Testcases 的 project/node/parent/PRD lineage 和 artifact identity 不一致时，在 runner
前失败。三者的 producer/execution `run_id` 可独立；canonical 与 legacy 分支不能混合。

## 5. 新固定中间产物

| 顺序 | 文件 | Schema |
|---:|---|---|
| 1 | `run_manifest.json` | `mocktest-run/v2` |
| 2 | `normalized_input.json` | `mocktest-normalized-input/v2` |
| 3 | `extraction_report.json` | `mocktest-extraction/v2` |
| 4 | `execution_plan.json` | `mocktest-plan/v2` |
| 5 | `scenario_events.json` | `mocktest-events/v2` |
| 6 | `contract_check.json` | `mocktest-contract-check/v2` |
| 7 | `validator_results.json` | `mocktest-validator-results/v2` |
| 8 | `strict_audit.json` | `mocktest-audit/v2` |
| 9 | `execution_log.json` | `mocktest-execution-log/v2` |

所有路径在 dispatch 前物化；BLOCKED、ERROR、zero-hop 使用合法空集合。迁移期的
`plan/hops/compat/val_results` 是 private evidence，不是下游合同。

## 6. 新固定最终报告

固定五件套：

1. `mocktest_report.json`
2. `mocktest_report.md`
3. `leaf_gate_evidence.json`
4. `execution_log.json`
5. `bundle_manifest.json`

主报告的 `source_artifacts` 固定保留两个上游 artifact 的 ID、类型、Schema 与 SHA-256，
不泄露或绑定本机绝对路径。

Markdown 永远是七章：Identity、State Summary、Coverage、Findings、Extraction Diagnostics、
Evidence、Errors。无 findings/errors 时仍保留表头和 `None`，章节不会增删。

Finding 固定包含 `finding_id/origin/category/severity/scope/tc_ids/requirement_ids/
component_ids/contract_ids/summary/evidence_refs`。解析/runner/tool 问题不再映射成 Architecture
业务缺陷；top-level/decompose 的默认 finding scope 分别为 TOP_LEVEL/MODULE，validator 显式
scope 可覆盖，禁止从建议文本猜 scope。

## 7. Schema 去重

新增 `schemas/mocktest-run.schema.json` 作为公共 `$defs` registry。report、Leaf evidence 和
execution log schema 只用 `$ref`，不再复制公共 envelope。删除本地重复的 Architecture v1 /
Testcases v1 normalized schema；上游 producer 继续拥有各自 canonical schema。

`write_schemas()` 已改为复制 checked-in registry，不再从旧 Pydantic 模型重新生成并覆盖 v2。

## 8. 兼容迁移与暂不删除内容

依据 Council 的 minority condition，本轮没有一次性删除：

- `main_session_strict_driver.py`
- `sim_driver.py`
- `pipeline.py`
- `StepMapper`
- `GapDetector`
- legacy renderer / report enhancements

原因不是认可重复设计，而是当前 compact checkout 原先没有测试语料，无法证明 resume、partial、
cache、zero-hop 等历史边界等价。它们已被降级为 private legacy/shadow 路径。待规定语料完成
字段、状态、产物等价后再物理删除，避免把重构变成不可审计的行为回归。

## 9. 验证证据

- canonical contract 回归：23 passed；
- 覆盖 Top-Level、Decompose、BOUND、UNBOUND、AMBIGUOUS、多 When；
- Feature v2 view 与 sibling Testcases v2 byte match / drift rejection；
- BLOCKED 固定空产物；
- execution/validation/audit 真值表；
- 相同 evidence 的五文件 byte determinism；
- strict `prepare` 实际绕过 Markdown parser 并生成 READY plan；
- Draft 2020-12 schema 自检和所有 canonical 中间/最终 JSON 实例验证；
- v2 input manifest 示例验证。
- producer run ID 与 Mocktest run ID 独立、跨分支 PRD lineage 拒绝、跨目录 fingerprint 稳定。

完整 strict component/validator 模型执行没有在本轮伪造；它仍需要真实 Architecture/Testcases
bundle、真实 subagent 响应和独立 strict audit 才能产生业务 PASS/FAIL。

当前 Leaf Gate reader 仍要求旧顶层 `status/defects`、common envelope 与共享 run ID；本轮未越界
修改它。`mocktest-report/v2` 的下游 adapter 必须在 Leaf Gate 重构中完成，因此本轮不声称全链
Leaf Gate 兼容或业务 PASS。
