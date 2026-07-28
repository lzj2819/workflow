# Contract Freeze — tutor-r01

- 冻结源：`tutor/L0-root/architecture/04-interface-contracts.md`（SHA-256 `45999185…3efb9f`，见 run-manifest）+ 各 L1 包 `04-contracts-and-runtime.md` 的内部契约节。
- 状态：**正式冻结**（matrix gate 2026-07-19 批准生效）。机器可读 schema 已落地到 `tutor-app/contracts/`（17 个跨模块契约 + 内部契约索引）；任何变更必须走契约变更流程。
- **CCR-001（AssessmentResult 删除接线，TD-08）已由用户批准方案 A（2026-07-22）并实施**：CT-012 消费者扩展为 `[MOD-02, MOD-04, MOD-05]`（payload 不变），新增 CT-015 AssessmentPurgeCompleted（MOD-04 → MOD-05，语义镜像 CT-014），MOD-05 批次状态改为 CT-014+CT-015 双回流聚合。
- 机器可读权威：各契约末尾 `contract_fields` YAML 块（设计包约定：正文与 YAML 冲突时以 YAML 为准）；`contracts/*.json` 为其逐字段落地，不得反向修改设计语义。

## 跨模块契约（共享，禁止叶子修改）

| 契约 | 类型 | Provider → Consumer | 关键约束 |
|---|---|---|---|
| CT-001 提交材料包上传 | sync_api | MOD-02 → MOD-01 | multipart 分片+断点续传；幂等键 submission_uuid；≤500MB 白名单；30 秒接收确认；错误码 AUTH_INVALID/VALIDATION_FAILED/PAYLOAD_TOO_LARGE/UNSUPPORTED_MEDIA_TYPE/REJECTED_MEMBERSHIP |
| CT-002 提交状态查询 | sync_api_query | MOD-02 → MOD-01 | 只读幂等；404 未知 UUID |
| CT-003 课程归属校验 | sync_api | MOD-03 → MOD-02 | 每次提交重新调用、禁止缓存通过结论；ROSTER_UNAVAILABLE 保持待校验重试 |
| CT-004 SubmissionReceived | event | MOD-02 → MOD-04 | Outbox；v=1；消费方按 submission_id 幂等 |
| CT-005 SubmissionScored/ScoringFailed | event | MOD-04 → MOD-02、MOD-05 | outcome 二值；scored 四件套/scoring_failed 两件套；重复事件不改终态 |
| CT-006 SubmissionReceived（读模型） | event | MOD-02 → MOD-05 | received 或 upload_failed 终态发布（LCD-002）；可重放重建 |
| CT-007 教师课程数据查询 | sync_api_query | MOD-05 → 教师浏览器 | 课程范围授权，403 记 AccessDeniedLogged；含 deletion_batches[] 出参 |
| CT-008 教师批注与最终等级调整 | sync_api | MOD-05 → 教师浏览器 | 幂等键 request_id；保留原始/最终等级+操作者+时间；NO_ORIGINAL_GRADE 拒绝伪造 |
| CT-009 展示视图生成 | sync_api | MOD-05 → 教师浏览器 | 快照一次性写入；NO_AVAILABLE_SUBMISSION 拒绝；幂等再生成 |
| CT-010 模型评估推理 | external_api | 外部模型服务 → MOD-04（ACL） | 单次 ≤3 分钟；数据最小化（禁发 submission_id/姓名）；三分类错误计入重试一次策略 |
| CT-011 删除确认 | sync_api（执行为异步批处理） | MOD-05 → 教师浏览器 | BATCH_NOT_EXPIRED 拒绝；exclusions[]；审计先于清除 |
| CT-012 RecordsDeleted | event | MOD-05 → MOD-02、MOD-04（+MOD-05 自消费） | 审计记录永久留存不在删除范围；CCR-001：MOD-04 清除评分记录并保留最小墓碑 |
| CT-013 名单导入 | sync_api | MOD-03 → 教师浏览器/文件 | 前置「课程已创建」；按（姓名+小组）去重；逐项错误报告 |
| CT-014 PurgeCompleted | event | MOD-02 → MOD-05 | failed_items[] 保留重跑 |
| CT-015 AssessmentPurgeCompleted | event | MOD-04 → MOD-05 | CCR-001 新增；语义镜像 CT-014；按 batch_id+purged_at 去重 |
| （未编号）POST /api/v1/auth/token | sync_api | MOD-02 → MOD-01 | CT-001 契约族附属；名单核对语义同 CT-003 |
| FLOW-011 课程结束时间只读引用 | internal_read（无网络契约） | MOD-03 → MOD-05 | 同 DU-2 进程内只读；不得升级为网络契约 |

## 模块内契约（冻结于各 L1 包，L2 可演进实现但不得外溢语义）

- MOD-01：IC-M01-01~05（意图/配置/采集编排/上传执行/状态展示端口）。
- MOD-02：IC-SI-01~06（上传会话、材料存储、归属校验客户端、提交聚合、Outbox 中继、清除执行）。
- MOD-03：CP-COURSE-ENDTIME、CP-ROSTER-QUERY（模块内只读端口）。
- MOD-04：ICT-001~008（认领任务、提示编排、材料只读加载、模型调用、完成/失败、发布、度量）+ ICT-009（CT-012 消费：评分清除+墓碑+CT-015 发布；CCR-001）。
- MOD-05：M05-IC-01~06（复核记录创建、读模型查询、课程结束时间读取、CT-012 发布、模块内复核事件、删除治理读端口）+ M05-IC-07（CT-014+CT-015 双回流批次聚合；CCR-001）+ M05-BIND-* 绑定流。

## 已知契约缺口（登记，不是变更）

1. ~~GAP-01 → CCR-001~~ **已关闭（2026-07-23）**：用户批准方案 A（2026-07-22）；CT-012 消费者扩展 MOD-04、新增 CT-015、MOD-05 双回流聚合已实施（验收见 SCENARIO-016）。
2. **GAP-02**：课程创建/邀请码签发无公共契约，v1 运维预置（MOD-03 LCD-004）。教师自助建课需求出现时走 return_to_parent。
3. **GAP-03**：课程级数据（名单/校验记录）保留清除无契约，v1 运维清除（MOD-03 LCD-005）。

## 变更流程

任何叶子或集成工作中发现必须变更上表任一共享契约（字段、语义、错误码、版本、新增跨模块交互）：
1. 立即停止相关工作；
2. 产出 `contract-change-request.md`（现状、提案、影响面、回滚）；
3. 交用户决策（human gate: contract_change）；
4. 批准后更新本文件与 `contracts/` schema 并记录版本。
