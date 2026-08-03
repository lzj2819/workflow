# 01 Design Context — MOD-01 codex-plugin（L1 设计上下文）

## 1. 本次设计范围

- **目标节点**：`MOD-01 codex-plugin`（父包 L0 唯一匹配，匹配证据见 `architecture-manifest.yaml`）。
- **当前 PRD**：`prd/L1/L1-mod-01/prd.md`（REQ-D001~REQ-D004 + D-AC-REQ-001-01 / D-AC-REQ-002-01 / D-AC-REQ-003-01）。
- **模式**：`new`；输出目录 `architecture/L1/L1-mod-01`（写入前已确认为空目录，不覆盖既有包）。
- 本层只设计 MOD-01 内部结构；兄弟节点（MOD-02~MOD-05）仅作为协作约束引用，不重设计其内部。

## 2. 父边界快照（Boundary Snapshot）

以下条目逐条摘自父包，构成本层不可逾越的「墙、门和水电」。

### 2.1 身份与职责

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 稳定身份 | `MOD-01 codex-plugin`，来源 BC-SUBMISSION（采集侧 ACL） | 01 §模块清单 | inherited-fixed |
| 职责 | 识别自然语言提交意图；管理插件配置；采集完整对话与材料；分片上传；展示提交编号与失败原因；断网保留本地待上传任务 | 01 §模块职责 | inherited-refinable（内部拆分开放） |
| 排除项 | 无服务端契约；不归属校验；不持有 Submission；不参与评分/教师端 | 01、03、04 §组件接口卡 | inherited-fixed |
| 部署形态 | DU-1 student-plugin，学生本机 Codex 环境内；随学生机器分布，无服务端扩容 | 06 §部署单元 | inherited-fixed |

### 2.2 需求与验收契约追溯

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 父需求 | REQ-001~REQ-004（FR-001~FR-004） | 01 §模块清单 | inherited-fixed |
| 单模块 AC | AC-REQ-001-01（提交意图）、AC-REQ-002-01（配置）归属 MOD-01 | acceptance-contract-projections.yaml §全量盘点结论 | inherited-fixed |
| 共享 AC | AC-REQ-003-01 = shared；MOD-01 为 participating module，verification_slice：采集完整对话与目录材料、关联作业/姓名/小组、经 CT-001 分片上传、中断时本地保留并呈现原因、断点续传 | acceptance-contract-projections.yaml §AC-REQ-003-01 | inherited-fixed |
| 成功指标 | SM-001（提交接收成功率 ≥95%）Contributing Module：上传与断点续传链路 | 01 §Success Metric 分配 | inherited-fixed |

### 2.3 契约与外部边界

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| 消费契约 | CT-001（上传，Provider MOD-02）、CT-002（状态查询，Provider MOD-02）；认证端点 `POST /api/v1/auth/token` 为 CT-001 契约族附属 | 04 §CT-001/CT-002/通用约定 | inherited-fixed |
| 提供契约 | 无（`provides_contracts: []`） | 04 §组件接口卡 | inherited-fixed |
| local_inbound | 学生自然语言提交指令（assignment+student_name+group_name 必填，F1-1 缺任一项不创建提交）；Codex 对话导出与本地材料文件 | 04 §组件接口卡 | inherited-refinable |
| local_outbound | 提交编号与接收确认展示、失败原因与缺失项展示；本地待上传任务队列 | 04 §组件接口卡 | inherited-refinable |
| 外部系统 | Codex 运行环境：插件进程内集成 + 本机文件读取；ACL 语义「对话导出与本地文件 → 材料包模型」 | 01 §外部系统边界 | inherited-refinable（C5 委托 Adapter/ACL 内部细化） |
| 相关父运行流 | FLOW-001（CT-001，DU-1→DU-2）、FLOW-002（CT-002）；SCENARIO-001 主链路 entry 在 MOD-01；DF-1 步骤 1–3（F1-1/F1-2） | 02 §合法数据流/场景链路 | inherited-fixed |

### 2.4 继承决策、技术与约束

| 条目 | 内容 | 父包来源 | 分类 |
|---|---|---|---|
| KD-003 | 基础级运维：全部请求 HTTPS | 05、04 §通用约定 | inherited-fixed |
| KD-004 | 单次提交 ≤500MB；文件类型白名单（代码/文本/图片/常见文档/压缩包） | 05、04 §通用约定 | inherited-fixed（服务端权威判定；客户端预检开放） |
| KD-005 | 访问令牌（邀请码+姓名+小组换取）+ 客户端幂等键（submission UUID）+ 分片断点续传 + `/api/v1` 前缀 | 05、04 §通用约定 | inherited-fixed |
| A-007 | 插件本地待上传队列的实现细节 = implementation_detail，留待详细设计 | 05 §暂缓到详细设计 | delegated（下一层/详细设计） |
| 技术形态 | Codex Plugin 机制内实现，本地待上传队列 | 05 §技术组件选择 | inherited-fixed |
| 数据约束 | 材料含个人信息与第三方代码：HTTPS 传输；MOD-01 侧无服务端存储义务 | 06 §合规、03 | inherited-fixed |

### 2.5 状态与数据所有权

- MOD-01 **无服务端聚合所有权**（03 §数据所有权：Submission 归 MOD-02）。
- MOD-01 本地状态仅两类来源（04 §组件接口卡 local_inbound/local_outbound）：**插件配置** 与 **本地待上传任务** —— 其内部状态拆分（`inherited-refinable`）由本层 `03-state-and-data.md` 规定。
- 提交状态机（upload_failed/rejected/received/processing/...）归 MOD-02；MOD-01 仅经 CT-001/CT-002 感知并展示，不复制、不预判、不缓存归属校验结论（REQ-006 约束在服务端）。

### 2.6 委托与未解决项

| 条目 | 处置 | 说明 |
|---|---|---|
| A-007 队列持久化机制 | delegated → 详细设计 | 本层只定义队列的状态与协作语义 |
| 宿主 Codex 环境对话导出 API | delegated → 下一层 CMP-DIALOGUE-COLLECTOR 细化 | 父层仅规定「进程内集成 + 本机文件读取」的 ACL 语义，未规定具体导出机制；不影响本层结构 |
| 父层未决项（数据库选型、教师前端等） | 与本节点无关 | 不引用、不放大 |

**阻塞缺口：无。** 关键父状态/契约/部署/决策全部可得；当前 PRD 不要求改变父边界。

## 3. 当前 PRD 需求分配

分类口径：`inherited`（父层已定，本层原样遵守）/ `allocated`（父层分配给本节点，需本层结构设计承接）/ `local`（本层内部细节）/ `out-of-scope`（不属于本节点）。

| 当前需求 | 分类 | 父层追踪 | 本子层承接（子节点见 02） |
|---|---|---|---|
| REQ-D001 识别提交意图并启动提交 | allocated | REQ-001 / FR-001；F1-1；AC-REQ-001-01；CT-001 entry_condition | CMP-INTENT-PARSER、CMP-PENDING-QUEUE、CMP-UPLOAD-CLIENT、CMP-STATUS-PRESENTER |
| REQ-D002 插件配置管理 | allocated | REQ-002 / FR-002；AC-REQ-002-01；组件接口卡 local_inbound | CMP-CONFIG-STORE（+CMP-STATUS-PRESENTER 展示目录错误） |
| REQ-D003 采集完整 Codex 对话 | allocated | REQ-003 / FR-003；AC-REQ-003-01 MOD-01 slice；01 §外部系统边界（ACL） | CMP-DIALOGUE-COLLECTOR |
| REQ-D004 按配置收集材料并关联身份 | allocated | REQ-004 / FR-004；AC-REQ-003-01 MOD-01 slice；CT-001 `material_chunks[]`（类别标注） | CMP-MATERIAL-COLLECTOR |
| D-AC-REQ-001-01 | allocated | parent_acceptance_contract: AC-REQ-001-01（MOD-01 单模块契约） | 运行流 R1/R3（04）；CMP-INTENT-PARSER、CMP-PENDING-QUEUE、CMP-UPLOAD-CLIENT |
| D-AC-REQ-002-01 | allocated | parent_acceptance_contract: AC-REQ-002-01（MOD-01 单模块契约） | 运行流 R3（04）；CMP-CONFIG-STORE |
| D-AC-REQ-003-01（shared 的 MOD-01 slice） | allocated | contract_projection: MOD-01:shared；acceptance-contract-projections.yaml §AC-REQ-003-01 | 运行流 R1/R2（04）；CMP-DIALOGUE-COLLECTOR、CMP-MATERIAL-COLLECTOR、CMP-UPLOAD-CLIENT、CMP-PENDING-QUEUE |
| 30 秒接收确认感知 | inherited | NFR-003；CT-001 Error/Timeout（30 秒超时→CT-002 查询） | CMP-UPLOAD-CLIENT（超时转 CT-002，不改动时限语义） |
| 500MB / 类型白名单 | inherited | KD-004（服务端权威判定） | CMP-MATERIAL-COLLECTOR 客户端预检（LCD-003，不改变服务端权威） |
| HTTPS / 令牌 / 幂等键 / 分片续传 / `/api/v1` | inherited | KD-003、KD-005 | CMP-UPLOAD-CLIENT、CMP-PENDING-QUEUE |
| 成功指标 SM-001（contributing） | inherited | 01 §Success Metric 分配 | 本层无统计义务；保障上传/续传链路行为符合 CT-001 状态统计口径 |
| out-of-scope | — | 无 | 当前 PRD 全部需求均在 MOD-01 边界内；无错分给兄弟节点的条目 |

说明：当前 PRD「架构输入契约」继承 `../../L0-root/architecture/01-system-overview.md`、`03-data-and-consistency.md` 与 `04-interface-contracts.md`；本层不新增系统边界、外部依赖或跨模块约束。

## 4. 局部驱动（Local Drivers）

1. **确定性缺项检查（F1-1）**：缺作业/姓名/小组时不创建提交、不产生网络调用（FLOW-001 entry_condition），必须本地确定性判定，不能依赖概率性解析放行。
2. **断网韧性**：上传中断/无网络时任务本地保留、原因可见、恢复后断点续传（AC-REQ-001-01 exceptions、KD-005）——这是 MOD-01 区别于普通表单客户端的核心驱动。
3. **采集完整性**：完整对话（REQ-D003）与三类目录材料（REQ-D004）须关联到作业/姓名/小组并以类别标注进入 `material_chunks[]`。
4. **30 秒结果未知处理**：超时未获接收确认时不伪造结果，经 CT-002 查询真实状态（CT-001 Error/Timeout 语义）。
5. **实现面**：`implementation_surfaces = [domain_logic, worker_job, integration_wiring]` → 意图/配置/采集（domain_logic）、待上传队列的后台续传调度（worker_job）、CT-001/CT-002 HTTP 与分片（integration_wiring）。

## 5. 可复用能力

- 父包已固化的契约语义（CT-001 分片协议：创建上传会话→逐分片→提交合并；幂等键 submission UUID；令牌换取），本层直接实现 consumer 侧，不重新设计协议。
- 父包错误码表（AUTH_INVALID / VALIDATION_FAILED / PAYLOAD_TOO_LARGE / UNSUPPORTED_MEDIA_TYPE / REJECTED_MEMBERSHIP / NOT_FOUND）原样作为展示与恢复分支依据。
- 验收契约投影已给出 MOD-01 slice，可直接映射到子节点与运行流。

## 6. 拟创建/更新文件

`architecture-manifest.yaml`（draft→ready_for_human_gate）、`01-design-context.md`（本文件）、`02-architecture-decomposition.md`、`03-state-and-data.md`、`04-contracts-and-runtime.md`、`05-local-decisions.md`、`child-handoff.md`。无 `parent-change-request.md`（无 return_to_parent 项）。

## 7. 上下游契约影响

**无变更。** 本层不新增、改名、弱化或升级任何父契约；CT-001/CT-002 仅做 consumer 侧实现映射；不向兄弟节点提出新契约；不引入新外部系统。当前 PRD frontmatter `dependency_refs: [MOD-05, MOD-02, MOD-03]` 与父包数据流核对后确认：MOD-01 仅与 MOD-02 存在网络流（FLOW-001/002）；MOD-03（归属校验）与 MOD-05（失败原因教师可见）为端到端链路的间接相关方，不产生本节点的新跨边界依赖，本层不为它们创建任何接口。

## 8. 交接验证方法

阶段 6 以实际证据验证：① 四必需输入解析与唯一匹配证据（已记入 manifest）；② REQ-D001~D004 与 3 条 D-AC 全部分配且有子节点承接；③ 子节点清单含追踪列且无豁免缺省；④ CT-001/CT-002 字段、owner、失败/幂等/版本语义逐字未改；⑤ 状态清单确认 Submission 所有权未转移；⑥ 决策队列无遗留 `decide_now`、无 `return_to_parent`；⑦ 全部清单按稳定 ID 排序。

## 9. 假设、问题与冲突

| 类型 | 内容 | 处置 |
|---|---|---|
| 假设 | 学生指令中的作业/姓名/小组与配置中的姓名/小组可能不一致时，以**当次指令**为准进入提交（AC-REQ-001-01 trigger 以指令为准）；配置中的姓名/小组作为默认值与展示参考 | 记入 `05-local-decisions.md` LCD-001 后果 |
| 假设 | 配置不完整（如缺邀请码）时允许保存（D-AC-REQ-002-01 boundaries），但上传前置检查会阻塞并提示；不伪造 AUTH_INVALID | 运行流 R3 |
| 问题（非阻塞） | 宿主 Codex 环境的对话导出 API 父层未规定 | delegated，记入 `child-handoff.md` 未解决项 |
| 冲突 | 无 | dependency_refs 差异已在 §7 解释 |
