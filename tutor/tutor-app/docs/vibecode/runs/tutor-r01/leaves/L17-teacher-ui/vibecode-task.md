# VibeCode Task — L17 CMP-TEACHER-UI（W3）

- run：tutor-r01；leaf：L17；波次：W3；分支：`tutor-r01/L17-teacher-ui`
- 模块：MOD-05 teacher-web / CMP-TEACHER-UI 教师网页前端（DU-2，SSR 服务端渲染，DD-003）。

## 目标

实现教师网页前端：课程/小组/学生/提交详情浏览、批注与最终等级调整表单、展示视图页面、删除批次确认入口、评分失败端内通知展示（A-005）。

## 交付物

1. SSR 页面（Jinja2 模板 + 少量原生 JS，不引入前端框架/构建链）：
   - 课程列表 → 小组列表 → 学生/提交详情（材料清单、处理状态、原始等级、五维依据、教师建议、批注、最终等级编辑入口）；
   - 展示视图页（blocks 渲染，缺失标记可见）；
   - 删除批次页（批次状态/到期时间/范围/排除标记 + 确认按钮，**仅调用 CT-011 API，该端点实现归 backfill——本叶子不自行补造后端接口或业务结论**）；
   - 评分失败端内通知展示（scoring_failed 原因与重试结果，不显示伪造等级）；
   - 登录页（教师账号会话表单；会话校验由平台/backfill 承担，页面只对接）。
2. API 客户端层：只消费已定义 API（CT-007/008/009/011），经注入（测试用 stub 或真实 router）；**不新增任何后端端点语义**。
3. 测试：`server/tests/test_l17_teacher_ui.py`（模板渲染断言 + 客户端注入断言）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-05/L2-mod-05-cmp-teacher-ui/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-05/architecture/`（05-local-decisions.md 的 LCD-007 渲染技术落地、A-005 通知展示面）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-007/008/009/011）
- 验收：根 PRD AC-REQ-009-01/010-01 交互面；AC-NFR-004-01 确认入口
- 仓库：`contracts/ct-007.json`、`ct-008.json`、`ct-009.json`、`ct-011.json`；L14/L15/L16 叶子（同波次未集成，按冻结契约注入，不做跨叶子真实接线）

## 关键语义

- 展示数据只来自已定义 API/读模型端口；评分失败展示真实原因；教师建议/原始等级仅教师侧可见（学生无此界面）。
- 不实现：L14/L15/L16 的后端逻辑、ACCESS-GATE/RETENTION-GOVERNANCE（backfill）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
