# Leaf Gate Override ? CMP-CONFIG-STORE

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — CMP-CONFIG-STORE L2

## 1. Current node binding

| Item | Value |
|---|---|
| Current node | `CMP-CONFIG-STORE` |
| Level | L2 component refinement |
| Responsibility | `PluginConfig` 本地持久化、读取、校验、完整性标记与有效配置保留 |
| Exclusions | 网络/上传/材料/对话/归属校验；父公共契约修改；独立服务、数据库、消息总线、部署单元 |
| Parent package | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` |
| Parent node | `MOD-01` |
| Current PRD | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-config-store/prd.md` |
| Boundary fingerprint | `CMP-CONFIG-STORE`, `ST-01`, `IC-M01-02`, `IC-M01-05 ConfigView`, `REQ-D002/REQ-DD002`, `D-AC-REQ-002-01`, `KD-005`, `A-007`, `DU-1` |

## 2. Next-level target registry

以下 `child_id` 可直接作为下一次递归调用的 `target_node_id`，按稳定 ID 排序。

| child_id | Responsibility | Exclusions | State | Requirement/parent trace | Recommended next focus |
|---|---|---|---|---|---|
| `CMP-CS-CONFIG-PORT` | 保存/读取入口与内部流程编排、EffectiveConfig 装配 | 不直接写状态、不执行 schema 细节、不做网络 | 请求上下文、派生视图 | `REQ-DD002`; `D-AC-REQ-002-01`; `IC-M01-02`; `IC-M01-05` | 请求模型、端口兼容和视图错误映射 |
| `CMP-CS-DIRECTORY-PROBE` | 三个配置目录的存在/可读/为空/错误探测 | 不持久化、不修改目录、不判断服务端白名单 | `DirectoryProbeResult` | `REQ-DD002`; `D-AC-REQ-002-01` | 平台文件系统 API、权限错误映射和超时边界 |
| `CMP-CS-SCHEMA-VALIDATOR` | 配置字段、格式、schema version 兼容性校验 | 不探测目录、不写状态、不做归属校验 | `ValidatedConfigCandidate` | `REQ-DD002`; `D-AC-REQ-002-01.exceptions`; `ST-01` | schema 定义、字段错误模型、迁移兼容规则 |
| `CMP-CS-STATE-STORE` | `ST-01` 唯一持有、读取、原子替换、旧值保留 | 不接收未验证候选、不探测目录、不暴露可写公共接口 | `ST-01 PluginConfig` | `ST-01`; `IC-M01-02`; `A-007` | 序列化、文件锁、并发策略、原子替换 primitive |

## 3. Contract registries

### Inherited contracts

| ID | Provider | Consumers | Binding |
|---|---|---|---|
| `IC-M01-02` | `CMP-CONFIG-STORE` | 设置页及父层配置读者 | 全量写入；读取 `EffectiveConfig`；`ConfigSaved/ConfigRejected`；语义不变 |
| `IC-M01-05` ConfigView | `CMP-CONFIG-STORE` / `CMP-PENDING-QUEUE` | `CMP-STATUS-PRESENTER` | `values`、`completeness[]`、`dir_errors[]`；展示不伪造结论 |

### Child-only contracts

| ID | Provider | Consumer | Purpose |
|---|---|---|---|
| `IC-CS-001` | `CMP-CS-SCHEMA-VALIDATOR` | `CMP-CS-CONFIG-PORT` | 纯配置候选校验 |
| `IC-CS-002` | `CMP-CS-DIRECTORY-PROBE` | `CMP-CS-CONFIG-PORT` | 当前目录事实探测 |
| `IC-CS-003` | `CMP-CS-STATE-STORE` | `CMP-CS-CONFIG-PORT` | 有效候选原子提交 |

## 4. State ownership registry

| State ID | Owner | Lifecycle | Consistency |
|---|---|---|---|
| `ST-01` | `CMP-CS-STATE-STORE` | 有效保存后持续存在；无效保存不改变 | 单写方、全量原子替换 |
| `ST-CS-01` | `CMP-CS-SCHEMA-VALIDATOR` | 单次保存请求内 | 纯校验结果，不持久化 |
| `ST-CS-02` | `CMP-CS-DIRECTORY-PROBE` | 单次保存/读取请求内 | 当前事实，不反写 `ST-01` |
| `ST-CS-03` | `CMP-CS-CONFIG-PORT` | 单次响应内 | 由配置快照和目录探测结果一致装配 |

## 5. Decisions and unresolved risks

- **已决定**：`LCD-CS-001` 校验先行+原子提交；`LCD-CS-002` 格式无效拒绝、目录问题显式标记；`LCD-CS-003` 保存探测+读取重探测；`LCD-CS-004` schema version 兼容读取。
- **继承**：`ST-01` 单写方、`IC-M01-02`/`IC-M01-05`、`A-007`、`KD-005`、`DU-1`。
- **下沉**：具体序列化、文件锁、原子替换 API、平台目录 API、字段错误文案。
- **风险**：平台文件系统的权限错误分类需在 `CMP-CS-DIRECTORY-PROBE` 细化时验证；当前不影响组件边界。
- **追踪豁免**：0；所有 child 都有需求或父层追踪。

## 6. Actual input/output inventory

### Inputs verified

- L2 PRD：存在并已读取。
- L1 parent architecture：存在并已读取。
- `CMP-CONFIG-STORE`：在 L1 decomposition、handoff 和 manifest 中唯一匹配。
- Output directory：存在但为空，按 `new` 模式安全创建。

### Outputs generated

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

## 7. Validation result and Human Gate

| Check | Result |
|---|---|
| 四项必需输入解析 | pass |
| 目标节点唯一匹配 | pass |
| 父边界/契约/状态所有权可用 | pass |
| 子节点均有稳定 ID 和需求/父层追踪 | pass |
| 父契约语义未改变 | pass |
| 父/兄弟状态所有权未转移 | pass |
| 未新增服务、存储平台、消息总线或部署边界 | pass |
| 决策队列无遗留 `decide_now` / `return_to_parent` | pass |
| 文件清单、排序和交接信息完整 | pass |

**未完成项及影响**：具体实现 primitive 留给下一层；无阻塞影响。

**当前状态**：`ready_for_human_gate`。

下一步可使用：`[NEXT CMP-CS-STATE-STORE]`、`[NEXT CMP-CS-SCHEMA-VALIDATOR]`、`[NEXT CMP-CS-DIRECTORY-PROBE]` 或 `[NEXT CMP-CS-CONFIG-PORT]`。
