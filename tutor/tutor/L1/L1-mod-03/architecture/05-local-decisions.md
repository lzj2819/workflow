# 05 Local Decisions — MOD-03 course-roster（L1 本地决策）

## 1. 本地决策（按 decision_id 排序）

### LCD-001 叶子节点与内部组件边界

- **决策**：MOD-03 停止在 L1，不产生 L2 子 PRD。`CMP-COURSE-ROSTER-ADMIN`（课程与名单管理，拥有 Course 聚合）与 `CMP-MEMBERSHIP-VERIFIER`（归属校验，拥有校验记录）保留为同一模块内的实现组件。
- **备选**：① 将两项内部职责拆为独立 L2 PRD；② 按传输适配/领域/存储三层拆 3+ 子节点；③ 邀请码管理独立成第三个子节点。
- **理由**：职责（热路径运行时校验 vs 低频行政管理）、状态（append-only 校验记录 vs 强一致 Course 聚合）、不变量（P3/P4/P5 vs P1/P2）、生命周期（并发毫秒级 vs 稀疏分钟级）、变化原因（校验策略演进 vs 名单来源演进，A-002）均不同；交互为单向只读依赖，无环。
- **后果**：正向——P3（不缓存）与 P4（逐条记录）由 VERIFIER 独立保障；A-002 外部名单系统未来接入仅影响 ADMIN（C5）。代价——两个内部组件需共享数据库 schema 治理（同库分表，owner 写原则约束），但不增加 PRD 层级。
- **来源**：产品负责人叶子节点决策；C1 映射仅约束实现边界，不要求增加 PRD 层级。

### LCD-002 校验读取战术：每次直读已提交名单，无缓存

- **决策**：每次 CT-003 调用对 Course 聚合做一次索引化直读（读已提交）；不引入结论缓存、名单读缓存、名单快照/版本化。
- **备选**：① 通过结论缓存（父契约明令禁止，REQ-006）；② 名单读缓存（TTL）（存在陈旧窗口，违反「当前名单」语义，且 100 名学生规模无性能必要）；③ 名单快照/版本化（复杂度远超收益）。
- **理由**：P3 + D-AC-REQ-006-01 要求每次按当前名单判定；毫秒级索引直读已满足 30 秒同步窗口（NFR-003）与 30 并发（NFR-002）；战术全部在模块内部，不引入父级平台（C6）。
- **后果**：名单导入提交后下一次校验即生效（R3）；数据库为该路径唯一可用性依赖，其故障按 R2 映射为 ROSTER_UNAVAILABLE。
- **来源**：父层只禁止缓存结论，不规定读取战术（`decide_now`）。

### LCD-003 校验记录模型与提交关联方式

- **决策**：VerificationRecord 以模块自有 `verification_id` 为主键，载 `invite_code`、`student_name`、`group_name`、`verified`、`reason?`、`course_id?`、`verified_at`；与具体 submission 的关联由调用方 MOD-02 侧持有（MOD-02 在 CT-001 处理中调用并自行记录），本模块不感知 submission_id。
- **备选**：① 给 CT-003 增加 `submission_id` 字段（父级契约变更 → 必须 return_to_parent，且当前无必要，拒绝）；② 不落校验记录（违反 CT-003 side_effects 与 D-AC-REQ-006-01 oracle，拒绝）。
- **理由**：CT-003 入参为父级 inherited-fixed；D-AC-REQ-006-01 要求的是「本次提交存在独立的校验时间/校验记录」——每次调用一条记录（P4）+ MOD-02 调用侧关联即可完整满足，无需改动契约。
- **后果**：审计可按请求要素与时间检索；若未来父层在 CT-003 增加关联字段，本模型仅做字段追加（向后兼容）。
- **来源**：父层未规定记录模型与关联方式，且契约无 submission_id（`decide_now`）。

### LCD-004 v1 课程与邀请码供给：运维预置，不新增公共 API

- **决策**：v1 课程创建与邀请码签发由运维预置（种子数据/管理脚本）完成，能力内置于 CMP-COURSE-ROSTER-ADMIN；不新增任何公共建课契约。
- **备选**：① 新增教师自助建课公共 API（父包契约清单中不存在，属新增父级公共边界 → 必须 return_to_parent；当前 PRD 无对应需求，拒绝）；② 借 CT-013 隐式建课（改变 CT-013 `dependencies: 课程已创建` 语义，违反 inherited-fixed，拒绝）。
- **理由**：CT-013 明确以「课程已创建」为前置；父包与当前 PRD 均未定义建课功能；运维预置不改变任何父边界即可满足 v1。
- **后果**：v1 上线需配套一次性预置操作；未来若产品要求教师自助建课，走 `parent-change-request` 路径（已在 handoff 观察项 2 登记触发条件）。
- **来源**：CT-013 dependencies「课程已创建」在父包无对应供给契约（`decide_now`，附未来 return_to_parent 路径登记）。

### LCD-005 课程级数据保留：对齐「课程结束+1 年」，运维清除

- **决策**：名单（ST-COURSE）与校验记录（ST-VERIFICATION-RECORD）保留对齐父包「课程结束后 1 年」的治理精神，随课程下线由运维清除；本层不自建批处理清除设施。
- **备选**：① 永久保留（与学生个人数据最小化原则相悖）；② 挂接 CT-012 删除流程（CT-012 范围为 submission_ids，属 MOD-05/MOD-02 父级契约，不可本地扩展 → 拒绝）。
- **理由**：父包 DF-3/NFR-004 的清除流程仅覆盖提交数据；课程级数据保留/清除无父级契约，影响限于 MOD-03 内部，可本地决定；对齐同一周期保持语义一致。
- **后果**：满足隐私保留预期且无新边界；若未来需契约化课程数据清除（如教师可触发的课程删除），须父层补充（观察项 3）。
- **来源**：父层保留治理未覆盖课程级数据（`decide_now`）。

## 2. 继承决策引用（标记为 inherited，本层不改）

| 决策 | 内容 | 对本层的约束 |
|---|---|---|
| KD-002 | 同组服务共部署 + 单一关系型数据库 + Outbox（本模块无事件） | 两子节点同在 DU-2，共享数据库；不得引入独立存储/消息设施 |
| KD-003 | 基础级运维（单地域/HTTPS/存储加密/每日备份/基础监控） | 传输与存储加密、监控告警由 DU-2 平台承担；AccessDeniedLogged 等留痕纳入日志 |
| KD-005 | 令牌认证 + 幂等键 + `/api/v1` | CT-013 教师会话、CT-003/CT-013 路径前缀、写操作幂等原样遵守 |
| A-002 | 名单首版教师手工维护，外部系统对接暂缓 | 本层不建外部名单 Adapter；触发后经 C5 在 ADMIN 内落地 |
| CT-003/CT-013 契约语义 | 04 §1 逐字继承 | 标识/字段/owner/失败/幂等/版本不可改 |
| FLOW-011 无网络契约 | internal_read 只读引用课程结束时间 | 以 CP-COURSE-ENDTIME 实现，不得升级为网络契约 |
| 数据库产品选型暂缓 | defer_to_detail_design | 继承至下一层/详细设计（§3） |

## 3. 委托给下一层的决策（defer_to_next_level）

| 事项 | 触发时机 | 说明 |
|---|---|---|
| 数据库产品选型 | DU-2 实施启动 | 继承父层暂缓项，仅要求事务 + 备份 |
| 拒绝原因编码枚举（P5 的具体取值） | CMP-MEMBERSHIP-VERIFIER 组件设计 | 本层只约束「至少区分邀请码无效 / 名单未命中两类」 |
| 名单文件格式、解析与冲突判定细则 | CMP-COURSE-ROSTER-ADMIN 组件设计 | 契约仅要求逐项报告 + conflicts[] 可见 |
| 邀请码生成规则（长度/字符集/防猜解） | 运维预置工具设计 | 父层仅约束 P1 唯一映射 |
| 校验超时预算毫秒值、内部调用鉴权方式 | 详细设计/部署 | CT-003 端点暴露面收敛为 DU-2 内部可达属部署事项 |

implementation_detail（不登记为架构决策）：连接池配置、索引 DDL、ORM/HTTP 框架配置、日志格式。

## 4. 本地禁止的父级决策（prohibited locally）

- 新增、改名、弱化、移动、版本升级任何父级契约（含给 CT-003 增加 submission_id 等字段）。
- 发布/订阅任何事件（`publishes_events`/`consumes_events` 保持 `[]`）；引入消息总线。
- 创建独立服务、容器、部署单元或公共运行时边界；将 FLOW-011 升级为网络契约。
- 缓存归属校验通过结论（REQ-006 明令）；引入名单读缓存替代直读（LCD-002）。
- 将 Course 聚合或校验记录所有权移出 MOD-03；设计兄弟节点内部。

## 5. 本地决策队列结果

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-001 | 本层 C1 映射 | MOD-03 | 02-architecture-decomposition | C1 要求拆分子节点但不决定数量与边界 | decide_now | 已决（§1）；结构固化于 02 |
| LCD-002 | CT-003 幂等条款 / REQ-006 | CT-003 | 03-state-and-data §3–4、04 R1–R3 | 父层只禁止缓存结论，不规定读取战术 | decide_now | 已决（§1） |
| LCD-003 | CT-003 side_effects / D-AC-REQ-006-01 | CT-003 | 03-state-and-data §1（ST-VERIFICATION-RECORD） | 父层未规定记录模型；契约无 submission_id 且不可加 | decide_now | 已决（§1） |
| LCD-004 | CT-013 dependencies | CT-013 | 02（ADMIN 职责）、handoff 观察项 2 | 「课程已创建」在父包无供给契约，PRD 无对应需求 | decide_now | 已决（§1）；未来需求触发 → return_to_parent |
| LCD-005 | 父包 DF-3/NFR-004 保留治理 | 03-data-and-consistency（父） | 03-state-and-data §5 | 父层清除流程仅覆盖提交数据，课程级数据无契约 | decide_now | 已决（§1）；契约化需求 → 父层补充（观察项 3） |
| —（数据库产品选型） | 父 05 §暂缓到详细设计 | KD 暂缓表 | — | 父层显式 defer | defer_to_next_level | child-handoff §5 |
| —（原因编码/文件格式/邀请码规则/超时预算） | CT-003/CT-013 字段语义 | CT-003、CT-013 | — | 契约只规定字段存在性，不规定取值细节 | defer_to_next_level | child-handoff §5 |
| —（连接池/索引 DDL/框架配置） | — | — | — | 编码与配置细节 | implementation_detail | 不登记 |

**队列结论：无遗留 `decide_now`；无 `return_to_parent`（未创建 `parent-change-request.md`）。**
