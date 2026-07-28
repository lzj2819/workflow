# 01 Design Context — SI-API L2

## 1. 递归输入与唯一父节点

| 输入 | 已解析值 |
|---|---|
| `current_prd` | `prd/L2-PRD/mod-02/L2-mod-02-si-api/prd.md` |
| `parent_architecture` | `architecture/L1/L1-mod-02` |
| `target_node_id` | `SI-API` |
| `output_dir` | `architecture/L2/mod-02/L2-mod-02-si-api` |
| `mode` | `new` |
| 父包类型 | recursive child package（存在 `architecture-manifest.yaml`） |

父节点在父包 `child-handoff.md` 的“下一层 target_node_id 清单”中唯一匹配为 `SI-API`；父 manifest 的 `children` 与 `02-architecture-decomposition.md` 交叉确认同一身份。输出目录在写入前存在但为空，不覆盖已有架构包。

## 2. 父边界快照

### 2.1 职责与排除项

`SI-API` 是 MOD-02 内的接入层，负责 CT-001 材料包上传端点、CT-002 提交状态查询、`POST /api/v1/auth/token` 令牌端点、认证、幂等接入、请求编排和 30 秒同步接收确认。它通过 `IC-SI-01`、`IC-SI-03`、`IC-SI-04` 调用 SI-XFER、SI-VERIFY、SI-CORE。

本层不拥有 `Submission(ST-01)`、`UploadSession(ST-02)`、`MaterialFile(ST-03)`、`OutboxRecord(ST-04)`，不执行评分与教师端能力，也不把 SI-STORE、SI-RELAY、SI-VERIFY 重新设计为独立 L2 目标。

### 2.2 绑定状态、数据与一致性

- `ST-06 AuthTokenGrant` 是 SI-API 的唯一父层持久状态所有权；用于令牌签发审计，不把令牌形态升级为新的公共契约。
- `ST-01` 只由 SI-CORE 写入；API 通过 `IC-SI-04` 读查询或发出命令。
- `ST-02` 只由 SI-XFER 写入；API 通过 `IC-SI-01` 驱动会话命令。
- `ST-03` 只由 SI-STORE 写入；API 不直接操作材料文件或配额。
- `submission_uuid`、分片 `seq`、`finalize` 的幂等语义沿用父包；API 只负责入口去重和结果复用。

### 2.3 继承契约与直接边界

| 父契约 | SI-API 角色 | 本层处理 |
|---|---|---|
| CT-001 | Provides to MOD-01 | 路由、认证、幂等入口、上传编排与响应映射 |
| CT-002 | Provides to MOD-01 | 路由、认证、查询调用和响应映射 |
| auth-token | Provides to MOD-01 | 令牌签发、ST-06 审计、名单校验调用 |
| CT-003 | Consumes from MOD-03 | 由 SI-VERIFY 端口调用；本层不缓存通过结论 |
| CT-004/CT-006 | Parent module publishes | SI-CORE/SI-RELAY 负责发布；本层只为同步响应等待必要的本地命令结果 |
| CT-005/CT-012/CT-014 | Parent module inbound/outbound | 由 SI-RELAY/SI-PURGE 支撑；SI-API 不直接消费或改变其语义 |

### 2.5 验证入口与场景责任

| 验证场景 | 当前层入口 | 当前层可验证结果 | 委托验证范围 |
|---|---|---|---|
| SCENARIO-001/002/004 | SI-API-ROUTER → CT-001 → SI-API-AUTH → SI-API-INTAKE-ORCHESTRATOR | 认证成功、CT-001 接收确认、submission_id、received_at、并发隔离和 CT-004 事件入口 | 不验证 MOD-04 内部评分实现 |
| SCENARIO-003 | SI-API-ROUTER → CT-002 查询 | API 能返回父模块当前 status，且不改变 ST-01 | received → processing → scored/scoring_failed 由 L1 MOD-02 状态机和 MOD-04 验证 |
| SCENARIO-005 | SI-API-ROUTER → CT-001 接收确认 | API 不拥有评分重试，也不消费 CT-005 | “再次失败”及教师通知由 MOD-04/MOD-05 的系统级场景验证 |

SI-API-AUTH 只负责认证、令牌签发和 ST-06 审计；它不是 CT-001 成功响应的业务字段生产者，也不拥有 scored/scoring_failed 状态。

### 2.4 运行流与约束

父包相关流程为 `FLOW-001/002/003/004/006/008`，核心顺序是：接入 → 认证/幂等 → 分片会话完成 → 材料归属校验 → SI-CORE 单事务确认 → 30 秒内返回；评分事件与后续状态推进在本层之外完成。

继承约束包括：DU-2 course-app 内部部署、30 并发提交、30 秒接收确认、500MB/类型白名单/课程配额、Outbox 不丢事件、CT-003 实时校验、六态加 `deleted` 的外部状态语义。数据库产品仍沿用父层延迟决策，不在本层选择。

## 3. 当前 PRD 需求分配

| 当前需求/指标 | 分类 | 父层追踪 | L2 分配 | 说明 |
|---|---|---|---|---|
| REQ-DD003：上传成功返回接收确认并异步执行 Agent 评分 | `allocated` | REQ-D003；D-AC-REQ-007-01；CT-001/CT-004 | ROUTER、INTAKE-ORCHESTRATOR、AUTH | API 只负责接收确认与事件链入口；评分归 MOD-04 |
| D-AC-REQ-007-01 | `inherited` | parent acceptance contract | ROUTER、INTAKE-ORCHESTRATOR | 必须返回 `submission_id`、`received_at`，状态可观察 |
| SM-001：有效提交接收成功率 ≥95% | `inherited` | MOD-02 owning metric；LCD-009 | OBSERVABILITY、INTAKE-ORCHESTRATOR | 采集边界和标签在本层细化，不改变指标口径 |
| 30 秒确认 | `inherited` | NFR-003；AC-NFR-003-01 | AUTH、ROUTER、INTAKE-ORCHESTRATOR | 只等待接收确认，不等待评分完成 |
| 30 并发 | `inherited` | NFR-002 | ROUTER、INTAKE-ORCHESTRATOR | 无状态接入、按 `submission_uuid` 隔离 |
| 评分、名单数据、教师端、保留治理 | `out-of-scope` | MOD-03/MOD-04/MOD-05 边界 | 不分配 | 仅作为协作约束引用 |

当前 PRD 的 FR/NFR 章节没有新增独立条目，架构输入约束使用待补充占位；由于父包已提供本节点所需的契约、状态、流程和部署绑定，本次不擅自补造父边界，也不构成阻塞。

## 4. 局部驱动与可复用能力

### 局部驱动

1. **短同步路径**：认证、幂等判断、会话完成、归属校验、单事务确认和响应映射必须在 30 秒预算内闭合。
2. **入口一致性**：同一 `submission_uuid` 重复请求返回既有结果，不重复创建提交或重复发布业务效果。
3. **所有权隔离**：API 只编排，不复制或写入兄弟聚合状态。
4. **失败可恢复**：可恢复上传中断进入父定义的恢复路径；名单不可用不向调用方暴露内部细节；终态错误按父错误码返回。
5. **可观测性**：以有效 CT-001 接入为起点，以 30 秒内 `received` 响应为成功点，沿用 LCD-009 的分母排除与标签口径。

### 可复用能力

- 父包 `IC-SI-01/03/04` 的字段、错误、幂等和 next-hop 约束。
- 父包 `ST-06` 令牌签发审计所有权。
- MOD-02 的单库/本地磁盘和 DU-2 部署边界。
- 父包已定义的 `CT-001/CT-002` HTTP 接口与六态外部状态值域。

## 5. 预检、阻塞缺口与交接验证

- **阻塞缺口**：无。当前 PRD 的占位约束由父包绑定信息补足，未发现需要改变父职责、契约、状态所有权、依赖方向、技术或部署的要求。
- **计划文件**：本 manifest、本文、02 分解、03 状态数据、04 契约运行时、05 局部决策、child-handoff，共七个文件。
- **上游影响**：无。MOD-01 仍使用原 CT-001/CT-002/auth-token。
- **下游影响**：无契约语义变化；SI-CORE/SI-XFER/SI-VERIFY 仅作为父包内部端口协作者。
- **验证方法**：检查唯一 target 匹配；使用入口绑定表将 CT-001/CT-002/auth-token 固定到 SI-API-ROUTER；逐条检查父契约字段/错误/幂等/版本不变；检查状态所有权；检查四个 child 的稳定 ID、追踪和排序；解析机器可读契约与 Mermaid 状态迁移；确认七文件清单。评分状态场景必须在 L1/system scope 运行，不在 AUTH child scope 内推断。

## 6. 假设与开放问题

- 令牌具体编码、密钥轮换、框架中间件实现仍属于父包 LCD-004 或实现细节，不在本层决定。
- 精确线程池、超时器、日志实现和框架配置不影响当前架构边界，留给实现阶段。
- Human Gate 需要重点审阅四 child 的职责边界、30 秒预算切片、CT-001/CT-002 字段映射和 ST-06 审计范围。
