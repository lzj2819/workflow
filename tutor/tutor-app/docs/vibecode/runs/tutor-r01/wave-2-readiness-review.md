# Wave 2 Readiness Review — tutor-r01

- 日期：2026-07-20；审查人：Integration Owner / Workflow Coordinator
- 范围：L08~L13（用户批准的 Wave 2 范围；L07 blocked by TD-01 未启动）
- 结论：**6/6 可合并，0 需返工，0 阻塞。等待用户集成批准。**

## 完成包核验

| 叶子 | 提交 | 改动文件 | 范围 | 新增测试 | 全量回归 | 裁决 |
|---|---|---|---|---|---|---|
| L08 SI-XFER | `a59c906` | 7 | ✅ 全部允许路径内 | 25 绿 | 101 server 绿（76 无回归） | **可合并** |
| L09 SI-API | `1e715be` | 9 | ✅ | 18 绿 | 94 server 绿 | **可合并** |
| L10 UPLOAD-CLIENT | `4ec5ac0` | 9 | ✅ | 12 绿 | 55 npm 绿 | **可合并** |
| L11 PENDING-QUEUE | `f061ed9` | 5 | ✅ | 10 绿 | 53 npm 绿 | **可合并** |
| L12 ASSESSMENT-ENGINE | `3e560c0` | 7 | ✅ | 13 绿 | 45 worker 绿 | **可合并** |
| L13 STATUS-PRESENTER | `848cb86` | 2 | ✅ | 16 绿 | 59 npm 绿 | **可合并** |

核验方式：每 worktree `git diff --name-only main...HEAD` 对照 allowed-context；重跑叶子测试与全量套件；completion-report.md 齐备（SHA/改动/验证输出/契约影响=无/范围自检）。派发方式为串行（API 配额约束，Wave 1 已验证；L08 首次启动遇 403 一次，恢复后完成）。

## 关键语义抽查（协调者复核）

- L08：checkpoint 只记已确认分片；逐片+合并双重 500MB/白名单；finalize 幂等；TTL 可注入时钟。
- L09：令牌不透明、服务端仅存哈希、签发/拒绝审计不含明文；REJECTED_MEMBERSHIP 以 200 + status=rejected 业务终态应答；submission_uuid 幂等；名单不可用有限重试后 503 暂态且不建提交。
- L10：类别映射为叶子内常量表（dialogue/code/screenshot/result → 对话/代码/截图/结果），**未触发 contract-change-request**（用户指令边界内）。
- L11：HostUnsupportedError 显式失败（failed_retryable，含 unsupported 原因，不伪造快照、不上传）——TD-01 边界遵守正确。
- L12：仅 FakeModelProvider；CT-010 请求经守卫且断言不含业务标识；成功/失败载荷已在 SQLite 上真实喂给 L03 complete/fail_assessment 验证兼容。
- L13：不伪造结论；失败状态无等级展示；状态映射表可追加键。

## 遗留注记（非返工项，集成/后续处理）

| # | 事项 | 处置 |
|---|---|---|
| N-01 | 迁移两头（0005_upload_sessions、0006_auth_tokens，均 down_revision=9c99fa53f9f8） | 集成时 alembic merge heads（同 Wave 1 纪律） |
| N-02 | L09 IC-SI-01 为冻结端口 stub 注入；与 L08 真实实现的接线 | 集成时由协调者完成并验证（低风险，形状已由双方测试锁定） |
| N-03 | L11 状态机含 confirm_required 保留态（30s unknown，L1 设计）；L13 状态取值映射 | 集成时对齐状态枚举口径（仅映射表追加，无契约影响） |
| N-04 | L10 ST-05 checkpoint 默认为内存实现；跨进程持久化（A-007） | 经预留 checkpointStore 接口在集成/B-04 注入 |
| N-05 | L12 材料类别→CT-010 三桶映射为临时实现（LCD-005） | backfill 的 RUBRIC-PROMPT-COMPOSER 细化 |
| N-06 | L11 终态清理协调（IC-PQ-004）不在本叶交付 | 后续波次/集成回填决定 |
| N-07 | L08 abort/TTL 统一 failed_terminal（reason 前缀区分） | 若 L09 需区分用户中止，在映射层处理，无契约变更 |

## 边界与门禁确认

- 契约影响：六个完成包均为「无」；contracts/ 未被触碰。
- L12 未接入真实模型、未外发材料（fake provider 限定遵守）；L07 未启动（TD-01）；CCR-001 pending（CT-012/014 未动）。
- tutor 设计包未动；未批准任何后续 gate（Wave 2 集成、Wave 3、Phase 5、release 均未批准）。
- Wave 1 的 L06 类别映射注记已由 L10 落实为叶子内常量表，关闭该注记。

## 待用户决定

1. **集成批准**：是否将六个叶子分支合并入 main（含 alembic merge heads 与合并后全量回归 + 集成冒烟扩展）；
2. 是否放行 Wave 3（L14~L17）；
3. CCR-001 与 TD-01 维持现状确认。
