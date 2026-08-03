# VibeCode Task — L14 CMP-REVIEW-COMMAND（W3）

- run：tutor-r01；leaf：L14；波次：W3；分支：`tutor-r01/L14-review-command`
- 模块：MOD-05 teacher-web / CMP-REVIEW-COMMAND 复核写侧（DU-2）。

## 目标

实现 CT-008 教师批注与最终等级调整（REQ-009 写侧）：ReviewRecord 聚合、幂等写、调整留痕。

## 交付物

1. ReviewRecord 聚合持久化（ST-REVIEW-RECORD）：批注、最终等级、调整记录（原始等级复制值不可变 + 操作者 + 时间，四元组留痕）。
2. CT-008 命令：`PUT /api/v1/teacher/submissions/{submission_id}/review`（FastAPI APIRouter，不挂载）：
   - 请求幂等键 request_id（重复请求返回同一复核记录）；
   - annotation 与 final_grade 至少其一；final_grade ∈ A–E；
   - **NO_ORIGINAL_GRADE**：scoring_failed 且无原始等级时拒绝设置最终等级（不得伪造等级）；
   - 并发修改后写为准并完整留痕（调整历史可追）；
   - **调整理由 adjustment_reason 可选、不强制（TD-09/DD-007）；若实现中发现需要改为必填 → 停止并在完成包中给出 contract-change-request 草案，不得自行改规则**。
3. M05-IC-01 复核记录创建端口（供 READMODEL-PROJECTOR 在 CT-005 到达时幂等创建复核记录；实现归 backfill 调用，本叶子提供端口实现）。
4. 迁移：`server/migrations/versions/0007_review_records.py`（`down_revision="b9c6e3d6276a"`）。
5. 测试：`server/tests/test_l14_review_command.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-05/L2-mod-05-cmp-review-command/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-05/architecture/`（03-state-and-data.md 的 ST-REVIEW-RECORD、04-contracts-and-runtime.md 的 M05-IC-01/05、05-local-decisions.md 的 LCD-003/009）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-008）
- 验收：根 PRD AC-REQ-009-01 写侧；F3-2/F3-3
- 仓库：`contracts/ct-008.json`、`internal-contracts.json`；L02 状态查询可注入（判断无原始等级场景）

## 关键语义

- 原始/最终等级、操作者、时间同时保留；AccessDeniedLogged 由 ACCESS-GATE 端口注入（backfill），本叶子调用而不实现。
- 不实现：读装配（L15）、展示（L16）、前端（L17）、删除治理（backfill）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
