# 03 State and Data — MOD-02 submission-intake 状态与数据

> 本文件是 C2（局部聚合/状态 → 状态所有者与局部一致性边界）的产物。父层（L0）数据所有权不变：Submission 聚合（含材料文件）仍归 MOD-02；本文件只划分 **MOD-02 内部** 的读写分工。状态按稳定 ID 排序。

## 状态所有权注册表

| state_id | 状态 | owner child_id | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-01 | Submission（提交记录、状态机、材料清单、完整性报告、缺失项标记、失败原因；`submission_uuid` 唯一） | SI-CORE | SI-API（CT-002/应答）、SI-RELAY（事件载荷/回写目标）、SI-PURGE（清除定位） | 仅 SI-CORE（经 IC-SI-04 命令端口） | 创建（received/rejected/upload_failed）→ processing → scored/scoring_failed（终态）→ deleted（清除执行）；终态不可逆 | 单库本地事务：状态迁移 + 材料清单 + 完整性报告 + Outbox 记录同事务提交 | 保留至课程结束后 1 年（到期计算在 MOD-05）；含姓名/小组（个人信息），数据库备份加密（KD-003）；清除执行后记录本体移除 | 父包 03 Submission 所有权行；INV-1~INV-5 |
| ST-02 | UploadSession（上传会话、分片清单、断点续传进度、receiving/interrupted_retryable/merged/pending_verification/failed_terminal 状态、失败原因、重试截止时间） | SI-XFER | SI-API（会话恢复/进度）、SI-VERIFY（待校验协调） | 仅 SI-XFER（经 IC-SI-01） | receiving → interrupted_retryable → receiving → merged → pending_verification → completed（提交成立）/ failed_terminal（不可恢复或重试窗口耗尽）；failed_terminal 才触发 upload_failed | 会话内单写者（按 `session_id` 串行化）；与 ST-01 无分布式事务——先会话 merged，后创建 Submission；`submission_uuid` 保证恢复幂等 | 暂存材料随会话清理；会话记录为短生命周期运行数据（TTL 为 implementation_detail），不含评分数据 | CT-001 分片协议；KD-005 断点续传；AC-REQ-003-01 exceptions |
| ST-03 | MaterialFile（材料文件，磁盘加密）与 CourseQuotaUsage（课程配额用量） | SI-STORE | SI-XFER（写入/合并）、SI-CORE（元数据/配额查询）、SI-PURGE（删除）、MOD-04（跨模块只读引用材料内容，KD-002 共享设施） | 仅 SI-STORE（经 IC-SI-02） | 暂存区 → 正式区（提交成立）→ 删除（清除执行/暂存清理）；删除后 `material_ref` 失效 | 文件写入与元数据登记原子化（先写文件后登记，失败回滚文件）；配额计数与写入同检查点 | 磁盘存储加密（KD-003）；500MB 单次上限 / 200GB 每课程配额（KD-004）；材料含个人信息与第三方代码 | 父包 03「材料文件」；KD-003/KD-004；CT-010 dependencies（MOD-04 只读来源） |
| ST-04 | OutboxRecord（待投递事件记录：CT-004/CT-006/CT-014 载荷、投递状态、重试计数、下次重试时间、消费者确认状态） | SI-RELAY | SI-RELAY 投递器 | SI-CORE/SI-PURGE（事务内写入，经 IC-SI-05）、SI-RELAY（投递确认标记） | pending → delivering → retry_wait → delivering → confirmed；CT-004 只有收到“评分任务已持久化”确认才进入 confirmed | 与产生它的业务数据同一本地事务（KD-002：不丢事件）；确认后推进对应业务状态的命令必须幂等 | 载荷含学生姓名/小组（随父契约 schema）；确认记录可归档，失败记录保留至重试闭环 | KD-002；CT-004/CT-006/CT-014 |
| ST-05 | InboundEventDedup（入站事件消费去重记录：CT-005 按 `submission_id`+终态、CT-012 按 `batch_id`+载荷哈希；含解析/处理状态） | SI-RELAY | SI-RELAY 消费端 | SI-RELAY | received → processing → applied；重复事件 → duplicate_ignored；schema 无效 → quarantined；可重试业务失败 → retry_wait | 去重检查与业务处理（状态回写/清除触发）同一事务；quarantined 不阻塞后续合法事件 | 仅含业务键、事件摘要和错误原因；按对应业务生命周期保留，隔离记录需可告警和人工重放 | CT-005/CT-012 幂等语义 |
| ST-06 | AuthTokenGrant（令牌签发审计：签发时间、邀请码、姓名、小组、有效期） | SI-API | SI-API（认证校验、访问审计） | SI-API | 签发 → 过期失效；验证无状态（签名令牌），审计记录长期保留至清除执行 | 签发记录追加式写入，无并发冲突 | 含姓名/小组；支撑 KD-005「访问审计」；随课程数据保留期清除 | KD-005；04 通用约定（auth-token 端点） |
| ST-07 | PurgeExecution（清除执行记录：`batch_id`、逐 `submission_id` 结果、失败原因、执行时间） | SI-PURGE | SI-PURGE（重跑定位）、SI-RELAY（CT-014 载荷组装） | SI-PURGE | 批次执行创建 → 部分失败保留 → 重跑更新 → 全部成功后归档 | 逐项清除为独立小事务（单项失败不阻塞其他项）；批次结果汇总后一次性写 Outbox | 仅为执行日志；删除审计记录归 MOD-05，本模块不复制 | CT-012/CT-014；DF-3 步骤 4–5；AC-NFR-004-01 |

## 机器可读状态迁移

```yaml
state_machine:
  submission:
    owner: SI-CORE
    transitions:
      - {from: "∅", to: received, trigger: ConfirmReceived, precondition: "CT-003 verified=true 且材料已转正式区", effects: [write_material_entries, write_integrity_report, enqueue_CT-004, enqueue_CT-006]}
      - {from: "∅", to: rejected, trigger: MarkRejected, precondition: "CT-003 verified=false", effects: [write_failure_reason, cleanup_staged_materials]}
      - {from: "∅", to: upload_failed, trigger: MarkUploadFailed, precondition: "UploadSession=failed_terminal", effects: [write_failure_reason, enqueue_CT-006]}
      - {from: received, to: processing, trigger: AdvanceToProcessing, precondition: "CT-004 consumer_ack=task_persisted", effects: [write_processing_at]}
      - {from: processing, to: scored, trigger: ApplyScoringOutcome, precondition: "CT-005 outcome=scored", effects: [write_scoring_terminal]}
      - {from: processing, to: scoring_failed, trigger: ApplyScoringOutcome, precondition: "CT-005 outcome=scoring_failed", effects: [write_failure_reason, write_scoring_terminal]}
      - {from: "[received, processing, scored, scoring_failed, rejected, upload_failed]", to: deleted, trigger: PurgeSubmission, precondition: "该 submission_id 的清除项成功", effects: [remove_submission_record]}
  upload_session:
    owner: SI-XFER
    transitions:
      - {from: receiving, to: interrupted_retryable, trigger: UploadInterrupted, precondition: "网络/客户端中断且仍在重试窗口", effects: [persist_progress, set_retry_deadline]}
      - {from: interrupted_retryable, to: receiving, trigger: ResumeUpload, precondition: "同 submission_uuid 且幂等校验通过", effects: [deduplicate_chunks, update_progress]}
      - {from: interrupted_retryable, to: failed_terminal, trigger: RetryWindowExpired, precondition: "超过 retry_deadline 或不可恢复错误", effects: [call_MarkUploadFailed]}
      - {from: merged, to: pending_verification, trigger: RosterUnavailable, precondition: "CT-003 暂不可用", effects: [retain_materials, schedule_retry]}
  outbox:
    owner: SI-RELAY
    transitions:
      - {from: pending, to: delivering, trigger: DeliveryAttempt}
      - {from: delivering, to: retry_wait, trigger: DeliveryFailed, effects: [increment_attempt_count, schedule_backoff]}
      - {from: delivering, to: confirmed, trigger: ConsumerAck, precondition: "CT-004=task_persisted；其他事件=payload_accepted"}
  inbound_event:
    owner: SI-RELAY
    transitions:
      - {from: received, to: processing, trigger: ConsumeInbound}
      - {from: processing, to: applied, trigger: BusinessApplySucceeded}
      - {from: processing, to: retry_wait, trigger: RetryableApplyFailed}
      - {from: received, to: quarantined, trigger: SchemaInvalid, effects: [alert, do_not_block_queue]}
```

## 存储意图（受父技术决策约束）

| 状态 | 存储形态 | 约束来源 |
|---|---|---|
| ST-01、ST-02、ST-04、ST-05、ST-06、ST-07 | 单一关系型数据库表（产品选型 defer_to_detail_design，仅要求事务 + 备份） | KD-002、父包 03 存储形态 |
| ST-03 材料文件 | 服务器本地磁盘（存储加密），DU-2/DU-3 共享设施 | KD-002、KD-003、父包 03/06 |

本层不引入新的数据库、缓存、搜索引擎、消息中间件或对象存储（遵守父包 05「不采用方案」）。

## 重要数据流

### 写入流

1. **接收写入（成功路径）**：SI-API 编排 SI-XFER 分片 → SI-STORE 暂存写入（流式计数 500MB）→ 合并后转正式区并登记元数据 → SI-API 调用 SI-VERIFY 经 CT-003 校验通过 → SI-CORE 单事务写入 Submission(received) + MaterialEntry 清单 + IntegrityReport + OutboxRecord（CT-004、CT-006）。
2. **拒绝/失败写入**：校验拒绝 → SI-CORE 写入 Submission(rejected + reason)；上传中断先进入 SI-XFER.interrupted_retryable，重试窗口耗尽后进入 failed_terminal，再由 SI-CORE 写入 Submission(upload_failed + reason) + OutboxRecord（CT-006，LCD-002）。
3. **回写写入**：CT-005 入站 → SI-RELAY 去重（ST-05）→ SI-CORE `ApplyScoringOutcome`（processing→终态，幂等）。
4. **清除写入**：CT-012 入站 → SI-PURGE 逐项执行（SI-STORE 删文件 → SI-CORE 记录 →deleted）→ ST-07 记录 → OutboxRecord（CT-014）。

### 读取流

- CT-002 状态查询：SI-API → SI-CORE 只读查询（按 `submission_uuid`）。
- 完整性报告生成：SI-CORE 读取 SI-STORE 材料元数据（类别/大小），与声明类别清单比对（INV-5，无内容解析）。
- 配额校验：SI-XFER/SI-CORE 查询 SI-STORE 的 CourseQuotaUsage。

### 派生与外部化

- 跨模块派生：CT-004（材料清单 + 缺失项 → MOD-04 评分输入）、CT-006（状态 + 缺失项 → MOD-05 教师读模型）、CT-014（清除结果 → MOD-05 批次状态）。
- MOD-04 经共享磁盘只读引用材料内容（CT-010 dependencies 的材料来源）；本模块不提供新的跨模块文件 API。
- 保留到期计算、`course_end_at` 引用均在 MOD-05/MOD-03，本模块不接收也不需要（父包 02/03 保留期规则）。

## 不变量、一致性、幂等与并发规则

- **一致性**：跨子节点无分布式事务。接收路径以「先 ST-02 merged、后 ST-01 创建」的编排顺序保证（LCD-001）；ST-01 与其 Outbox 记录严格同事务（KD-002）。跨模块一律最终一致（父包 03 跨边界策略）。
- **幂等**：CT-001 以 `submission_uuid` 唯一约束去重（重复请求返回首次结果，含分片会话续传）；分片按序号去重；CT-005 按 `submission_id`+终态去重（重复事件不改终态）；CT-012 重复消费对已删记录为空操作（天然幂等，允许同批次重跑）；CT-002 只读天然幂等。
- **并发**：30 并发提交（NFR-002）下，每个提交独立 `submission_id` 与状态（AC-REQ-007-01 boundaries）；`submission_uuid` 唯一约束防重复建单；会话按 `session_id` 串行化写入；配额计数采用「预检 + 终检」并在写入检查点串行更新，防止并发超限。
- **清除安全**：审计记录（MOD-05）不在清除范围；SI-PURGE 单项失败不影响其他项；失败项保留于 ST-07 供原批次重跑，重跑结果再次经 CT-014 回传（CT-014 错误语义）。

## 父/兄弟所有权未转移确认

- Submission 聚合（含材料文件）所有权仍为 MOD-02；本文件仅将内部读/写分工到 SI-* 子节点，未向任何兄弟模块转移所有权。
- Course/名单（MOD-03）、AssessmentResult（MOD-04）、ReviewRecord/PresentationView/DeletionBatch/教师读模型（MOD-05）所有权不变；本模块不持有其任何数据的写副本（ST-05 仅为消费幂等的业务键记录，ST-07 仅为执行日志）。
- 未新增跨边界强一致要求；未引入分布式事务。
