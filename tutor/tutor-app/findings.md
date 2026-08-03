# tutor-app Findings

设计包阅读结论与决策登记。最近更新：2026-07-20（matrix 批准 + TD 重分类）。

## 关键事实

1. **实现范围 = 17 个叶子**：`tutor/L2/leaf-gate.L2-terminal.md` 冻结 16 个 L2 节点（STOP_LAYERING，2026-07-19T14:38:58Z）；MOD-03 course-roster 在 L1 即终端叶子（`06-leaf-decision.md`，children 为空）。两者合计 17，legacy 的 16 节点扫描不含 MOD-03，不得误用。matrix human gate 已由用户于 2026-07-19 批准。
2. **模块与部署**：MOD-01（DU-1 插件）/ MOD-02 + MOD-03 + MOD-05（DU-2 course-app 共部署）/ MOD-04（DU-3 assessment-worker 独立部署）。
3. **内部支撑组件不是叶子**：MOD-02 的 SI-STORE/SI-RELAY/SI-VERIFY/SI-PURGE、MOD-04 的 CMP-MODEL-SERVICE-ACL/CMP-RESULT-PUBLISHER/CMP-RUBRIC-PROMPT-COMPOSER/CMP-SCORING-METRICS、MOD-05 的 CMP-ACCESS-GATE/CMP-READMODEL-PROJECTOR/CMP-RETENTION-GOVERNANCE 无 L2 PRD，由各 L1 child-handoff 明确「不作为 L2 target」，实现责任落在 Integration Owner 的父级 backfill（Phase 5），已在 task_plan 登记，防止 CT-011/CT-012/CT-014 保留删除链路无人实现。
4. **已冻结的架构决策（KD，用户已确认，直接继承）**：KD-001 外部模型 API + ACL 最小化；KD-002 同组共部署 + 单一关系库 + 数据库 Outbox；KD-003 基础级运维；KD-004 500MB/白名单/200GB；KD-005 令牌 + 幂等键 + 分片续传 + `/api/v1`。
5. **契约面**：14 个编号契约（CT-001~CT-014）+ 未编号附属端点 `POST /api/v1/auth/token` + FLOW-011（internal_read，无网络契约）。Phase 1 已将机器可读 schema 落地到 `contracts/`（见 contract-freeze.md）。

## 决策重分类（用户 2026-07-19 确认）

原 Phase 0 的 TD-02~TD-10「待用户决策」中，8 项按用户指示改为**已冻结/详细设计**，落地记录见 `docs/design/phase-1-detail-design.md`：

| ID | 结论 | 落地 |
|---|---|---|
| TD-02 | 继承 L0 已定 DU-1/DU-2/DU-3；教师前端 SSR/SPA 为 MOD-05 LCD-007 详细设计 | DD-001、DD-003 |
| TD-03 | 单一关系型数据库已定；具体产品为详细设计 | DD-002 |
| TD-04 | KD-001 已定外部模型 API、ACL、数据最小化、供应商可替换；供应商配置为实现细节 | DD-009 |
| TD-05 | 继承 KD-005（令牌/幂等/续传/`/api/v1`）；令牌 TTL/形态为实现细节 | DD-004 |
| TD-06 | 继承本地材料磁盘、存储加密、500MB、200GB；目录与算法参数由 SI-STORE 详细设计 | DD-005 |
| TD-07 | 继承数据库 Outbox 与 DU-3 按积压扩容；2–3 worker 为部署基线，投递参数为详细设计 | DD-006 |
| TD-09 | 按 MOD-05 LCD-009 默认：调整理由可选，字段保留但不强制 | DD-007 |
| TD-10 | 继承 KD-003 与 L0 部署架构；实际地域/域名/服务器配置留 Phase 6 | DD-008 |

## 最终门禁待决事项（2026-07-22，final-gate-decision-pack.md）

- D-1 TD-01：A/B/C 三案待选（建议先核实宿主导出能力）。
- D-2 CCR-001：方案 A（CT-012 扩消费者 + CT-015）待批准/退回；批准前冻结不改不实施。
- D-3 received→processing 接线点：推荐 DU-2 relayer CT-004 confirmed 扫描钩子，待批准实现位置。
- D-4 正式压测：计划与工具/环境待批准。
- D-5 供应商合规：是否启动评估与只读条款调研待批准。

## 保留的两个真实事项

### TD-01：Codex 对话导出能力（**mechanism confirmed 2026-07-22；D-1 选 A**）

- 宿主证据（结构级只读核实，未读任何会话内容）：codex-cli 0.144.1 已安装；会话回放文件 `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`（`codex resume` 同一数据源）；`codex plugin` 机制存在。
- 权限模型：学生本机文件读取（PRD 既定采集侧 ACL）；适配器只读配置的 sessions 根以内，不输出内容到日志。
- 关闭条件：L07 实现该机制的适配 + 集成验证（导出物完整性/快照稳定性）。**L07 已解除 blocked，进入派发。**

### TD-08：AssessmentResult 删除接线（closed — CCR-001 方案 A 已实施 2026-07-23）

- 用户 2026-07-22 批准 CCR-001 方案 A：CT-012 消费者扩展 `[MOD-02, MOD-04, MOD-05]`；新增 CT-015 AssessmentPurgeCompleted（MOD-04 → MOD-05，镜像 CT-014）；MOD-05 批次双回流聚合。
- 实施：MOD-04 ICT-009 清除执行器（评分结果+任务删除、最小墓碑、CT-015 回传、CT-004 重放守卫）+ 迁移 0016；组合根注册 CT-012 第三消费方与 CT-015 路由。
- 验收：SCENARIO-016 E2E 17/17 通过；AC-NFR-004-01（含评分记录删除）可宣称。

## 设计包内已登记的风险/开放项（实现时必须遵循其处置）

- ~~GAP-02（2026-07-23，D-4 staging 发现）~~ **已关闭（2026-07-25）**：用户批准后实施——DU-3 常驻认领循环（CT-004 入站 contract 过滤、N 槽并发认领、租约心跳续期、REQ-012 任务内重试、优雅关闭、崩溃重认领恢复、12 项 metrics 告警面）+ ICT-003 材料只读生产实现（L02 清单授权、final 限定、DATA_DIR 限界、500MB 派生上限、只读无副作用、拒绝可观测）。验证：runner 10 测 + reader 13 测、PG 全链 E2E（无手工 tick 全自动 8/8）、staging 容器级 NFR-001/002 复跑全过（1624/1624=100%）、重启恢复与 SIGTERM 优雅关闭容器级实证。过程修复 5 项缺陷（Outbox 跨 DU 认领竞争、授权键与 D-P5-01 勘误对齐、alembic fileConfig 禁用既有 logger、SQLite 伪并发假象、worker 连接池容量）。报告：`docs/vibecode/runs/tutor-r01/gap-02-verification-report.md`。
- R-02（MOD-03 观察项）：「课程已结束的提交是否拒绝」父包未定义，默认不实现；需要时回父层。
- R-03（MOD-05 Q-02）：无提交的课程是否对教师可见——默认按 CT-007 现有出参实现，不新增课程目录投影。
- R-04（MOD-05 LCD-004）：复核调整后立即生成展示视图存在秒级读模型滞后，由 CT-009 幂等再生成吸收，不得引入跨模块同步读。
- R-05（MOD-01 LCD-001）：指令中的姓名/小组与插件配置不一致时以当次指令为准；服务端 CT-003 为最终权威。

## 笔记

- **Phase 6（2026-07-22）**：发布准备完成。环境注记：① `sqlite:///file:NAME?cache=shared` 是磁盘文件而非内存库（真内存须 `mode=memory`，且需锚定连接防 alembic 关连后销毁）；② docker 镜像站可能 403，直接 pull 可绕过；③ db.engine 连接池参数对 SQLite 非法（须按方言条件化）。

- **Phase 5（2026-07-21）**：受限回填完成（B-01~B-05 + 双 E2E_OK）。遗留登记：received→processing 生产接线点；SI-STORE `_unassigned` 课程键重组织；ACL 强制超时层（真实供应商接入时）；metrics 进程内统计；IC-PQ-004 冷态执行；读模型 material_refs 空投影（CT-006 载荷事实）。裁决 D-P5-01：SI-STORE 在接收编排中 promote 先于课程归属校验，v1 接受 `_unassigned/{submission_uuid}` 路径 + 按提交键字节配额（硬顶生效）；课程键重组织（DD-005 完整形态）登记为后续细化，非契约问题，不走 CCR。
- **Wave 3 集成（2026-07-20）**：L14~L17 集成入 main（merge-head `11a22f91f4b3`，PG 19 表）。M05-IC-02 为双侧面端口（L15 query() / L16 group_view()），已验证单一实现可服务两消费方（PROJECTOR 设计输入）；L03 任务内重试为同租约 attempt_no=2 回调（无需重新认领，冒烟接线注记）。
- **Wave 3（2026-07-20）**：L14~L17 完成并核验（4/4 可合并），readiness review 见 run 目录。**16/17 叶子完成，仅 L07 blocked（TD-01）**。L14 的 NO_ORIGINAL_GRADE 映射 HTTP 409 与 L16 幂等时间窗（UTC 自然日）为 implementation_detail 登记项；M05-IC-02 端口形状对齐列入集成事项。
- **Wave 2 集成（2026-07-20）**：L08~L13 集成入 main。IC-SI-01 适配器（wiring.py）为 Integration Owner 集成层文件；L13 状态语义表追加 L11 五键（追加式，不改既有语义）；TestClient 场景 SQLite 内存库需 StaticPool 跨线程共享（环境注记）。

- **执行环境（用户 2026-07-20 更正）**：协调者与全部 Leaf Owner 均为 Claude Code（子代理 + 隔离 worktree），不使用 Codex 对话执行实现工作。
- **Wave 2（2026-07-20）**：L08~L13 完成并核验（6/6 可合并），readiness review 见 run 目录。串行派发（配额约束；L08 首次 403 一次后恢复）。L06 类别映射注记已由 L10 以叶子内常量表关闭。L11 状态机含 confirm_required 保留态（L1 设计），与 L13 状态映射的口径对齐列入集成事项。
- **Wave 1（2026-07-20）**：L01~L06 完成、核验并集成入 main（integration/wave-1，零冲突；merge-head `9c99fa53f9f8`；PG 迁移验证通过）。过程注记：API 配额导致并发失败，串行恢复有效；`contracts/ct-003.json` 做过一次落地修正（course_id 条件化，对齐冻结设计 R1 流，非契约变更）；L1 附录字段名 screenshot_dir/result_dir 与冻结 schema screenshots_dir/results_dir 存在措辞差异，实现以冻结 schema 为准（L04 登记）；系统 PATH 上 Anaconda alembic 与 Python 3.14 不兼容，统一 `python -m alembic`；alembic.ini 注释需 ASCII（locale 读取）。
- Phase 1（2026-07-20）已完成：contracts/ 契约 schema 落地并冻结；monorepo 骨架与工程基线就绪；全部验证通过（35+8+8）；DD-001~DD-009 见 `docs/design/phase-1-detail-design.md`；MOD-02 三项待复验复核通过；验证报告见 run 目录。
- 工作流仓库 legacy `vibecode/state.json` 为 generic INIT，本运行不使用、不推进；tutor-r01 的真相文件在 `docs/vibecode/runs/tutor-r01/`。
- 工作流仓库根的 `task_plan.md` / `progress.md` / `findings.md` 已由用户重建为 Tutor 项目跨对话协调索引（2026-07-20）；本仓库控制面与其保持一致，冲突时以本仓库 run-scoped 文件为准并先对账。
- ~~MOD-02 child-handoff 自查有 3 项「待复验」~~ → 2026-07-20 复核通过（验证报告 §5）。
