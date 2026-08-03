# Mocktest / validate-arch

Mocktest 验证当前层 Architecture 是否能够支撑 canonical Testcases。它不会修改
Architecture 或 Feature，也不会用近似词、显示名或 LLM 猜测来补齐缺失合同。

当前公共合同是 `mocktest/v2`：Architecture v2 和 Testcases v2 先进入唯一
Canonical IR，再由 strict runner 产生证据，最后从同一个结果对象发布固定 bundle。

## 1. 规范流程

```text
architecture/v2 + testcases/v2 (feature/v2 是测试用例的确定性视图)
                      │
                      ▼
        versioned canonical-v2 adapter
                      │
                      ▼
 normalized_input + extraction_report + execution_plan
                      │
              BOUND? ├── no ──► BLOCKED + 固定空产物
                      ▼
        单一 strict runner / one hop per component
                      │
                      ▼
 contract_check + validator_results + strict_audit
                      │
                      ▼
       one Canonical Result / fixed delivery bundle
```

Markdown Architecture 和旧 `.feature` 仍可通过 `legacy-markdown/v1` 兼容入口运行，
但它们不是公共事实源。旧 Pipeline、StepMapper、GapDetector 和旧 renderer 只承担
迁移兼容；完成 shadow 等价验证前不会物理删除，且不得定义 v2 输出状态。

## 2. 输入合同

推荐直接传入：

- `prd-to-artecture-skill` 生成的 `architecture.json`，
  `artifact_schema_version=architecture/v2`；Top-Level 和 Decompose 两种模式使用同一
  schema，`architecture_mode` 分别为 `top_level` 与 `decompose`。
- `prd-to-gherkin` 生成的 `testcases.json`，
  `artifact_schema_version=testcases/v2`。`.feature` 是 `feature/v2` 只读视图，不是
  第二事实源。

两项输入必须同时为 v2，且 `project_id`、`node_id`、`parent_node_id`、PRD 身份和内容 hash 必须一致。
不得把一个 v2 JSON 与一个 legacy Markdown/Feature 混合进入同一次运行。

Architecture、Testcases 和 Mocktest 的 `run_id` 分别表示各自 producer/execution，不要求
三者相等；跨阶段身份由 project/node/parent/source PRD 与 artifact hash 共同约束。

### 确定性入口绑定

Canonical adapter 使用以下证据绑定测试场景：

1. Testcase 的 `requirement_ids`；
2. Architecture `payload.runtime_flows[].requirement_ids`；
3. 匹配 flow 的有序首步 `contract_id` 与 `to_id`；
4. `payload.contracts[]` 中同 ID 的合同。

绑定状态固定为：

| 状态 | 含义 | 是否可执行 |
|---|---|---|
| `BOUND` | 恰好一个 component/contract/flow 候选 | 是 |
| `AMBIGUOUS` | 多个合法候选 | 否 |
| `UNBOUND` | 无候选 | 否 |
| `INVALID` | 身份、hash 或结构无效 | 否 |

`confidence` 只用于诊断，不参与放行。`AMBIGUOUS`、`UNBOUND` 和 `INVALID` 不能被
entry override 或近似别名提升为 strict PASS。每个候选必须保留字段级 provenance。

## 3. 安装与预检

要求 Python 3.10+、Codex CLI 和项目依赖：

```powershell
python -m pip install -e .
python .agents\skills\validate-arch\scripts\preflight.py --root .
```

## 4. 执行

### Canonical v2（推荐）

```powershell
python .agents\skills\validate-arch\run_subagent_skill.py run-strict `
  --arch <architecture-bundle>\architecture.json `
  --feature <testcase-bundle>\testcases.json `
  --output-dir .work\validate-arch\runs\<run-id> `
  --slim-prompts `
  --compact-trace
```

`--feature` 为兼容现有 CLI 名称；传入 Testcases v2 时它表示机器权威
`testcases.json`。也可传 sibling `testcases.feature`，但 adapter 会先要求同目录存在
`testcases.json`，并逐字节验证 Feature 等于 canonical JSON 的确定性视图；不会把 Feature
反向解析成第二份事实。

也可使用 `mocktest-input/v2` manifest。manifest 中 Architecture/Testcases 分支必须
分别声明 `architecture/v2` 和 `testcases/v2`。

### 主会话 strict driver

需要由 Codex 主会话逐个派发 component/validator 时，使用：

```powershell
python .agents\skills\validate-arch\main_session_strict_driver.py init `
  --arch <architecture.json> `
  --feature <testcases.json> `
  --output-dir .work\validate-arch\runs\<run-id>
```

随后严格执行 `next-components → consume-component → prepare-validators →
next-validators → consume-validator → finalize`。同一场景的 hop 串行，不同场景可并行。
`finalize` 与 `run-strict` 都调用相同的 v2 bundle publisher。

### 重新发布已完成运行

```powershell
python scripts\canonicalize_run.py `
  --run-dir .work\validate-arch\runs\<run-id> `
  --output-dir reports\<run-id>
```

重新发布不会重新模拟；它只消费保留的规范输入和 strict 证据。

## 5. 固定中间产物

Canonical run workspace 每次都包含以下文件；阻塞、零 hop 和错误路径也必须写出
合法空集合，不能因为“没有执行”而缺文件。

| 文件 | Schema | 作用 |
|---|---|---|
| `run_manifest.json` | `mocktest-run/v2` | 输入指纹与固定文件清单 |
| `normalized_input.json` | `mocktest-normalized-input/v2` | 唯一规范输入快照 |
| `extraction_report.json` | `mocktest-extraction/v2` | 绑定候选、provenance、歧义与诊断 |
| `execution_plan.json` | `mocktest-plan/v2` | 场景、原始步骤、绑定和 READY/BLOCKED |
| `scenario_events.json` | `mocktest-events/v2` | 有序 component hop 事件 |
| `contract_check.json` | `mocktest-contract-check/v2` | 确定性合同检查 |
| `validator_results.json` | `mocktest-validator-results/v2` | 每场景独立判断 |
| `strict_audit.json` | `mocktest-audit/v2` | 证据结构审计 |
| `execution_log.json` | `mocktest-execution-log/v2` | 规范事件账本 |

迁移期还可能看到 `plan.json`、`hops.json`、`compat.json`、`val_results.json`、
`subagent_calls.jsonl` 等 private legacy evidence。下游不得读取这些文件。

## 6. 固定交付 bundle

每次发布固定生成五个文件：

| 文件 | 用途 |
|---|---|
| `mocktest_report.json` | 唯一机器主结果，`mocktest-report/v2` |
| `mocktest_report.md` | 从同一 JSON 纯渲染的固定七章节视图 |
| `leaf_gate_evidence.json` | Leaf Gate 最小 ALLOW/BLOCK/ERROR 证据 |
| `execution_log.json` | 固定执行状态和事件 |
| `bundle_manifest.json` | 四个内容文件的 SHA-256 与 bundle hash |

JSON 使用 UTF-8、LF、terminal newline、稳定键排序；数组按稳定 ID 或显式顺序。
Markdown 不参与业务判定。`content_sha256` 排除自身字段；`bundle_sha256` 覆盖文件
清单和每个文件 hash。时间戳和本机绝对路径不进入语义 `input_fingerprint`；报告通过
不含本机路径的 `source_artifacts` 保留 producer artifact ID、版本与 SHA-256。

公共 JSON Schema 位于 `schemas/mocktest-run.schema.json`。其余输出 schema 只通过
`$ref` 指向公共 `$defs`，不再复制 `ArtifactRecord` 或状态字段。

## 7. 状态代数

最终结果不再用单个 `status` 混合不同事实：

| 维度 | 枚举 |
|---|---|
| `execution_state` | `NOT_STARTED / BLOCKED / PARTIAL / COMPLETED / ERROR` |
| `validation_verdict` | `NOT_EVALUATED / PASS / WARNING / FAIL` |
| `audit_state` | `NOT_RUN / PASS / FAIL` |
| `publication_state` | `NOT_STARTED / COMPLETE / ERROR` |
| `overall` | `PASS / WARNING / FAIL / BLOCKED / ERROR` |

派生规则：

- 工具/产物错误或 audit FAIL → `overall=ERROR`；
- 未启动、绑定阻塞或部分执行 → `overall=BLOCKED`；
- 执行完整且业务失败 → `overall=FAIL`；
- 执行完整且只有警告 → `overall=WARNING`；
- 只有执行完整、audit PASS、validation PASS 才是 `overall=PASS`。

strict audit PASS 只证明证据链完整，不能替代 validation PASS。

## 8. 退出码

| 退出码 | 含义 |
|---:|---|
| `0` | `overall=PASS` |
| `2` | 有效 `FAIL / WARNING / BLOCKED` 结果 |
| `3` | 输入路径、依赖或配置错误 |
| `4` | 执行、证据或发布错误 |
| `5` | Schema、身份或跨阶段契约错误 |

## 9. Legacy 迁移边界

当前保留 legacy adapter 是为了验证兼容，不代表两条公共流程：

- legacy 只可把旧输入转成 Canonical IR；
- 不允许 legacy renderer 决定 v2 状态；
- 旧 domain-specific `patch_plan.py` 已删除；
- 只有 normal、multi-When、ambiguous、unbound、zero-hop、partial、tool-error、
  top-level 和 decompose fixtures 全部完成字段/状态/产物 shadow 等价后，才能删除
  旧 driver、StepMapper、GapDetector 或 renderer。

## 10. 开发验证

```powershell
python -m compileall -q src scripts
python -m pytest -q
```

最低回归矩阵：

- Top-Level Architecture v2；
- Decompose Architecture v2；
- Feature v2 多 `When`；
- 唯一绑定、无绑定、多绑定；
- 输入数组重排后的 fingerprint/plan 稳定性；
- zero-hop、partial、PASS、WARNING、FAIL、ERROR；
- 相同输入和相同 response evidence 的 bundle hash 一致；
- Markdown 七章节和表头始终一致。

## 11. 安全边界

- Architecture、Testcases 和 Feature 是冻结输入，不自动修改；
- 不手工补写调用日志或伪造 hop；
- 不把组件 ID 当事件，不把显示名当 contract ID；
- 不在 audit FAIL 或执行不完整时声称 strict 完成；
- `.work` 是可变执行证据，正式交付目录与它分离；
- 不分发 `.env`、凭据、缓存、历史业务输入或用户报告。
