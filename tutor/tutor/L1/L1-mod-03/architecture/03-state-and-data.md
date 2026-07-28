# 03 State and Data — MOD-03 course-roster（L1 状态与数据）

## 1. 状态所有权清单（按 state_id 排序）

| state_id | 状态 | Owner 子节点 | Readers | Writers | 生命周期 | 一致性边界 | 保留 / 隐私 | 父追踪 |
|---|---|---|---|---|---|---|---|---|
| ST-COURSE | Course 聚合：`Course`（课程）+ `InviteCode`（邀请码）+ `RosterEntry[]`（名单条目：student_name、group_name）+ `course_end_time` | CMP-COURSE-ROSTER-ADMIN | CMP-MEMBERSHIP-VERIFIER（经 CP-ROSTER-QUERY）；MOD-05（经 CP-COURSE-ENDTIME，仅 course_end_time）；教师浏览器（CT-013 应答） | CMP-COURSE-ROSTER-ADMIN（CT-013 导入；v1 课程/邀请码运维预置，LCD-004） | 已预置 → 维护中 → 已结束（course_end_time 设定）；结束后的校验策略父包未定义，本层不增设（01 §9） | 单聚合、单本地事务（名单/小组变更与课程一致性，父 03 §本地事务边界）；不变量 P1：邀请码唯一映射课程（唯一约束保证）；导入去重键 =（course_id + student_name + group_name）（CT-013 幂等条款） | 含学生姓名：HTTPS + 存储加密（KD-003）；课程范围授权失败记录 AccessDeniedLogged；保留对齐「课程结束+1 年」（LCD-005） | 父 03 §数据所有权 Course 行；aggregates.md Course；FR-005 |
| ST-VERIFICATION-RECORD | VerificationRecord（校验记录）：`verification_id`、`invite_code`、`student_name`、`group_name`、`verified`、`reason?`、`course_id?`、`verified_at` | CMP-MEMBERSHIP-VERIFIER | 模块内审计/排障（无公共契约暴露）；监控统计（REJECTED_MEMBERSHIP 口径，支撑 SM-001 链路） | CMP-MEMBERSHIP-VERIFIER（每次产生结论的 CT-003 调用一条） | append-only，无状态机 | 结论与记录同一本地事务（未成功记录则不应答结论，P4）；按调用逐条写入、不去重（审计意图：每次提交存在独立校验时间/校验记录） | 含学生姓名+小组：存储加密（KD-003）；不向任何外部方输出（无事件、无查询契约）；保留对齐「课程结束+1 年」（LCD-005） | CT-003 side_effects「记录校验结果（通过/拒绝原因）」；D-AC-REQ-006-01 oracle「本次提交存在独立的校验时间/校验记录」 |

## 2. 存储意图（受父技术决策约束）

- 两类状态均存于 **DU-2 共享的单一关系型数据库**（KD-002；产品选型 defer_to_detail_design，仅要求事务 + 备份）；同库分表，各表仅由其 owner 子节点写入。
- 传输 HTTPS、存储加密、每日备份保留 30 天由 DU-2 平台统一承担（KD-003），本层不另建存储设施。
- 访问形态（战术层，DDL/索引细节为 implementation_detail）：校验路径对 `invite_code` 唯一索引单次解析 + 按（course_id, student_name, group_name）命中名单条目；校验记录顺序追加。100 名学生规模下无需缓存、搜索或读模型（父 03 §读模型说明同款结论）。

## 3. 数据流

### 3.1 写

| 流 | 内容 | 事务边界 |
|---|---|---|
| CT-013 名单导入 | 教师浏览器 → ADMIN：逐条校验 → 按（姓名+小组）去重 → 冲突检测 → 写入 Course 聚合 | 单次导入一个本地事务；部分成功以 `import_result`（imported_count / skipped_duplicates[] / conflicts[]）可见 |
| 课程/邀请码预置 | 运维预置（v1，LCD-004）→ ADMIN 写入 Course/InviteCode | 单本地事务；非公共契约 |
| 校验记录写入 | VERIFIER 每次产生结论的 CT-003 调用 → 写入一条 VerificationRecord | 与结论判定同一本地事务（P4：未记录不应答） |

### 3.2 读

| 流 | 内容 | 一致性 |
|---|---|---|
| CT-003 校验查询 | VERIFIER 经 CP-ROSTER-QUERY 读取当前名单 | 读已提交（read-committed）；调用时刻已提交状态即「当前名单」 |
| 课程结束时间只读引用 | MOD-05 经 CP-COURSE-ENDTIME 读取最新 course_end_time（FLOW-011） | 批处理执行时读取最新已提交值（父 03 §跨边界一致性策略） |

### 3.3 派生与外部化

- 派生状态：**无**。本模块不维护读模型/快照/缓存（P3 不缓存结论；名单直读已满足性能）。
- 外部化状态：**无**。`publishes_events: []`（父组件接口卡不变）；校验记录不离开模块边界。

## 4. 不变量、一致性、幂等与并发规则

1. **P1 邀请码唯一映射课程**：数据库唯一约束兜底；导入/预置时违反即整体拒绝（VALIDATION_FAILED）。
2. **P2 姓名+小组命中名单才通过**：校验判定仅基于当前已提交名单，不引入名单外数据源。
3. **CT-003 结果幂等**：同一请求要素在名单状态不变时重复执行结果一致；但**记录按调用逐条产生**（P4），不复用、不更新旧记录（审计意图，D-AC-REQ-006-01）。
4. **CT-013 导入幂等**：同一文件重复导入按（姓名+小组）去重，不产生重复条目（父契约原样继承）。
5. **并发——校验 vs 导入**：校验读已提交状态，不加锁；与导入并发时看到调用前已提交状态，两种结果均为有效「当前」（01 §9 假设）。名单稀疏变更 + 30 并发校验读取，无竞争瓶颈。
6. **并发——多导入**：同学院并发导入由唯一约束与同事务保证；后提交事务中的重复条目进入 `skipped_duplicates[]` / `conflicts[]` 报告（冲突判定细则 delegated 至下一层）。
7. **不产生跨聚合/跨模块事务**：校验记录与 Course 聚合分属两个一致性边界，两者之间无事务耦合（校验只读名单）。

## 5. 保留与隐私

- **保留**（LCD-005）：父包 DF-3/NFR-004 的清除流程仅覆盖提交数据（CT-012 范围为 submission_ids），未覆盖课程级数据。本地决定：名单与校验记录保留对齐「课程结束后 1 年」，随课程下线运维清除；如需契约化清除流程须父层补充（观察项 3）。
- **隐私**：名单与校验记录含学生姓名（PRD 风险节：材料含个人信息）；HTTPS 传输、存储加密（KD-003）；CT-013 课程范围授权失败返回 FORBIDDEN 并记录 AccessDeniedLogged；校验记录无任何对外查询契约，不进入事件、不进入教师读模型。

## 6. 所有权确认

- Course 聚合所有权仍归 MOD-03（父 03 未变），本层仅将其内部 owner 定为 CMP-COURSE-ROSTER-ADMIN。
- VerificationRecord 为本层在 MOD-03 边界内新增的审计状态，不构成父级聚合，不涉及兄弟节点。
- 未对 Submission（MOD-02）、AssessmentResult（MOD-04）、ReviewRecord/PresentationView/DeletionBatch（MOD-05）做任何所有权重分配；父与兄弟状态所有权未变。
