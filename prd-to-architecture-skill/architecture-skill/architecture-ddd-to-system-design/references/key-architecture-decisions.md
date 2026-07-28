# 关键架构取舍确认

## 目标

处理阶段二映射后仍无法安全决定的关键架构取舍。只处理会影响以下内容的问题：

- 模块边界。
- 数据边界或事务边界。
- 核心运行时协作方式。
- 重要技术组件。
- 部署形态。
- 合规、安全、可用性或故障隔离。
- 迁移成本高、不可逆或明显超出团队能力的选择。

本阶段不是完整 ADD，不重做 DDD，也不讨论普通实现细节。

## 进入条件

只有 `architecture-workbench.md` 中的 `Key Decision Queue` 不为空时才进入本阶段。

如果队列为空，直接进入最终输出。

## 输入

- `architecture-workbench.md`
- 阶段一 DDD 产物。
- 阶段二 M1 到 M6 的映射结果。
- PRD、约束、补充说明和 `assumptions.md`。

## 输出

本阶段只更新必要文件：

- `architecture-workbench.md`
- 受影响的 `output/` 文件。

不要创建完整 ADD 过程包：`ADR/`、`ADD-iterations/`、`QAS.md`、`ASR.md`、`constraints.md` 不属于本流程默认输出。

## 处理流程

1. 读取 `Key Decision Queue`。
2. 检查每一项是否包含 `Source Artifact`、`Source ID` 和 `Affected Output`。如果缺失，先回到阶段二映射结果补齐来源，不要直接做判断。
3. 将每一项分类为：
   - `decide_now`：现在必须决定，否则最终架构会不完整或自相矛盾。
   - `defer_to_detail_design`：可以留到模块详细设计阶段，不影响系统级结构。
   - `return_to_ddd`：问题来自领域边界、聚合或领域事件不清，需要回到 DDD 阶段修正。
   - `implementation_detail`：只是编码、框架配置或局部实现细节，不属于系统级架构取舍。
4. 在 `architecture-workbench.md` 中为队列补充分类结果。
5. 只对 `decide_now` 项生成候选方案。
6. 每个 `decide_now` 项只生成 2 到 3 个候选方案，候选必须紧贴当前问题。
7. 用简单标准比较候选：
   - 简单性。
   - 稳定性。
   - 业务符合度。
   - 团队维护成本。
   - 未来演进成本。
   - 失败处理成本。
8. 给出推荐方案；如果需要用户判断，暂停并展示选项。
9. 决策确认后，先沉淀到 `output/05-decisions-and-technology.md`，再回填 `architecture-workbench.md` 和受影响的最终输出文件。

## 分类结果表

在 `architecture-workbench.md` 的 `Key Decision Queue` 下补充：

| Decision ID | Classification | Candidate Needed | Decision Status | Follow-up Target |
|---|---|---|---|---|

字段说明：

- `Classification`：只能填写 `decide_now`、`defer_to_detail_design`、`return_to_ddd` 或 `implementation_detail`。
- `Candidate Needed`：只有 `decide_now` 才写 `Yes`。
- `Decision Status`：填写 `decided`、`waiting_user`、`deferred`、`returned_to_ddd` 或 `not_architecture_level`。
- `Follow-up Target`：填写需要回填、后续设计或返回修正的文件。

## 决策记录模板

```markdown
## KD-001 <问题名称>

### 问题来源

- Source Flow:
- Source Event:
- Source Modules:
- Source Requirement / Constraint:
- Source Artifact:
- Source ID:
- Affected Output:

### 为什么普通映射不够

### 分类

`decide_now`

### 候选方案

| Candidate | Benefits | Costs / Risks | Best Fit |
|---|---|---|---|

### 比较

| Criteria | Candidate A | Candidate B | Candidate C |
|---|---|---|---|

### 决策

### 原因

### 回填位置

- `architecture-workbench.md`
- `output/05-decisions-and-technology.md`
- `output/...`
```

## 处理规则

- 如果分类为 `return_to_ddd`，不要在架构阶段硬做决定；暂停并说明需要回到哪些 DDD 产物。
- 如果分类为 `defer_to_detail_design`，记录后续事项；除非它影响系统级结构，否则不要阻塞最终架构输出。
- 如果分类为 `implementation_detail`，从关键架构取舍清单中移除或标记为非阻塞。
- 不要把所有问题都做候选比较；只比较结构性选择。
- 如果必须由用户决定，给出明确选项、推荐方案和推荐理由。

## 退出标准

- 所有 `decide_now` 项已经决策，或正在等待明确的用户确认。
- 所有 `return_to_ddd` 项已经指出需要返回修改的 DDD 产物。
- 所有 `defer_to_detail_design` 项已经记录为后续事项。
- 所有 `implementation_detail` 项已经移出系统级架构决策。
- 已确认的决策已经沉淀到 `output/05-decisions-and-technology.md`，并回填到 `architecture-workbench.md` 和受影响的 `output/` 文件。
