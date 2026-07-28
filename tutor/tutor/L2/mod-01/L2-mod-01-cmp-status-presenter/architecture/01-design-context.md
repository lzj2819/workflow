# 01 Design Context — CMP-STATUS-PRESENTER（L2）

## 1. 本次设计范围

- **目标节点**：`CMP-STATUS-PRESENTER`，来自 L1 `MOD-01` 的唯一子节点匹配。
- **当前 PRD**：`prd/L2-PRD/mod-01/L2-mod-01-cmp-status-presenter/prd.md`。
- **模式**：`new`；输出目录为 `architecture/L2/mod-01/L2-mod-01-cmp-status-presenter`。
- 本层只细化学生侧状态与错误展示的内部结构；不重设计 `CMP-PENDING-QUEUE`、`CMP-CONFIG-STORE`、`CMP-UPLOAD-CLIENT` 或 MOD-02。

## 2. 父边界快照

### 2.1 身份、职责与排除项

| 条目 | 内容 | 父层来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `CMP-STATUS-PRESENTER`，MOD-01 内部组件 | `child-handoff.md §2` | inherited-fixed |
| 职责 | 展示缺失字段、配置/目录错误、提交编号、接收确认、失败原因及远端状态 | L1 child-handoff；当前 PRD Problem Statement | inherited-refinable |
| 状态所有权 | 不拥有状态；只读 ST-01 `PluginConfig` 与 ST-04 `PendingTask` | `03-state-and-data.md §1/§3.2` | inherited-fixed |
| 对外语义 | 学生看到的是本地任务视图与远端应答的派生结果，不伪造结论 | `04-contracts-and-runtime.md §4~§6` | inherited-fixed |
| 部署形态 | DU-1 学生本机 Codex Plugin 进程 | L1 manifest §boundary_fingerprint | inherited-fixed |
| 排除项 | 不上传、不重试、不查询远端、不做归属校验、不持久化展示副本 | L1 manifest；L1 child-handoff | inherited-fixed |

### 2.2 父契约与直接边界

| 边界 | 内容 | 所有者/方向 | 分类 |
|---|---|---|---|
| `IC-M01-05` | `status`、`submission_id`、`missing_items[]`、`failure_reason`、`progress`、`completeness[]`、`dir_errors[]` → `task_view/config_view` | CMP-PENDING-QUEUE、CMP-CONFIG-STORE → 本节点 | inherited-fixed |
| 上游状态 | ST-04 任务状态与失败原因；ST-01 配置完整性与目录错误 | 上游组件拥有，本节点只读 | inherited-fixed |
| 学生侧输出 | 提交编号/确认、具体缺失项、具体目录错误、失败原因、远端状态 | 本节点通过父层 local_outbound 展示 | inherited-refinable |
| 外部系统 | 学生与宿主 Codex 交互面；具体渲染 API 未规定 | DU-1 宿主边界 | delegated |

### 2.3 相关父流程

- `FLOW-M01-001`：任务完成或远端结果到达 → `IC-M01-05` → 展示接收确认、提交编号或缺失项。
- `FLOW-M01-002`：上传中断、结果未知、`rejected`、`upload_failed` → 由上游记录后展示真实状态与失败原因。
- `FLOW-M01-003`：配置保存成功、不完整或拒绝 → 展示配置结果和具体目录错误。

### 2.4 验收场景分段声明

Gherkin 场景（`L2测试/L2-mod-01-cmp-status-presenter/L2-mod-01-cmp-status-presenter.feature`，SC-001~011）为端到端验收链路；本节点只参与其中的展示段，其余段由父层兄弟组件或 MOD-02 承担，不属于本包的合法数据流。

| 场景 | 本节点参与段 | 非本节点段及归属 |
|---|---|---|
| SC-001 创建任务并提交服务器 | 无（仅结果到达后的展示，见 SC-002/005/006） | 创建与提交：`CMP-INTENT-PARSER`、`CMP-UPLOAD-CLIENT` |
| SC-002 返回唯一提交编号 | 展示提交编号（`RF-SP-01`） | 编号生成与记录：`CMP-UPLOAD-CLIENT`/MOD-02 → ST-04 |
| SC-003 服务器记录信息 | 无 | 远端记录：MOD-02 |
| SC-004 缺必填信息不创建可评分提交 | 无（创建决策不在本节点） | 判定与拒绝创建：`CMP-INTENT-PARSER`/`CMP-PENDING-QUEUE` |
| SC-005 返回具体缺失字段 | 展示具体缺失字段与不完整状态（`RF-SP-02`） | `missing_items[]` 产生：上游 → ST-04 |
| SC-006 保留任务并显示失败原因 | 显示失败原因（`RF-SP-02`） | 保留本地待上传任务：`CMP-PENDING-QUEUE`（ST-04） |
| SC-007 保存配置并下次使用 | 展示保存成功结果（`RF-SP-03`） | 保存与复用：`CMP-CONFIG-STORE`（ST-01）、`CMP-UPLOAD-CLIENT` |
| SC-008 配置重新打开后值一致 | 无 | 设置页重开回填：`CMP-CONFIG-STORE` 直读 ST-01；本节点只展示保存结果，不展示配置原值 |
| SC-009 目录不可读显示具体错误 | 展示具体目录错误（`RF-SP-03`） | `dir_errors[]` 产生：`CMP-CONFIG-STORE` |
| SC-010 配置不完整列出缺失项 | 展示配置缺失项（`RF-SP-03`） | 不完整判定与保存：`CMP-CONFIG-STORE` |
| SC-011 拒绝保存并保留上次有效配置 | 展示拒绝结果与具体错误（`RF-SP-03`） | 拒绝与保留上次有效配置：`CMP-CONFIG-STORE` |

SC-008 范围说明：本节点不承接"配置值一致展示"——`IC-M01-05` 不含配置原值字段，PRD 机会窗口也未列举该职责；值回填由设置页经 `CMP-CONFIG-STORE` 完成，无需 `return_to_parent`。

## 3. 当前 PRD 需求分配

| 当前需求/验收契约 | 分类 | 父层追踪 | 本层承接 |
|---|---|---|---|
| `REQ-DD001`：提交任务完成后提供可观察结果 | allocated | `REQ-001/FR-001`；`IC-M01-05`；`AC-REQ-001-01` | 任务视图投影、状态/错误映射、学生侧渲染 |
| `D-AC-REQ-001-01`：返回唯一提交编号；缺项具体可见；服务器不可达时保留任务并显示失败原因 | allocated | `AC-REQ-001-01`；L1 `FLOW-M01-001/002` | 成功确认、缺失字段、`rejected`、`upload_failed`、未知结果的只读展示 |
| `REQ-DD002`：配置结果可复核 | allocated | `REQ-002/FR-002`；`IC-M01-05`；`AC-REQ-002-01` | 配置完整性、缺失目录和目录错误的展示 |
| `D-AC-REQ-002-01`：目录不可读/为空、格式无效时具体可见且保留上次有效配置语义 | allocated | `AC-REQ-002-01`；L1 `FLOW-M01-003` | 配置视图投影与错误文案映射；不参与保存决策 |
| HTTPS、令牌、幂等键、分片续传、500MB/白名单 | inherited | `KD-003/004/005` | 仅保持展示语义，不实现这些机制 |
| 当前 PRD 的系统边界、外部依赖、明确约束 | inherited | PRD 标记“待补充；不得擅自决定” | 继承 L1，不新增父级边界 |

当前 PRD 的有效需求均在本节点范围内；无需求需要分配给兄弟节点，也没有触发 `return_to_parent`。

## 4. 本层局部驱动

1. **真实状态可见**：`received`、`rejected`、`upload_failed`、结果未知等状态必须按上游事实展示，不能推断或改写为成功/失败。
2. **缺项具体**：缺少作业、姓名或小组时展示字段级信息，不创建或修改任务。
3. **配置问题可行动**：目录为空、不可读或配置不完整时给出具体目录/字段信息；不覆盖上一次有效配置。
4. **无状态低耦合**：展示组件不复制 ST-01/ST-04，不引入第二份提交状态或错误存储。
5. **宿主适配隔离**：展示文案/视图模型与宿主渲染机制分离，使交互形式可以在下一层细化而不改变父契约。

## 5. 可复用能力与阻塞检查

- 可复用：L1 `IC-M01-05`、ST-01/ST-04 的所有权、父流程终止状态、错误语义与 DU-1 运行边界。
- 本层新增：四个内部 child node、三个节点内契约和瞬时派生视图模型。
- 阻塞缺口：无。宿主具体展示 API 影响实现选型，但不改变当前内部边界，已委托给 `CMP-SP-RENDER-ADAPTER` 下一层。

## 6. 上下游影响与交接验证方法

- **上游**：`CMP-PENDING-QUEUE`、`CMP-CONFIG-STORE` 仍是 `IC-M01-05` provider；契约字段和只读语义不变。
- **下游**：学生侧展示面只接收本节点输出；不新增跨模块 provider/consumer。
- **兄弟节点**：仅引用 `CMP-INTENT-PARSER`、`CMP-UPLOAD-CLIENT` 产生的事实，不重设计其内部。
- **验证方法**：检查七文件存在性；逐项追踪 `REQ-DD001/002` 和两条 D-AC；核对 `IC-M01-05` 字段/owner/side effects；核对无持久状态与无跨父边界决策。

## 7. 假设、开放问题与冲突

| 项目 | 处置 | 影响 |
|---|---|---|
| 宿主 Codex 的具体渲染 API 未规定 | `defer_to_next_level`，交给 `CMP-SP-RENDER-ADAPTER` | 不阻塞本层结构；下一层必须提供兼容适配方案 |
| 文案是否支持多语言 | implementation_detail，留给下一层/详细设计 | 不改变状态、错误和字段语义 |
| 是否增加新的远端状态值 | 不在本层决定；新增值必须由上游契约先定义 | 防止 presenter 私自扩展父契约 |
| 父层/当前 PRD 冲突 | 未发现 | 无 `parent-change-request.md` |
