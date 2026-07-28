# 03 State and Data — CMP-DIALOGUE-COLLECTOR（L2）

## 1. 状态所有权注册表（按稳定 ID 排序）

| 状态 ID | 状态 | Owner child_id | 读方 | 写方 | 生命周期 | 一致性边界 | 保留/隐私约束 | 父层追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-DLG-01 | `DialogueCaptureSession`：submission_uuid、task_created_at、phase、source_observation、failure_reason | CMP-DLG-CAPTURE-COORDINATOR | Coordinator、PENDING-QUEUE（通过返回结果） | 仅 Coordinator | 任务采集期间；成功后可压缩为 artifact provenance，终态后清理 | 同一 submission_uuid 至多一个 active session；phase 与返回事件原子一致 | 只在学生本机保存必要诊断；不得记录宿主秘密或完整内容副本 | L1 ST-02；IC-M01-03；LCD-002 |
| ST-DLG-02 | `DialogueArtifact`：manifest、ordered entries、category=dialogue、capture anchor、checksum、byte size、source provenance | CMP-DLG-ARTIFACT-STORE | Coordinator、PENDING-QUEUE、UPLOAD-CLIENT（经 BundleRef） | 仅 Artifact Store | 任务创建后生成一次；received/rejected 后由队列触发清理；failed 时保留以便同 UUID 恢复 | 不可变；同一 submission_uuid 至多一个有效 artifact；读取必须返回完整 manifest | 仅本机暂存；含个人信息/第三方代码内容；HTTPS 外发由父层 UPLOAD-CLIENT 执行；终态清理 | L1 ST-02；REQ-D003；CT-001 dialogue material slice |

无持久状态的子节点：`CMP-DLG-HOST-ADAPTER`、`CMP-DLG-SNAPSHOT-VALIDATOR`。它们只产生短生命周期数据，不拥有独立业务状态，也不构成追踪豁免。

## 2. 逻辑数据模型

```yaml
DialogueArtifact:
  submission_uuid: string        # inherited idempotency key, immutable
  category: dialogue             # fixed by CT-001 semantics
  capture_anchor: task_created_at
  source:
    host_kind: codex_runtime
    capability_id: string
    capability_version: string?
    source_revision: string?
  completeness:
    status: complete|incomplete|unknown
    expected_scope: string
    pagination_complete: boolean
    truncation_detected: boolean
  entries:
    - ordinal: integer
      role: user|assistant|system|tool|other
      occurred_at: timestamp?
      content_ref: local_payload_ref
      source_ordinal: integer?
  checksum: string
  byte_size: integer
```

该模型是本层逻辑 schema，不改变 CT-001 的外部字段；UPLOAD-CLIENT 负责将其投影为父契约既有的 `material_chunks[]` dialogue 条目。

## 3. 数据流

### 3.1 成功写入流

1. PENDING-QUEUE 通过既有 IC-M01-03 提供 `submission_uuid`、作业上下文和 `config_ref`；Coordinator 使用队列已有 ST-04 任务创建时间解析 capture anchor，不修改 IC-M01-03 的字段集合。
2. Coordinator 建立 ST-DLG-01，并以该既有任务时间戳形成不可变 capture anchor。
3. Host Adapter 返回带来源与分页/截断信息的 HostDialogueSnapshot。
4. Snapshot Validator 检查 scope、顺序、完整性和可读性，生成规范化快照。
5. Artifact Store 一次写入 ST-DLG-02，返回 `DialogueArtifactRef`。
6. Coordinator 向 PENDING-QUEUE 返回 `dialogue_artifact`；由父层原有流程并行合并材料并上传。

### 3.2 失败与恢复流

- 宿主能力不可用、导出失败、超时或快照不完整：不生成可上传 artifact，返回稳定 `DIALOGUE_*` 错误和 `recoverable` 标志；PENDING-QUEUE 按父层 IC-M01-03 将任务保留为失败/待恢复。
- 同一 UUID 重试：若 ST-DLG-02 已存在，直接返回相同引用；若不存在，沿同一 capture anchor 重试，不创建新 UUID。
- 若宿主无法重现任务锚点且无法证明快照等价，停止在本地，不能用当前最新对话替代；该情况是实现前的父层变更触发条件，而不是本层自动降级。

### 3.3 清理流

PENDING-QUEUE 在服务端终态 `received` 或 `rejected` 后触发父层既有本地清理。Artifact Store 删除 ST-DLG-02；Coordinator 清理 ST-DLG-01。清理失败只记录本地诊断并重试，不改变服务端状态，也不删除 `failed`/`confirm_required` 任务。

## 4. 不变量、一致性、幂等与并发

| 规则 | 内容 | 依据 |
|---|---|---|
| INV-DLG-1 | 没有父层 `submission_uuid` 不得开始采集 | L1 IC-M01-03、KD-005 |
| INV-DLG-2 | `capture_anchor=task_created_at`；重试和上传重传不采集新时刻对话 | L1 LCD-002、INV-4 |
| INV-DLG-3 | completeness 不是 `complete`、检测到截断或分页未完成时不得生成可上传 artifact | REQ-DD003、D-AC-REQ-003-01 dialogue slice |
| INV-DLG-4 | 每个 submission_uuid 至多一个有效 ST-DLG-02；重复请求返回同一引用 | L1 IC-M01-03 幂等语义 |
| INV-DLG-5 | artifact category 恒为 `dialogue`；不得添加 CT-001 未定义的跨节点类别 | CT-001、KD-004 |
| CON-DLG-1 | 同一 UUID 的 active capture session 至多一个；并行任务之间相互隔离 | 本地一致性 |
| CON-DLG-2 | Artifact Store 单一写方；读者只能读取完整 manifest + payload | ST-02 owner 约束 |
| PRIV-DLG-1 | 对话内容仅在 DU-1 本机暂存；网络外发仍由 UPLOAD-CLIENT 负责 | KD-003、L1 ST-02 |

## 5. 父/兄弟所有权确认

- Submission、服务端材料保存、服务端完整性报告和状态机仍归 MOD-02。
- 代码/截图/结果材料仍归 `CMP-MATERIAL-COLLECTOR`。
- PendingTask、恢复调度和任务终态清理编排仍归 `CMP-PENDING-QUEUE`。
- 本层只把 L1 ST-02 细化为两个本地状态，不向父节点或兄弟节点转移数据所有权。
