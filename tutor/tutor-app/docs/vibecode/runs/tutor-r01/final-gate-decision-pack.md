# Final Gate Decision Pack — tutor-r01

- 日期：2026-07-22；基线：main `87ae372`
- 编制：Integration Owner / Workflow Coordinator
- 用途：供用户逐项审批。每项含方案、影响、验证条件、风险与建议。**本文档不修改任何冻结契约与业务代码；批准前不执行任何方案。**

---

## D-1 TD-01：REQ-003 完整 Codex 对话采集

### 背景

REQ-003（每次提交采集当前作业项目相关的完整 Codex 对话）依赖宿主 Codex 环境的对话导出能力。TD-01 未确认该机制是否存在/可自动化/可授权。当前状态：L07 未启动；host port 显式 `HostUnsupportedError`；插件对 unsupported 如实呈现（不伪造、不静默降级）。对话材料在 CT-001 材料类别中占「对话」一席，缺失时按 REQ-011 显式标记 missing_items。

### 方案 A：实现宿主导出适配（关闭 TD-01）

- 内容：确认宿主真实导出接口/格式/权限模型 → 实现 L07（CMP-DIALOGUE-COLLECTOR）真实适配 → 集成验证（对话导出物完整性校验、INV-4 快照重传不重采）。
- 影响：REQ-003 可宣称完成；「对话」missing_items 消失；学生材料包完整度提升；评估维度「Codex 迭代过程」获得真实输入。
- 验证条件：宿主导出机制文档/实测证据；导出物满足 dialogue-export-port 形状（format_version/source_host/exported_at/turns[] 完整非截断）；权限与授权链路明确（学生知情/同意）。
- 风险：宿主无官方导出能力 → 转为方案 B；导出能力弱（仅当前会话/需手动）→ 完整性打折；隐私面扩大（对话可能含第三方信息）。
- 预估工作量：宿主确认后 1 个叶子周期（L07 任务包已就绪）。

### 方案 B：从本版本范围正式移除或降级（产品决策）

- 内容：宣布首版不采集「对话」类别（REQ-003 标记 out_of_version 或降级为「可选材料」），missing_items 中「对话」作为明示默认状态呈现。
- 影响：**属产品范围变更**——REQ-003 是 Must Have，移除需修改 PRD/范围声明（走 return_to_parent / 正式范围变更流程，非本仓库可自决）；评估维度「Codex 迭代过程」无输入（rubric 需降级说明）；SM 指标口径需重述。
- 验证条件：产品范围变更批准；教师端缺失标记文案确认；rubric 对无对话输入的降级措辞。
- 风险：产品价值主张削弱（过程评估是本产品核心卖点）；范围变更流程成本。

### 方案 C：暂不发布（等待 TD-01 解除）

- 内容：发布整体推迟到宿主导出能力确认后。
- 影响：全部其他已验证能力被一并延迟；课程时间窗风险。
- 验证条件：无（纯排期决策）。
- 风险：错过课程周期；阻塞感转移到排期。

### 协调者建议

优先核实宿主导出能力（方案 A 前置调研，成本最低）；若宿主确无能力，走方案 B 的正式范围变更而非带病发布；不建议方案 C（除非课程窗口充裕）。

**待你决策**：A / B / C，或先授权宿主调研（只读、不读未授权会话文件）。

---

## D-2 CCR-001：AssessmentResult 到期删除契约变更

### 背景

NFR-004/AC-NFR-004-01 要求「提交内容和评分记录」到期删除。现行冻结契约 CT-012 消费者为 `[MOD-02, MOD-05]`，不含 MOD-04；AssessmentResult（scoring_results / scoring_tasks）不在删除接线内。retention_drill 已实证：提交侧删除链路可用且**评分结果未被删除**（缺口证据）。现状完全符合冻结契约——缺口在契约本身（设计包 MOD-04 Q-001 已登记）。

### 正式变更方案（推荐方案 A，源自 contract-change-request.md）

1. **CT-012 消费者集合扩展为 `[MOD-02, MOD-04, MOD-05]`**。payload 不变（batch_id、submission_ids[]、scope、operator、executed_at、audit_record_id、v=1 已足够）；幂等语义不变。
2. **新增 CT-015 AssessmentPurgeCompleted**（event，MOD-04 → MOD-05，v=1）：必填 batch_id、purged_submission_ids[]、failed_items[]（submission_id+reason）、purged_at、v；幂等按 batch_id+purged_at；语义镜像 CT-014。
3. **MOD-04 清除行为**：按 submission_ids[] 删除 AssessmentResult 业务内容与 ScoringTask；保留最小墓碑（submission_id、batch_id、purged_at）用于重放守卫（拒绝旧 CT-005 事件重建已删结果）；墓碑不含评分内容。
4. **回流聚合**：MOD-05 批次完成 = CT-014（MOD-02）与 CT-015（MOD-04）双到达合并判定（全部成功 / 部分失败）。
5. **审计**：DeletionBatch 审计记录仍 MOD-05 持有、先于清除写入、永久留存；CT-015 到达后追加 MOD-04 清除结果（审计只增不删）。
6. **失败重跑**：MOD-04 清除部分失败 → CT-015 failed_items[]；原批次重跑触发 CT-012 重发（幂等），两侧各自重跑失败项。

### 影响面

| 对象 | 变更 |
|---|---|
| 契约文档 | contracts/ct-012.json consumer 扩展；新增 contracts/ct-015.json；contract-freeze 更新（GAP-01 关闭） |
| 代码（批准后） | MOD-04：CT-012 消费 handler + 清除执行 + 墓碑 + CT-015 发布（B-02 追加任务）；MOD-05：批次状态双回流聚合（B-03 小改）；MOD-02：无影响 |
| 迁移 | MOD-04 墓碑表 1 张（新 migration，down_revision=当前单头） |
| 验收 | 见下 |

### SCENARIO-016 验收条件（批准后执行）

1. 到期批次经 CT-011 确认后：提交材料/记录、读模型、**AssessmentResult** 均不可被教师端读取；
2. CT-012/CT-014/CT-015 三事件载荷与契约一致且幂等（重放不改终态）；
3. 部分失败（分别注入 MOD-02/MOD-04 清除失败）→ 批次 partially_failed，失败项重跑成功 → completed；
4. 审计记录完整（范围/操作者/时间/两侧清除结果）且永久留存；
5. 重放守卫：清除后重放旧 CT-005 事件不重建已删数据；
6. AC-NFR-004-01 按上述条款正式执行并通过。

### 备选（不推荐）

- 方案 B（仅匿名化）：违背 NFR-004「删除」口径与数据最小化；
- 方案 C（MOD-02 同步代理删除）：引入 DU-2→DU-3 同步依赖，违背故障隔离。

**待你决策**：批准方案 A / 选 B / 选 C / 退回修订。**批准前 CT-012/CT-014 保持冻结、不实施。**

---

## D-3 received → processing 生产接线点

### 背景

LCD-003：CT-004 投递确认（MOD-04 评分任务持久化）后，Submission 从 received 推进到 processing。当前组合根未含该自动接线（E2E 由脚本显式 ack）；生产若无接线，提交将停在 received，CT-005 到达时 apply_scoring_outcome 因 expected_state=processing 失败。

### 实现位置（建议）

DU-2 relayer 的 **CT-004 确认后钩子**：由于 CT-004 由 DU-3（进程外）消费并确认，DU-2 需要一个观察点。两个候选：

- **A（推荐）**：DU-2 relayer 每轮 poll 后，扫描 outbox_records 中 `contract_id='CT-004' AND status='confirmed' AND advanced=0` 的记录，调用 `core_service.advance_to_processing(submission_id, consumer_ack='task_persisted')` 并标记 advanced（新列或入站去重表承载）。幂等（重复推进为空操作，L02 已实现）。
- B：DU-3 worker 确认后经新网络回调通知 DU-2——引入新契约（需 CCR），不推荐。

### 失败处理

- advance 失败（非法状态）：该提交记录失败原因并告警（metrics counter `advance_processing_failed_total`），不阻塞其他记录；
- 提交中途 upload_failed/rejected：advance 为空操作（L02 守卫），无噪音；
- relayer 崩溃：记录持久化，重启后扫描继续。

### 监控

- 指标：`received_not_processing_seconds`（received 未推进时长表盘）、`advance_processing_failed_total`；
- 告警：received 超过 60s 未推进（意味着 worker/接线故障）。

### 验收测试

1. E2E：提交后不经手工 ack，relayer 自动推进 received→processing，CT-005 正常回写 scored；
2. 幂等：重复扫描不重复推进（状态稳定）；
3. 失败注入：advance 异常时记录告警且不影响其他提交；
4. SCENARIO-001 在无手工驱动下全自动通过。

**待你决策**：批准实现方案 A（小增量集成工作，归 Integration Owner），或指定其他位置。

---

## D-4 正式性能与部署环境验收

### 压测场景（对应 AC-NFR-001/002/003）

| 场景 | 数据规模 | 指标阈值 | 方法 |
|---|---|---|---|
| AC-NFR-001 规模验证 | 100 学生 / 20–50 小组 / 全量名单导入 + 创建、查询、展示 | 全部操作正常完成 | 种子脚本生成规模数据 → CT-013 导入 → 教师端列表/详情/展示视图遍历 |
| AC-NFR-002 并发接收 | 30 并发提交，持续 5 分钟 | 成功接收率 ≥95% | 压测工具（自研 probe 的 uvicorn 真服务版或 k6/locust）打 CT-001，含分片上传 |
| AC-NFR-003 时限 | 课程期间有效提交 | ≥95% 在 30s 内接收确认；≥95% 在 10min 内完成评分 | 压测窗口内埋点统计（received_at 与 scored_at 差值）；评分用真实供应商或校准过的 fake 延迟 |

### 部署前置条件

- 部署环境就绪（deploy-runbook §0-1 完成：迁移单头、课程/教师预置、备份任务、磁盘加密、health/ready 全 ok）；
- received→processing 接线（D-3）已上线；
- 监控指标（received_not_processing_seconds、SM-001~003 计数）可抓取；
- 压测用课程与学生名单为测试域（与生产数据隔离）。

### 通过标准

- 三项 AC 全部达到阈值且证据（压测报告 + 原始数据）归档；
- 失败重试行为在压测中可观测（无伪造状态、无重复提交）；
- 压测后数据清理走 CT-011/CT-012 流程（顺带复核删除链路，注意 CCR-001 边界）。

**待你决策**：批准压测计划与工具选型（自研 probe 扩展 vs k6/locust），以及执行环境（本机 docker vs 目标云主机）。

---

## D-5 真实模型供应商接入合规（接入前必读；本阶段不接入、不发送真实数据）

### 必须逐项批准的事项

| # | 事项 | 要求 |
|---|---|---|
| 1 | 供应商与模型选择 | 明确供应商/模型版本/区域端点；供应商数据处理协议（DPA）获得并归档；禁止默认"提升计划"条款 |
| 2 | 数据最小化（KD-001 既有） | CT-010 请求仅含 evaluation_prompt + materials（dialogue_summary/code/result_description）；**禁发 submission_id、学生姓名、小组、课程标识**（代码已强制校验）；材料内容经截断预算（三桶 4000/8000/2000 字符） |
| 3 | 学生材料外发授权 | 课程层面取得学生/校方知情同意（文本存档）；教师可见的外发说明；敏感文件类型白名单复核 |
| 4 | 密钥管理 | API key 仅存环境变量/密钥管理（`MODEL_API_KEY`）；不入库、不入日志、不入仓库；轮换流程明确；泄露处置（吊销+轮换+审计） |
| 5 | 保留与删除 | 供应商侧数据保留策略（零保留或最短）；删除请求链路；与 NFR-004 到期删除的供应商侧对齐 |
| 6 | 审计 | 每次调用的 request_id 与结果分类记录（不发内容）；失败三分类（MODEL_TIMEOUT/ERROR/INVALID_SCHEMA）可观测；SM-002/003 统计接入 |
| 7 | 回退 | 一键切回 `MODEL_PROVIDER=fake`（或下线评分）能力；供应商不可用窗口的 scoring_failed 兜底（已有）与教师通知（已有端内通知） |
| 8 | 强化超时 | 真实接入时为 ACL 增加强制超时层（当前为事后判定） |

### 当前状态（证据）

- 最小化校验：`worker/assessment_worker/model_provider.py::validate_request` + `model_acl` 出站守卫，测试锁定（禁发业务标识）；
- fake 链路：全链路 E2E 通过（FakeVendorAdapter，来源标注）；
- 未配置任何真实密钥；未发送任何真实数据。

**待你决策**：是否启动供应商评估（以及是否允许我先做只读的供应商条款调研）；接入排期定在 CCR-001/TD-01 决策之后。

---

## 附：最终发布阻塞简表（见会话输出）

本决策包五项全部落定前，final gate 不批准。
