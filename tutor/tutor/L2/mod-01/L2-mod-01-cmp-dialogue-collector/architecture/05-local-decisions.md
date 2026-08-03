# 05 Local Decisions — CMP-DIALOGUE-COLLECTOR（L2）

## 1. 本层已决定（按稳定 Decision ID 排序）

### LCD-DLG-001 宿主导出必须隔离在 ACL Adapter

- **来源**：REQ-DD003；L1 C5 委托；宿主导出 API 未固定。
- **问题**：由协调器直接调用宿主机制，还是隔离宿主变化？
- **方案比较**：
  1. **选定：Host Adapter + HostDialogueSourcePort**。只允许 `CMP-DLG-HOST-ADAPTER` 接触宿主，向内部返回规范化能力观察和快照。
  2. Coordinator 直接调用宿主 API：耦合宿主版本，拒绝。
  3. 新增独立导出服务/外部文件同步：改变父部署和外部边界，必须回父层，拒绝。
- **后果**：具体宿主 API 名称、版本和调用方式下沉到 Adapter 详细设计；不新增外部系统。
- **分类**：`decide_now`（边界结构）；具体 API 绑定是 `implementation_detail`。

### LCD-DLG-002 以任务创建时刻作为快照锚点

- **来源**：L1 LCD-002、INV-4、REQ-D003。
- **问题**：重试时是否重新读取当前对话？
- **方案比较**：
  1. **选定：task_created_at anchor + 同 UUID 幂等**。若已有 artifact 则复用；没有则按原 anchor 重试。
  2. 每次上传前读取最新对话：会把新内容混入旧提交，破坏幂等，拒绝。
  3. 仅在内存中保存首次读取：崩溃/断网会丢失快照，拒绝。
- **后果**：宿主必须能提供等价的历史快照或在任务创建时形成不可变导出；否则不能自动降级。
- **分类**：`decide_now`（继承父语义并固定本层实现）。

### LCD-DLG-003 对完整性证据不足时 fail closed

- **来源**：REQ-DD003“完整对话”；D-AC-REQ-003-01 dialogue slice。
- **问题**：宿主返回部分数据、分页未完成或无法报告截断时是否上传？
- **方案比较**：
  1. **选定：验证失败，不生成可上传 artifact**；返回可诊断错误，保留任务恢复。
  2. 以 warning 上传部分数据：违反“完整对话”并让服务端无法区分部分材料，拒绝。
  3. 本层自行补写/推断缺失条目：不可验证且改变材料真实性，拒绝。
- **后果**：服务端仍是材料业务校验权威；本层只负责本地采集完整性放行。
- **分类**：`decide_now`。

### LCD-DLG-004 对话产物不可变且单一写方

- **来源**：L1 ST-02、IC-M01-03 幂等、KD-005。
- **问题**：产物是否允许上传重试期间被重新生成或覆盖？
- **方案比较**：
  1. **选定：Artifact Store 单一写方，checksum 绑定 submission_uuid**；同 UUID 不允许不同 payload 覆盖。
  2. 上传器每次自行读取宿主：职责泄漏且破坏快照，拒绝。
  3. 多组件共享写入：无法保证唯一 artifact，拒绝。
- **分类**：`decide_now`。

## 2. 委托下一层（defer_to_next_level）

| Decision ID | 事项 | 目标 child_id | 触发条件 |
|---|---|---|---|
| LCD-DLG-005 | 宿主具体导出 API/能力版本、分页协议、宿主会话标识映射 | CMP-DLG-HOST-ADAPTER | 进入下一层前必须证明可按任务 anchor 获取快照，并能报告截断/不完整 |
| LCD-DLG-006 | 本地产物的具体序列化格式、临时文件布局和清理重试实现 | CMP-DLG-ARTIFACT-STORE | 不能改变 ST-DLG-02 不可变、终态清理和本机隐私边界 |

## 3. 实现细节（implementation_detail）

| Decision ID | 事项 | 约束 |
|---|---|---|
| LCD-DLG-007 | Adapter 的 API 调用封装、线程/异步方式、局部超时数值 | 不改变 IC-DLG-002 的错误和幂等语义 |
| LCD-DLG-008 | checksum 算法、压缩方式、临时文件命名 | 不改变 artifact manifest 语义；不新增 CT-001 字段 |

## 4. 继承决策与本层禁止事项

| 父决策/约束 | 本层处理 |
|---|---|
| KD-003 | 不发网络；未来产物外发仍必须经 UPLOAD-CLIENT HTTPS |
| KD-004 | 本层不负责三类材料白名单/500MB 服务端权威判断；只保证 dialogue 类别不被篡改 |
| KD-005 | 复用 submission_uuid 幂等键；不创建第二个提交键，不做上传断点逻辑 |
| A-007 | 本地持久化机制仍是实现细节；本层只规定 ST-DLG-02 生命周期 |
| DU-1 | 不创建服务、容器、数据库、消息总线或独立部署单元 |
| CT-001/CT-002 | 字段、路径、owner、失败、重试、版本语义不可在本层修改 |

## 5. 局部决策队列汇总

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-DLG-001 | L1 02 / 当前 PRD | REQ-DD003 / C5 | CMP-DLG-HOST-ADAPTER、IC-DLG-002 | 宿主机制需要稳定隔离面 | decide_now | — |
| LCD-DLG-002 | L1 05 / L1 03 | LCD-002 / INV-4 | Coordinator、ST-DLG-01/02 | 锚点决定幂等与完整性 | decide_now | — |
| LCD-DLG-003 | 当前 PRD / D-AC | REQ-DD003 / D-AC-REQ-003-01 | Snapshot Validator | 完整性不足时是否放行需固定 | decide_now | — |
| LCD-DLG-004 | L1 03/04 | ST-02 / IC-M01-03 | Artifact Store | 产物唯一性和恢复语义需固定 | decide_now | — |
| LCD-DLG-005 | L1 child-handoff | 宿主导出能力未规定 | Host Adapter | 具体宿主 API 需下一层验证 | defer_to_next_level | CMP-DLG-HOST-ADAPTER |
| LCD-DLG-006 | L1 03 / A-007 | ST-02 / A-007 | Artifact Store | 序列化和布局不影响当前边界 | defer_to_next_level | CMP-DLG-ARTIFACT-STORE |
| LCD-DLG-007 | 本层 | IC-DLG-002 | Host Adapter | 编码实现细节 | implementation_detail | — |
| LCD-DLG-008 | 本层 | IC-DLG-004 | Artifact Store | 编码实现细节 | implementation_detail | — |

**队列结论**：所有 `decide_now` 已记录；无 `return_to_parent`。宿主能力是已声明的非阻塞开放风险，但若验证发现需要新外部依赖或无法满足任务锚定快照，后续运行必须按规则生成 `parent-change-request.md` 并停止。
