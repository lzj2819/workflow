# Leaf Gate Override ? CMP-INTENT-PARSER

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-INTENT-PARSER（L2 → 下一层）

本文件是下一层细化的唯一入口。Human Gate 批准后，可使用 `[NEXT child_id]` 选择下表精确 ID；不得把当前目标 ID 当作子节点 ID。

## 1. 当前节点身份与父层绑定

| 条目 | 值 |
|---|---|
| 节点 | `CMP-INTENT-PARSER`（L2，MOD-01 内部组件） |
| 职责 | 自然语言提交指令 → `SubmissionIntent`；确定性检查 assignment/student_name/group_name 并返回具体缺失字段 |
| 排除项 | 不持久化、不创建任务、不上传、不采集材料、不调用服务端、不做服务端归属校验 |
| 直接父包 | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` |
| 当前 PRD | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-intent-parser/prd.md` |
| 绑定契约 | `IC-M01-01`、只读 `IC-M01-02` |
| 绑定决策 | L1 `LCD-001`、`INV-1`、DU-1；本层 `LCD-IP-001~003` |
| 部署/运行时 | 学生本机 Codex Plugin 进程内；无独立服务或公共运行时边界 |
| 边界指纹 | 详见 `architecture-manifest.yaml §boundary_fingerprint` 与 `01-design-context.md §2` |

## 2. 下一层可选 child_id（按稳定 ID 排序）

| child_id | 一句话职责 | 建议细化焦点 | 需求/父层追踪 |
|---|---|---|---|
| UNIT-INTENT-PARSER-COMMAND-ADAPTER | 实现 IC-M01-01 入口/出口并编排内部链 | 端口适配、请求上下文边界、配置只读引用 | `REQ-DD001`；`IC-M01-01/02` |
| UNIT-INTENT-PARSER-FIELD-EXTRACTOR | 从自然语言中提取三字段候选 | 宿主能力/本地规则选择；候选来源与不确定性 | `REQ-DD001`；L1 `LCD-001` |
| UNIT-INTENT-PARSER-NORMALIZER | 规范化字段候选并识别空值/冲突 | Unicode/空白、别名、冲突保留和诊断 | `D-AC-REQ-001-01`；`INV-IP-03` |
| UNIT-INTENT-PARSER-REQUIRED-FIELD-GATE | 确定性判断是否返回完整意图 | 三字段闸门、fail-closed、缺项错误映射 | `F1-1`；`INV-1`；`IC-M01-01` |

所有子节点均有直接需求或父层追踪；`trace_exemption_reason` 缺省数为 0。

## 3. 继承及内部契约清单

**继承契约（语义不可变）**：

- `IC-M01-01`：`command_text` → `SubmissionIntent` 或 `MissingFields`，provider 为当前组件、consumer 为 `CMP-PENDING-QUEUE`。
- `IC-M01-02`：`CMP-CONFIG-STORE` → 当前组件的只读 `EffectiveConfig` 查询；配置所有权不变。

**内部契约**：

| 契约 ID | 名称 | Owner → Consumer |
|---|---|---|
| IC-IP-01 | 解析请求上下文 | COMMAND-ADAPTER → FIELD-EXTRACTOR |
| IC-IP-02 | 候选字段提取 | FIELD-EXTRACTOR → NORMALIZER |
| IC-IP-03 | 规范化候选 | NORMALIZER → REQUIRED-FIELD-GATE |
| IC-IP-04 | 确定性放行结果 | REQUIRED-FIELD-GATE → COMMAND-ADAPTER |

字段、错误和兼容语义详见 `04-contracts-and-runtime.md §3`。

## 4. 状态所有权清单

| 状态 ID | 状态 | Owner | 持久化 |
|---|---|---|---|
| ST-IP-01 | ParseRequestContext | COMMAND-ADAPTER | none，单次调用 |
| ST-IP-02 | ExtractedSlotCandidates | FIELD-EXTRACTOR | none，单次调用 |
| ST-IP-03 | NormalizedIntentCandidate | NORMALIZER | none，单次调用 |
| ST-IP-04 | ParseResult | REQUIRED-FIELD-GATE | none，返回即释放 |

关键不变量：`INV-IP-01` 缺项/歧义不放行；`INV-IP-02` 无副作用；`INV-IP-03` 指令优先；`INV-IP-04` 可重复；`INV-IP-05` 结果互斥。

## 5. 决策继承、本地决定与委托

- 继承：L1 `LCD-001`、`IC-M01-01/02`、`INV-1`、DU-1、无网络/无持久化边界。
- 本层已决定：`LCD-IP-001`（分层解析）、`LCD-IP-002`（歧义 fail-closed）、`LCD-IP-003`（配置只读参考）。
- 委托下一层：`LCD-IP-004`，由 `UNIT-INTENT-PARSER-FIELD-EXTRACTOR` 细化具体宿主能力/规则策略。
- 无 `return_to_parent`。若提取器需要外部 NLU、共享缓存、修改父契约或新增公共运行时边界，必须暂停并返回父层。

## 6. 未解决风险与推荐下一步

| 事项 | 影响 | 建议 |
|---|---|---|
| 宿主 Codex NL 能力未由父层规定 | 影响提取器实现，不影响本层结构 | 先细化 `UNIT-INTENT-PARSER-FIELD-EXTRACTOR`；禁止未经批准新增外部依赖 |
| 字段别名和歧义判定词典未定 | 影响规范化细节 | 在 NORMALIZER/EXTRACTOR 下一层作为 implementation_detail 固化并保留来源证据 |
| 日志隐私策略 | 影响可观测实现 | 只记录结果类型、字段名、耗时和版本，不记录完整 command_text |

推荐顺序：

1. `UNIT-INTENT-PARSER-REQUIRED-FIELD-GATE`：验收闸门和 `INV-1` 风险最高。
2. `UNIT-INTENT-PARSER-FIELD-EXTRACTOR`：落实宿主能力未决项。
3. `UNIT-INTENT-PARSER-NORMALIZER`：确定字段别名、空值和冲突规则。
4. `UNIT-INTENT-PARSER-COMMAND-ADAPTER`：最后固化端口适配与编排。

## 7. 实际输入/输出、验证证据与未完成项

### 实际解析输入

| 输入 | 路径 | 状态 |
|---|---|---|
| parent_architecture | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` | 已读；递归父包，匹配唯一 |
| target_node_id | `CMP-INTENT-PARSER` | 已在 L1 三份产物中精确唯一匹配 |
| current_prd | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-intent-parser/prd.md` | 已读；`REQ-DD001` 与 D-AC-REQ-001-01 ready |
| output_dir | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L2/mod-01/L2-mod-01-cmp-intent-parser` | 写入前不存在，安全创建 |
| parent_prd | 未使用 | 父包已提供足够追踪，不需要补读 |

### 实际生成输出

已生成七个标准文件：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。未生成 `parent-change-request.md`。

### 验证检查

| 检查 | 结果 |
|---|---|
| 四必需输入与输出安全 | 通过 |
| 父包识别与目标唯一匹配 | 通过 |
| 需求和验收契约追踪 | 通过 |
| 子节点追踪列与稳定 ID | 通过；4 个子节点，豁免数 0 |
| 父契约语义不变 | 通过；`IC-M01-01/02` 无字段、owner、失败、版本变化 |
| 状态所有权未转移 | 通过；全为瞬态，无持久 owner |
| 决策队列 | 通过；无未处理 `decide_now`，无 `return_to_parent` |
| 清单稳定排序 | 通过；child/contract/state/decision 均按稳定 ID 排序 |

### 未完成项与阻塞影响

- 提取机制的具体宿主能力或规则库仍为 implementation_detail，交由下一层细化。
- 若未来需要外部 NLU、持久化解析缓存或父契约变更，当前包必须走 `return_to_parent`；此项不阻塞当前 Human Gate。
- 当前包内部一致，可进入一次 Human Gate。
