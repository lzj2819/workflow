# Execution Matrix — tutor-r01（17 叶子）

- 状态：**approved**（matrix human gate，用户批准，2026-07-19）。
- 范围依据：`tutor/L2/leaf-gate.L2-terminal.md`（16 个 L2 STOP_LAYERING）+ `tutor/L1/L1-mod-03/architecture/06-leaf-decision.md`（MOD-03 L1 终端叶子）。
- 目录为草案（Phase 1 脚手架固化，变更需更新本矩阵并记录）。

## 波次定义

- **Wave 1**：无跨叶子运行时依赖（或仅依赖已冻结契约，可用 mock 开发）。
- **Wave 2**：依赖 Wave 1 叶子的内部端口或父级聚合。
- **Wave 3**：依赖 Wave 1/2 产出的事件流与读模型（可用录制事件夹具提前开发，但集成验证排在最后）。

## 叶子矩阵

| # | leaf_id | 父模块 | DU | 波次 | allowed_paths（草案） | 依赖（叶子级） | 契约（提供/消费） | 验收锚点 |
|---|---|---|---|---|---|---|---|---|
| L01 | MOD-03 course-roster（整模块，L1 叶子；内部组件 CMP-MEMBERSHIP-VERIFIER + CMP-COURSE-ROSTER-ADMIN） | L0 | DU-2 | W1 | `server/course_app/course_roster/**` | 无 | 提供 CT-003、CT-013；提供 CP-COURSE-ENDTIME（FLOW-011 只读端口）；不消费/不发布事件 | AC-REQ-003-01（shared slice）、AC-REQ-006-01；REQ-005/006 |
| L02 | SI-CORE | MOD-02 | DU-2 | W1 | `server/course_app/submission_intake/core/**` | 无（CT-003 经 SI-VERIFY 客户端，backfill 接线） | Submission 聚合/状态机；IC-SI-04 owner；经 RELAY 消费 CT-005/CT-012 | AC-REQ-003-01、AC-REQ-007-01（owning）；INV-1~5 |
| L03 | CMP-SCORING-ORCHESTRATOR | MOD-04 | DU-3 | W1 | `worker/assessment_worker/scoring_orchestrator/**` | 无（CT-004 事件可 mock） | 消费 CT-004（submission_id 幂等）；ICT-001 ClaimScoringTask；任务状态机/租约 | AC-REQ-007-01 MOD-04 slice；REQ-012 重试一次 |
| L04 | CMP-CONFIG-STORE | MOD-01 | DU-1 | W1 | `plugin/src/config_store/**` | 无 | IC-M01-02 配置端口 owner；ST-01 PluginConfig | AC-REQ-002-01；INV-3 |
| L05 | CMP-INTENT-PARSER | MOD-01 | DU-1 | W1 | `plugin/src/intent_parser/**` | 无 | IC-M01-01 owner；确定性缺项闸门（LCD-001） | AC-REQ-001-01；F1-1 |
| L06 | CMP-MATERIAL-COLLECTOR | MOD-01 | DU-1 | W1 | `plugin/src/material_collector/**` | L04（读目录配置，经冻结端口） | IC-M01-03 材料侧；ST-03 MaterialManifest；KD-004 白名单/预算 | AC-REQ-003-01 MOD-01 slice；REQ-004 |
| L07 | CMP-DIALOGUE-COLLECTOR | MOD-01 | DU-1 | W1（**TD-01 解除前 blocked**） | `plugin/src/dialogue_collector/**` | 无（依赖宿主导出能力） | 采集侧 ACL；ST-02 对话导出物；INV-4 快照重传不重采 | AC-REQ-003-01 MOD-01 slice；REQ-003 |
| L08 | SI-XFER | MOD-02 | DU-2 | W2 | `server/course_app/submission_intake/xfer/**` | 无叶子依赖（ST-03 由 backfill 的 SI-STORE 支撑） | CT-001 分片协议承载；IC-SI-01 owner；ST-02 UploadSession；500MB/白名单预检 | AC-REQ-001-01 exceptions、AC-REQ-003-01；KD-005 |
| L09 | SI-API | MOD-02 | DU-2 | W2 | `server/course_app/submission_intake/api/**` | L02、L08（经冻结 IC-SI-01/04） | 提供 CT-001、CT-002、`POST /api/v1/auth/token`；30 秒编排；错误码映射 | AC-REQ-001-01、AC-REQ-003-01、AC-REQ-007-01；NFR-002/003 |
| L10 | CMP-UPLOAD-CLIENT | MOD-01 | DU-1 | W2 | `plugin/src/upload_client/**` | L04（配置）、L06+L07 产出物（经 PENDING-QUEUE 编排） | 消费 CT-001/CT-002；IC-M01-04；ST-05 UploadCheckpoint（INV-5）；令牌缓存 LCD-006 | AC-REQ-001-01；KD-005 断点续传 |
| L11 | CMP-PENDING-QUEUE | MOD-01 | DU-1 | W2 | `plugin/src/pending_queue/**` | L04、L05、L06、L07、L10（内部端口均已冻结） | IC-M01-01/03/04/05 枢纽；ST-04 PendingTask 状态机；LCD-005 恢复调度 | AC-REQ-001-01 exceptions；SM-001 contributing |
| L12 | CMP-ASSESSMENT-ENGINE | MOD-04 | DU-3 | W2 | `worker/assessment_worker/assessment_engine/**` | L03（编排器先细化，handoff 触发条件） | 五维度评估装配；ICT-002/004/005/006；缺失材料影响说明 | AC-REQ-008-01（owning）；D-AC-REQ-008-01 |
| L13 | CMP-STATUS-PRESENTER | MOD-01 | DU-1 | W2 | `plugin/src/status_presenter/**` | L04、L11（IC-M01-05 消费） | 提交编号/失败原因/缺失项展示；不伪造结论 | AC-REQ-001-01 展示面；REQ-004 |
| L14 | CMP-REVIEW-COMMAND | MOD-05 | DU-2 | W3 | `server/course_app/teacher_web/review_command/**` | 读模型（backfill PROJECTOR 提供）；CT-005 派生复核记录 | 提供 CT-008；ST-REVIEW-RECORD；NO_ORIGINAL_GRADE 不得伪造 | AC-REQ-009-01 写侧；F3-2/F3-3 |
| L15 | CMP-REVIEW-QUERY | MOD-05 | DU-2 | W3 | `server/course_app/teacher_web/review_query/**` | 读模型（PROJECTOR）；L01 课程结束时间（经 RETENTION） | 提供 CT-007（含 deletion_batches[] 出参） | AC-REQ-009-01 读侧；AC-NFR-001-01 |
| L16 | CMP-PRESENTATION | MOD-05 | DU-2 | W3 | `server/course_app/teacher_web/presentation/**` | L14、L15、读模型 | 提供 CT-009；ST-PRESENTATION-VIEW 一次性快照；缺失标记不隐藏 | AC-REQ-010-01；F4-1；R-04 滞后由幂等再生成吸收 |
| L17 | CMP-TEACHER-UI | MOD-05 | DU-2 | W3 | `server/course_app/teacher_web/ui/**` | L14、L15、L16 + CT-011 端点（backfill RETENTION 提供） | 教师浏览器表面（SSR，DD-003）；消费 CT-007/008/009/011；A-005 端内通知展示 | AC-REQ-009-01/010-01 交互面；AC-NFR-004-01 确认入口 |

## 父级 backfill 范围（Integration Owner，Phase 5；非叶子）

| 父模块 | 内部支撑组件 | 关键职责 |
|---|---|---|
| MOD-02 | SI-STORE、SI-RELAY、SI-VERIFY、SI-PURGE | 材料加密磁盘写入/配额；Outbox 写入+投递+入站去重（CT-004/005/006/012/014）；CT-003 客户端封装；CT-012 清除执行与 CT-014 回传 |
| MOD-04 | CMP-MODEL-SERVICE-ACL、CMP-RESULT-PUBLISHER、CMP-RUBRIC-PROMPT-COMPOSER、CMP-SCORING-METRICS | CT-010 ACL（最小化/≤3min/schema 校验）；CT-005 发布；准则提示版本化；SM-002/003 度量 |
| MOD-05 | CMP-ACCESS-GATE、CMP-READMODEL-PROJECTOR、CMP-RETENTION-GOVERNANCE | 课程范围授权+AccessDeniedLogged；CT-005/006/014 投影与重放守卫；CT-011 端点、到期批处理、CT-012 发布、删除审计 |

## 依赖说明

- 2026-07-20 更正：MOD-02/03/04/05 叶子的 allowed_paths 与 Phase 1 脚手架包位置对齐（server/course_app/、worker/assessment_worker/ 前缀）；属路径勘误，不改变范围与边界。


- 跨叶子依赖一律经由 L1 设计包已冻结的内部契约（IC-M01-xx / IC-SI-xx / ICT-xxx / M05-IC-xx / CP-*），叶子间不得直接读取对方内部。
- 跨模块依赖一律经由冻结的 CT 契约 / FLOW-011；任何新增跨模块需要 → 停止并产出 contract-change-request.md。
- L07 的 blocked 指 TD-01（宿主导出机制）未确认：Phase 1 仅落地端口、fixture 与测试（含显式 unsupported 状态），真实适配待确认后实现；L12/L17 原 TD-04/TD-02 阻塞已经用户决策解除（供应商配置、前端 SSR 均为详细设计，见 DD-003/DD-009）。

## 批准记录

- matrix gate：**approved**，2026-07-19，由用户在对话中显式批准（17 叶子 + 三波次 + backfill 范围）。
