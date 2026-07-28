# 05 Local Decisions — MOD-04 局部决策

## 1. 继承决策（明确标记，本层原样执行，不得修改）

| 来源 ID | 内容 | 本层执行方式 |
|---|---|---|
| KD-001 | 外部模型 API + MOD-04 内 ACL 隔离；材料最小化（不外发业务标识）；供应商可替换 | CMP-MODEL-SERVICE-ACL 单点收口全部供应商交互（ICT-004） |
| KD-002 | 同组共部署；数据库任务表 + Outbox 表；单一关系库 + 本地材料磁盘 | ST-001 任务表、ST-003 Outbox 行；不引入消息中间件；材料只读共享存储（LCD-001） |
| KD-003 | 基础级运维（单地域、加密、每日备份、基础监控、RPO 24h/RTO 48h） | 指标钩子对接基础监控（ICT-008）；日志最小化 |
| REQ-012 / FR-012 / DF-2 | 自动重试仅一次；再失败标记 scoring_failed 并通知教师；不得伪造等级 | 状态机强制执行（INV-1/INV-2；重试决策表） |
| NFR-003 / FR-015 | CT-010 单次 ≤3 分钟；评分 ≤10 分钟（≥95%） | 超时与期限跟踪（LCD-004） |
| 06-deployment | DU-3 仅含 MOD-04；2–3 worker 副本；故障隔离、任务可恢复 | 任务表认领协调多副本（CON-1/CON-2）；不新建部署单元 |
| 父层「不采用方案」 | 无消息中间件、工作流引擎、缓存/搜索引擎、分布式事务、自托管模型 | 内部协作全部进程内调用 + 任务表协调 |

## 2. 局部决策队列结果

| Decision ID | Source Artifact | Source ID | Affected Child Artifact | Why Mapping Is Not Enough | Classification | Follow-up Target |
|---|---|---|---|---|---|---|
| LCD-001 | 04-interface-contracts | CT-010 dependencies「材料包内容」；KD-002 | ICT-003；CMP-ASSESSMENT-ENGINE | 父层未规定 MOD-04 取得材料内容的通道 | decide_now | 本文件 §3.1 |
| LCD-002 | domain-flow / PRD | DF-2；REQ-D002 | CMP-SCORING-ORCHESTRATOR；重试决策表 | “自动重试一次”的调度时点与崩溃恢复计入规则父层未定 | decide_now | 本文件 §3.2 |
| LCD-003 | FR.md | FR-008（默认区间） | CMP-RUBRIC-PROMPT-COMPOSER；ST-004；ST-002 | 准则/提示词的变更管理与存证方式父层未定 | decide_now | 本文件 §3.3 |
| LCD-004 | 01-system-overview | SM-002；NFR-003 | CMP-SCORING-ORCHESTRATOR；ST-001 deadline_at | 10 分钟期限的执行语义（强杀与否）父层未定 | decide_now | 本文件 §3.4 |
| LCD-005 | 本层分解 | CMP-RUBRIC-PROMPT-COMPOSER / CMP-MODEL-SERVICE-ACL | 提示模板细节、对话摘要压缩策略 | 不影响本层结构与契约 | defer_to_next_level | child-handoff §2 |
| LCD-006 | 本层分解 | 全部子节点 | 任务表 schema 细节、轮询间隔、租约参数、供应商端点与密钥配置 | 编码/配置层面 | implementation_detail | 详细设计 |
| Q-001 | 父层 03/04 | CT-012、DF-3 | （父层事项） | 父层未将 AssessmentResult 纳入删除接线 | 父层专属（登记，非 return_to_parent） | 本文件 §5；child-handoff §4 |

## 3. decide_now 决策

### 3.1 LCD-001：材料内容读取通道 —— 共享存储只读端口

- **决定**：MOD-04 经内部只读端口（ICT-003）读取同组共享材料磁盘/清单（KD-002 同组共部署存储），所有权留 MOD-02，不复制可写状态。
- **替代方案**：(b) 请求 MOD-02 新增材料查询契约——改变父契约集，须 return_to_parent，且父层已以 CT-004 material_refs[] + 共部署存储表达该意图；(c) CT-004 直接携带全部材料内容——改变父事件字段与体量语义，同上须上返。均拒绝。
- **后果**：与 FLOW-011（MOD-05 只读引用课程结束时间）同构的只读引用模式；MOD-02 存储布局变更为边界协商项；材料不可读按基础设施失败进入 REQ-D002 路径（A-001）。

### 3.2 LCD-002：重试调度 —— 任务轮次内有界退避，崩溃重跑不耗重试预算

- **决定**：首次 classified 失败后在同一任务轮次内有界退避（默认 ≤60 秒，配置项）立即发起第二次尝试；worker 崩溃（无 classified 结果）经租约过期重认领，同一 attempt 重跑、attempts 不增；reclaim_count>3 按基础设施失败终态化（failure_reason=REPEATED_WORKER_CRASH）。
- **替代方案**：(b) 无退避立即重试——供应商短暂不可用（MODEL_ERROR）时第二次几乎必败，浪费唯一重试；(c) 任务重新排队延迟重试——延迟叠加积压易突破 10 分钟口径，且状态机增加“等待重试”外部态，复杂度无收益。均拒绝。
- **后果**：双次尝试 + 退避最坏约 7 分钟（3+1+3），在 10 分钟口径内；崩溃最多造成一次重复模型调用（成本可接受，request_id 新值）；防毒上限保证 SM-003 终态覆盖不被毒任务击穿。

### 3.3 LCD-003：评分准则与提示词版本化存证

- **决定**：RubricPolicy 与提示模板以版本化配置管理（ST-004）；每次评估固定单一版本；prompt_version、rubric_version 随结果写入 ST-002（内部存证，不经 CT-005 外发）。
- **替代方案**：(b) 无版本直接改模板——评估结果不可复现、调优无法回归对比，违背审计诉求（材料含个人信息系统留痕要求）；(c) 版本号加入 CT-005 载荷——改变父契约字段，须 return_to_parent，拒绝（保留为父层未接受替代方案）。
- **后果**：调优仅影响新版本任务；历史结果可按版本回溯；版本升级属内部发布事项。

### 3.4 LCD-004：10 分钟期限语义 —— 跟踪统计，不强杀、不伪标记

- **决定**：deadline_at = created_at + 10min 仅用于 SM-002 统计（created_at → outcome=scored 时长）与积压观测；到期任务继续执行完成，不强制终止、不伪标记 scoring_failed。
- **替代方案**：(b) 到期强杀并标记失败——把容量问题转化为虚假评估失败，违反“不得伪造等级/失败须记录真实原因”（FR-012）；且 SM-002 为 ≥95% 统计目标而非单任务硬保证（AC-NFR-003-01 pass_rule）；(c) 不设期限字段——SM-002 无从度量，拒绝。
- **后果**：超期任务如实完成并计入未达标比例；容量侧由 06 既定策略（2–3 worker、按积压扩容）保障。

## 4. 下一层委托与实现细节

- **defer_to_next_level（LCD-005）**：提示词模板具体文本、对话摘要压缩策略（截断/摘要算法）——目标子节点 CMP-RUBRIC-PROMPT-COMPOSER、CMP-MODEL-SERVICE-ACL；触发条件：各自进入下一层细化或实施。
- **implementation_detail（LCD-006）**：任务表/结果表具体 schema 与索引、轮询间隔、租约时长参数、供应商端点与密钥配置、日志框架接入——详细设计阶段，不改变本层结构。

## 5. 父层专属禁止项与未决登记

**禁止项（本层不得触碰，违者须 return_to_parent）：**

- 不得为 MOD-04 新建网络/API 契约、部署单元或独立服务；
- 不得修改 CT-004/CT-005/CT-010 的标识、所有者、字段（含新增必需字段）、副作用、失败与版本语义；
- 不得把 student_name、group_name、submission_id 等业务标识外发至模型供应商（KD-001）；
- 不得消费 CT-012 或自建 AssessmentResult 删除接线；
- 不得伪造等级；评分失败必须携带真实 failure_reason 与 retry_record；
- 不得引入消息中间件、工作流引擎、缓存/搜索引擎、分布式事务、自托管模型。

**Q-001（父层未决，登记而非上返）**：父层删除流程（DF-3、CT-012）的消费者不含 MOD-04，AssessmentResult 的保留期清除无接线。本层 PRD（REQ-D001/D002）不依赖该行为，影响封闭在 MOD-04 内，故不构成 `return_to_parent`；建议 L0 修订时处置（候选：扩展 CT-012 消费者至 MOD-04，或新增保留清除契约）。登记于 child-handoff §4 未解决风险。

**本轮无 return_to_parent 项，未创建 parent-change-request.md。**
