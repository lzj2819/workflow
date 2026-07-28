# VibeCode Task — L15 CMP-REVIEW-QUERY（W3）

- run：tutor-r01；leaf：L15；波次：W3；分支：`tutor-r01/L15-review-query`
- 模块：MOD-05 teacher-web / CMP-REVIEW-QUERY 教师查询读装配（DU-2）。

## 目标

实现 CT-007 教师课程数据查询（REQ-009 读侧、NFR-001）：课程/小组/学生/提交详情视图族读装配。

## 交付物

1. CT-007 视图族端点（FastAPI APIRouter，不挂载）：课程列表、小组列表、学生详情、提交详情（材料清单、处理状态、Agent 原始等级/五维依据/教师建议、批注、最终等级、失败原因与重试结果）、删除批次列表（batch_id、retention_due_at、scope、batch_status、exclusions[]）。
2. 读模型查询端口消费（M05-IC-02，PROJECTOR owner 归 backfill，本叶子注入 stub/直接表实现均可，但读模型表结构以 PROJECTOR 为 owner——本叶子**不建读模型表**，经端口注入）。
3. 课程范围授权检查调用（ACCESS-GATE 端口注入）：无权 → 403 + AccessDeniedLogged（断言端口被调用，日志由 backfill 持久化）。
4. 失败可见：scoring_failed 展示 failure_reason + retry_record，**不伪造等级**；评分建议默认教师可见（学生侧无此端点）。
5. 测试：`server/tests/test_l15_review_query.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-05/L2-mod-05-cmp-review-query/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-05/architecture/`（03-state-and-data.md 的读模型/ST-PROJECTION-CHECKPOINT、04-contracts-and-runtime.md 的 M05-IC-02）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-007）、`03-data-and-consistency.md`（读模型说明）
- 验收：根 PRD AC-REQ-009-01 读侧；AC-NFR-001-01（100 学生/20–50 小组规模查询）
- 仓库：`contracts/ct-007.json`、`internal-contracts.json`

## 关键语义

- 只读，天然幂等；读模型秒级滞后接受（不做跨模块同步读，R-04）。
- 不实现：复核写（L14）、展示生成（L16）、前端（L17）、ACCESS-GATE/PROJECTOR（backfill）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
