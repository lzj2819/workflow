# 03 State and Data — SI-CORE submission-core L2

> 本文件执行 C2（父状态 → L2 状态语义与一致性边界）。父层 `ST-01` 的业务所有权仍归 SI-CORE；本层只进一步区分语义 owner 与物理事务写入者，不转移父层或兄弟所有权。

## 1. 状态所有权注册表（按稳定 ID 排序）

| state_id | 状态 | owner child_id | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| SIC-ST-01 | SubmissionIdentityAndLifecycle：身份关联、`submission_id/uuid`、状态、失败原因、接收时间、生命周期时间戳 | SI-CORE-AGG | SI-CORE-TX、SI-API（CT-002）、SI-RELAY、SI-PURGE | SI-CORE-TX 通过 SI-CORE-AGG 聚合端口；语义写 owner 仍为 AGG | `∅→received/rejected/upload_failed→processing→scored/scoring_failed→deleted`；终态不可逆 | 与 SIC-ST-02/03、父 ST-04 Outbox 写入组成同一本地事务 | 课程结束后 1 年；姓名/小组为个人信息；备份加密 KD-003；删除后记录本体移除 | ST-01；INV-1/2；父 03 state-and-data |
| SIC-ST-02 | MaterialManifest：`material_ref`、category、size、declared、expected category snapshot | SI-CORE-INTEGRITY | SI-CORE-AGG、SI-CORE-TX、SI-API、SI-RELAY（事件载荷）、SI-PURGE（定位） | SI-CORE-TX 通过完整性端口；文件本体只由 SI-STORE 写入 | 合并后的正式材料元数据进入提交；提交删除时引用失效 | 清单与 Submission 状态在 ConfirmReceived/MarkUploadFailed 事务中一致；不包含文件内容 | 随 ST-01 保留；不得复制材料内容或名单数据 | ST-01 的材料清单；INV-4/5；REQ-DD001/002 |
| SIC-ST-03 | IntegrityReport：expected/received/missing categories、生成时间、报告版本 | SI-CORE-INTEGRITY | SI-CORE-AGG、SI-API、SI-RELAY（CT-004/006 payload） | SI-CORE-TX 通过完整性端口 | ConfirmReceived/MarkUploadFailed 时生成或更新；随后只读，随提交删除 | 必须与清单和状态同事务提交；缺失项不触发拒绝 | 随提交保留；不含材料内容分析结果 | ST-01；INV-3/5；REQ-DD004 |
| SIC-ST-04 | TransitionResult：一次命令的迁移结果、幂等命中/拒绝原因（短生命周期返回值，不是新持久化状态） | SI-CORE-AGG | SI-CORE-TX、SI-API | SI-CORE-AGG 在命令返回时生成 | 随单次命令创建，返回后释放；不得作为父状态机新状态 | 与当前聚合版本/预期状态检查绑定 | 不持久化个人信息副本；日志按 KD-003/父监控约束 | IC-SI-04；INV-2/6 |

### 1.1 机器可解析状态迁移注册表

下面的注册表是验证器和后续实现的权威状态映射。`semantic_owner` 负责业务状态语义，`transaction_coordinator` 只负责本地事务组合和物理提交；不能把 SI-CORE-TX 误识别为状态 owner。

```yaml
state_transition_registry:
  state_entity: SIC-ST-01
  semantic_owner: SI-CORE-AGG
  transaction_coordinator: SI-CORE-TX
  transitions:
    - transition_id: SIC-TR-001
      command: ConfirmReceived
      from: ["∅"]
      to: received
      trigger: IC-SIC-04.ConfirmReceived
      preconditions: ["verification=verified", "material_refs_are_registered"]
      success_effects: [write_submission, write_material_manifest, write_integrity_report, enqueue_CT-004, enqueue_CT-006]
      failure_effects: [rollback_transaction, return_ILLEGAL_TRANSITION_or_METADATA_ERROR]
      observable_fields: [submission_id, status, received_at, missing_items, transition_result]
    - transition_id: SIC-TR-002
      command: MarkRejected
      from: ["∅"]
      to: rejected
      trigger: IC-SIC-04.MarkRejected
      preconditions: ["verification=not_verified"]
      success_effects: [write_failure_reason, cleanup_staged_materials]
      failure_effects: [rollback_transaction, return_ILLEGAL_TRANSITION]
      observable_fields: [status, failure_reason, transition_result]
    - transition_id: SIC-TR-003
      command: MarkUploadFailed
      from: ["∅"]
      to: upload_failed
      trigger: IC-SIC-04.MarkUploadFailed
      preconditions: ["upload_session_state=failed_terminal", "retry_window_exhausted"]
      success_effects: [write_failure_reason, write_integrity_report, enqueue_CT-006]
      failure_effects: [rollback_transaction, retain_upload_session_for_retry]
      observable_fields: [status, failure_reason, transition_result]
    - transition_id: SIC-TR-004
      command: AdvanceToProcessing
      from: [received]
      to: processing
      trigger: CT-004.consumer_ack
      preconditions: ["consumer_ack=task_persisted", "expected_state=received"]
      success_effects: [write_processing_at]
      failure_effects: [return_ILLEGAL_TRANSITION, retry_idempotently]
      observable_fields: [status, processing_at, transition_result]
    - transition_id: SIC-TR-005
      command: ApplyScoringOutcome
      from: [processing]
      to: [scored, scoring_failed]
      trigger: CT-005
      preconditions: ["expected_state=processing", "outcome in scored|scoring_failed"]
      success_effects: [write_scoring_terminal_or_failure_reason]
      failure_effects: [return_ILLEGAL_TRANSITION, ignore_duplicate_terminal_outcome]
      observable_fields: [status, failure_reason, transition_result]
    - transition_id: SIC-TR-006
      command: PurgeSubmission
      from: [received, processing, scored, scoring_failed, rejected, upload_failed]
      to: deleted
      trigger: CT-012
      preconditions: ["purge_item_succeeded"]
      success_effects: [remove_submission_record]
      failure_effects: [retain_failed_purge_item, return_item_failure]
      observable_fields: [submission_id, status, transition_result]
```

### 所有权确认

- `ST-01` 仍由 SI-CORE 拥有；`SIC-ST-01~03` 是本层语义拆分，不是新的跨模块数据所有权。
- `ST-03 MaterialFile/CourseQuotaUsage` 仍由 SI-STORE 拥有；本层只保存引用和元数据。
- `ST-04 OutboxRecord`、`ST-05 InboundEventDedup`、`ST-07 PurgeExecution` 仍分别由 SI-RELAY/SI-PURGE 拥有。
- 本层没有把状态副本转给 SI-API、SI-RELAY 或任何兄弟模块；CT-006/CT-004 payload 是父契约投递数据，不是新的本地 owner。

## 2. 存储意图（受父层约束）

1. 结构化 Submission、材料清单和完整性报告继续使用父层已确定的单一关系型数据库边界；数据库产品选型仍是父包 `defer_to_detail_design`，本层不指定产品。
2. 材料文件、暂存区、正式区和配额计数继续经 SI-STORE 的 IC-SI-02 端口访问；本层不新增文件接口、对象存储或缓存。
3. 事务边界由 `SI-CORE-TX` 组合 `SIC-ST-01~03` 和父 `ST-04` 的 Outbox 写入；不使用分布式事务、事件溯源或新的消息中间件。
4. 备份、加密、个人信息处理和删除语义继承 KD-003、父 retention 规则与 MOD-05 审计边界。

## 3. 关键数据流

| 流程 | 读/写顺序 | 一致性与失败处理 |
|---|---|---|
| 成功接收 | SI-API → SI-CORE-TX → SI-CORE-INTEGRITY 读取 SI-STORE 元数据 → SI-CORE-AGG `ConfirmReceived` → 同事务写 SIC-ST-01/02/03 + ST-04 | 任一校验/持久化失败则整笔事务回滚；不得产生部分 Submission 或孤立 Outbox |
| 校验拒绝 | SI-API 传入 SI-VERIFY 结论 → SI-CORE-TX → SI-CORE-AGG `MarkRejected` → 写失败原因；暂存材料清理由父层其他节点处理 | `rejected` 终态；不写 CT-004/CT-006；不把 `ROSTER_UNAVAILABLE` 当作 rejected |
| 上传终态失败 | SI-XFER/SI-API → `MarkUploadFailed` → SI-CORE-INTEGRITY 生成已知清单/缺失报告 → 同事务写 `upload_failed` + CT-006 Outbox | 与 LCD-002 一致；重试窗口未耗尽时不创建此终态 |
| 评分回写 | SI-RELAY 去重后 → SI-CORE-TX → SI-CORE-AGG `ApplyScoringOutcome` | 仅 `processing` 可转终态；重复终态回写为空操作；评分原始内容不落地 |
| 清除回写 | SI-PURGE → SI-CORE-TX → SI-CORE-AGG `PurgeSubmission` | 已删除为空操作；材料删除由 SI-STORE/SI-PURGE 负责；不写 CT-014 |

## 4. 不变量、一致性、幂等与并发

- **并发写**：同一 `submission_uuid` 的创建/确认按唯一键和聚合版本/行锁语义串行化；不同提交可并行，不能共享聚合锁。
- **状态守卫**：命令必须携带 `expected_state`（如适用），由 SI-CORE-AGG 在提交前校验；非法迁移返回 `ILLEGAL_TRANSITION`，不写副作用。
- **报告一致性**：报告只基于声明类别与材料元数据；空目录生成 `missing_items[]`，不得把缺失转换为拒绝。
- **Outbox 原子性**：CT-004/CT-006 的 Outbox 记录必须和业务状态同事务提交；投递失败不回滚已提交 Submission，而由 SI-RELAY 按 KD-002 重试。
- **回写幂等**：`submission_id+outcome`、`submission_uuid`、已删除记录均幂等；幂等命中返回已有结果，不重复发布新语义事件。
- **读一致性**：CT-002 查询读取已提交的 SIC-ST-01~03；查询没有写副作用，也不读取未提交暂存会话。

## 5. C2 结论

本层只细化 SI-CORE 内部的一致性边界：聚合语义由 SI-CORE-AGG 拥有、清单/报告语义由 SI-CORE-INTEGRITY 拥有、物理提交由 SI-CORE-TX 协调。父层和兄弟模块的状态、数据、存储设施和审计所有权均未重新分配。
