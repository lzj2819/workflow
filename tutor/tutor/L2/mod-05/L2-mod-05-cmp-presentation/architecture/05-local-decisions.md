# 05 Local Decisions — L2 / CMP-PRESENTATION

> 决策按稳定 ID 排序。`return_to_parent` 为 0；本包没有需要改变父边界、父契约、技术或部署的选择。

## 1. 本层决定（decide_now）

### LCD-PRES-001：生成流程的局部编排归属

- 来源：CT-009、M05-FLOW-004、`REQ-DD002`。
- 备选：
  - (a) **由 `CMP-PRES-GENERATION-COORDINATOR` 统一编排**（采用）：确保资格判定、区块装配、快照写入和响应返回保持父顺序。
  - (b) 由 Snapshot Store 兼任编排：状态所有者会混入业务规则，扩大持久化组件职责。
  - (c) 由 Output Adapter 反向驱动：响应边界会拥有业务判定，无法清晰保持 NO_AVAILABLE_SUBMISSION。
- 后果：CT-009 只有一个本层入口；其余 child 通过 PRES-IC-01~04 协作，不引入通用 service 层。

### LCD-PRES-002：缺失标记与资格判定分离

- 来源：D-AC-REQ-010-01 boundary/exception、P-生成资格、P-MISSING-MARKS-VISIBLE。
- 备选：
  - (a) **同一 child `CMP-PRES-MISSING-MARKS` 内部先判资格、再产出缺失标记**（采用）：保持“缺失可展示”与“无可用提交拒绝”的规则在同一语义边界内。
  - (b) 由 Block Assembler 隐式判断：可能在装配过程中产生部分结果，弱化整体拒绝不变量。
  - (c) 由 UI 判定：将服务端业务资格错误地下放到浏览器。
- 后果：PRES-IC-01 输出纯派生结果；资格失败在持久化前结束，缺失不会被静默过滤。

### LCD-PRES-003：PresentationView 与幂等记录的状态所有者

- 来源：L1 ST-PRESENTATION-VIEW、ST-IDEMPOTENCY-PRESENTATION、父 03 本地事务边界。
- 备选：
  - (a) **由 `CMP-PRES-SNAPSHOT-STORE` 同一事务拥有两者**（采用）：保证 `presentation_id`、快照和幂等查找不漂移。
  - (b) 分给 Coordinator 与独立存储组件：产生两个写方和跨 child 一致性缺口。
  - (c) 由 Output Adapter 保存响应缓存：违反快照与响应边界，且无法满足父删除语义。
- 后果：所有生成成功必须经 PRES-IC-03；读模型只作为输入，不成为快照写方。

### LCD-PRES-004：CT-009 响应与具体渲染解耦

- 来源：父 LCD-008、当前 PRD “可在教师网页端打开”、CT-009 `blocks[]`。
- 备选：
  - (a) **本层只固定 `presentation_id + blocks[]` 的稳定响应，由 `CMP-PRES-OUTPUT-ADAPTER` 继续细化网页/导出格式**（采用）。
  - (b) 本层直接选定 HTML/SPA/文件导出技术：会把父层 defer 项提前决定，并可能越过 CMP-TEACHER-UI 边界。
  - (c) 让 MOD-04 输出渲染产物：改变 CT-005/兄弟职责，必须 return_to_parent。
- 后果：当前包可完成 CT-009 架构闭合；具体格式作为 `defer_to_next_level`，触发目标明确。

### LCD-PRES-005：删除后的展示快照擦除入口

- 来源：父 LCD-005、CT-012 自消费、ST-PRESENTATION-VIEW 生命周期。
- 备选：
  - (a) **由父 `CMP-READMODEL-PROJECTOR` 通过 PRES-IC-05 通知 Snapshot Store，按批次幂等擦除内容**（采用）：不转移 CT-012 ownership，且可让重放守卫复用已清除集合。
  - (b) 由 MOD-02 直接调用本层：跨兄弟引入未声明契约，违反数据所有权。
  - (c) 保留快照本体：删除后重放可能复活，且不满足父保留治理语义。
- 后果：PRES-IC-05 是当前节点内部契约；审计与材料清除仍归父/兄弟所有者，展示快照仅做内容级擦除。

## 2. 继承决策（inherited-fixed）

- `KD-002`：DU-2 共部署、共享父数据库与 Outbox；本层不创建服务/容器/消息平台。
- `KD-003`：基础级监控、日志最小化、加密与备份；本层不记录材料内容。
- `KD-005`：`/api/v1` 与写/生成幂等键；CT-009 的幂等键含义不可改。
- `LCD-004`：展示视图从教师读模型装配，不直接跨模块读取 MOD-02/MOD-04。
- `LCD-005`：删除后擦除展示内容并设置重放守卫，不使已删数据复活。

## 3. 下一层委托（defer_to_next_level）

| decision_id | deferred choice | exact target | trigger | inherited reason |
|---|---|---|---|---|
| LCD-PRES-006 | 具体网页渲染、导出格式、媒体布局和格式版本 | `CMP-PRES-OUTPUT-ADAPTER` | 启动该 child 的下一层细化 | 父 LCD-008；本层已固定 CT-009 blocks 兼容边界 |

## 4. 实现细节（implementation_detail）

- 读模型查询的表结构、索引与数据库产品。
- 幂等键的具体编码、过期清理实现和快照物理存储布局。
- 内部事件/端口的进程内传递机制，只要求可追溯、可重放和事务语义。
- missing_marks 的具体展示文案与本地化资源格式，只要不隐藏缺口且不改变 CT-009 语义。

## 5. 决策队列结果与禁止项

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-PRES-001 | L1 CT-009/F4-1 | CT-009 | CMP-PRES-GENERATION-COORDINATOR | 需要本层唯一编排入口 | decide_now | — |
| LCD-PRES-002 | L2 D-AC-REQ-010-01 | D-AC-REQ-010-01 | CMP-PRES-MISSING-MARKS | 需要同时满足整体拒绝与缺失可见 | decide_now | — |
| LCD-PRES-003 | L1 03-state-and-data.md | ST-PRESENTATION-VIEW/ST-IDEMPOTENCY-PRESENTATION | CMP-PRES-SNAPSHOT-STORE | 需要本层状态单写方 | decide_now | — |
| LCD-PRES-004 | L1 05-local-decisions.md | LCD-008 | CMP-PRES-OUTPUT-ADAPTER | 需要界定 blocks 与具体渲染的边界 | decide_now | CMP-PRES-OUTPUT-ADAPTER |
| LCD-PRES-005 | L1 05-local-decisions.md | LCD-005 | CMP-PRES-SNAPSHOT-STORE | 需要定义 CT-012 自消费到快照擦除的内部端口 | decide_now | — |
| LCD-PRES-006 | L1 05-local-decisions.md | LCD-008 | CMP-PRES-OUTPUT-ADAPTER | 具体渲染格式可独立演进且不影响当前 CT-009 | defer_to_next_level | CMP-PRES-OUTPUT-ADAPTER |

父级专属事项（改动 CT-009、M05-IC-02 owner/字段/错误/版本、PresentationView 跨节点所有权、DU-2/数据库/Outbox）均禁止在本层决定；本轮没有 `return_to_parent`。
