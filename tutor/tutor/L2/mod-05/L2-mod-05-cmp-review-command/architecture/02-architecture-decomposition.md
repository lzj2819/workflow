# 02 Architecture Decomposition — 架构分解（L2 / CMP-REVIEW-COMMAND）

> 仅细化 L1 `CMP-REVIEW-COMMAND`；不重画 MOD-05 边界，不设计 QUERY、PRESENTATION、TEACHER-UI、ACCESS-GATE 或 READMODEL-PROJECTOR 内部。

## 1. 局部语义细化

### 1.1 聚合与不变量

| 聚合/概念 | 本层细化 | 不变量 |
|---|---|---|
| ReviewRecord | `ReviewRecord` 包含 Annotation、OriginalGradeSnapshot、FinalGrade、GradeAdjustmentRecord | 原始等级复制值与来源 submission_id 创建后不可变；最终等级未调整时等于原始等级；调整记录含 operator、updated_at、adjustment_id；评分失败无原始等级时不得设置最终等级 |
| ReviewCommand | CT-008 的写意图，包含 request_id、submission_id、annotation、final_grade、teacher_session 上下文 | annotation 与 final_grade 至少一项；request_id 重复返回首次结果；授权已由父网关完成 |
| ReviewMutation | 一次聚合变化及其可追溯局部事件 | 业务写入、幂等记录和 M05-IC-05 可追溯记录遵守同一提交边界；事件不得在事务提交前对外可见 |

### 1.2 命令、内部事件和策略

| 类型 | 名称 | 入口/作用 |
|---|---|---|
| command | `CreateReviewRecord` | M05-IC-01，评分完成后固化原始等级 |
| command | `SaveAnnotation` | CT-008 写侧，保存批注并记录操作者/时间 |
| command | `AdjustFinalGrade` | CT-008 写侧，在有原始等级且等级合法时更新最终等级 |
| local event | `AnnotationSaved` | M05-IC-05，供 RMP 更新教师读模型 |
| local event | `GradeAdjusted` | M05-IC-05，供 RMP 更新教师读模型 |
| command | `PurgeReviewRecordContent` | M05-IC-07，父级删除批次提交后清除 ReviewRecord 内容 |
| policy | `P-ReviewInputCompleteness` | annotation/final_grade 至少一项，空值和格式错误返回 VALIDATION_FAILED |
| policy | `P-NoOriginalGrade` | scoring_failed 或 original_grade 缺失时拒绝最终等级写入，返回 NO_ORIGINAL_GRADE |
| policy | `P-ReviewIdempotency` | CT-008 以 request_id；M05-IC-01 以 submission_id；重复请求不重复写入 |
| policy | `P-LatestWriteWins` | 并发调整以父契约规定的后写为准，但保留每个 adjustment_id 的留痕 |

### 1.3 生命周期

`absent → created_on_scored → annotated / adjusted → purged_content`。

`scoring_failed` 不进入 `created_on_scored`；删除批次完成后由父级保留治理/投影链路触发内容清除，本层不拥有删除批次状态机。

## 2. Child Registry（按稳定 child_id 排序）

| child_id | responsibility | exclusions | owned_state | requirement_or_parent_trace | dependencies | reason_for_existence | trace_exemption_reason |
|---|---|---|---|---|---|---|---|
| CMP-RC-REVIEW-IDEMPOTENCY-GUARD | 统一 CT-008 request_id 与 M05-IC-01 submission_id 入口去重、首次响应回放和同事务幂等控制 | 不执行业务等级校验、不直接改变 ReviewRecord 字段、不实现课程授权 | ST-IDEMPOTENCY-REVIEW | REQ-DD001；D-AC-REQ-009-01；CT-008；M05-IC-01；KD-005 | ACCESS-GATE 已授权上下文；REVIEW-INTEGRITY-POLICY；REVIEW-RECORD-WRITER | 两种写入口有不同业务键，必须在聚合写入前收敛重复副作用 | |
| CMP-RC-REVIEW-INTEGRITY-POLICY | 验证批注/等级输入、原始等级存在性、评分失败禁伪造和父级错误映射 | 不持有 ReviewRecord，不决定课程授权，不新增错误码 | 无持久状态；纯本地策略 | REQ-DD001；D-AC-REQ-009-01；CT-008；P-禁伪造等级；LCD-009 | REVIEW-IDEMPOTENCY-GUARD；REVIEW-RECORD-WRITER | 将业务不变量集中在一个本地策略边界，避免 writer 和入口重复实现 | |
| CMP-RC-REVIEW-RECORD-WRITER | 创建 ReviewRecord、保存批注、调整最终等级、追加调整留痕、执行 M05-IC-07 内容清除并在提交后生成 M05-IC-05 | 不创建读模型，不消费 CT-005，不发布跨模块事件，不拥有删除批次或删除审计 | ST-REVIEW-RECORD（含 Annotation、GradeAdjustmentRecord、purge tombstone） | REQ-DD001；D-AC-REQ-009-01；CT-008；M05-IC-01；M05-IC-05；M05-IC-07；LCD-003 | REVIEW-IDEMPOTENCY-GUARD；REVIEW-INTEGRITY-POLICY；CMP-RETENTION-GOVERNANCE（仅 M05-IC-07） | 让 ReviewRecord 保持单写方，统一创建、更新、清除、不可变快照和局部事件提交顺序 | |

## 3. C1-C6 映射与依赖

### 3.1 C1：选定节点到内部 child

`CMP-REVIEW-COMMAND` → `CMP-RC-REVIEW-IDEMPOTENCY-GUARD`、`CMP-RC-REVIEW-INTEGRITY-POLICY`、`CMP-RC-REVIEW-RECORD-WRITER`。

拆分依据是不同的业务不变量和状态边界：幂等键/回放、输入完整性/禁伪造策略、ReviewRecord 聚合写入与事件提交。不是按 Controller/Service/Repository 泛化分层。

### 3.2 C2：状态到所有者

- `ST-IDEMPOTENCY-REVIEW` → `CMP-RC-REVIEW-IDEMPOTENCY-GUARD`。
- `ST-REVIEW-RECORD` → `CMP-RC-REVIEW-RECORD-WRITER`。
- 禁伪造和输入校验是无持久状态的策略，由 `CMP-RC-REVIEW-INTEGRITY-POLICY` 执行。

### 3.3 C3：父流程到内部协作

| 父入口 | 内部顺序 | 终态 |
|---|---|---|
| M05-IC-01 | IDEMPOTENCY-GUARD → INTEGRITY-POLICY → RECORD-WRITER | created / duplicate_returned / rejected |
| CT-008 | IDEMPOTENCY-GUARD → INTEGRITY-POLICY → RECORD-WRITER → M05-IC-05 | updated / duplicate_returned / validation_failed / no_original_grade |
| M05-IC-05 失败恢复 | RECORD-WRITER 提交事件记录 → RMP 重放 | committed / replay_required |
| M05-IC-07 | RETENTION-GOVERNANCE → RECORD-WRITER | purged / already_purged / partial_failed / retry |

### 3.4 C4：父契约到内部实现

| 父契约 | 内部实现 |
|---|---|
| CT-008 | GUARD 透传 request_id 并回放；POLICY 校验；WRITER 事务写 ReviewRecord/AdjustmentRecord 并返回 review_record |
| M05-IC-01 | GUARD 以 submission_id 去重；POLICY 确认 outcome=scored 且原始等级存在；WRITER 固化 OriginalGradeSnapshot |
| M05-IC-05 | WRITER 在事务提交后生成 AnnotationSaved/GradeAdjusted，字段原样交给父级 RMP |
| M05-IC-07 | WRITER 按 submission_id 清除 ReviewRecord 内容并保留最小 tombstone/幂等记录 |

### 3.5 C5：父外部依赖与适配

本节点不拥有新的外部依赖。ACCESS-GATE 已完成授权；RMP 是 M05-IC-01 的调用方和 M05-IC-05 的消费者；RETENTION-GOVERNANCE 仅通过 M05-IC-07 触发本节点自身 ReviewRecord 内容清除；Outbox/数据库能力由 DU-2 父级提供。不得把 MOD-04、MOD-02 或 MOD-03 的内部实现拉入本包。

### 3.6 C6：局部驱动到内部策略

| 局部驱动 | 内部策略 |
|---|---|
| 幂等优先 | `P-ReviewIdempotency` + ST-IDEMPOTENCY-REVIEW 同事务 |
| 失败透明 | `P-NoOriginalGrade` 映射 NO_ORIGINAL_GRADE，不写伪造等级 |
| 聚合单写方 | WRITER 独占 ST-REVIEW-RECORD |
| 留痕完整 | WRITER 追加 GradeAdjustmentRecord，理由可选 |
| 事件可重放 | WRITER 提交后生成 M05-IC-05，按 adjustment_id 去重 |

## 4. 依赖图与兄弟边界

```text
CT-008 / M05-IC-01
        |
        v
CMP-RC-REVIEW-IDEMPOTENCY-GUARD
        |
        v
CMP-RC-REVIEW-INTEGRITY-POLICY
        |
        v
CMP-RC-REVIEW-RECORD-WRITER ---- M05-IC-05 ----> CMP-READMODEL-PROJECTOR
        |
        +---- ST-REVIEW-RECORD

CMP-RETENTION-GOVERNANCE ---- M05-IC-07 ----> CMP-RC-REVIEW-RECORD-WRITER

CMP-ACCESS-GATE --(已授权请求)--> GUARD
CMP-REVIEW-QUERY / CMP-TEACHER-UI --(父流程引用)--> CT-008
```

兄弟节点和支撑节点只作为父契约的协作者被引用，未设计其内部状态、算法、接口或部署；本层没有新增跨模块依赖。
