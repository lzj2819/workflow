# Child Handoff — 子层交接（L1 / MOD-05 teacher-web）

> 本文件是下一层（L2）细化与 Human Gate 的入口。`[NEXT child_id]` 仅在本次 Human Gate 批准后使用。

## 1. 当前节点身份与父层绑定

- **节点**：MOD-05 teacher-web（L1），来源 BC-REVIEW + BC-RETENTION；DU-2 course-app 内部节点（非独立部署单元）。
- **职责**：教师课程/小组/学生/提交查询（课程范围授权）；批注与最终等级调整（保留原始等级与调整记录）；展示视图生成；评分失败可见；删除确认与审计查看。
- **排除项**：不持有 Submission/Course/AssessmentResult 聚合；不做归属校验；不接触模型服务；不伪造等级；不创建独立服务/容器/部署单元；不修改父契约。
- **边界指纹**：完整记录于 `architecture-manifest.yaml` boundary_fingerprint（父产物 8 组、契约 10 项、决策 KD-002/003/005 + A-001/003/005、所有权与部署约束）。

## 2. 下一层可选 target_node_id（直接 child_id，按稳定 ID 排序）

| child_id | 一句话职责 | 建议优先级 | L2 细化所需祖先上下文 |
|---|---|---|---|
| CMP-PRESENTATION | 展示视图生成与快照（CT-009） | **高** | REQ-D002 / AC-REQ-010-01 / D-AC-REQ-010-01；F4-1；A-003；LCD-004、LCD-008（defer 项在本节点落地） |
| CMP-REVIEW-COMMAND | 复核写侧、ReviewRecord 聚合（CT-008） | **高** | REQ-D001 写侧；FR-009；F3-2/F3-3；LCD-003、LCD-009（defer 项承接位） |
| CMP-REVIEW-QUERY | 教师查询读装配（CT-007） | 中 | REQ-D001 读侧；NFR-001 / AC-NFR-001-01；CT-007 出参完整性（含 deletion_batches[]） |
| CMP-TEACHER-UI | 教师网页前端 | 中 | REQ-D001/D002 frontend surface；LCD-007（渲染技术 defer 项在本节点落地）；A-005 通知展示面 |

> `CMP-ACCESS-GATE`、`CMP-READMODEL-PROJECTOR`、`CMP-RETENTION-GOVERNANCE` 为内部支撑组件，不作为 L2 target。`CMP-RETENTION-GOVERNANCE` 若需继续细化，必须先在 L1 PRD 中确认并投影 current `NFR-Dxxx`。

## 3. 契约清单

**继承父契约（语义不可变，L2 仅可按 04 §1 实现映射继续落地）：**
- 提供：CT-007（查询）、CT-008（复核写）、CT-009（展示）、CT-011（删除确认）
- 消费：CT-005、CT-006、CT-014；发布+自消费：CT-012
- 内部读取：FLOW-011（MOD-03 课程结束时间，无网络契约，范围不得扩展）

**本层内部契约（MOD-05 限定，L2 可演进但不得外溢语义）：**
- M05-IC-01 创建复核记录（PROJECTOR→COMMAND，幂等）
- M05-IC-02 读模型查询端口（PROJECTOR owner；QUERY/PRESENTATION 消费）
- M05-IC-03 课程结束时间读取（RETENTION→MOD-03）
- M05-IC-04 CT-012 发布端口（RETENTION→Outbox）
- M05-IC-05 复核模块内事件（COMMAND→PROJECTOR）
- M05-IC-06 删除治理读端口（RETENTION owner；QUERY 批次视图 / PROJECTOR 重放守卫）

**本层机器可读绑定与合法流：**
- `M05-BIND-FLOW-009-BROWSER-UI`：教师浏览器 → CMP-TEACHER-UI
- `M05-BIND-CT-007-*`：UI → ACCESS-GATE → REVIEW-QUERY
- `M05-BIND-CT-008-*`：UI → ACCESS-GATE → REVIEW-COMMAND
- `M05-BIND-CT-009-*`：UI → ACCESS-GATE → PRESENTATION
- `M05-BIND-CT-011-*`：UI → ACCESS-GATE → RETENTION-GOVERNANCE
- `M05-BIND-CT-005/006/012/014-*`：跨模块事件到 PROJECTOR / RETENTION-GOVERNANCE
- `04-contracts-and-runtime.md` §2.1 `local_legal_flows`：L2 不得引入未声明的组件边或改变父层 FLOW-007~012 语义。

## 4. 状态所有权清单（L2 不得跨子节点转移）

| 状态 | owner | 关键约束 |
|---|---|---|
| ST-ACCESS-DENIED-LOG | CMP-ACCESS-GATE | 追加式审计，不随提交删除 |
| ST-DELETION-BATCH（含审计记录） | CMP-RETENTION-GOVERNANCE | 审计先行、永久留存、不在删除范围 |
| ST-IDEMPOTENCY-DELETION / PRESENTATION / REVIEW | 各命令子节点 | 与业务写入同事务 |
| ST-PRESENTATION-VIEW | CMP-PRESENTATION | 一次性快照；随批次擦除内容 |
| ST-PROJECTION-CHECKPOINT | CMP-READMODEL-PROJECTOR | 位点与投影同事务 |
| ST-READ-MODEL | CMP-READMODEL-PROJECTOR | 派生可重建；重放守卫过滤已清除数据 |
| ST-REVIEW-RECORD | CMP-REVIEW-COMMAND | 原始等级复制值不可变；调整四元组留痕 |
| ST-TEACHER-ACCESS-GRANT | CMP-ACCESS-GATE | MOD-05 内部授权数据（LCD-006） |

## 5. 决策与未解决风险

- **继承决策（不得修改）**：KD-002、KD-003、KD-005；父 03/04/06 全部边界语义；数据库产品选型继续搁置。
- **本层已决（L2 遵循）**：LCD-001 通知并入投影；LCD-002 按所有者分散消费；LCD-003 复核记录统一经 M05-IC-01 创建；LCD-004 展示快照源自读模型；LCD-005 擦除+重放守卫；LCD-006 授权数据本地持有。
- **已委托 L2**：LCD-007 前端渲染技术（→CMP-TEACHER-UI）；LCD-008 展示导出格式（→CMP-PRESENTATION）；LCD-009 调整理由强制与否（产品决策，→CMP-REVIEW-COMMAND 承接）。
- **未解决风险/开放问题**：
  - Q-02（01-design-context）：无提交课程是否需对教师可见——若产品提出，须回父层新增课程目录投影来源（return_to_parent 路径已标注）。
  - LCD-004 已识别：刚调整立即生成展示时读模型可能秒级滞后，由 CT-009 幂等再生成吸收；L2 不得为此引入跨模块同步读。
  - Q-04：教师多角色/自助授权需求出现时，TeacherAccessGrant 模型需回父层评估。

## 6. 追踪豁免

直接 child_id 需求所有权：4 个直接子节点均拥有 current `REQ-Dxxx`；3 个内部支撑组件保留契约/流程/状态追踪但不作为 L2 target。

## 7. 实际输入 / 输出与验证证据

**实际解析输入**：`parent_architecture=architecture/L0/output`；`target_node_id=MOD-05`；`current_prd=prd/L1/L1-mod-05/prd.md`；`parent_prd=prd/L0/vibe-coding-course-prd.md`（可选，实际读取）；`output_dir=architecture/L1/L1-mod-05`；`mode=new`。

**实际生成输出（7 个文件）**：`architecture-manifest.yaml`、`01-design-context.md`、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。

**实际执行的检查及结果**：

| 检查 | 结果 |
|---|---|
| 四项必需输入解析 + 输出目录为空（new 安全） | 通过 |
| 目标节点唯一匹配（01 模块清单 / 04 接口卡 / 06 部署映射 + L1 PRD frontmatter 交叉确认，共 4 条证据） | 通过 |
| 当前 PRD 不越父边界（REQ-D001/D002 ⊆ REQ-009/REQ-010，无父契约变更诉求） | 通过 |
| 每个直接 child_id 拥有 current REQ-D/NFR-D；内部支撑不进入 direct children | 待复验（4 个直接 child_id；3 个内部支撑组件） |
| C1–C6 映射齐备（C1=02§3；C2=03§1；C3=04§3；C4=04§1；C5=04§2 M05-IC-03/04+FLOW-011；C6=01§4→03/04 策略） | 通过 |
| 父契约逐字段不可变（路径/字段/错误码/幂等/版本与父 04 比对；04 §5 自检） | 通过 |
| 状态所有权不越界（仅 ReviewRecord/PresentationView/DeletionBatch + 派生/内部状态；03 §5 确认） | 通过 |
| 兄弟节点仅引用未重设计（02 §4 确认；与 MOD-01 无交互） | 通过 |
| 决策队列清零：decide_now 6/6 已决，无 return_to_parent | 通过 |
| 带 ID 清单按稳定 ID 排序（CMP / ST / M05-IC / LCD） | 通过 |

**未完成项及阻塞影响**：无阻塞项。3 项 defer_to_next_level（LCD-007/008/009）与 4 项 implementation_detail 已登记目标与触发条件，不影响本包进入 Human Gate。

## 8. Human Gate

本包状态：`ready_for_human_gate`。可用命令：`[APPROVE]` / `[REVISE phase-N]` / `[EXPLAIN decision-id]` / `[PARENT_CHANGE]` / `[NEXT child_id]`（建议首批：`CMP-REVIEW-COMMAND`、`CMP-READMODEL-PROJECTOR`、`CMP-RETENTION-GOVERNANCE`、`CMP-PRESENTATION`）。
