# 01 Design Context — 设计上下文（L2 / CMP-REVIEW-QUERY）

## 1. 已解析输入与预检证据

| 必需输入 | 解析值 | 状态 |
|---|---|---|
| `parent_architecture` | `architecture/L1/L1-mod-05` | 已读；递归子架构包，根存在 `architecture-manifest.yaml` |
| `target_node_id` | `CMP-REVIEW-QUERY` | 唯一匹配；证据记录于 manifest，且被父 decomposition、handoff、CT-007 binding 交叉确认 |
| `current_prd` | `prd/L2-PRD/mod-05/L2-mod-05-cmp-review-query/prd.md` | 已读；schema 2.0，status complete，`REQ-DD001 -> REQ-D001` |
| `output_dir` | `architecture/L2/mod-05/L2-mod-05-cmp-review-query` | 写入前为空，`mode=new` 安全，不覆盖既有包 |
| `mode` | `new` | 本次创建新递归子包 |

当前 L2 PRD 的「系统边界/外部依赖/明确约束/架构决策」仍为待补充占位符，因此本层不擅自决定外部边界；所有边界由 L1 CMP-REVIEW-QUERY 与其父契约继承。

## 2. 父边界快照

### 2.1 身份、职责与排除项（inherited-fixed）

- **身份**：MOD-05 teacher-web 内的查询读侧，直接 child_id 为 `CMP-REVIEW-QUERY`。
- **职责**：在 `CMP-ACCESS-GATE` 已完成认证和课程范围授权后，装配 CT-007 的课程/小组/学生/提交详情只读响应；输出材料引用、处理状态、原始等级、五维依据、建议、批注、最终等级、失败原因、重试结果和 `deletion_batches[]`。
- **不拥有状态**：父包明确该节点为无状态读侧；`ST-READ-MODEL` 由 `CMP-READMODEL-PROJECTOR` 写入，`ST-DELETION-BATCH` 由 `CMP-RETENTION-GOVERNANCE` 写入。
- **排除项**：不做认证授权、不执行课程归属校验、不消费事件、不写 ReviewRecord/PresentationView/DeletionBatch、不装配展示视图、不引入缓存/搜索/新运行时边界。

### 2.2 父契约与直接边界（inherited-fixed / inherited-refinable）

| 项目 | 继承内容 | L2 行为 |
|---|---|---|
| CT-007 | `GET /api/v1/teacher/courses/...`、只读、≤10 秒、完整出参、错误码 | 由 `CMP-RQ-QUERY-FACADE` 组织，内部 child 只实现装配，不改变外部语义 |
| M05-IC-02 | 输入查询选择条件；输出教师读模型字段集；Owner=RMP | 由 Scope/Submission/Outcome 子节点消费；只读、天然幂等 |
| M05-IC-06 | 输入批次/提交选择；输出批次状态、范围、排除项、已清除集合；Owner=RG | 由 Retention View Adapter 消费；读取失败整体失败，不返回缺失批次字段 |
| ST-READ-MODEL | 派生、秒级最终一致、可重放、不允许删除后复活 | 只读；不缓存、不重建、不改变字段所有权 |
| ST-DELETION-BATCH | `deletion_batches[]` 的唯一写方在 RG，审计记录永久 | 只读；不计算、不修改、不隐藏批次 |
| DU-2 / KD-002/003/005 | 共部署、共享数据库/Outbox、基础运维、`/api/v1` 与教师会话/写幂等 | 本节点不新增部署、存储、平台或公共边界 |

### 2.3 当前 PRD 需求分配

| 需求 | 分类 | 追踪来源 | 本节点处理 |
|---|---|---|---|
| REQ-DD001 | allocated | `requirement_id`；`REQ-D001`；`D-AC-REQ-009-01`；父 `REQ-009/FR-009` | 覆盖课程/小组/学生/提交详情、评分字段、失败结果和教师可观察查询响应 |
| AC-REQ-009-01 | inherited acceptance | 父 acceptance contract | 只实现读取/装配部分；批注保存和最终等级调整由兄弟 `CMP-REVIEW-COMMAND` 提供 |
| NFR-001 | inherited | 父 NFR-001 / `AC-NFR-001-01` | 查询侧遵守约 100 名学生、20–50 个小组规模与 ≤10 秒响应约束 |
| REQ-011 缺失标记 | inherited support | 父 CT-006 `missing_items[]` 与读模型派生 | 只呈现读模型已有缺失标记，不取得 MOD-02 材料所有权 |
| NFR-004 保留删除 | out-of-scope except read | 父 `AC-NFR-004-01`；治理归 RG | 仅读取 `deletion_batches[]` 与已清除事实，不实现删除治理 |

### 2.4 局部驱动与阻塞缺口

- **D-RQ-01 完整响应**：CT-007 的 `deletion_batches[]`、失败字段与常规字段均为响应契约的一部分，不能按调用路径省略。
- **D-RQ-02 结果真实性**：`scoring_failed` 时只能展示 `failure_reason` 与 `retry_record`，不得用空值推导出虚假等级，也不得从查询侧临时推导通知。
- **D-RQ-03 只读隔离**：查询装配与 RMP 投影写入分离，任何查询分支不产生业务副作用。
- **D-RQ-04 最终一致可见**：读模型短暂落后可被接受，但不能以旧缓存或缺字段降级掩盖读取失败。
- **阻塞缺口**：当前没有需要改变父职责、父契约、数据所有权、部署或技术决策的事项，因此不创建 `parent-change-request.md`。

## 3. 可复用能力、拟创建文件与验证方式

| 项目 | 结论 |
|---|---|
| 可复用父能力 | CMP-ACCESS-GATE 的授权后路由、RMP 的 ST-READ-MODEL 投影、RG 的 ST-DELETION-BATCH 读端口、父层 CT-007 字段与合法流 |
| 本层拟创建 | 本目录七个架构文件；五个内部 child 仅在本节点内生效 |
| 不创建 | 代码、测试、数据库 schema、部署清单、公共 API、缓存/搜索平台 |
| 上游影响 | 无；继续接受 GATE → QUERY 的 CT-007 绑定 |
| 下游影响 | 仅在本节点内部由 Facade 调用 Scope/Submission/Outcome/Retention Adapter；对外仍返回 CT-007 |
| 交付验证 | 文件/ID/YAML 检查、需求追踪检查、父契约逐字段比对、所有权检查、合法流检查、决策队列检查 |

## 4. C1-C6 映射

| 映射 | 本层落点 |
|---|---|
| C1 | CMP-REVIEW-QUERY → 五个稳定 child_id |
| C2 | 无持久化状态；只读消费 ST-READ-MODEL/ST-DELETION-BATCH，所有权保留在父级支撑组件 |
| C3 | CT-007 入口 → Query Facade → Scope/Submission/Outcome/Retention → 完整响应；失败流终止于父错误码或可重试状态 |
| C4 | CT-007 由 Facade 暴露；M05-IC-02 由 Scope/Submission/Outcome 消费；M05-IC-06 由 Retention Adapter 消费 |
| C5 | 只通过已委托的 M05-IC-02/M05-IC-06 读取端口，不重设计 RMP/RG/MOD-02/MOD-03 |
| C6 | 显式失败结果、完整字段和无副作用由 Outcome/Facade 的局部策略实现，不引入新平台能力 |

## 5. 验证责任与场景路由

验证报告中的 SCENARIO-002/003 同时覆盖查询观察与复核写侧语义，不能由本节点单独模拟为查询组件的写操作。本层采用以下责任路由：

| 场景 | 业务断言 | 权威责任组件/契约 | 本节点的验证范围 |
|---|---|---|---|
| SCENARIO-001 | 教师查看提交详情及已有评分信息 | `CMP-REVIEW-QUERY` / CT-007 / M05-IC-02 | 验证已授权查询响应字段完整 |
| SCENARIO-002 | 保存批注和调整后的等级 | `CMP-REVIEW-COMMAND` / CT-008 / ReviewRecord；提交后由 M05-IC-05 投影到 M05-IC-02 | 仅验证查询侧能读取已投影结果；不新增 Query→Command 写调用 |
| SCENARIO-003 | 原始等级、最终等级、操作者和时间留痕 | `CMP-REVIEW-COMMAND` / ReviewRecord；读侧经 RMP 投影 | 不验证持久化写入；只验证 CT-007 对已存在读模型事实的展示 |
| SCENARIO-004 | 失败原因和重试结果可见且不伪造等级 | `CMP-REVIEW-QUERY` / CT-007 / M05-IC-02 | 验证 `scoring_failed` 分支 |
| SCENARIO-005 | 无权限读取被拒绝并留痕 | `CMP-ACCESS-GATE` / CT-007 | 验证 GATE 终止，本层不重复授权 |

该路由是验证范围澄清，不改变父契约、状态所有权或部署边界；不创建 `parent-change-request.md`。

## 6. 父边界锁定声明

本层所有 child 都位于 `CMP-REVIEW-QUERY` 内部；不改变兄弟 `CMP-REVIEW-COMMAND`、`CMP-PRESENTATION`、`CMP-TEACHER-UI` 或内部支撑组件的职责。任何新增查询字段、分页/导出能力、授权语义、跨模块同步读取或持久化写入，都必须先回到父层审查。
