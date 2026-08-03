# Wave 3 Readiness Review — tutor-r01

- 日期：2026-07-20；审查人：Integration Owner / Workflow Coordinator
- 范围：L14~L17（用户批准的 Wave 3 范围；L07 blocked by TD-01 未启动）
- 结论：**4/4 可合并，0 需返工，0 阻塞。等待用户集成批准。**

## 完成包核验

| 叶子 | 提交 | 改动文件 | 范围 | 新增测试 | 全量回归 | 裁决 |
|---|---|---|---|---|---|---|
| L14 REVIEW-COMMAND | `58b6ee9` | 8 | ✅ 全部允许路径内 | 17 绿 | 136 server 绿（119 无回归） | **可合并** |
| L15 REVIEW-QUERY | `c846a36` | 7 | ✅ | 15 绿 | 134 server 绿 | **可合并** |
| L16 PRESENTATION | `34bb13b` | 12 | ✅ | 13 绿 | 132 server 绿 | **可合并** |
| L17 TEACHER-UI | `70119ae` | 16 | ✅ | 19 绿 | 138 server 绿 | **可合并** |

核验方式：每 worktree `git diff --name-only main...HEAD` 对照 allowed-context；重跑叶子测试与全量套件；completion-report.md 齐备（SHA/改动/验证输出/契约影响=无/范围自检）。派发方式：串行（API 配额约束），全部一次通过。

## 关键语义抽查（协调者复核）

- L14：request_id/submission_id 双键幂等；NO_ORIGINAL_GRADE 禁伪造（映射 HTTP 409，契约只冻结错误码，登记）；**adjustment_reason 保持可选**（TD-09 遵守）；原始等级复制值不可变；M05-IC-01 端口实现供 PROJECTOR 幂等调用。
- L15：CT-007 视图族读装配；**未建读模型表**（M05-IC-02 注入）；scoring_failed 返回 failure_reason + retry_record，无等级填充；deletion_batches[] 出参齐备。
- L16：快照一次性写入 + 新窗口 superseded；NO_AVAILABLE_SUBMISSION 整体拒绝且零落库；missing_marks 按冻结枚举显式；静态 HTML 导出（v1 无 PDF）；幂等时间窗取 UTC 自然日（implementation_detail，登记）。
- L17：只消费已定义 API（CT-007/008/009/011 + 会话）注入式客户端；**CT-011 仅 spy 调用断言，未补造端点**；scoring_failed 展示真实原因无等级；CT-008 携带 request_id 幂等键；登录页无令牌明文；Jinja2 SSR 无前端框架。

## 遗留注记（非返工项，集成/Phase 5 处理）

| # | 事项 | 处置 |
|---|---|---|
| N-01 | 迁移两头（0007_review_records、0008_presentation_views，均 down_revision=b9c6e3d6276a） | 集成时 alembic merge heads（既定纪律） |
| N-02 | M05-IC-02 端口形状在 L15/L16 间的落地对齐（双方均按冻结端口实现） | 集成时接线验证（读模型查询端口真实实现归 B-03 PROJECTOR） |
| N-03 | L14 NO_ORIGINAL_GRADE 映射 HTTP 409（契约只冻结错误码） | backfill 统一错误码→HTTP 映射表时确认（B-03） |
| N-04 | L16 幂等时间窗粒度（UTC 自然日） | implementation_detail，如需调整在 B-03 参数化 |
| N-05 | L17 SSR 路由挂载与真实 HTTP 联调 | 集成/backfill（B-03 + main.py 挂载） |
| N-06 | ACCESS-GATE / READMODEL-PROJECTOR / RETENTION-GOVERNANCE / CT-011 端点 | Phase 5 B-03（教师端最后一块） |

## 边界与门禁确认

- 契约影响：四个完成包均为「无」；contracts/ 未被触碰。
- L07 未启动（TD-01）；CCR-001 pending（CT-012/014 未动）；tutor 设计包未动；未批准 Phase 5/发布。
- 17 叶子状态：**16/17 完成（L01~L06、L08~L17），L07 blocked（TD-01）**。

## 待用户决定

1. **集成批准**：是否将四个叶子分支合并入 main（含 alembic merge heads 与合并后全量回归 + 集成冒烟扩展）；
2. Phase 5 backfill（B-01~B-05）放行时机；
3. CCR-001 与 TD-01 维持现状确认。
