# 05 Local Decisions — CMP-STATUS-PRESENTER（L2）

## 1. 本层已决定

### LCD-SP-001：采用无状态投影管线

- **来源**：L1 `03-state-and-data.md §3.2`；当前 PRD `D-AC-REQ-001-01/002-01`。
- **问题**：状态展示是否维护自己的缓存/状态副本？
- **方案比较**：
  1. **选定：无状态投影**。每次从 IC-M01-05 读取完整输入，按 projector → mapper → renderer 生成视图。
  2. presenter 缓存最近任务状态：降低重复读取，但会复制 ST-04 并产生状态漂移，拒绝。
  3. presenter 自己查询 MOD-02：破坏父层依赖方向和“由 Pending Queue 记录事实”的边界，拒绝。
- **后果**：当前节点无持久化状态；展示与上游事实保持同一请求快照。
- **分类**：`decide_now`。

### LCD-SP-002：任务视图与配置视图分开投影

- **来源**：`IC-M01-05` 的 `task_view/config_view` 双输出；REQ-DD001/REQ-DD002。
- **问题**：是否使用一个通用 projector 处理所有展示输入？
- **方案比较**：
  1. **选定：任务/配置分开 projector，共用 mapper**。变化原因和输入所有权不同，但错误语义可统一。
  2. 单一通用 projector：代码量少，但容易混合 ST-01/ST-04 生命周期和字段规则，拒绝。
  3. 每个状态一个 projector：过度拆分，状态值由父层演进，拒绝。
- **后果**：形成 `CMP-SP-TASK-VIEW-PROJECTOR` 与 `CMP-SP-CONFIG-VIEW-PROJECTOR` 两个稳定子节点。
- **分类**：`decide_now`。

### LCD-SP-003：状态映射保持事实值并采用中性未知结果

- **来源**：L1 `FLOW-M01-002`、CT-001/CT-002 timeout 语义、当前 PRD D-AC-REQ-001-01。
- **问题**：`confirm_required`、`upload_failed`、`rejected` 等状态如何展示？
- **方案比较**：
  1. **选定：保留原始 status，映射可读消息**；未知结果展示“尚未确认/请稍后查看”，不推断成功或失败。
  2. 将所有非成功状态统一为“提交失败”：会丢失恢复和远端拒绝语义，拒绝。
  3. presenter 主动查询远端：引入新的依赖和副作用，违反父边界，拒绝。
- **后果**：`STATUS-MESSAGE-MAPPER` 只负责语义呈现，不负责业务决策。
- **分类**：`decide_now`。

## 2. 委托下一层

| Decision ID | 事项 | 委托目标 | 触发条件 |
|---|---|---|---|
| `LCD-SP-004` | 宿主 Codex 的具体渲染 API、交互载体和展示失败恢复方式 | `CMP-SP-RENDER-ADAPTER` L3 | 需要选择宿主调用方式或呈现媒介时；不得改变 IC-M01-05 |
| `LCD-SP-005` | 文案资源、多语言和 message_key 的组织方式 | `CMP-SP-STATUS-MESSAGE-MAPPER` L3 | 需要确定文案资源边界时；状态值仍由父契约约束 |

## 3. 实现细节

| Decision ID | 事项 | 依据 |
|---|---|---|
| `LCD-SP-006` | 具体 UI 框架、渲染函数、模板格式 | 不改变架构边界的编码选择 |
| `LCD-SP-007` | 日志字段编码与本地调试开关 | 仅允许非敏感摘要；不改变契约或状态所有权 |

## 4. 继承决策登记

| 父决策/约束 | 对本层的约束 |
|---|---|
| `KD-003` | 本层不引入明文网络交互；实际上本层不发起网络交互 |
| `KD-004` | 500MB/白名单由上游采集/服务端判定；本层只展示已记录结果 |
| `KD-005` | 令牌、submission UUID、分片续传、`/api/v1` 不由本层实现或修改 |
| `A-007` | 队列持久化实现不在本层决定 |
| `IC-M01-05` | 只读 owner/consumer/字段/错误/版本语义原样继承 |
| `DU-1` | 继续运行在学生本机 Codex Plugin 内，不创建独立部署单元 |

## 5. 父层专属禁止项

- 不新增或改写 IC-M01-05 的 required fields。
- 不把 presenter 的 `PresentationView` 提升为跨模块公共契约。
- 不写入 ST-01/ST-04，不复制远端 Submission 状态机。
- 不直接调用 MOD-02、CT-001、CT-002 或 auth/token。
- 不为展示引入消息中间件、服务端存储、独立服务或容器。

## 6. 局部决策队列汇总

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| `LCD-SP-001` | L1 state/data + current PRD | ST-01/ST-04；D-AC-REQ-001-01/002-01 | 所有子节点 | 是否允许 presenter 持有副本影响一致性与边界 | decide_now | — |
| `LCD-SP-002` | L1 interface contract | IC-M01-05 | TASK/CONFIG projector | 两类输入的所有权与生命周期不同 | decide_now | — |
| `LCD-SP-003` | L1 runtime/contract | FLOW-M01-002；CT timeout | STATUS-MESSAGE-MAPPER | 未知结果的呈现不能由字段映射自动推出 | decide_now | — |
| `LCD-SP-004` | L1 child-handoff | 宿主展示机制未规定 | RENDER-ADAPTER | 需要具体宿主能力才能落地交互适配 | defer_to_next_level | CMP-SP-RENDER-ADAPTER L3 |
| `LCD-SP-005` | 当前 PRD | 展示文案未规定 | STATUS-MESSAGE-MAPPER | 文案资源/多语言不是本层边界决策 | defer_to_next_level | CMP-SP-STATUS-MESSAGE-MAPPER L3 |
| `LCD-SP-006` | 当前层设计 | renderer 实现形式 | RENDER-ADAPTER | 属于编码实现选择 | implementation_detail | 详细设计 |
| `LCD-SP-007` | 当前层设计 | 本地诊断 | RENDER-ADAPTER | 属于非功能实现细节 | implementation_detail | 详细设计 |

**队列结论**：无遗留 `decide_now`，无 `return_to_parent`；两个局部展示问题已明确委托下一层，不阻塞本包交接。
