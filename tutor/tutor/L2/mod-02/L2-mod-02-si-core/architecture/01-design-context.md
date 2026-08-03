# 01 Design Context — SI-CORE submission-core L2

> 本包只细化 L1 `MOD-02` 的 `SI-CORE`，不重划 MOD-02 边界、不设计兄弟模块内部。父包是绑定契约；本文件记录本层实际使用的父边界快照、当前 PRD 分配和局部驱动。

## 1. 输入与预检结论

| 项目 | 已解析结果 |
|---|---|
| `parent_architecture` | `architecture/L1/L1-mod-02`，递归子架构包 |
| `target_node_id` | `SI-CORE`，display name `submission-core` |
| `current_prd` | `prd/L2-PRD/mod-02/L2-mod-02-si-core/prd.md`，status `complete`，schema `2.0` |
| `output_dir` | `architecture/L2/mod-02/L2-mod-02-si-core`，生成前不存在，`mode=new` 安全 |
| `parent_prd` | 未读取；L1 包已经提供足够的需求、状态、契约、流程和决策追踪 |
| 目标匹配 | 父 `child-handoff.md`、父 manifest、父 decomposition 唯一匹配 `SI-CORE` |
| 计划文件 | manifest、01~05 五份设计文件、child-handoff，共 7 个 |
| 交接验证 | 静态追踪、契约不变性、状态所有权、ID 排序和边界红线检查 |

当前 PRD 的“系统边界/外部依赖/明确约束/人工决策”仍为待补充占位符。本次不把占位符当作自由授权，而是以父包已锁定的边界、契约、状态、部署和决策作为有效输入；因此没有产生允许多种实质不同子架构的阻塞缺口。

## 2. 父边界快照

### 2.1 节点身份、职责与排除项

- **父节点**：`MOD-02` / `submission-intake`，部署于 `DU-2 course-app`，进程内组件，不独立部署。
- **当前节点**：`SI-CORE` / `submission-core`。
- **职责**：Submission 聚合唯一写入口；维护提交记录、生命周期状态机、材料清单、完整性报告和缺失项标记；在状态、清单、报告和 Outbox 记录之间保持单一本地事务；支撑 CT-002 查询；承接评分结果和清除结果回写。
- **排除**：HTTP/认证/编排归 `SI-API`；上传会话归 `SI-XFER`；文件与配额归 `SI-STORE`；Outbox 投递和入站去重归 `SI-RELAY`；清除批处理归 `SI-PURGE`；评分归 `MOD-04`；教师端和保留治理归 `MOD-05`。

### 2.2 状态与数据所有权

| 父状态/数据 | 当前层继承方式 | 本层边界 |
|---|---|---|
| `ST-01 Submission` | `inherited-fixed` ownership 仍为 SI-CORE | 细化为聚合生命周期语义、材料清单和完整性报告三个局部状态视角；物理提交由事务子节点协调 |
| `ST-03 MaterialFile/CourseQuotaUsage` | `inherited-fixed` ownership 为 SI-STORE | SI-CORE 只保存 `material_ref`、类别、大小和声明信息，不读写文件内容 |
| `ST-04 OutboxRecord` | `inherited-fixed` ownership 为 SI-RELAY | SI-CORE 在同一本地事务内请求写入，不拥有投递状态 |
| `ST-05 InboundEventDedup` | `inherited-fixed` ownership 为 SI-RELAY | SI-CORE 接收已经去重的回写命令，不重新实现去重 |
| `ST-07 PurgeExecution` | `inherited-fixed` ownership 为 SI-PURGE | SI-CORE 只执行单条 Submission 的 `deleted` 守卫和持久化结果 |

### 2.3 父契约与直接边界

| 契约/边界 | 父层语义 | 本层实现位置 |
|---|---|---|
| `IC-SI-04` | Submission 聚合命令/查询，状态机守卫，唯一写入 | `SI-CORE-TX` 接收命令；`SI-CORE-AGG` 执行语义；`SI-CORE-INTEGRITY` 生成清单/报告 |
| `IC-SI-05` | Outbox 事务写入和入站路由 | `SI-CORE-TX` 只调用父层 relay port；投递、去重和外部发送仍由 SI-RELAY |
| `CT-001` | 上传成功后返回提交确认；父模块通过 SI-API 编排 | ConfirmReceived / MarkRejected / MarkUploadFailed 的聚合命令 |
| `CT-002` | 按 `submission_uuid` 只读查询 | `SI-CORE-AGG` 的 query port，经过 `SI-CORE-TX` 暴露一致读边界 |
| `CT-003` | 每次提交重新校验，失败/不可用语义固定 | 只消费 SI-VERIFY 返回的结论，不直接调用 MOD-03 |
| `CT-004` | SubmissionReceived，v=1，任务持久化确认后推进 processing | `SI-CORE-TX` 与聚合/报告完成同事务后写入父 Outbox |
| `CT-005` | scored/scoring_failed 回写，按提交和终态幂等 | SI-RELAY 去重后调用 ApplyScoringOutcome |
| `CT-006` | `received` 或终态 `upload_failed` 的教师端派生事件 | `SI-CORE-TX` 写入父 Outbox；schema、消费者和版本不变 |
| `CT-012/CT-014` | 清除命令入站与结果出站 | SI-PURGE 调用本层 `PurgeSubmission`；CT-014 仍由 SI-PURGE/SI-RELAY 发布 |

### 2.4 继承分类

| 项目 | 分类 | 本层处理 |
|---|---|---|
| 父契约标识、字段、所有者、消费者、版本、失败和幂等语义 | `inherited-fixed` | 原样保留 |
| `Submission` 内部状态守卫与完整性报告实现 | `inherited-refinable` | 只在 SI-CORE 内细化 |
| `LCD-002`：`upload_failed` 也触发 CT-006 | `inherited-fixed` | 由 SI-CORE-TX 固定写 Outbox |
| `LCD-003`：CT-004 任务持久化确认后才 `received→processing` | `inherited-fixed` | 由回写命令调用状态守卫 |
| `KD-002/003/004/005`、DU-2 | `inherited-fixed` | 不重开，不引入新平台或部署边界 |
| 事务协调方式、报告建模方式、读查询实现方式 | `delegated` | 在本层局部决策中落定；字段/索引等细节继续委托下一层 |

## 3. 当前 PRD 需求分配

| 当前需求 | 分类 | 父层追踪 | 分配到本层 | 说明 |
|---|---|---|---|---|
| `REQ-DD001` | `allocated` | `REQ-D001` → `REQ-003`；`D-AC-REQ-003-01` | `SI-CORE-AGG`、`SI-CORE-INTEGRITY`、`SI-CORE-TX` | 保存提交关联信息、清单和报告；校验通过后形成可观察的提交状态 |
| `REQ-DD002` | `allocated` | `REQ-D002` → `REQ-004`；`CT-001`、`KD-004` | `SI-CORE-INTEGRITY`、`SI-CORE-TX` | 按声明类别接收材料元数据，形成 `MaterialEntry[]` 和完整性报告；文件写入仍归 SI-STORE |
| `REQ-DD004` | `allocated` | `REQ-D004` → `REQ-011`；`AC-REQ-003-01` boundary | `SI-CORE-INTEGRITY`、`SI-CORE-AGG`、`SI-CORE-TX` | 缺失项显式标记但不阻塞 `received`、CT-004 或评分推进 |
| `SM-001` | `inherited` | L1 SM-001；`AC-NFR-003-01` | 不新增 owner；为 SI-API 的成功确认提供可查询状态 | 指标采集归 SI-API/基础监控，不能在本层重定义分子、分母或标签 |
| `NFR-002/NFR-003` | `inherited` | L1 NFR-002/NFR-003 | 通过单事务短路径支撑；预算编排归 SI-API | 本层不改变 30 秒/30 并发父约束 |
| HTTP、认证、分片、文件内容、课程名单、评分、教师端、保留期计算 | `out-of-scope` | L1 sibling boundary | 不分配 | 仅作为直接协作约束引用 |

## 4. 本层局部驱动

1. **状态机不可越级**：所有状态变迁必须经过 `SI-CORE-AGG` 守卫；`received` 只有在父层 CT-004 的 `task_persisted` 确认后才推进 `processing`。
2. **完整性不阻断评分**：清单级缺失只生成 `missing_items[]`，不能把空目录解释成拒绝；拒绝只来自父层归属校验失败或不可恢复上传失败。
3. **事务一致性**：`Submission` 状态、`MaterialEntry[]`、`IntegrityReport` 和父 Outbox 写入必须在同一本地事务中提交；不引入分布式事务或事件溯源。
4. **幂等回写**：`submission_uuid`、`submission_id+outcome` 和已删除记录必须保持幂等；重复评分回写和重复清除不可改变终态。
5. **契约适配隔离**：SI-CORE 只接收父层已定义的领域命令和元数据；文件系统、网络、投递和去重通过父层端口完成。

## 5. 可复用能力、开放问题与交接

### 可复用能力

- L1 已确定的 `ST-01` 所有权、INV-1~INV-5、IC-SI-04/05 和 `DU-2` 进程内边界。
- `KD-002` 同事务 Outbox、`KD-003` 加密/备份、`KD-004` 容量约束和 `KD-005` 幂等键语义。
- 父层 CT-004/005/006 的字段、版本、消费者和重试语义。

### 开放问题（不阻塞当前包）

- 数据库产品选型仍遵循父包 `defer_to_detail_design`，本层不决定。
- 具体表/索引/ORM 或事务框架属于下一层实现细节，不改变当前三个子节点边界。
- 报告中缺失项排序、类别规范化和错误码内部映射仍在子节点详细设计时确定；SI-CORE-TX 的操作级输入/输出、错误分支和 next_hop 已在 `04-contracts-and-runtime.md` 固化，不得改变父契约。

### 上下游影响

- **上游**：SI-API、SI-RELAY、SI-PURGE 继续通过 IC-SI-04 语义调用；无需改契约。
- **下游**：SI-STORE 提供材料元数据，SI-RELAY 接收同事务 Outbox 写入；无需转移所有权。
- **兄弟模块**：MOD-04、MOD-05 只通过父层 CT-004/006/014 参与；本包不设计其内部。

### 交接验证方法

检查 manifest 的输入/输出清单、子节点追踪、状态 owner、继承契约不变性、内部契约 ID 排序、运行流覆盖成功/失败/生命周期，以及父边界红线。完成后停在 `ready_for_human_gate`。
