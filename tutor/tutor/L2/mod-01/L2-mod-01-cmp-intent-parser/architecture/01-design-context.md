# 01 Design Context — CMP-INTENT-PARSER（L2）

## 1. 本次设计范围与预检证据

| 项目 | 实际解析值 |
|---|---|
| `parent_architecture` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-01` |
| `target_node_id` | `CMP-INTENT-PARSER` |
| `current_prd` | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-01/L2-mod-01-cmp-intent-parser/prd.md` |
| `output_dir` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L2/mod-01/L2-mod-01-cmp-intent-parser` |
| `mode` | `new` |
| 输出安全 | 目标目录不存在；父目录已有 `cmp-config-store`、`cmp-dialogue-collector` 两个兄弟目录，本次不覆盖、不修改 |
| 父包类型 | `recursive_child_package` |
| 目标匹配 | 在 L1 `child-handoff.md`、`02-architecture-decomposition.md`、`04-contracts-and-runtime.md` 三处唯一匹配 |
| `parent_prd` | 未读取；L1 父包已提供完整需求、契约、流程和决策追踪 |

本次只细化 `CMP-INTENT-PARSER` 内部，不重设计 `CMP-PENDING-QUEUE`、`CMP-STATUS-PRESENTER`、`CMP-CONFIG-STORE` 或其他兄弟节点。

## 2. 父边界快照

### 2.1 身份、职责与排除项

| 条目 | 父层约束 | 来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `CMP-INTENT-PARSER`，MOD-01 内部组件 | L1 `child-handoff.md §2` | inherited-fixed |
| 职责 | 自然语言提交指令 → `SubmissionIntent`；确定性缺项检测并返回具体缺失字段 | L1 `02 §2` | inherited-refinable |
| 不持久化 | 不拥有任何持久状态；解析是即时计算 | L1 `03 §1` | inherited-fixed |
| 不编排任务 | 不创建 `PendingTask`、不生成 UUID、不上传 | L1 `02 §2` | inherited-fixed |
| 不收集材料 | 不导出对话、不读取目录 | L1 `02 §2` | inherited-fixed |
| 部署身份 | 随 DU-1 学生侧插件进程运行，不创建服务或部署单元 | L1 `01 §2.4`、`child-handoff.md §1` | inherited-fixed |

### 2.2 父契约、状态与直接边界

| 类型 | 内容 | 当前层行为 | 分类 |
|---|---|---|---|
| 内部契约 | `IC-M01-01`：`command_text` → `SubmissionIntent` 或 `MissingFields`，纯进程内，无副作用 | 由本层 `PORT-ADAPTER` 对外实现，内部再分派到提取、规范化、闸门 | inherited-fixed / inherited-refinable |
| 配置依赖 | `IC-M01-02`：只读获得 `EffectiveConfig`，配置 owner 仍是 `CMP-CONFIG-STORE` | 仅作上下文/诊断参考；不得静默用配置补齐当前指令的必填槽位 | inherited-fixed |
| 上游 | 学生提交自然语言指令、L1 入口编排 | 接收 `command_text`，不直接与学生 UI 或网络交互 | inherited-refinable |
| 下游 | `CMP-PENDING-QUEUE` | 完整时交付 `SubmissionIntent`；缺项/不确定时交付具体 `MissingFields` | inherited-fixed |
| 间接展示 | `CMP-STATUS-PRESENTER` 经队列/状态端口展示缺项 | 本层不建立直接跨组件展示接口 | inherited-fixed |
| 状态 | 本层无持久状态；仅存在请求范围候选槽位、规范化值和结果 | 明确标注 `persistence=none` | inherited-fixed |

### 2.3 继承决策和不变量

- `LCD-001`：采用“可演进提取 + 确定性必填闸门”；`assignment`、`student_name`、`group_name` 任一缺失或无法确定时不得放行。
- 指令中的姓名/小组优先于配置中的同名字段；配置不得覆盖当次指令语义。
- `INV-1`：缺项不创建提交、不产生网络调用。
- 本层不得引入外部 NLU 服务、消息总线、数据库、缓存持久化或独立运行时。

## 3. 当前 PRD 需求分配

| 当前需求 | 分类 | 父层追踪 | 本层承接 |
|---|---|---|---|
| `REQ-DD001` | allocated | `REQ-D001` → `REQ-001/FR-001`；L1 `F1-1`；`IC-M01-01` | 解析入口、字段提取、规范化和确定性缺项闸门 |
| `D-AC-REQ-001-01` | allocated | `REQ-DD001`；父 `AC-REQ-001-01` / `D-AC-REQ-001-01` | 完整指令返回唯一可交付 `SubmissionIntent`；缺项返回具体字段 |
| 缺项不创建可评分提交 | inherited | `INV-1`；L1 `FLOW-M01-001` 分支 `required_field_missing` | 只返回 `MissingFields`，不调用队列创建任务或任何网络 |
| 服务器不可达时保留本地任务 | out-of-scope for this node | L1 `D-AC-REQ-001-01 exceptions`；`CMP-PENDING-QUEUE` / `CMP-UPLOAD-CLIENT` | 本层仅保证无网络副作用；任务保留与恢复由兄弟节点负责 |
| 配置持久化、材料上传、状态展示 | out-of-scope | L1 `REQ-D002/D004`、`IC-M01-02/03/04/05` | 仅通过父层已有端口引用，不复制职责 |

## 4. 局部驱动

1. **确定性**：最终放行必须由本层规则判断，不由概率性解析或外部服务决定。
2. **可替换提取**：自然语言提取机制可以演进，但不能改变 `IC-M01-01` 的输入/输出和缺项语义。
3. **失败闭合**：字段歧义、空值或无法确认时返回具体缺失/不确定诊断，不猜测、不放行。
4. **零副作用**：同一 `command_text` 与同一配置快照得到同一结果；解析失败不产生持久化和网络副作用。

## 5. 可复用能力、缺口与影响

### 可复用能力

- L1 已定义的 `SubmissionIntent` 三字段和值对象语义。
- `IC-M01-01`、`IC-M01-02` 的字段、错误、幂等和 owner 约束。
- L1 的 `FLOW-M01-001` 缺项分支与 `INV-1`。

### 非阻塞缺口

- 具体宿主 Codex NL 能力、模板或规则库尚未由父层规定；本层将其保留为提取器实现细节。
- 若实现需要外部 NLU 服务或把解析结果持久化，影响父边界，必须返回父层，不在本层假设批准。

### 文件与上下游影响

本次创建七个标准文件；不创建 `parent-change-request.md`。不改变父契约、不新增跨模块契约、不改变兄弟状态所有权。`CMP-STATUS-PRESENTER` 只通过 L1 已有间接链路接收缺项展示数据。

## 6. 交接验证方法

1. 复核四必需输入、输出目录安全和目标唯一匹配证据。
2. 逐条检查 `REQ-DD001`、`D-AC-REQ-001-01`、`REQ-D001/F1-1` 已映射到子节点与运行流。
3. 核对 `IC-M01-01/02` 的 provider、consumer、字段、失败、幂等和副作用未被改写。
4. 检查所有子节点有稳定 ID、职责、排除项、状态、依赖、存在理由和追踪列。
5. 确认所有状态均为请求范围瞬态，未转移 `PluginConfig`、`PendingTask` 或服务端 `Submission` 所有权。
6. 确认决策队列没有未处理 `decide_now` 或 `return_to_parent`。

## 7. 假设、问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | 三个必填槽位必须从当次提交指令中明确得到；配置值不静默填补缺项 | 继承 L1 `LCD-001` 与验收边界 |
| 问题 | 宿主 NL 提取能力的具体调用方式未定 | 委托提取器子节点作为 implementation_detail；若引入外部依赖再 `return_to_parent` |
| 冲突 | 当前 L2 PRD 的系统边界/外部依赖栏为“待补充” | 以已验证 L1 父边界为绑定约束，不擅自扩展 |
