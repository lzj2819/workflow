# Leaf Gate Override ? SI-CORE

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — SI-CORE submission-core L2

> 本文件是 L2 包交接入口。当前包状态为 `ready_for_human_gate`；Human Gate 批准后，下一次递归细化使用下表中精确的 `child_id` 作为 `target_node_id`。

## 1. 节点身份与父层绑定

- **当前节点**：`target_node_id=SI-CORE`，名称 `submission-core`，层级 L2。
- **父节点**：`MOD-02/submission-intake`，父包 `architecture/L1/L1-mod-02`，部署边界 `DU-2 course-app`，进程内组件，不独立部署。
- **职责**：Submission 聚合唯一写入口、状态机守卫、材料清单、完整性报告、缺失项标记、单事务状态/报告/Outbox 组合提交、CT-002 查询、评分和清除回写。
- **排除项**：HTTP/认证、分片会话、文件/配额、名单校验、Outbox 投递/入站去重、清除批处理、评分、教师端和保留期计算。
- **边界指纹**：`ST-01`、`INV-1..INV-5`、`IC-SI-04`、`IC-SI-05`、`CT-001/002/003/004/005/006/012/014`、`KD-002/003/004/005`、`LCD-002/003`、`DU-2`。

## 2. 下一层 target_node_id 清单（按稳定 ID 排序）

| child_id | 名称 | 一句话职责 | 主要状态/边界 | 需求与父层追踪 | 建议下一步 |
|---|---|---|---|---|---|
| SI-CORE-AGG | submission aggregate lifecycle | Submission 身份、状态机守卫、终态和回写幂等 | `SIC-ST-01`、INV-1/2/6 | REQ-DD001/004；IC-SI-04；ST-01 | 细化状态迁移表、版本/锁定策略、命令处理和查询快照 |
| SI-CORE-INTEGRITY | material manifest and integrity report | 材料清单、类别声明、完整性报告和缺失项 | `SIC-ST-02/03`、INV-3/4/5 | REQ-DD001/002/004；REQ-D001/002/004 | 细化类别规范化、报告模型、SI-STORE 元数据端口和缺失项排序 |
| SI-CORE-TX | transaction coordinator | 聚合/报告/父 Outbox 的单一本地事务组合 | `SIC-TX-BOUNDARY`；不拥有父 ST-04 | REQ-DD001/002/004；IC-SI-04/05；KD-002 | 细化事务脚本、失败回滚、幂等重试和持久化适配；不选择父数据库产品 |

## 3. 继承契约注册表

| contract_id | 当前 L2 角色 | 实现映射 |
|---|---|---|
| CT-001 | 参与提供 | SI-API → SI-CORE-TX；TX 组合 AGG/INTEGRITY 并写 CT-004/006 Outbox |
| CT-002 | 参与提供 | SI-API → SI-CORE-AGG query port |
| CT-003 | 参与消费 | 只消费 SI-VERIFY 结论；不直接调用 MOD-03 |
| CT-004 | 参与发布 | TX 同事务请求 SI-RELAY 写入；task_persisted 后回写 processing |
| CT-005 | 参与消费 | SI-RELAY 去重后 → TX/AGG 状态终态回写 |
| CT-006 | 参与发布 | ConfirmReceived/MarkUploadFailed 两条命令均按父 schema 写入 |
| CT-012 | 参与消费 | SI-PURGE 调用 TX/AGG 的单项 PurgeSubmission |
| CT-014 | 非 owner 参与 | 单项删除结果返回 SI-PURGE；组装/发布仍归 SI-PURGE/SI-RELAY |

## 4. L2 内部契约注册表

| contract_id | owner → consumer | 用途 |
|---|---|---|
| IC-SIC-01 | SI-CORE-AGG → SI-CORE-TX | 生命周期命令、状态守卫和幂等结果 |
| IC-SIC-02 | SI-CORE-INTEGRITY → SI-CORE-TX | 材料元数据到清单/报告的构建 |
| IC-SIC-03 | SI-CORE-AGG → SI-CORE-TX/SI-API | 已提交 Submission 一致只读查询 |
| IC-SIC-04 | SI-CORE-TX → SI-API/SI-RELAY/SI-PURGE | 事务内命令编排与父端口适配；`04-contracts-and-runtime.md` 的 `operation_contract_registry` 按操作声明字段、错误、依赖和 next_hop |

## 5. 状态所有权注册表

| state_id | 状态 | owner | 物理写入边界 |
|---|---|---|---|
| SIC-ST-01 | Submission identity/lifecycle | SI-CORE-AGG | SI-CORE-TX 通过聚合端口提交 |
| SIC-ST-02 | MaterialManifest | SI-CORE-INTEGRITY | SI-CORE-TX 与 ST-01 同事务提交；文件本体仍 SI-STORE |
| SIC-ST-03 | IntegrityReport | SI-CORE-INTEGRITY | SI-CORE-TX 与 ST-01/02 同事务提交 |
| SIC-ST-04 | TransitionResult（短生命周期返回值） | SI-CORE-AGG | 不持久化为新状态 |

父 `ST-03`、`ST-04`、`ST-05`、`ST-07` 的所有权没有转移；本包没有 trace exemption。

## 6. 决策与风险

- **已决定**：`LCD-SIC-001` 采用 SI-CORE-TX 事务协调者；`LCD-SIC-002` 报告作为 Submission 内值对象；`LCD-SIC-003` 不建立独立读模型；`LCD-SIC-004` 所有回写统一走状态守卫。
- **委托下一层**：`LCD-SIC-005` 数据库/索引/ORM 等持久化细节；`LCD-SIC-006` 类别规范化、报告字段和错误码内部映射。
- **实现细节**：`LCD-SIC-007` 事务框架、锁配置和重试参数。
- **继承不重开**：KD-002/003/004/005、LCD-002、LCD-003；父数据库产品仍处于 defer 状态。
- **未决风险**：Human Gate 尚未批准；批准前不得使用 `[NEXT SI-CORE-*]` 继续递归。当前没有 parent-impacting blocker；本次操作级契约和验证场景修改完成后需重新运行 strict validation。

## 7. 实际输入/输出与验证结果

### 实际输入

- `prd/L2-PRD/mod-02/L2-mod-02-si-core/prd.md`
- `architecture/L1/L1-mod-02/architecture-manifest.yaml`
- `architecture/L1/L1-mod-02/01-design-context.md`
- `architecture/L1/L1-mod-02/02-architecture-decomposition.md`
- `architecture/L1/L1-mod-02/03-state-and-data.md`
- `architecture/L1/L1-mod-02/04-contracts-and-runtime.md`
- `architecture/L1/L1-mod-02/05-local-decisions.md`
- `architecture/L1/L1-mod-02/child-handoff.md`

未读取 `parent_prd`：父包已提供足够追踪，且当前 PRD 的三个需求均能追溯到父层。

### 实际输出

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

共 7 个文件，无 `parent-change-request.md`。

### 验证检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 父包识别与 SI-CORE 唯一匹配 | 通过 | 父 manifest、decomposition、handoff 三处一致 |
| REQ-DD001/002/004 需求分配完整 | 通过 | 01 需求分配表、02 child registry |
| 每个 child_id 有责任、排除、状态/边界、依赖和追踪 | 通过 | 02 decomposition |
| 父契约字段/owner/consumer/version/失败/幂等语义不变 | 通过 | 04 inherited contract inventory + operation_contract_registry |
| 成功、失败/恢复、生命周期运行流覆盖 | 通过 | 04 RF-SIC-01/02/03 |
| 父/兄弟状态所有权未转移 | 通过 | 03 ownership confirmation |
| 未新增公共运行时边界、平台、数据库、消息总线或部署单元 | 通过 | 02 boundary confirmation、05 prohibited decisions |
| stable ID 排序与交接锚点完整 | 通过 | manifest、02、03、04、05、handoff registries |

## 8. Human commands

- `[APPROVE]`：批准本 L2 包后，选择一个 `SI-CORE-*` 进入下一层。
- `[REVISE phase-N]`：按阶段修订本包。
- `[EXPLAIN LCD-SIC-00X]`：查看某个局部决策的替代方案和后果。
- `[NEXT SI-CORE-AGG]`、`[NEXT SI-CORE-INTEGRITY]` 或 `[NEXT SI-CORE-TX]`：仅在 Human Gate 批准后启动下一层。
