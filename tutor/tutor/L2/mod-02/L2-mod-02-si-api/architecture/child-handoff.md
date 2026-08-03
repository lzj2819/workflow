# Leaf Gate Override ? SI-API

> **Authoritative:** This L2 node is a terminal leaf by explicit product-owner decision. Do not use any historical ?next layer?, `[NEXT]`, child, L3, or L4 instruction below to create further PRD or architecture nodes. Proceed directly to vibe coding in this node.

- Decision: `STOP_LAYERING`
- Children: `[]`
- Next action: `VIBE_CODING`
- Implementation details stay inside this node.

---

# Child Handoff — SI-API L2

## 1. 当前节点与父绑定

- `target_node_id`: `SI-API`
- 节点名称：`intake-api`
- 层级：L2；父包：`architecture/L1/L1-mod-02`
- 职责：CT-001/CT-002/auth-token 接入、认证、幂等、30 秒同步接收确认和请求级观测。
- 排除：Submission/UploadSession/MaterialFile/Outbox 所有权、评分、名单持久化、教师端、保留治理和新部署边界。
- 边界指纹：父 `architecture-manifest.yaml`、`01-design-context.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`child-handoff.md` 中的 SI-API、CT-001/002/003/004/005/006/012/014、IC-SI-01/03/04、ST-06、KD-002/003/004/005、DU-2。

## 2. 下一层 target_node_id 清单（按稳定 ID 排序）

| child_id | 一句话职责 | owned state | requirement/parent trace | 建议下一步 |
|---|---|---|---|---|
| SI-API-AUTH | 认证、Bearer 校验、auth-token 签发及 ST-06 审计 | ST-06、AuthContext | REQ-DD003、CT-001/auth-token、ST-06 | 细化 token 适配与审计字段，但不改变父端点 |
| SI-API-INTAKE-ORCHESTRATOR | CT-001/CT-002 接收编排、幂等与 30 秒预算 | IntakeAdmission（瞬态） | REQ-DD003、D-AC-REQ-007-01、IC-SI-01/03/04 | 优先细化端口顺序、预算和恢复分支 |
| SI-API-OBSERVABILITY | SM-001 与请求级诊断关联 | AdmissionTelemetry（瞬态） | SM-001、LCD-009、NFR-003 | 细化指标事件字段与脱敏策略 |
| SI-API-ROUTER | 公共端点路由、中间件和错误映射 | RequestContext（瞬态） | REQ-DD003、CT-001、CT-002、auth-token | 细化路由表和错误映射，但不升版本 |

以上四个 `child_id` 是本包精确的下一层 target；不要将 SI-XFER、SI-CORE、SI-VERIFY、SI-STORE、SI-RELAY、SI-PURGE 作为本包的 `[NEXT]` 目标，它们属于父包兄弟/内部支撑边界。

## 3. 契约注册表

### 3.1 继承契约

| contract_id | owner/consumer | 本层 child realization | 不变约束 |
|---|---|---|---|
| CT-001 | SI-API → MOD-01 | ROUTER → AUTH → ORCHESTRATOR → IC-SI-01/03/04 | 路径、字段、错误、30 秒、幂等不变 |
| CT-002 | SI-API → MOD-01 | ROUTER → AUTH → ORCHESTRATOR → IC-SI-04 query | 只读字段和 NOT_FOUND 不变 |
| auth-token | SI-API → MOD-01 | ROUTER → AUTH → IC-SI-03 → ST-06 | CT-001 契约族附属端点，不独立升版本 |
| CT-003 | MOD-03 → SI-VERIFY | ORCHESTRATOR 经 SI-VERIFY 支撑调用 | 实时校验，不缓存通过结论 |
| CT-004/006 | SI-CORE/SI-RELAY → MOD-04/MOD-05 | 本层只等待父端口结果 | owner、schema、触发时机和版本不变 |
| CT-005/012/014 | SI-RELAY/SI-PURGE 支撑链路 | 本层不直接消费/发布 | 由父支撑组件继续负责 |

### 3.2 Child-only contracts

`LC-SIAPI-001` 至 `LC-SIAPI-007` 的完整 owner、consumer、输入/输出字段、错误、重试、幂等和兼容说明见 `04-contracts-and-runtime.md` 第 3 节；这些契约仅限 DU-2 进程内，不是跨模块公共契约。公共入口 `ENTRY-CT-001`、`ENTRY-CT-002` 和 `ENTRY-AUTH-TOKEN` 固定落到 `SI-API-ROUTER`。

## 4. 状态所有权注册表

| state_id | owner | lifecycle | parent trace |
|---|---|---|---|
| ST-06 | SI-API-AUTH | issued/rejected/expired | parent ST-06 |
| ST-API-01 | SI-API-ROUTER | request-scoped | parent CT-001/002/auth-token |
| ST-API-02 | SI-API-INTAKE-ORCHESTRATOR | admitted/duplicate/rejected/received/timeout | parent FLOW-008/IC-SI-01/03/04 |
| ST-API-03 | SI-API-OBSERVABILITY | opened/recorded/exported | parent SM-001/LCD-009 |

父 ST-01/ST-02/ST-03/ST-04/ST-05 的 owner 未改变。

## 5. 决策、委托与风险

- **继承**：KD-002/003/004/005、LCD-001/003/009，不重开。
- **本层已决定**：LCD-SIAPI-001 至 LCD-SIAPI-005，以及 LCD-SIAPI-008，固化 child 边界、30 秒同步路径、认证策略、幂等承载、SM-001 口径和验证入口/跨层状态边界。
- **实现细节**：LCD-SIAPI-006，token 具体形态留给实现。
- **委托下一层**：LCD-SIAPI-007，下一层可细化中间件顺序、预算切片、端口适配和脱敏。
- **未决风险**：Human Gate 需关注 CT-001 字段映射、30 秒预算是否覆盖所有必要端口，以及 ST-06 审计字段的最小化；这些风险不改变父边界，未触发 parent change。
- **验证范围**：本包验证 CT-001/CT-002/auth-token 的入口、认证、接收确认、幂等、并发和观测；`received → processing → scored/scoring_failed` 与评分重试通知由 L1 MOD-02/MOD-04/MOD-05 系统场景验证，不归属于 SI-API-AUTH。
- **trace exemption**：无。四个 child 均有当前需求、指标或父契约/状态追踪。

## 6. 实际输入/输出与验证

### 实际输入

- `C:/Users/Lenovo/Desktop/codex_plugin/prd/L2-PRD/mod-02/L2-mod-02-si-api/prd.md`
- `C:/Users/Lenovo/Desktop/codex_plugin/architecture/L1/L1-mod-02`
- 用户确认的四 child 设计

### 实际输出

- `architecture-manifest.yaml`
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`

### 交接检查

| 检查 | 结果 |
|---|---|
| 父包识别与 `SI-API` 唯一匹配 | 通过 |
| 当前 PRD `REQ-DD003` → `REQ-D003` 追踪 | 通过 |
| 每个 child 有稳定 ID、职责、排除、状态、依赖与父/需求追踪 | 通过 |
| 父契约字段、owner、错误、幂等、版本未改变 | 通过 |
| 父/兄弟状态所有权未重新分配 | 通过 |
| 七文件齐全、YAML 可解析、注册表排序 | 通过 |
| 公共入口绑定、机器可读契约字段和局部状态迁移 | 已补充，需重新运行 strict audit |
| `parent-change-request.md` | 不创建；无 `return_to_parent` |

## 7. 推荐交接顺序

Human Gate 批准后，建议按 `[NEXT SI-API-INTAKE-ORCHESTRATOR]`、`[NEXT SI-API-ROUTER]`、`[NEXT SI-API-AUTH]`、`[NEXT SI-API-OBSERVABILITY]` 细化。每次下一层调用必须携带本包与 `architecture/L1/L1-mod-02` 的祖先上下文。
