# 01 Design Context — CMP-MATERIAL-COLLECTOR（L2）

## 1. 本次设计范围

- **目标节点**：`CMP-MATERIAL-COLLECTOR`，父包为 `architecture/L1/L1-mod-01`，唯一匹配证据见 `architecture-manifest.yaml`。
- **当前 PRD**：`prd/L2-PRD/mod-01/L2-mod-01-cmp-material-collector/prd.md`。
- **模式**：`new`；输出目录为 `architecture/L2/mod-01/L2-mod-01-cmp-material-collector`，写入前已确认不存在。
- 本层只细化材料收集器内部；`CMP-CONFIG-STORE`、`CMP-DIALOGUE-COLLECTOR`、`CMP-PENDING-QUEUE`、`CMP-UPLOAD-CLIENT`、`CMP-STATUS-PRESENTER` 仅作为协作者引用，不重设计其内部。

## 2. 父边界快照

### 2.1 身份、职责与排除项

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `CMP-MATERIAL-COLLECTOR`，MOD-01 内材料收集组件 | `02-architecture-decomposition.md` §2 | inherited-fixed |
| 职责 | 按配置目录收集代码、截图、项目结果文件；白名单过滤与 500MB 预算预检；生成 `MaterialManifest` 并关联作业/姓名/小组 | 父包组件行；当前 PRD 机会窗口 | inherited-refinable（内部细化开放） |
| 排除项 | 不导出对话、不上传、不执行服务端归属校验；空材料类别的服务端缺失标记不在本组件决定 | 父包 `02`、`04` | inherited-fixed |
| 部署 | DU-1 student-plugin，学生本机 Codex 环境内进程 | L1 `01` §2.1、`06` 部署约束 | inherited-fixed |

### 2.2 状态与数据所有权

| 条目 | 内容 | 分类 |
|---|---|---|
| 父状态 | `ST-03 MaterialManifest + 材料暂存引用` 由本目标组件拥有 | inherited-fixed |
| 状态范围 | 三类目录材料的路径引用、类别、大小、采集时间、缺失/预检警告；不持有 Submission | inherited-fixed |
| 生命周期 | 任务创建时生成；上传重试复用快照；任务进入 `received`/`rejected` 后由 MOD-01 队列协调清理 | inherited-fixed |
| 服务端权威 | 500MB/白名单的最终拒绝由服务端 CT-001 处理；本层只做预检，不复制远端状态机 | inherited-fixed |

### 2.3 契约与直接边界

| 条目 | 内容 | 分类 |
|---|---|---|
| 上游编排 | `IC-M01-03`：`CMP-PENDING-QUEUE` 向对话/材料采集器发起采集；本组件返回材料清单 | inherited-fixed |
| 外部上传 | `CT-001` 由 `CMP-UPLOAD-CLIENT` consumer 实现；本组件只提供 `material_chunks[]` 的材料来源 | inherited-fixed |
| 配置依赖 | 读取 `CMP-CONFIG-STORE` 提供的 `code_dir`、`screenshot_dir`、`result_dir` 与配置完整性 | inherited-fixed |
| 外部系统 | 学生本机文件系统，属于父层 Codex 运行环境/本地文件读取边界；本层可细化 ACL/Adapter，不拥有外部系统 | inherited-refinable |
| 下游读方 | `CMP-PENDING-QUEUE`、`CMP-UPLOAD-CLIENT`、`CMP-STATUS-PRESENTER` 读取清单或警告 | inherited-fixed |

### 2.4 相关运行流与继承决策

- `FLOW-001` / `SCENARIO-001`：任务创建后，队列驱动对话和材料采集，再交给上传链路。
- `DF-1` 步骤 1–3：缺项检查、采集材料、进入 CT-001 上传准备。
- `KD-004`：500MB 与文件类型白名单；服务端权威，本层客户端预检。
- `KD-003` / `KD-005`：HTTPS、submission UUID 幂等键、分片断点续传；本层不改动这些语义。
- `LCD-003`：客户端预检 + 服务端权威，预检只告警，不以本地判断替代服务端判定。
- `A-007`：本地持久化机制属于实现细节；本层不选择文件/KV/数据库平台。

## 3. 当前 PRD 需求分配

| 当前需求/契约 | 分类 | 父层追踪 | 本层承接 |
|---|---|---|---|
| `REQ-DD004`：按配置目录收集代码、截图、项目结果文件并关联身份 | allocated | `REQ-D004` / `REQ-004` / `FR-004`；父 `02` 组件行 | 扫描、过滤、清单组装三个 L2 child |
| `D-AC-REQ-003-01`：提交详情可列出代码、截图、结果及缺失项 | allocated | `REQ-DD004`；`AC-REQ-003-01` shared 的 MOD-01 slice；`CT-001 material_chunks[]` | `MaterialManifest` 类别、缺失项和警告可被队列/展示器读取 |
| 500MB 与文件白名单预检 | inherited | `KD-004`、`LCD-003` | `CMP-MC-FILTER-POLICY` 只做客户端预检，不改变服务端权威 |
| 关联作业/姓名/小组 | inherited | 父 `IC-M01-03` 任务身份快照、`REQ-D004` | `CMP-MC-MANIFEST-BUILDER` 将任务身份写入清单上下文 |
| 空材料目录 | inherited | L1 `02`/`03`：类别照常留空，缺失标记归服务端 | 保留类别条目与 `missing_categories[]` 供上游展示/上传 |
| PRD 架构输入契约中的“待补充”项 | inherited | 当前 PRD 明确禁止生成器擅自决定 | 全部沿用父层边界，不新增系统边界或外部依赖 |
| `dependency_refs` 中的兄弟组件 | inherited | `CMP-CONFIG-STORE`、`CMP-PENDING-QUEUE`、`CMP-UPLOAD-CLIENT` 等 | 仅消费既有协作语义，不为兄弟节点创建新契约 |

## 4. 局部驱动

1. **类别完整性**：代码、截图、结果必须分别标注，类别映射必须能直接进入父契约 `material_chunks[]`。
2. **预检可解释性**：过滤原因、超预算和目录缺失应形成可展示的诊断，不把服务端最终拒绝伪装成本地结论。
3. **快照一致性**：同一 `submission_uuid` 的重传不能因目录后续变化而重新生成另一份材料清单。
4. **身份关联**：清单必须绑定任务创建时的 `assignment`、`student_name`、`group_name`，但不承担课程归属校验。

## 5. 可复用能力与阻塞判断

### 可复用能力

- `CMP-CONFIG-STORE` 已拥有配置校验与三个目录字段；本层只读取有效配置快照。
- `CMP-PENDING-QUEUE` 已拥有任务 UUID、任务创建时刻和采集编排；本层不生成新的公共任务 ID。
- L1 已定义 `ST-03`、`MaterialManifest`、`IC-M01-03` 与 `CT-001` 类别语义；本层直接实现，不重复定义父契约。

### 阻塞缺口

- 无阻塞缺口。当前 PRD 的系统边界、外部依赖和技术约束明确要求继承父层；父包已提供所需证据。
- 目录遍历深度、符号链接和忽略目录策略属于下一层扫描器细化，不阻塞当前 L2 结构。

## 6. C1-C6 预检映射与上下游影响

| 映射 | 本层结果 | 边界结论 |
|---|---|---|
| C1 | `CMP-MATERIAL-COLLECTOR` → 三个 L2 child | 全部留在选定组件内部 |
| C2 | `ST-03` → 清单构建器；候选集/过滤结果为内部短生命周期状态 | 不转移父组件或兄弟所有权 |
| C3 | `IC-M01-03` 采集编排 → 扫描→过滤→组装→返回 | 保持父层采集顺序与外部结果 |
| C4 | 父采集端口由清单构建器实现；内部使用两个 node-scoped 契约 | 不修改 `IC-M01-03` 或 `CT-001` |
| C5 | 本地文件系统由扫描器作为 ACL/Adapter 使用 | 不 redesign 文件系统或宿主环境 |
| C6 | 完整性、可解释性、快照一致性 → 本地策略与状态约束 | 不引入父级平台或部署边界 |

## 7. 预定输出与交接验证

计划创建七个文件：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`；不创建 `parent-change-request.md`。

交接时检查：输入与唯一匹配证据、REQ-DD004/验收契约覆盖、child trace 列、ST-03 所有权、CT-001/IC-M01-03 语义不变、成功/失败/生命周期流、无遗留 `decide_now` 或 `return_to_parent`、清单按稳定 ID 排序。

## 8. 假设、问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | 配置中的三个目录字段已经由 `CMP-CONFIG-STORE` 提供有效快照 | 本层不重复配置校验；运行中失效按材料收集错误返回 |
| 假设 | 预算统计针对白名单过滤后的候选材料；被过滤文件不进入待上传集合 | 作为 `LCD-L2-MC-002` 本地决定记录 |
| 委托 | 递归遍历、符号链接和忽略目录策略 | 委托 `CMP-MC-DIRECTORY-SCANNER` 下一层细化 |
| 冲突 | 无 | 当前 PRD 没有要求变更父责任、契约、所有权、技术或部署 |
