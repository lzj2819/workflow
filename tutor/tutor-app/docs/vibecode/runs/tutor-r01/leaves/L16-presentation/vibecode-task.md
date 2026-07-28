# VibeCode Task — L16 CMP-PRESENTATION（W3）

- run：tutor-r01；leaf：L16；波次：W3；分支：`tutor-r01/L16-presentation`
- 模块：MOD-05 teacher-web / CMP-PRESENTATION 展示视图生成与快照（DU-2）。

## 目标

实现 CT-009 展示视图生成（REQ-010）：按小组生成课堂展示视图快照（项目结果、过程摘要、评分、批注、缺失标记）。

## 交付物

1. PresentationView 快照持久化（ST-PRESENTATION-VIEW）：一次性快照写入，不随源数据实时更新；重新生成获取最新内容。
2. CT-009 端点（FastAPI APIRouter，不挂载）：`POST /api/v1/teacher/presentations`：
   - 请求 group_ids[]（≥1）；应答 presentation_id + blocks[]（group_id、project_result、process_summary、grades、annotations、missing_marks）；
   - 任一选定小组无可用提交 → NO_AVAILABLE_SUBMISSION 拒绝并说明原因；
   - 幂等再生成（教师+小组集合+时间窗）：相同参数返回最新快照，不产生重复视图记录；
   - 缺失材料类别在 blocks 中显式 missing_marks，**不隐藏缺口**；
   - 数据源为读模型查询端口（M05-IC-02 注入，与 L15 同一冻结端口；不做跨模块同步读，R-04 秒级滞后由幂等再生成吸收）。
3. 迁移：`server/migrations/versions/0008_presentation_views.py`（`down_revision="b9c6e3d6276a"`）。
4. 测试：`server/tests/test_l16_presentation.py`。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-05/L2-mod-05-cmp-presentation/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-05/architecture/`（03-state-and-data.md 的 ST-PRESENTATION-VIEW、05-local-decisions.md 的 LCD-004/008）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-009）
- 验收：根 PRD AC-REQ-010-01；F4-1
- 仓库：`contracts/ct-009.json`、`internal-contracts.json`

## 关键语义

- 快照一次性写入；展示导出格式为静态 HTML（DD-003/LCD-008），v1 不做 PDF。
- 不实现：复核写（L14）、查询装配（L15）、前端（L17）、ACCESS-GATE/PROJECTOR（backfill）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
