# 05 Local Decisions — CMP-MATERIAL-COLLECTOR（L2）

## 1. 本层决策

### LCD-L2-MC-001：按责任与状态拆分三个 child

- **来源**：当前 PRD 机会窗口；父 `02` 的单一材料收集器职责。
- **问题**：目录扫描、过滤预算、Manifest schema 是否放在一个内部节点，还是按职责拆分？
- **方案比较**：
  1. **选定：扫描器 + 过滤策略 + 清单构建器**。每个 child 具有单一状态/变更原因，能分别细化目录访问、策略和 schema。
  2. 单一 `MaterialCollectorCore`。结构简单，但文件系统、规则和清单 schema 的变化相互耦合，难以独立递归细化。
  3. 按三层 Controller/Service/Repository 拆分。层次通用但不能表达类别、预算和状态所有权，弃用。
- **后果**：新增三个稳定 `child_id`；目标组件仍是唯一父所有者，无独立部署边界。
- **分类**：`decide_now`。

### LCD-L2-MC-002：先白名单过滤，再累计预算

- **来源**：`KD-004`、`LCD-003`、当前 PRD 的白名单与 500MB 预检。
- **问题**：预算应包含被白名单排除的文件，还是只计算可上传候选？
- **方案比较**：
  1. **选定：只计算白名单通过项**。预算与最终材料集合一致，诊断可解释；被排除文件不会造成虚假超限。
  2. 先统计目录全部文件。实现简单，但可能提示学生精简不可上传文件，产生错误引导。
  3. 交给服务端统一统计。失去客户端预检价值，违反父层 LCD-003 的体验目标。
- **后果**：`FilteredMaterialSet.total_accepted_bytes` 是客户端预检口径；服务端仍是最终权威。
- **分类**：`decide_now`。

### LCD-L2-MC-003：空类别保留，不在本层阻断

- **来源**：父 `02/03`、`D-AC-REQ-003-01` 的空目录边界。
- **决策**：目录存在但为空时保留 code/screenshot/result 类别，写入 `missing_categories[]`，不生成本地 rejected；服务端负责最终缺失标记。
- **分类**：`inherited-fixed` 的本层实现。

### LCD-L2-MC-004：预算超限只告警，不替代服务端拒绝

- **来源**：父 `LCD-003`。
- **决策**：超过 500MB 时返回 `over_budget=true` 和警告，允许上游决定是否继续；本层不改写 CT-001 的 `PAYLOAD_TOO_LARGE` 语义。
- **分类**：`inherited-fixed` 的本层实现。

## 2. 委托下一层

| Decision ID | 事项 | 委托目标 | 触发条件 | 分类 |
|---|---|---|---|---|
| LCD-L2-MC-005 | 目录递归深度、符号链接、忽略目录和文件排序策略 | `CMP-MC-DIRECTORY-SCANNER` | 进入 L3 细化，需要在不改变三类类别映射的前提下确定遍历行为 | `defer_to_next_level` |
| LCD-L2-MC-006 | 白名单的具体扩展名/MIME 表与平台差异适配 | `CMP-MC-FILTER-POLICY` | 进入 L3 细化，需要与父 KD-004 允许集合逐项对齐 | `defer_to_next_level` |
| LCD-L2-MC-007 | Manifest 字段编码、路径规范化和诊断文案格式 | `CMP-MC-MANIFEST-BUILDER` | 进入 L3 细化，需要保持父 `material_chunks[]` 兼容 | `defer_to_next_level` |

## 3. 实现细节（不在本层做架构决定）

| 事项 | 依据 |
|---|---|
| 本机持久化采用文件还是嵌入式 KV | 父 `A-007` 已委托详细设计 |
| 具体文件读取库、线程模型和缓冲区大小 | implementation_detail；不改变组件边界 |
| MIME 检测库的具体调用方式 | 由 `CMP-MC-FILTER-POLICY` L3 细化 |

## 4. 继承决策与父层禁止项

| 父决策/约束 | 本层处理 |
|---|---|
| `KD-003` HTTPS | 本层无网络；不引入明文通道 |
| `KD-004` 500MB/白名单 | 本层只做客户端预检；服务端权威不变 |
| `KD-005` UUID/分片续传 | 本层接收并保留任务 UUID，不生成新的公共幂等键 |
| `A-007` 本地持久化 | 不在本层选择机制 |
| DU-1 student-plugin | 不创建独立服务、容器、数据库或部署单元 |

## 5. 决策队列结论

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Classification | Follow-up Target |
|---|---|---|---|---|---|
| LCD-L2-MC-001 | 当前 PRD / 父 `02` | `REQ-DD004` / `REQ-D004` | 三个 child | `decide_now`（已处理） | — |
| LCD-L2-MC-002 | 父 `05` / 当前 PRD | `KD-004` / `LCD-003` | `CMP-MC-FILTER-POLICY` | `decide_now`（已处理） | — |
| LCD-L2-MC-003 | 父 `03` / 当前验收边界 | 空材料目录 | `CMP-MC-MANIFEST-BUILDER` | `inherited-fixed` | — |
| LCD-L2-MC-004 | 父 `05` | `LCD-003` | `CMP-MC-FILTER-POLICY` | `inherited-fixed` | — |
| LCD-L2-MC-005 | 当前 PRD 未规定 | 目录遍历细节 | `CMP-MC-DIRECTORY-SCANNER` | `defer_to_next_level` | `CMP-MC-DIRECTORY-SCANNER` |
| LCD-L2-MC-006 | 当前 PRD 未规定 | 白名单表细节 | `CMP-MC-FILTER-POLICY` | `defer_to_next_level` | `CMP-MC-FILTER-POLICY` |
| LCD-L2-MC-007 | 当前 PRD 未规定 | Manifest 编码细节 | `CMP-MC-MANIFEST-BUILDER` | `defer_to_next_level` | `CMP-MC-MANIFEST-BUILDER` |

**结论**：无遗留 `decide_now`，无 `return_to_parent`。本层未发现需要改变父责任、跨模块契约、数据所有权、技术栈、部署边界或祖先不变量的决定。
