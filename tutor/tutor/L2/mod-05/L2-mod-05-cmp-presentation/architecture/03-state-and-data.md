# 03 State and Data — L2 / CMP-PRESENTATION

## 1. 状态所有权清单（按稳定 state_id 排序）

| state_id | state | owner child_id | readers | writers | lifecycle | consistency boundary | retention/privacy | parent trace |
|---|---|---|---|---|---|---|---|---|
| ST-IDEMPOTENCY-PRESENTATION | 父 CT-009 幂等键（教师 + 规范化小组集合 + 时间窗 → presentation_id/最新快照） | CMP-PRES-SNAPSHOT-STORE | CMP-PRES-SNAPSHOT-STORE；经 CT-009 返回教师端 | CMP-PRES-SNAPSHOT-STORE | active → superseded/expired；随快照生命周期管理 | 与对应 PresentationView 写入同一父本地事务 | 不含材料文件本体；仅保留生成关联数据，沿父数据库加密/备份约束 | L1 ST-IDEMPOTENCY-PRESENTATION；CT-009 idempotency |
| ST-PRESENTATION-VIEW | PresentationView 快照：生成参数、GroupSection[]、项目结果引用、ProcessSummary、评分、批注、missing_marks、生成时间 | CMP-PRES-SNAPSHOT-STORE | CMP-PRES-SNAPSHOT-STORE；CMP-PRES-OUTPUT-ADAPTER；教师端仅经 CT-009 | CMP-PRES-SNAPSHOT-STORE | snapshot_created → superseded → purged | 快照模型与幂等记录在同一父本地事务中；生成后不实时更新 | 含学生作业/评分内容；随所属删除批次擦除；不得因读模型重放复活 | L1 ST-PRESENTATION-VIEW；PresentationView；F4-1；CT-009；LCD-005 |
| ST-PRES-GENERATION-CONTEXT | 一次生成请求的已授权上下文、规范化 group_ids、读模型版本和资格结果 | CMP-PRES-GENERATION-COORDINATOR | 当前生成调用链 | CMP-PRES-GENERATION-COORDINATOR | request_started → completed/rejected/failed；请求结束释放 | 单次请求内存/调用边界，不跨请求持久化 | 不落库；日志只保留 KD-003 允许的最小关联信息 | CT-009；M05-FLOW-004 |
| ST-PRES-MISSING-MARKS | 每个 GroupSection 的缺失标记值对象与可观察说明 | CMP-PRES-MISSING-MARKS | CMP-PRES-BLOCK-ASSEMBLER；PresentationView 写入前的 coordinator | CMP-PRES-MISSING-MARKS | evaluated → attached/discarded；随请求结束释放，附着后的值进入快照 | 同一生成请求内只读传递；不成为独立外部状态 | 不增加源数据；只复制父读模型缺失字段，遵循父隐私策略 | REQ-DD002；D-AC-REQ-010-01；CT-009 `missing_marks` |
| ST-PRES-RESPONSE | 父 CT-009 的 `presentation_id + blocks[]` 响应 DTO | CMP-PRES-OUTPUT-ADAPTER | CMP-PRES-GENERATION-COORDINATOR、CMP-TEACHER-UI（经父 API） | CMP-PRES-OUTPUT-ADAPTER | assembled → returned/discarded | 单次调用边界；不独立持久化 | 不缓存学生内容；响应遵循父 API 访问控制与传输保护 | CT-009 produced_fields |

父层与兄弟状态所有权没有转移：MOD-02 仍拥有 Submission/MaterialFile，MOD-04 仍拥有评估产出，`ST-READ-MODEL` 仍由 `CMP-READMODEL-PROJECTOR` 唯一写入；本包只持有展示快照中的引用/复制值。

## 2. 存储意图

- `ST-PRESENTATION-VIEW` 与 `ST-IDEMPOTENCY-PRESENTATION` 继续存于父 DU-2 共享关系型数据库；不选择具体数据库产品。
- 快照写入、幂等键登记和 supersede 关联必须保持父本地事务语义；不要引入缓存、搜索引擎、独立消息总线或新的存储。
- 快照只保留 `material_refs`/结果引用与展示所需复制值，不保存材料文件本体；字段级加密、备份和删除范围遵循 KD-003、父 03 和 LCD-005。
- `ST-PRES-GENERATION-CONTEXT`、`ST-PRES-MISSING-MARKS`、`ST-PRES-RESPONSE` 是请求内派生状态，不得被误当成公共持久化所有权。

## 3. 关键数据流

### 3.1 生成写入流

`CMP-ACCESS-GATE → CMP-PRES-GENERATION-COORDINATOR → M05-IC-02 → CMP-PRES-MISSING-MARKS → CMP-PRES-BLOCK-ASSEMBLER → CMP-PRES-SNAPSHOT-STORE → CMP-PRES-OUTPUT-ADAPTER → CT-009 response`

- M05-IC-02 返回课程/小组/提交视图、材料引用、状态、评分、批注和缺失输入。
- 资格失败（任一所选小组无可用提交）在快照写入前终止，返回父错误码 `NO_AVAILABLE_SUBMISSION`。
- 资格通过时生成 `GroupSection[]`，在 ST-PRESENTATION-VIEW 与 ST-IDEMPOTENCY-PRESENTATION 同事务写入，再生成 CT-009 响应。

### 3.2 再生成读取流

相同父幂等键先由 `CMP-PRES-SNAPSHOT-STORE` 查询最新快照；若存在且仍可用，返回其最新 blocks；若需要重新生成，则重新读取 M05-IC-02、建立新快照并将旧快照标记 superseded。外部仍只返回 CT-009 定义的 `presentation_id + blocks[]`。

### 3.3 删除/重放流

父 CT-012 的 MOD-05 自消费仍由 `CMP-READMODEL-PROJECTOR` 处理；投影器通过本层 `PRES-IC-05` 传递已清除的 `submission_ids`/`batch_id`，`CMP-PRES-SNAPSHOT-STORE` 对相关 PresentationView 做内容擦除并幂等记录。重放时只允许恢复未被完成删除批次覆盖的内容，不能复活已擦除快照。

## 4. 不变量、一致性、幂等与并发

1. 任一选定小组无可用提交 → 整体拒绝；不得写部分快照。
2. 缺失材料/缺失项必须在对应 GroupSection 的 missing_marks 中可见；不可通过过滤缺失组来制造成功视图。
3. `PresentationView` 是一次性快照；快照内容不会随 `ST-READ-MODEL` 实时变化，重新生成才获取新内容。
4. 同一生成键的重复请求返回同一幂等语义下的最新快照，不产生不可见重复副作用；幂等记录与快照写入同事务。
5. `presentation_id` 与 `blocks[]` 必须来自同一次快照装配，不能跨版本混拼。
6. CT-009 读模型短暂落后时，不以缺字段响应降级；由父 M05-IC-02 的最终一致和调用重试策略处理，并保留缺失事实。
7. 删除擦除按 `batch_id + submission_id` 幂等；审计记录与 MOD-02 材料清除仍由父/兄弟所有者负责。

## 5. 所有权再确认

本包未将 PresentationView 之外的任何父或兄弟状态纳入本层；没有把 `ST-READ-MODEL`、Submission、AssessmentResult、Course 或 DeletionBatch 变成本层所有。所有新增状态仅是当前生成调用内的派生状态，或是父允许的本地 PresentationView 生命周期细化。
