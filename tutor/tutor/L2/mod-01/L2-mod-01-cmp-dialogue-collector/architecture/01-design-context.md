# 01 Design Context — CMP-DIALOGUE-COLLECTOR（L2）

## 1. 本次设计范围

- **目标节点**：`CMP-DIALOGUE-COLLECTOR`，父包 L1 `MOD-01 codex-plugin` 的一个内部组件。
- **当前 PRD**：`C:\Users\Lenovo\Desktop\codex_plugin\prd\L2-PRD\mod-01\L2-mod-01-cmp-dialogue-collector\prd.md`。
- **模式**：`new`；输出目录在写入前为空，仅创建本次 L2 架构包。
- **范围**：细化对话导出、快照完整性、规范化和本地材料产物持久化；不重划 MOD-01 边界。
- **父/兄弟约束**：PENDING-QUEUE 仍拥有编排和任务状态；UPLOAD-CLIENT 仍是唯一网络出口；MATERIAL-COLLECTOR 仍负责代码/截图/结果；宿主 Codex 环境只作为外部 ACL 被引用。

## 2. 父边界快照

| 边界条目 | L1 绑定内容 | 分类 | 来源 |
|---|---|---|---|
| 稳定身份 | `CMP-DIALOGUE-COLLECTOR`，位于 MOD-01、DU-1 内 | inherited-fixed | L1/02、L1/06 |
| 职责 | 将当前作业项目相关的完整 Codex 对话导出为 dialogue 类提交材料 | inherited-refinable | L1/02 子节点注册表 |
| 排除项 | 不读三类材料目录；不上传；不决定提交时机；不做服务端归属校验 | inherited-fixed | L1/02、L1/04 |
| 状态所有权 | 持有本地 `ST-02` 对话导出物；一次采集、任务终态后清理 | inherited-fixed | L1/03 ST-02 |
| 上游编排 | `CMP-PENDING-QUEUE` 通过 `IC-M01-03` 传入 `task_ref` | inherited-fixed | L1/04 IC-M01-03 |
| 配置读取 | 只读消费 `IC-M01-02` 提供的有效配置/上下文 | inherited-refinable | L1/04 IC-M01-02 |
| 下游上传 | 产物成为 CT-001 `material_chunks[]` 的 `category=dialogue` 条目 | inherited-fixed | L1/04 CT-001 映射 |
| 外部系统 | 宿主 Codex 运行环境；父层只规定进程内集成 + 本机读取的 ACL 语义 | delegated | L1/01、L1/child-handoff |
| 部署 | DU-1 学生本机插件内组件，不创建独立运行时边界 | inherited-fixed | L1/03、L1/06 |
| 技术/契约 | HTTPS、令牌、幂等键、分片与服务端状态语义由父层固定；本组件不直接使用网络 | inherited-fixed | KD-003/KD-005、CT-001/CT-002 |

### 2.1 不可改变的父契约

本层只能实现 CT-001 的内容来源部分，不改变其 owner、路径、字段、类别语义、失败语义、幂等键或版本策略。`submission_uuid` 由 PENDING-QUEUE 生成并冻结；本组件只使用它作为采集会话的幂等关联键。服务端对材料完整性、邀请码、姓名、小组及课程归属的判断仍归 MOD-02。

## 3. 当前 PRD 需求分配

当前 PRD 的 `REQ-DD003` 通过 frontmatter 映射到父层 `REQ-D003`；`D-AC-REQ-003-01` 的完整服务器验收属于端到端继承契约，本组件只承接其中的对话采集切片。

| 当前需求/契约 | 分类 | 父层追踪 | L2 承接 |
|---|---|---|---|
| REQ-DD003：导出当前作业项目相关的完整 Codex 对话 | allocated | REQ-D003 / FR-003；REQ-DD003 映射；L1 ST-02 | 采集请求、宿主 ACL、完整性验证、不可变 artifact |
| D-AC-REQ-003-01：对话应可在提交详情中列出 | allocated（本组件切片） | parent AC-REQ-003-01；`contract_projection:CMP-DIALOGUE-COLLECTOR:shared` | 生成 `category=dialogue` 的可上传、可追踪产物 |
| D-AC-REQ-003-01：服务端校验、processing/rejected、教师端可见失败 | inherited / out-of-scope | L1 CT-001、MOD-02 状态机、MOD-05 展示 | 仅保证输入产物不伪造、不丢失 provenance；不实现服务器行为 |
| LCD-002：任务创建时刻采集、重传不重采 | inherited | L1/LCD-002、INV-4 | 以 `task_created_at` 作为 capture anchor；同一 UUID 返回已有 artifact |
| CT-001：`material_chunks[]` 类别标注 | inherited | L1/04 CT-001 | 只产生 dialogue 类条目，不新增类别和字段语义 |
| 宿主导出 API 形态 | delegated | L1/child-handoff §6 | 以 HostDialogueSourcePort 隔离，具体绑定不扩散到协调器或上传器 |
| 新网络依赖、独立部署或新公共契约 | out-of-scope | L1/02、L1/03、L1/04 | 不创建；如实现所需则 `return_to_parent` |

## 4. 局部驱动

1. **完整性优先**：不能把部分、顺序不明或来源不可证明的对话伪装成完整提交材料。
2. **快照稳定性**：任务创建后重试、断点续传或重新打开插件不得把新的对话混入旧 `submission_uuid`。
3. **宿主变化隔离**：宿主导出能力变化只能影响 ACL/Adapter，不得污染 PENDING-QUEUE、UPLOAD-CLIENT 或 CT-001。
4. **本地隐私边界**：对话只在学生本机暂存，上传由父层 UPLOAD-CLIENT 通过 HTTPS 执行，任务终态后由队列触发清理。
5. **失败可诊断**：导出失败必须返回稳定错误类别和可展示原因，不生成可上传的伪 artifact。

## 5. 可复用能力与阻塞缺口

- 可复用：L1 `ST-02` 生命周期、`IC-M01-03` 采集编排端口、CT-001 的 dialogue 类别语义、DU-1 本地运行形态、LCD-002 快照规则。
- 本层新增：对话采集内部端口、宿主 ACL、快照验证规则和 artifact manifest；均是选定节点内部结构。
- 非阻塞缺口：父层未提供宿主导出 API 的具体名称或版本。因此本层不假定具体 API 名称，而只定义所需能力（按任务锚点获取快照、提供来源/完整性元数据、可报告不可用）。
- 阻塞条件：若宿主只能提供当前时刻且不能证明任务创建时刻快照，或必须引入父层未批准的外部服务/文件系统/公共 API，则停止实现并提交 `parent-change-request.md`，本包架构不替代该审批。

## 6. 上下游影响与交接验证

- **上游**：`IC-M01-03` 的入参和返回字段不变；新增的 L2 内部端口只在 CMP-DIALOGUE-COLLECTOR 内部使用。
- **下游**：`dialogue_artifact` 仍由 PENDING-QUEUE 交给 UPLOAD-CLIENT，作为 CT-001 `material_chunks[]` 的 dialogue 条目；不新增网络交互。
- **兄弟节点**：仅引用 CONFIG-STORE、PENDING-QUEUE、MATERIAL-COLLECTOR、UPLOAD-CLIENT 的既有职责，不读取或重设计其内部。
- **交接验证**：检查七文件实际存在；需求和父追踪完整；所有子节点有稳定 ID 与追踪；ST-02 单一 owner；CT-001 语义无变化；三条本地运行流覆盖成功、失败/恢复、生命周期；无 `decide_now` 遗留。

## 7. 假设、开放问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | 宿主可通过进程内能力或本机既有导出机制提供对话快照及来源元数据 | 以 `CMP-DLG-HOST-ADAPTER` 封装；具体 API 绑定下沉 |
| 开放问题 | 宿主是否支持按 `task_created_at` 获取一致快照、是否能报告截断/分页 | 作为下一层 Host Adapter 的入口验收条件 |
| 冲突 | 当前 PRD 架构输入契约均为“待补充”，且禁止生成器擅自新增系统边界 | 父包已有绑定边界，故只采用既有宿主 ACL，不新增外部系统；无父边界冲突 |
