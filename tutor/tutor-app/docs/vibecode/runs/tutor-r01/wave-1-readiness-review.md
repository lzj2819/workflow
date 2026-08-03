# Wave 1 Readiness Review — tutor-r01

- 日期：2026-07-20；审查人：Integration Owner / Workflow Coordinator
- 范围：L01~L06（用户批准的 Wave 1 范围；L07 blocked by TD-01 未启动）
- 结论：**6/6 可合并，0 需返工，0 阻塞。等待用户集成批准。**

## 完成包核验

| 叶子 | 提交 | 改动文件 | 范围 | 新增测试 | 全量回归 | 裁决 |
|---|---|---|---|---|---|---|
| L01 course-roster | `972e1f9` | 9 | ✅ 全部允许路径内 | 18 绿 | 53 项（唯一失败为协调者基线缺陷，已另修 `2ad9dc6`） | **可合并** |
| L02 SI-CORE | `2970b01` | 9 | ✅ | 22 绿 | 57 全绿 | **可合并** |
| L03 SCORING-ORCHESTRATOR | `066e516` | 7 | ✅ | 24 绿 | 32 全绿 | **可合并** |
| L04 CONFIG-STORE | `12927a5` | 3 | ✅ | 10 绿 | 18 全绿 | **可合并** |
| L05 INTENT-PARSER | `8610326` | 6 | ✅ | 15 绿 | 23 全绿 | **可合并** |
| L06 MATERIAL-COLLECTOR | `f7f4dc2` | 2 | ✅ | 9 绿 | 17 全绿 | **可合并** |

核验方式：每 worktree `git diff --name-only main...HEAD` 对照 allowed-context；重跑叶子测试与全量套件；阅读 completion-report.md（均含 SHA、改动清单、验证输出、契约影响=无、范围自检）。

## 协调者过程记录

- 六个代理初始并发派发遭遇 API 配额上限（403），切换为**串行恢复**（L06 探针 → L01~L05 依次），全部完成；无代码损失。
- 路径勘误（协调者过错，已修复 `52072eb`）：L01/L02/L03 allowed_paths 对齐 Phase 1 脚手架包位置（`server/course_app/`、`worker/assessment_worker/`）；L02 部分文件位置天然正确。
- 基线缺陷修复：`2ad9dc6`（test_platform.TestOutbox 时钟无关化）、`80ace9f`（contracts/ct-003.json 落地修正：course_id 按 verified 条件化，对齐冻结设计 R1 拒绝流；非契约语义变更）。

## 遗留注记（均非返工项，集成/后续波次处理）

| # | 事项 | 处置 |
|---|---|---|
| N-01 | 迁移三头（0002/0003/0004 均 down_revision=0001_baseline） | 集成时 `alembic merge heads` 生成合并点（协调者） |
| N-02 | Outbox 同事务语义经抽象验证（内存实现）；真实 PG 会话绑定的 OutboxStore | Phase 5 SI-RELAY / RESULT-PUBLISHER backfill 提供（L02/L03 完成包均已登记） |
| N-03 | L06 内部类别标识（code/screenshot/result）→ CT-001 中文类别映射 | L10 上传集成时确认（与父架构 INV-L2-MC-01 一致） |
| N-04 | L01 CT-013 教师会话鉴权（AUTH_INVALID/FORBIDDEN + AccessDeniedLogged） | 平台面，router 挂载时依赖注入（backfill） |
| N-05 | L04：L1 契约附录字段名 screenshot_dir/result_dir 与冻结 schema screenshots_dir/results_dir 措辞差异 | 已按冻结 schema 实现；设计文档措辞问题，不改设计包，登记 findings |
| N-06 | L05：无标签口语化输入 fail-closed（按缺项请学生补全） | 设计内取舍；规则表可扩充不触碰闸门语义 |
| N-07 | L05 testcases.json 的 TC-002/TC-006 | 归 L11/L10，后续波次覆盖 |

## 边界与门禁确认

- 契约影响：六个完成包均为「无」；contracts/ 仅协调者做了 N-01 外的落地修正（80ace9f，已登记）。
- CCR-001 保持 pending：L03 未实现任何 CT-012 消费/删除逻辑。
- L07 未启动（TD-01）；Wave 2/3、Phase 5、最终发布均未批准。
- 未发生越界改动、未批准任何 gate、tutor 设计包未被修改。

## 待用户决定

1. **集成批准**：是否将六个叶子分支合并入 main（含 alembic merge heads 与合并后全量回归）；
2. 是否放行 Wave 2（L08~L13）；
3. CCR-001 与 TD-01 维持现状（pending / blocked）。
