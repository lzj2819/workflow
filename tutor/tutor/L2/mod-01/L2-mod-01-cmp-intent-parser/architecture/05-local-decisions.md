# 05 Local Decisions — CMP-INTENT-PARSER（L2）

本层只处理 `CMP-INTENT-PARSER` 内部的局部选择。L1 的 `LCD-001`、`IC-M01-01` 和部署/边界决策均原样继承。

## 1. 本层已决定（decide_now，按稳定 ID 排序）

### LCD-IP-001：采用“可替换提取 + 确定性闸门”的两阶段策略

- 来源：L1 `LCD-001`、`REQ-DD001`、`D-AC-REQ-001-01`。
- 方案比较：
  1. **选定**：提取器负责候选识别，规范化器负责无损清理，必填闸门负责唯一放行。提取机制可演进，父契约稳定。
  2. 纯关键词模板：确定性高但自然语言覆盖差，且把变化与固定规则耦合。
  3. 外部 NLU 服务：增加网络依赖、隐私边界和离线失败面，违反当前父边界。
- 后果：本层可以替换 `FIELD-EXTRACTOR`，但不能替换或弱化 `REQUIRED-FIELD-GATE` 的 fail-closed 语义。
- 分类：`decide_now`。

### LCD-IP-002：歧义字段按缺项/不确定处理，不猜测放行

- 来源：L1 `IC-M01-01`“无法确定字段时返回 MissingFields”；`INV-1`。
- 方案比较：
  1. **选定**：冲突或低确定性字段进入 `MissingFields`，由学生修正指令。
  2. 选择首个候选：可能把错误姓名/小组送入服务端，破坏验收与归属校验。
  3. 让队列或服务端补判：会让缺项闸门失去确定性并产生不必要网络调用。
- 后果：解析器不承担服务端归属权威；`CMP-PENDING-QUEUE` 只接收明确结果。
- 分类：`decide_now`。

### LCD-IP-003：配置只作为只读上下文，不静默补齐当前指令必填槽位

- 来源：L1 `LCD-001`“以当次指令为准”；`IC-M01-02`；当前 D-AC 边界。
- 方案比较：
  1. **选定**：配置可提供版本/诊断上下文；三个必填槽位必须在当前指令中明确得到。
  2. 配置自动补齐：会把“当前指令缺项”变成隐式成功，削弱 `F1-1`。
  3. 完全禁止读取配置：丢失父层既有配置上下文依赖。
- 后果：配置 owner 不变；指令与配置冲突时指令优先。
- 分类：`decide_now`。

## 2. 委托下一层（defer_to_next_level）

| 决策 ID | 事项 | 委托目标 | 触发条件 |
|---|---|---|---|
| LCD-IP-004 | 宿主 Codex NL 能力、规则库或本地提取策略的具体实现 | `UNIT-INTENT-PARSER-FIELD-EXTRACTOR` 的下一层详细设计 | 需要在不新增外部依赖的前提下替换提取策略 |

## 3. 实现细节（implementation_detail）

| 事项 | 约束 |
|---|---|
| parser 版本号、日志字段和本地调用预算 | 只影响本地实现；日志不得记录完整指令原文 |
| 字段别名表、空白/Unicode 处理 | 必须保持三字段语义和来源可追溯 |
| 具体编程框架、函数组织和测试替身 | 不生成代码；不升级为架构决策 |

## 4. 继承决策与父层专属禁止项

| 父决策/约束 | 本层行为 |
|---|---|
| L1 `LCD-001` | 确定性必填闸门固定；提取机制可演进 |
| `INV-1` | 缺项不创建任务、不产生网络调用 |
| `IC-M01-01` | 三字段输出或具体缺项输出；无副作用 |
| DU-1 / L1 `KD-003/KD-005` | 不创建服务、不发起 HTTPS、不接触上传协议 |

本层禁止：修改 `IC-M01-01/02` 字段或 owner；增加外部 NLU 依赖；持久化解析结果；直接调用 `CMP-STATUS-PRESENTER`；转移 `PendingTask` 或 Submission 所有权。

## 5. 决策队列汇总

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-IP-001 | L1 architecture / current PRD | `LCD-001` / `REQ-DD001` | FIELD-EXTRACTOR、REQUIRED-FIELD-GATE | 需要把可演进提取与固定放行边界显式化 | decide_now | — |
| LCD-IP-002 | L1 contracts | `IC-M01-01` / `INV-1` | REQUIRED-FIELD-GATE | 歧义时的安全结果影响是否会创建任务 | decide_now | — |
| LCD-IP-003 | L1 contracts / current PRD | `LCD-001` / `IC-M01-02` | COMMAND-ADAPTER、NORMALIZER | 配置默认值是否能改变缺项语义 | decide_now | — |
| LCD-IP-004 | L1 handoff | “提取机制 implementation_detail” | FIELD-EXTRACTOR | 具体宿主能力未定但不影响当前结构 | defer_to_next_level | FIELD-EXTRACTOR |

队列结论：所有 `decide_now` 均已记录选择、替代方案和后果；无 `return_to_parent`。当前包可进入交接。
