# 01 Design Context — L2 / CMP-PRESENTATION

## 1. 输入绑定与父边界快照

| 项目 | 已解析值 |
|---|---|
| `parent_architecture` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-05` |
| `target_node_id` | `CMP-PRESENTATION`，在父 manifest、decomposition、handoff 中唯一匹配 |
| `current_prd` | `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-05/L2-mod-05-cmp-presentation/prd.md` |
| `output_dir` | `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L2/mod-05/L2-mod-05-cmp-presentation` |
| `mode` | `new`；目录写入前为空 |

父节点是 `MOD-05 / teacher-web` 内的直接 child，运行在 `DU-2 course-app`，不是独立服务或部署单元。本包只细化 CMP-PRESENTATION 内部，不重设计兄弟节点。

### 1.1 继承的固定边界

- 对外唯一职责是 CT-009 展示视图生成：教师提交 `group_ids[]`，返回 `presentation_id` 与 `blocks[]`，缺失材料使用 `missing_marks` 显式表达，无可用提交返回 `NO_AVAILABLE_SUBMISSION`。
- PresentationView 与 ST-IDEMPOTENCY-PRESENTATION 仍由 CMP-PRESENTATION 独占；快照写入、同参数再生成、superseded 与 purged 生命周期保持父层定义。
- 生成时只能通过 M05-IC-02 读取 `ST-READ-MODEL`；不得同步读取 MOD-02/MOD-04 源数据，不得把教师读模型写入职责移入本节点。
- `/api/v1`、CT-009 字段、错误语义、幂等键（教师 + 小组集合 + 时间窗）、版本与 CT-009 父副作用全部 inherited-fixed。
- 沿用 KD-002（共部署 + Outbox）、KD-003（基础级运维）、KD-005（教师会话与幂等键）以及父层关系型数据库/事务/备份约束。

### 1.2 可细化与委托边界

- 可在本层细化：选择小组的资格判定、缺失标记规则、GroupSection/ProcessSummary/评分/批注的区块装配、快照事务与幂等实现、父 CT-009 的内部协作。
- `LCD-004` 已固定展示视图从教师读模型装配；不能改成跨模块实时读取或由 MOD-04 预生成。
- `LCD-008` 已委托到本节点；本包只固定稳定的 `blocks[]` 响应形态，具体网页渲染和导出格式继续委托给 `CMP-PRES-OUTPUT-ADAPTER` 的下一层细化。

## 2. 当前 PRD 需求分配

当前 L2 PRD 的功能/NFR 表为空，但 frontmatter 明确 `inheritance_complete: true`、`release_scope_frozen: true`，并通过 `requirement_id_mapping` 与 `REQ-DD002`/D-AC-REQ-010-01 提供本层需求真源。因此不新造 REQ/NFR。

| 当前 PRD 项 | 分类 | 父层/本层追踪 | 本层处理 |
|---|---|---|---|
| `REQ-DD002`：生成教师可打开的展示视图 | allocated | 父 `REQ-D002`；CT-009；F4-1 | 由生成编排、资格判定、区块装配、快照存储和响应适配共同实现 |
| `D-AC-REQ-010-01`：小组与选择一致，包含项目结果/过程摘要/评分/批注，缺材料显式标记 | allocated acceptance | `REQ-DD002`；父 `D-AC-REQ-010-01`；CT-009 | 由 `CMP-PRES-MISSING-MARKS` 与 `CMP-PRES-BLOCK-ASSEMBLER` 落地；不隐藏缺口 |
| `D-AC-REQ-010-01.exceptions`：无可用提交阻止生成并说明原因 | inherited + allocated | 父 CT-009 `NO_AVAILABLE_SUBMISSION`；P-生成资格 | 由 `CMP-PRES-GENERATION-COORDINATOR` + `CMP-PRES-MISSING-MARKS` 判定；不写快照 |
| PRD `系统边界/外部依赖/明确约束/需要人工确认的架构决策` 的待补充占位 | inherited | 父包 boundary_fingerprint、KD-002/003/005、CT-009/M05-IC-02 | 以父包绑定约束为准；不把占位符解释成新增自由度 |

## 3. 局部架构驱动

1. **资格闭合**：任一选定小组无可用提交时整体拒绝，避免产生部分成功的展示快照。
2. **缺失可见**：缺失材料是展示内容，不是过滤条件；必须以稳定的 missing_marks 进入每个 GroupSection。
3. **快照一致**：PresentationView、幂等记录和返回的 `presentation_id`/`blocks[]` 必须在同一父约束允许的本地事务内闭合。
4. **读模型隔离**：本节点是读模型消费者，不成为 CT-005/006 的事件消费者或 ST-READ-MODEL 写方。
5. **格式可演进**：稳定 CT-009 blocks 契约与具体网页/导出渲染解耦，避免 LCD-008 的实现选择污染父 API。

## 4. C1-C6 预览

| 映射 | 本包落点 |
|---|---|
| C1 | CMP-PRESENTATION → 五个稳定内部 child_id，均留在 MOD-05/DU-2 内 |
| C2 | PresentationView 与 ST-IDEMPOTENCY-PRESENTATION → `CMP-PRES-SNAPSHOT-STORE`；缺失判定与装配结果仅为本地瞬时状态 |
| C3 | 父 M05-FLOW-004/F4-1 → 资格判定 → 读模型读取 → 缺失判定 → 区块装配 → 快照写入 → CT-009 响应 |
| C4 | 父 CT-009 由 generation coordinator 作为入口实现；M05-IC-02 仍由父 RMP 提供，内部 child-only ports 不外溢 |
| C5 | 父外部依赖仅是 M05-IC-02 读端口；本层不创建 Adapter/ACL，不改变 RMP 所有权 |
| C6 | 资格闭合、缺失显式化、幂等快照和格式隔离分别落到本地 policy/child，不新增平台能力 |

## 5. 预检、假设与未决项

### 预检结论

- 可复用能力：父 CT-009、M05-IC-02、PresentationView 状态、父幂等和 DU-2 存储边界。
- 阻塞缺口：无；当前 PRD 的空 FR/NFR 表由继承完成标记和父级追踪补足，未允许 materially different 的父架构。
- 上游影响：CMP-ACCESS-GATE 只负责认证/授权并路由到本节点；M05-IC-02 的 owner/字段/失败语义不变。
- 下游影响：CMP-TEACHER-UI 继续消费 CT-009 `presentation_id + blocks[]`；具体网页/导出渲染在下一层处理。
- 交接验证方法：YAML 解析、七文件清单、child/contract/state/decision ID 排序、当前需求追踪、父契约字段不变、无新公共边界、三类运行流完整性检查。

### 假设

- `available submission` 的判定输入已由父读模型投影到 M05-IC-02；本层不重新定义 MOD-02 的提交状态。
- `ProcessSummary` 继续是对评估产出的引用/快照字段，不在本层重新计算评分或过程分析。
- “可在教师网页端打开”由 CT-009 返回 blocks 并交给 CMP-TEACHER-UI 观察；本层不直接承担浏览器渲染。

### 未决项

- `LCD-008` 的具体网页渲染、导出格式、媒体布局和格式版本：分类为 `defer_to_next_level`，目标为 `CMP-PRES-OUTPUT-ADAPTER`。
- 数据库产品、表结构、索引和本地事件传递方式：继承父层 `defer_to_detail_design`/implementation_detail，不在本层决定。

## 6. 兄弟与父边界确认

`CMP-READMODEL-PROJECTOR`、`CMP-ACCESS-GATE`、`CMP-REVIEW-QUERY`、`CMP-TEACHER-UI` 只作为协作者或边界约束被引用；本包没有重设计它们的内部结构。没有状态从 MOD-02/MOD-03/MOD-04、兄弟节点或父支撑组件转移到本层，也没有增加跨模块契约。
