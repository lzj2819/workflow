# Child Handoff — MOD-03 course-roster（L1 交接）

## 1. 节点身份与父绑定

| 条目 | 内容 |
|---|---|
| 当前节点 | `MOD-03 course-roster`（L1；父节点即 L0 包中的 MOD-03 本身） |
| 职责 | 课程、邀请码、名单（姓名+小组）维护；每次提交的归属校验（不缓存通过结论）；提供课程结束时间供保留治理引用 |
| 排除项 | 不消费/不发布任何契约事件；不持有兄弟聚合；不参与评分与教师端展示；不执行保留清除；不承接成功指标 |
| 父绑定 | 父包 `architecture/L0/output`（top_level_ddd_to_system_package）；匹配证据见 `architecture-manifest.yaml` §node_match_evidence（五处 exact_unique + 一处 cross_confirmation） |
| 部署 | DU-2 course-app（与 MOD-02/05 共部署）；直接 child_id 与内部支撑均在 DU-2 内，无新部署边界 |

**Boundary fingerprint（本包引用的父级锚点）**：CT-003、CT-013、FLOW-003、FLOW-011；Course 聚合所有权与不变量（父 03）；KD-002、KD-003、KD-005；A-002；AC-REQ-003-01（shared，MOD-03 slice）、AC-REQ-006-01（单模块投影）；DF-1 步骤 4–5（F1-4）、DF-3 步骤 1；DU-2。完整清单见 manifest §boundary_fingerprint。

## 2. 叶子节点实现边界

| component_id | 名称 | 一句话职责 | 拥有状态 | 实现契约 |
|---|---|---|---|---|
| `CMP-MEMBERSHIP-VERIFIER` | 归属校验 | CT-003 端点、校验策略 P1–P5、逐条校验记录、ROSTER_UNAVAILABLE 映射 | ST-VERIFICATION-RECORD | CT-003（provider）、CP-ROSTER-QUERY（consumer） |

> MOD-03 是 L1 叶子节点。`CMP-MEMBERSHIP-VERIFIER` 与 `CMP-COURSE-ROSTER-ADMIN` 均为内部实现组件，不作为 L2 target；实现阶段直接依据本包契约、状态与本地决策落地。

## 3. 契约清单

### 3.1 继承契约（语义不变，详见 04 §1）

| contract_id | Provider→Consumer | 类型 | 实现子节点 |
|---|---|---|---|
| CT-003 课程归属校验 | MOD-03 → MOD-02 | sync_api | CMP-MEMBERSHIP-VERIFIER |
| CT-013 名单导入 | MOD-03 → 教师浏览器/名单文件 | sync_api | CMP-COURSE-ROSTER-ADMIN |
| FLOW-011 课程结束时间只读引用 | MOD-03 → MOD-05 | internal_read（无网络契约） | CMP-COURSE-ROSTER-ADMIN |

### 3.2 子级契约（模块内/继承边界内，详见 04 §3）

| contract_id | Provider→Consumer | 类型 | 要点 |
|---|---|---|---|
| CP-COURSE-ENDTIME | CMP-COURSE-ROSTER-ADMIN → MOD-05 | 模块内只读端口 | FLOW-011 的实现形态；只读；不得升级为网络契约 |
| CP-ROSTER-QUERY | CMP-COURSE-ROSTER-ADMIN → CMP-MEMBERSHIP-VERIFIER | 模块内只读端口 | 每次 CT-003 调用直读当前已提交名单；不允许结论缓存 |

## 4. 状态所有权清单

| state_id | 状态 | Owner | 一致性要点 |
|---|---|---|---|
| ST-COURSE | Course 聚合（课程/邀请码/名单/课程结束时间） | CMP-COURSE-ROSTER-ADMIN | 单聚合本地事务；邀请码唯一（P1）；导入去重键（course_id+姓名+小组） |
| ST-VERIFICATION-RECORD | 校验记录（append-only 审计） | CMP-MEMBERSHIP-VERIFIER | 结论与记录同事务（P4）；按调用逐条、不去重 |

## 5. 决策登记

- **继承（inherited，不可改）**：KD-002、KD-003、KD-005；A-002；CT-003/CT-013 全部契约语义；FLOW-011 无网络契约形态；数据库产品选型暂缓（父层 defer）。
- **本地已决（LCD，详见 05 §1）**：LCD-001 两子节点划分；LCD-002 每次直读无缓存；LCD-003 校验记录模型与调用方关联；LCD-004 v1 课程/邀请码运维预置；LCD-005 课程级数据保留对齐课程结束+1 年。
- **委托下一层（defer_to_next_level）**：数据库产品选型（继承）；拒绝原因编码枚举；名单文件格式与冲突判定细则；邀请码生成规则；校验超时预算毫秒值与内部调用鉴权方式。
- **未解决风险/开放问题**：
  1. 观察项 1：`identity_validation_failed` 状态名属 MOD-02 状态机细化（父包 FLOW-003 为「保持待校验并重试」），对 MOD-03 无契约影响 → **MOD-02 L1 设计时核对**。
  2. 观察项 2：课程创建/邀请码签发无父级公共契约，v1 运维预置；若产品提出教师自助建课 → **return_to_parent**（新增父级契约）。
  3. 观察项 3：课程级数据（名单/校验记录）保留清除无父级契约；若需契约化清除流程 → **父层补充**。
  4. 开放问题：「课程已结束的提交是否拒绝」父包未定义，本层显式未增设 → 如需该策略由父层决策。

## 6. 叶子节点实现输入

| 建议顺序 | 实现组件 | 实现重点 | 所需祖先上下文 |
|---|---|---|---|
| 1（建议） | `CMP-MEMBERSHIP-VERIFIER` | 校验执行组件、原因编码落地、记录模型落地、超时预算 | 本包 04 §1.1（CT-003 逐字契约）、03 §1（ST-VERIFICATION-RECORD）、05 LCD-002/003；父包 CT-003、FLOW-003、REQ-005/006 |
| 2 | `CMP-COURSE-ROSTER-ADMIN` | 导入解析与冲突细则、授权留痕落地、预置工具形态、课程结束时间端口落地 | 本包 04 §1.2/§3、03 §1（ST-COURSE）、05 LCD-004/005；父包 CT-013、FLOW-011、A-002、KD-003/005 |

两项内部实现之间无顺序阻塞，可并行实现；任一实现时不得修改本包 04 §1 的继承契约语义与 03 §1 的所有权分配。

## 7. 交接清单

**实际解析输入**：`parent_architecture=architecture/L0/output`；`target_node_id=MOD-03`；`current_prd=prd/L1/L1-mod-03/prd.md`；`output_dir=architecture/L1/L1-mod-03`；`mode=new`；`parent_prd` 未读取（父包追踪充分）。

**实际生成输出**（7 个文件，无 `parent-change-request.md`）：

- `architecture-manifest.yaml`（L1 叶子节点，`children: []`）
- `01-design-context.md`
- `02-architecture-decomposition.md`
- `03-state-and-data.md`
- `04-contracts-and-runtime.md`
- `05-local-decisions.md`
- `child-handoff.md`（本文件）
- `06-leaf-decision.md`

**执行的检查与结果**（与 manifest §validation 一致）：① 输入解析与唯一匹配——通过；② 需求/验收契约完整保留在 MOD-03——通过；③ MOD-03 不存在直接子节点——通过；④ 继承契约语义逐字未改——通过；⑤ 状态所有权未重分配——通过；⑥ 决策队列无遗留 decide_now、无 return_to_parent——通过；⑦ 清单按稳定 ID 排序——通过；⑧ 未引入新部署单元/事件/总线/公共边界——通过。

**未完成项及阻塞影响**：仅 §5 四个非阻塞观察项/开放问题；**无阻塞影响**，本包内部一致，可在 Leaf Gate 通过后直接进入实现。

## 8. Human Gate 命令

```text
[APPROVE]                  批准本包，随后直接进入实现
[REVISE phase-N]           按阶段号修订（1 输入绑定 / 2 需求分配 / 3 分解 / 4 契约运行时 / 5 决策 / 6 交接）
[EXPLAIN decision-id]      解释 LCD-001 ~ LCD-005 任一决策
[PARENT_CHANGE]            发起父级变更请求（如教师自助建课 API）
[STOP_LAYERING]
```
