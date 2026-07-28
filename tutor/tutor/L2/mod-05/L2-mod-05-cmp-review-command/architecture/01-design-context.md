# 01 Design Context — 设计上下文（L2 / CMP-REVIEW-COMMAND）

## 1. 输入绑定与预检

| 必需输入 | 解析值 | 结果 |
|---|---|---|
| `parent_architecture` | `architecture/L1/L1-mod-05` | 可读；根存在 `architecture-manifest.yaml`，识别为递归子架构包 |
| `target_node_id` | `CMP-REVIEW-COMMAND` | 在父 manifest、分解表、handoff 中各唯一命中 |
| `current_prd` | `prd/L2-PRD/mod-05/L2-mod-05-cmp-review-command/prd.md` | 已读；status=complete；REQ-DD001 映射 REQ-D001 |
| `output_dir` | `architecture/L2/mod-05/L2-mod-05-cmp-review-command` | 写入前为空；`mode=new` 安全 |

当前 PRD 的系统边界、外部依赖、明确约束字段为占位内容。本包不从占位内容推导新边界，而是继承 L1 父包已经锁定的 CT-008、ReviewRecord 所有权、DU-2 部署和 LCD-003/LCD-009 约束。

## 2. 父边界快照

### 2.1 身份、职责和排除项

- **父节点**：`CMP-REVIEW-COMMAND`，L1 / MOD-05 内部直接 child。
- **本层职责**：实现 CT-008 教师批注与最终等级调整；经 M05-IC-01 接收评分完成后的 ReviewRecord 创建；经 M05-IC-05 将已提交的批注/等级调整通知投影组件。
- **父层排除**：不实现教师查询、展示视图、UI、课程范围授权、评分执行、材料访问、保留治理和 MOD-02 清除。
- **清除入口**：ReviewRecord 内容清除只接受父级 `CMP-RETENTION-GOVERNANCE` 通过 `M05-IC-07` 发出的内部命令；本节点不计算保留期、不创建删除批次、不写删除审计。
- **父级状态**：ReviewRecord（含 Annotation、FinalGrade、GradeAdjustmentRecord）由本节点拥有；教师读模型由 CMP-READMODEL-PROJECTOR 拥有。

### 2.2 继承分类

| 项目 | 分类 | 本层处理 |
|---|---|---|
| CT-008 标识、路径、字段、错误码、幂等与版本 | inherited-fixed | 逐字段实现，不扩展外部语义 |
| M05-IC-01 创建 ReviewRecord | inherited-refinable | 在本节点内细化幂等入口和聚合写入顺序 |
| M05-IC-05 本地事件 | inherited-refinable | 在 ReviewRecord 事务提交后发出，保持字段和去重语义 |
| ReviewRecord 单写方原则 | inherited-fixed | 所有创建、批注、等级调整都经本节点聚合写入 |
| P-禁伪造等级 | inherited-fixed | scoring_failed 且无原始等级时返回 NO_ORIGINAL_GRADE |
| LCD-003 创建路径 | inherited-fixed | CMP-READMODEL-PROJECTOR 只能通过 M05-IC-01 请求创建 |
| LCD-009 调整理由 | delegated | 本层采用可选字段，不设必填，不改变 CT-008 必填字段 |
| KD-002/KD-003/KD-005 与 DU-2 | inherited-fixed | 不新增运行时、存储或部署边界 |

### 2.3 父契约边界

| 契约 | 本节点角色 | 固定语义 |
|---|---|---|
| CT-008 | Provider 的内部实现节点 | `/api/v1/teacher/submissions/{id}/review`；`request_id` 幂等；annotation/final_grade 至少一项；NO_ORIGINAL_GRADE；并发后写为准；返回 review_record |
| M05-IC-01 | Consumer/command target | 输入 submission_id、original_grade、dimension_rationales、scored_at；按 submission_id 幂等创建 ReviewRecord |
| M05-IC-05 | Provider | 输入 submission_id、annotation_excerpt、operator、updated_at、adjustment_id；输出 AnnotationSaved/GradeAdjusted；按 adjustment_id 或 submission_id+updated_at 去重 |
| M05-IC-07 | Consumer/command target | 输入 batch_id、submission_ids、scope、operator、executed_at、audit_record_id、v；输出 purged_submission_ids、failed_items、purged_at、v；按 batch_id+submission_id 去重，只清除 ReviewRecord 内容 |
| CT-005 | 间接触发来源 | 由 CMP-READMODEL-PROJECTOR 消费；本节点不直接消费父事件，不改变 scoring_failed 的无记录语义 |

### 2.4 相关父流程与直接边界

- `DF-1` 步骤 11：CT-005 outcome=scored → RMP → M05-IC-01 → 本节点创建 ReviewRecord；步骤 12 的教师查看属于 CMP-REVIEW-QUERY/UI。
- `F3-2/F3-3`：教师通过 UI/GATE 进入 CT-008；本节点执行幂等、完整性校验、事务写入并返回 ReviewRecord。
- `DF-2` 步骤 6：评分失败不产生原始等级；本节点不得接受以 CT-008 伪造最终等级。
- `M05-IC-05`：本节点事务提交后向 RMP 提供局部事件；事件不跨 MOD-05。
- `M05-IC-07`：父级删除批次审计提交并发布 CT-012 后，向本节点发送 ReviewRecord 内容清除命令；失败项由父级按批次重试。
- 上游：CMP-ACCESS-GATE、CMP-READMODEL-PROJECTOR。下游：CMP-READMODEL-PROJECTOR；教师 UI 仅通过 CT-008 访问。

### 2.5 数据与部署约束

- `ST-REVIEW-RECORD` 的原始等级复制值不可变；最终等级未调整时等于原始等级；每次调整保留操作者、时间、调整 ID，可选理由。
- `ST-IDEMPOTENCY-REVIEW` 与业务写入同事务；重复 request_id 返回首次 ReviewRecord，不重复产生副作用。
- `M05-IC-07` 清除与 Writer 的 ReviewRecord 内容状态、清除幂等记录同一事务；删除批次和删除审计仍归父级 Retention-Governance。
- 本地事务只覆盖 ReviewRecord、GradeAdjustmentRecord、Annotation、幂等记录和可追溯的模块内事件记录；不得转移读模型所有权。
- 运行于 DU-2 course-app，共享父级数据库/Outbox 能力；不引入消息中间件、缓存、搜索引擎或新服务。

## 3. 当前 PRD 需求分配

| 当前需求 | 分类 | 父层来源 | 本层分配 | 说明 |
|---|---|---|---|---|
| REQ-DD001 | allocated | REQ-D001 → REQ-009；D-AC-REQ-009-01 → AC-REQ-009-01 | `CMP-RC-REVIEW-RECORD-WRITER`、`CMP-RC-REVIEW-INTEGRITY-POLICY`、`CMP-RC-REVIEW-IDEMPOTENCY-GUARD` | 仅承接写侧：保存批注、调整最终等级、ReviewRecord 留痕和禁伪造；查询/UI/授权属于兄弟或支撑节点 |
| D-AC-REQ-009-01 | allocated | `parent_acceptance_contract: AC-REQ-009-01` | 三个 child 协同实现 | 保存批注/等级调整、保留原始/最终/操作者/时间、失败时不伪造等级 |
| “教师打开详情并展示数据” | out-of-scope | REQ-D001 的读侧 | CMP-REVIEW-QUERY/CMP-TEACHER-UI | 本目标只实现写侧，不重复设计兄弟内部 |
| AUTH_INVALID/FORBIDDEN 与 AccessDeniedLogged | inherited | CT-008、FR-009 | CMP-ACCESS-GATE | 本层消费已授权请求，不重实现授权网关 |

分配结论：当前 PRD 没有要求修改父契约、父数据所有权、依赖方向、技术栈或部署边界；无需 `parent-change-request.md`。

## 3.1 验证场景边界（不改变测试文件）

当前 Gherkin 将 REQ-DD001 的读、写、展示和访问拒绝行为放在同一验收集合中；本节点只声明其中的写侧参与，验证器不得把所有场景都当作 Command 入口：

| 场景职责 | 归属流 | 本节点角色 |
|---|---|---|
| 提交详情展示、材料引用、等级入口 | CT-007：UI → ACCESS-GATE → REVIEW-QUERY | out-of-scope；只接收 Query 的写侧后续 CT-008 请求 |
| 保存批注和调整最终等级 | CT-008：UI → ACCESS-GATE → REVIEW-COMMAND | in-scope；由 GUARD → POLICY → WRITER 完成 |
| 保留原始/最终等级、操作者、时间 | CT-008 写入 ReviewRecord；CT-007 查询展示 | in-scope 写入；读取由 QUERY/UI 完成 |
| 评分失败原因和重试结果展示 | CT-005/CT-007：RMP 投影后由 Query/UI 展示；CT-008 仅拒绝伪造等级 | partial；本节点只负责 NO_ORIGINAL_GRADE |
| 无权限读取和 AccessDeniedLogged | CT-007：UI → ACCESS-GATE | out-of-scope；由 ACCESS-GATE 决定并审计 |

## 4. 局部驱动

1. **聚合单写方**：ReviewRecord 的创建和所有教师写入都经过同一聚合写入 child。
2. **失败透明**：评分失败没有原始等级时，写侧返回 NO_ORIGINAL_GRADE，不填充任何替代等级。
3. **幂等优先**：request_id 和 submission_id 两种入口键必须在同一事务内收敛重复请求。
4. **留痕完整**：原始等级、最终等级、操作者、时间和调整记录必须可追溯；调整理由可选。
5. **内部事件可重放**：M05-IC-05 只能在业务事务提交后产生，失败时可按 adjustment_id 重放，不改变 CT-008 外部响应。

## 5. 预检、复用能力与交接方法

- **可复用能力**：父级 ReviewRecord 聚合语义、CT-008 API 适配、M05-IC-01/M05-IC-05 端口、DU-2 事务/Outbox 能力。
- **阻塞缺口**：无；PRD 的占位架构输入不造成不同的本层架构，因为父包已锁定边界。
- **拟创建文件**：严格七文件，见 manifest 与 child-handoff。
- **上游/下游影响**：在本节点展开 CT-008、M05-IC-01、M05-IC-05 和 M05-IC-07；CT-008/M05-IC-01/M05-IC-05 外部字段、错误码、版本和所有者不变，M05-IC-07 只增加父级内部清除协作。
- **验证方法**：检查输入/唯一匹配、child 追踪、C1-C6、父契约逐字段不变、状态所有权、稳定排序、YAML 解析和决策队列。

## 6. 假设与开放项

| ID | 类型 | 内容 | 处置 |
|---|---|---|---|
| Q-01 | 假设 | CT-008 到达本节点前已由 ACCESS-GATE 完成会话和课程范围授权 | 本层只验证请求上下文已授权；授权失败仍由父网关按原语义处理 |
| Q-02 | 产品开放项 | GradeAdjustmentRecord 的理由是否强制填写 | 按 LCD-009 采用可选、不设必填；若产品要求新增必填字段，必须回父层修改 CT-008 |
| Q-03 | 非阻塞 | PRD dependency_refs 包含 QUERY/UI/PRESENTATION | 只保留父流程中的合法调用关系，不新增与这些节点的内部依赖 |
