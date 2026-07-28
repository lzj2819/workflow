# Leaf Gate Override ? SI-XFER

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — SI-XFER upload-transfer L2 架构包交接

## 当前节点身份与父层绑定

- `target_node_id`：`SI-XFER`，L2，父节点为 L1 `MOD-02` 内的 `upload-transfer`。
- 职责：上传会话、分片接收、断点续传、顺序/幂等校验、500MB/白名单约束、合并最终化。
- 排除项：不拥有 Submission、MaterialFile/CourseQuotaUsage、名单校验、HTTP/API 编排、Outbox、外部事件、部署单元。
- 父包：`architecture/L1/L1-mod-02`；匹配证据为 `child-handoff.md` 中 SI-XFER 唯一行，并由 manifest children、ST-02 owner、IC-SI-01 owner 交叉确认。
- 边界指纹：见 `architecture-manifest.yaml`，包含父 manifest、handoff、状态、契约和当前 PRD SHA-256。

## 下一层 target_node_id 清单

| child_id | 名称 | 一句话职责 | 建议细化焦点 | 所需祖先上下文 |
|---|---|---|---|---|
| XFER-CHUNK | chunk-receiver | 分片接收、流式限制校验、顺序和摘要幂等、暂存写入 | 分片元数据模型、I/O 失败恢复、类型检测和 seq 冲突处理 | 本包 ST-XFER-02、IC-XFER-02、父 KD-004/005、IC-SI-02 |
| XFER-FINALIZE | transfer-finalizer | 分片完整性检查、合并/正式化和 material_refs 结果 | promote 幂等、崩溃恢复、最终化检查点和缺失类别投影 | 本包 ST-XFER-03、IC-XFER-03/04、父 IC-SI-02 |
| XFER-SESSION | upload-session | 会话建立/恢复/中止、单写者状态迁移和进度查询 | session 锁/版本、状态投影、TTL 接入、失败终止回调 | 本包 ST-XFER-01、IC-XFER-01、父 ST-02、LCD-001/006 |

## 继承契约与内部契约

继承且语义不变：`IC-SI-01`、`IC-SI-02`、`CT-001`。本包新增的内部契约均限定在 SI-XFER：

| contract_id | owner → consumer | 用途 |
|---|---|---|
| IC-XFER-01 | XFER-SESSION → SI-API | 会话建档、查询、恢复和中止 |
| IC-XFER-02 | XFER-CHUNK → XFER-SESSION | 分片接受结果和会话进度更新 |
| IC-XFER-03 | XFER-FINALIZE → XFER-CHUNK | 读取有序分片清单和完整性结果 |
| IC-XFER-04 | XFER-FINALIZE → XFER-SESSION | 最终化成功/失败/恢复结果 |
| IC-XFER-05 | SI-XFER 子节点 → observation sink | 非阻塞上传观测 |

## 状态所有权清单

| state_id | 状态 | owner |
|---|---|---|
| ST-XFER-01 | UploadSession 与会话生命周期/进度 | XFER-SESSION |
| ST-XFER-02 | ChunkReceipt 与分片接收元数据 | XFER-CHUNK |
| ST-XFER-03 | FinalizeAttempt 与最终化检查点 | XFER-FINALIZE |
| ST-XFER-04 | TransferObservation 与上传过程指标摘要 | XFER-SESSION（采集协调） |

父层状态 `ST-02` 仍由 SI-XFER 统一拥有；本表只是其内部拆分。`ST-03 MaterialFile/CourseQuotaUsage` 仍由 SI-STORE 拥有。

## 决策、风险和未解决项

- 继承不重开：KD-002、KD-003、KD-004、KD-005、LCD-001、LCD-005、LCD-006、LCD-007。
- 本层已决定：L2D-001（会话级单写者/版本保护）、L2D-002（严格 next_seq + 相同摘要幂等）、L2D-003（最终化持久化检查点）、L2D-004（非阻塞最小化观测）。
- 委托下一层：L2D-005，SI-STORE 决定目录布局、文件命名和加密参数。
- 实现细节：L2D-006 会话 TTL/归档/扫描参数；L2D-007 分片大小、缓冲区和具体摘要库。
- 风险：父 L1 manifest 仍要求 strict audit 复验；这不阻塞本包的局部结构交接，但 Human Gate 需要同时关注父包审计状态。
- 未发现 `return_to_parent` 项；没有公共契约、状态所有权、依赖方向、技术或部署边界变更请求。

## 推荐下一步

1. Human Gate 重点评审 L2D-001/002/003、严格 next_seq 语义，以及 ST-XFER-01/02/03 与父 ST-02 的映射。
2. 批准后优先细化 `[NEXT XFER-CHUNK]`，因为其分片写入和幂等是会话/最终化的基础；随后细化 `[NEXT XFER-FINALIZE]` 与 `[NEXT XFER-SESSION]`。
3. 下一层必须继续携带直接父包、本包和 L1 `architecture/L1/L1-mod-02` 的边界上下文，不得把 SI-STORE 设计成当前节点内部。

## 追踪豁免与实际输入/输出

- 三个直接 child_id 均具有当前 PRD REQ-DD001/REQ-DD002 或父层 REQ-D001/REQ-D002、IC-SI-01/02、ST-02、KD-004/005 的追踪；无追踪豁免节点。
- 实际输入：`prd/L2-PRD/mod-02/L2-mod-02-si-xfer/prd.md`、`architecture/L1/L1-mod-02/architecture-manifest.yaml`、`child-handoff.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`；未读取 parent_prd。
- 实际输出：本目录七个架构文件；无 `parent-change-request.md`，无代码、测试、部署清单。

## 验证检查及结果

| 检查 | 结果 |
|---|---|
| 四项必需输入解析、输出目录为空且 new 模式无覆盖 | 通过 |
| 父包识别与 SI-XFER 唯一匹配 | 通过 |
| 当前 PRD REQ-DD001/REQ-DD002 到父层 REQ-D001/REQ-D002 的追踪 | 通过 |
| 每个 child_id 含职责、排除项、状态、依赖、存在理由和追踪 | 通过 |
| 状态、契约、决策按稳定 ID 排序 | 通过 |
| 父契约、兄弟所有权、部署和技术边界未改变 | 通过 |
| 七个文件存在、manifest 输出清单与实际文件一致、关键引用可解析 | 通过（交付前结构/追踪/边界检查） |

未完成项：L1 父包的 strict audit 仍需在其工作区重新执行；本 L2 包不将其标记为已通过。当前 L2 包本身无阻塞项，状态为 `ready_for_human_gate`。
