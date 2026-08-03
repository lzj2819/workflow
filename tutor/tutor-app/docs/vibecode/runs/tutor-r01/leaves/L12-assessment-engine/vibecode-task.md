# VibeCode Task — L12 CMP-ASSESSMENT-ENGINE（W2）

- run：tutor-r01；leaf：L12；波次：W2；分支：`tutor-r01/L12-assessment-engine`
- 模块：MOD-04 assessment / CMP-ASSESSMENT-ENGINE 五维评估装配（DU-3）。

## 目标

实现五维度评估装配：提示编排（端口注入）、材料内容加载（ICT-003 只读端口）、模型调用（ICT-004，**仅 fake ModelProvider**）、应答 schema 校验、AssessmentResult 装配与缺失材料影响说明。

## 交付物

1. 评估执行器：输入 ClaimedTask 上下文（L03 形状）→ 组装 evaluation_prompt（ICT-002，rubric composer 端口注入）→ 加载材料内容（ICT-003 只读端口注入，MOD-02 所有权）→ 调用 ModelProvider（`worker/assessment_worker/model_provider.py` 协议；**禁止接入真实供应商、禁止外发任何材料**）→ 校验应答对 contracts/ct-010.json response schema → 装配结果（原始等级、五维依据、教师建议、缺失材料影响说明）。
2. 成功 → ICT-005 输出（喂给 L03 complete_assessment 的参数形状）；失败分类（MODEL_TIMEOUT/MODEL_ERROR/INVALID_RESPONSE_SCHEMA）→ ICT-006 输出（喂给 L03 fail_assessment）。
3. 缺失材料影响说明：missing_items 非空时在结果中列出缺失类别对评估的影响（AC-REQ-008-01 boundaries）。
4. 测试：`worker/tests/test_l12_assessment_engine.py`（fake provider + stub 端口；断言 CT-010 请求不含业务标识——数据最小化）。

## 设计输入（只读）

- `E:/pythonproject/完整流程/代码设计/完整代码开发工作流/tutor/L2/mod-04/L2-mod-04-cmp-assessment-engine/`（prd.md、architecture/、testcases.json）
- `tutor/L1/L1-mod-04/architecture/`（03-state-and-data.md 的 ST-002、04-contracts-and-runtime.md 的 ICT-002~006、05-local-decisions.md 的 LCD-003/005）
- `tutor/L0-root/architecture/04-interface-contracts.md`（CT-010）
- 验收：根 PRD AC-REQ-008-01（owning）、REQ-012 失败分类
- 仓库：`contracts/ct-010.json`、`worker/assessment_worker/model_provider.py`（协议+fake+validate_request）、L03 的 orchestrator.py（complete/fail 签名，只读）

## 关键语义

- 数据最小化：发往 provider 的请求不得含 submission_id/姓名/小组等业务标识（KD-001）。
- 材料不完整仍生成结果并说明影响；不伪造评估（fake 结果仅作链路测试，标注 fake 来源）。
- 不实现：编排器（L03）、rubric composer、结果发布、模型 ACL 的供应商适配（均 backfill）。

## 完成包

写入主仓任务包目录 completion-report.md：提交 SHA、改动清单、验证命令与结果、契约影响（预期：无）、风险/阻塞、范围自检。
