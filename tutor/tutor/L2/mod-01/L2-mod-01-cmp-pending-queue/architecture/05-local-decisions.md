# 05 Local Decisions — CMP-PENDING-QUEUE 局部决策

> 父层 KD-003、KD-005、DU-1、CT-001/CT-002 及 A-007 的边界原样继承。本文件只记录当前 L2 为保证内部完整性所作的选择。

## 1. 本层已决定（decide_now，按稳定 ID 排序）

### `LCD-PQ-001` 恢复触发采用混合触发器

- **来源**：L1 `LCD-005`、AC-REQ-001-01 exceptions、CT-001 Retry。
- **问题**：网络恢复后如何触发同一 uuid 的续传？
- **方案比较**：
  1. **选定：启动恢复 + 可达性提示 + 退避定时器 + 手动重试**。覆盖进程重启、网络恢复、无网络提示能力和用户主动恢复；所有入口统一到 `RecoveryRequested`，由 lease/uuid 去重。
  2. 仅固定间隔轮询。实现简单，但网络恢复响应慢，且空闲时有无效唤醒。
  3. 仅手动重试。资源最省，但不满足“恢复后保留并可继续”的顺畅语义，进程重启后容易遗忘。
- **决策**：采用方案 1；可达性提示是优化信号，缺失时定时器和手动入口仍提供可恢复性。
- **后果**：RECOVERY-SCHEDULER 拥有 RecoverySchedule；不会创建消息总线或新的后台服务。
- **分类**：`decide_now`。

### `LCD-PQ-002` 单任务租约保证单飞上传

- **来源**：L1 `CON-1`、IC-M01-04、KD-005。
- **问题**：多个恢复触发、进程重启和手动重试同时到达时如何避免同一 uuid 并发上传？
- **方案比较**：
  1. **选定：持久化 TaskLease + lease 过期回收**。将“同一任务最多一个活跃执行”作为本地架构不变量，触发请求可并发到达但只能一个获得 lease。
  2. 仅进程内互斥锁。无法覆盖进程重启或多个 worker 实例。
  3. 允许并发并依赖服务端幂等。会增加分片/ checkpoint 对账竞争，不能满足本地状态一致性。
- **决策**：采用方案 1；lease 只约束本机队列，不改变服务端幂等键语义。
- **后果**：ORCHESTRATOR/STATE-STORE 需要原子 acquire/renew/release；lease 参数下沉到下一层。
- **分类**：`decide_now`。

### `LCD-PQ-003` 使用逻辑 StateStore 端口与 revision 原子提交

- **来源**：L1 `A-007`、父 ST-04、PQ-INV-006。
- **问题**：如何在不提前锁定文件/KV 产品的情况下保证崩溃恢复？
- **方案比较**：
  1. **选定：StateStore 逻辑端口 + revision/checksum + 原子提交语义**。业务只依赖 load/commit/CAS，具体介质下沉；可检测半写入并保留最近有效 revision。
  2. 业务节点直接写文件。短期简单，但把实现细节泄露到所有调用方，难以迁移。
  3. 事件溯源式全量事件日志。恢复和审计能力强，但超过当前本地队列需要，增加复杂度和隐私保留面。
- **决策**：采用方案 1；不在本层选择具体存储产品、序列化格式或加密库。
- **后果**：STATE-STORE 提供一致性边界；下一层只需在该端口内选择实现。
- **分类**：`decide_now`（具体机制为 implementation_detail）。

## 2. 委托下一层（defer_to_next_level）

| Decision ID | 事项 | 委托目标 | 触发条件 |
|---|---|---|---|
| `LCD-PQ-004` | 具体 worker 调度 API、timer 精度、网络可达性适配方式 | `CMP-PENDING-QUEUE-RECOVERY-SCHEDULER` | 不改变混合触发语义、trigger_id 去重或 lease 规则 |
| `LCD-PQ-005` | 本地文件/KV 产品、序列化 schema、加密和迁移策略 | `CMP-PENDING-QUEUE-STATE-STORE` | 必须满足 revision 原子性、checksum 校验和最近有效状态保护 |
| `LCD-PQ-006` | artifact 清理批次、错误退避和进程启动补偿 | `CMP-PENDING-QUEUE-CLEANUP` | 不清理 failed/confirm_required，不改变父 retain/delete 边界 |

## 3. 实现细节（implementation_detail）

| 事项 | 依据 |
|---|---|
| timer 的具体线程/任务 API | 父层仅规定 worker_job 实现面；不影响本层契约 |
| lease 的具体时长、时钟源和随机抖动 | 不改变单飞不变量，交由下一层参数化 |
| 文件名、目录布局、序列化库、checksum 算法 | A-007 implementation_detail；本层只固定 StateStore 端口 |
| cleanup 的具体删除调用顺序 | artifact owner 仍是 DC/MC/UC；本层只固定协调和幂等结果 |

## 4. 继承决策显式登记

| 父决策 | 当前层约束 |
|---|---|
| KD-003 | 任何网络交互仍由 CMP-UPLOAD-CLIENT 通过 HTTPS 执行；本层不新增网络通道 |
| KD-005 | submission_uuid 全程不变；恢复使用相同 uuid 与 checkpoint；`/api/v1` 和令牌语义不改 |
| A-007 | 本层固定持久化语义，不指定具体介质 |
| DU-1 | 四个子节点均为学生本机插件内逻辑组件，不创建服务、容器或独立部署单元 |
| 父状态边界 | `received/rejected` 只来自上传客户端/服务端应答；队列只维护客户端视图 |

## 5. 父层专属禁止项

- 不把 RecoveryScheduler 变成消息中间件或独立 worker 服务。
- 不把 PendingTask 状态提升为 MOD-02 Submission 状态机。
- 不改变 CT-001/CT-002 的必需字段、owner、失败/重试、幂等、版本或路径。
- 不在本层决定具体数据库、KV 产品或云服务；这会违反父层本地部署边界。
- 不把清理失败当成远端上传失败，也不因清理失败删除 failed/confirm_required 任务。

## 6. 局部决策队列汇总

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| `LCD-PQ-001` | L1 05 / 当前 PRD | LCD-005 / D-AC-REQ-001-01 | RECOVERY-SCHEDULER、R2 | 需要在多种触发器间选择，同时保持父契约不变 | decide_now | — |
| `LCD-PQ-002` | L1 03/04 | CON-1 / IC-M01-04 | ORCHESTRATOR、STATE-STORE | 并发恢复需要本地 single-flight 边界 | decide_now | — |
| `LCD-PQ-003` | L1 05 / 当前 PRD | A-007 / REQ-DD001 | STATE-STORE | 需要固定原子恢复语义，但不能提前选技术产品 | decide_now | — |
| `LCD-PQ-004` | 本层 | LCD-PQ-001 | RECOVERY-SCHEDULER | API/参数是下一层内部实现 | defer_to_next_level | RECOVERY-SCHEDULER |
| `LCD-PQ-005` | 本层 | LCD-PQ-003 | STATE-STORE | 存储产品与 schema 迁移细节未影响当前边界 | defer_to_next_level | STATE-STORE |
| `LCD-PQ-006` | 本层 | retention_boundary | CLEANUP | 清理批次参数不改变生命周期规则 | defer_to_next_level | CLEANUP |

队列结论：无遗留 `decide_now`，无 `return_to_parent`；当前包可进入 Human Gate。
